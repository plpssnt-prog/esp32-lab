"""Genera le guide PDF di ESP32 Lab (una per progetto + manuale), stile UNO Lab.

Uso:  python3 tools/guide.py          -> public/pdf/ESP32-Lab-NN-id.pdf e ESP32-Lab-manuale.pdf
Richiede: reportlab, pypdf, node (per leggere public/js/projects.js).
"""
import io, json, os, subprocess, sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, os.path.dirname(__file__))
from guide_data import G  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'public', 'pdf')
FONTS = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('S', FONTS + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('SB', FONTS + 'DejaVuSans-Bold.ttf'))
MONO = 'M' if os.path.exists(FONTS + 'DejaVuSansMono.ttf') else 'Courier'
if MONO == 'M':
    pdfmetrics.registerFont(TTFont('M', FONTS + 'DejaVuSansMono.ttf'))

W, H = A4
ACC = HexColor('#2563eb'); GREY = HexColor('#555b66'); LIGHT = HexColor('#eef1f5')
WARN_BG = HexColor('#fff4d6'); WARN_FG = HexColor('#7a5a00'); PCB = HexColor('#22324a')
GREEN = HexColor('#2a9d3a')
c = None


# ------------------------------------------------------------------ dati dalla PWA
def load():
    js = ("import('" + os.path.join(ROOT, 'public/js/projects.js') + "').then(m => console.log(JSON.stringify("
          "{P: m.PROJECTS, PARTS: m.PARTS, LEVELS: m.LEVELS, PINMAP: m.PINMAP, BOARD: m.BOARD})))")
    return json.loads(subprocess.check_output(['node', '--input-type=module', '-e', js]))


# ------------------------------------------------------------------ testo
def text(x, y, s, size=10, font='S', color=black, anchor='l'):
    c.setFont(font, size); c.setFillColor(color)
    {'c': c.drawCentredString, 'r': c.drawRightString}.get(anchor, c.drawString)(x, y, s)


def wrap(x, y, s, width, size=10.5, lead=14.5, font='S', color=black):
    for ln in simpleSplit(s, font, size, width):
        text(x, y, ln, size, font, color); y -= lead
    return y


def header(titolo, sotto, n, tot, num):
    c.setFillColor(HexColor('#0f1115')); c.rect(0, H - 78, W, 78, stroke=0, fill=1)
    text(40, H - 30, 'ESP32 LAB  ·  MANUALE' if num == '–' else f'ESP32 LAB  ·  PROGETTO {num}', 8.5, 'SB', HexColor('#7fb2ff'))
    text(40, H - 52, titolo, 20, 'SB', white)
    text(40, H - 69, sotto, 10, 'S', HexColor('#b8c0cc'))
    text(W - 40, 22, f'{titolo}  ·  pagina {n} di {tot}' if tot else titolo, 8, 'S', GREY, 'r')


def titolo_sez(x, y, s):
    text(x, y, s, 13, 'SB'); return y - 22


def badge(x, y, n, col=ACC):
    c.setFillColor(col); c.circle(x, y, 10, stroke=0, fill=1)
    text(x, y - 4, str(n), 10.5, 'SB', white, 'c')


def riquadro(x, y, w, righe, bg=LIGHT, fg=black, titolo=None, size=9.8):
    lines = []
    for r in righe:
        lines += simpleSplit(r, 'S', size, w - 24) + [None]
    hh = 14 + (18 if titolo else 0) + sum(14 if l else 3 for l in lines)
    c.setFillColor(bg); c.roundRect(x, y - hh, w, hh, 7, stroke=0, fill=1)
    yy = y - 18
    if titolo:
        text(x + 12, yy, titolo, 10.5, 'SB', fg); yy -= 18
    for l in lines:
        if l: text(x + 12, yy, l, size, 'S', fg); yy -= 14
        else: yy -= 3
    return y - hh - 12


def riquadro_h(w, righe, titolo=None, size=9.8):
    n = sum(len(simpleSplit(r, 'S', size, w - 24)) for r in righe)
    return 14 + (18 if titolo else 0) + n * 14 + len(righe) * 3 + 12


def passi(x, y, w, lista, start=1):
    for i, (tit, desc) in enumerate(lista, start):
        badge(x + 10, y + 4, i)
        y = wrap(x + 30, y, tit, w - 30, 10.5, 14, 'SB')
        if desc:
            y = wrap(x + 30, y, desc, w - 30, 9.4, 12.5, 'S', GREY)
        y -= 6
    return y


def problemi(y, lista):
    for a, b in lista:
        y = wrap(40, y, a, W - 80, 10.5, 14, 'SB')
        y = wrap(40, y, b, W - 80, 9.4, 12.5, 'S', GREY) - 6
    return y - 4


def tabella(y, righe, w=W - 80, x=40, testa=('Componente / piedino', 'Va a')):
    c.setFillColor(HexColor('#e8ecf2')); c.rect(x, y - 4, w, 18, stroke=0, fill=1)
    text(x + 8, y + 1, testa[0], 9, 'SB'); text(x + w * 0.66, y + 1, testa[1], 9, 'SB')
    y -= 16
    for i, (a, b, col) in enumerate(righe):
        if i % 2: c.setFillColor(HexColor('#f6f8fb')); c.rect(x, y - 4, w, 15, stroke=0, fill=1)
        c.setFillColor(HexColor(col)); c.roundRect(x + 6, y - 1, 9, 9, 2, stroke=0, fill=1)
        text(x + 20, y, a if len(a) <= 72 else a[:71] + '…', 8.8); text(x + w * 0.66, y, b, 8.8, 'SB')
        y -= 15
    return y - 10


# ------------------------------------------------------------------ logica collegamenti (come diagram.js)
ALIAS = {'Sensori': 'Sensore', 'Connettore': 'ULN2003'}
NICE = {'LED': 'LED', 'Pulsante': 'Pulsante', 'Buzzer': 'Buzzer passivo', 'Potenziometro': 'Potenziometro',
        'Fotoresistenza': 'Fotoresistenza', 'DHT11': 'Sensore DHT11', 'HC-SR04': 'HC-SR04 ultrasuoni',
        'Joystick': 'Joystick', 'Ricevitore': 'Ricevitore IR', 'Servo': 'Servo SG90', 'L293D': 'Driver L293D',
        'ULN2003': 'ULN2003 + motore 28BYJ-48', 'MAX7219': 'Matrice 8×8 MAX7219', 'OLED': 'Display OLED',
        'MPU-6050': 'MPU-6050', 'Anello': 'Anello LED WS2812', 'PIR': 'Sensore PIR', 'L298N': 'Driver motori L298N',
        'Sensore': 'Sensori di linea TCRT5000', 'Partitore': 'Partitore 1k / 2k', 'Resistenza': 'Resistenza 10 kΩ'}
ALT = {'#2563eb': '#16a34a', '#9333ea': '#0891b2'}


def terminal(to):
    import re
    if re.fullmatch(r'GPIO\d+', to) or to in ('GND', '3V3'):
        return to
    if (to == '5V' or to.startswith('5V ')) and 'L298N' not in to:
        return '5V'
    return None


def expand(wiring):
    import re
    out = []
    for frm, to, col in wiring:
        tos = to.split(' / ')
        if len(tos) > 1 and all(re.fullmatch(r'GPIO\d+', t) for t in tos):
            parts = frm.split(' / ')
            first = parts[0].split(' ')
            prefix = ' '.join(first[:-1]) + ' ' if len(first) > 1 else ''
            for i, t in enumerate(tos):
                out.append((parts[0] if i == 0 else prefix + (parts[i] if i < len(parts) else parts[0]), t,
                            col if i == 0 else ALT.get(col, col)))
        else:
            out.append((frm, to, col))
    return out


def split(frm):
    w = frm.split(' ')
    comp, pin = w[0], ' '.join(w[1:])
    if comp.startswith('GPIO'):
        comp, pin = 'Partitore', frm
    comp = ALIAS.get(comp, comp)
    return comp, pin or frm


def componenti(p):
    rows = expand(p['wiring'])
    comps, by = [], {}
    for frm, to, col in rows:
        k, pin = split(frm)
        if k not in by:
            by[k] = {'key': k, 'name': NICE.get(k, k), 'pins': []}
            comps.append(by[k])
        by[k]['pins'].append({'pin': pin, 'to': to, 'col': col, 'term': terminal(to)})
    return comps


# ------------------------------------------------------------------ disegni dei componenti
def icon(key, x, y):
    """Disegna l'icona del componente con l'angolo in basso a sinistra in (x, y), area 70x44."""
    s = c
    if key == 'LED':
        s.setFillColor(HexColor('#e11d48')); s.circle(x + 35, y + 26, 11, stroke=0, fill=1)
        s.rect(x + 24, y + 14, 22, 12, stroke=0, fill=1)
        s.setStrokeColor(HexColor('#9a9a9a')); s.setLineWidth(1.6); s.line(x + 30, y + 14, x + 30, y); s.line(x + 40, y + 14, x + 40, y + 4)
    elif key in ('Partitore', 'Resistenza'):
        s.setStrokeColor(HexColor('#9a9a9a')); s.setLineWidth(1.6); s.line(x + 4, y + 22, x + 66, y + 22)
        s.setFillColor(HexColor('#d9c39a')); s.roundRect(x + 18, y + 15, 34, 14, 6, stroke=0, fill=1)
        for i, col in enumerate(['#7a4a21', '#111111', '#d62828', '#d4a100']):
            s.setFillColor(HexColor(col)); s.rect(x + 23 + i * 7, y + 15, 3, 14, stroke=0, fill=1)
    elif key == 'Pulsante':
        s.setFillColor(HexColor('#374151')); s.rect(x + 20, y + 6, 30, 30, stroke=0, fill=1)
        s.setFillColor(HexColor('#111827')); s.circle(x + 35, y + 21, 9, stroke=0, fill=1)
    elif key == 'Buzzer':
        s.setFillColor(HexColor('#111827')); s.circle(x + 35, y + 22, 17, stroke=0, fill=1)
        s.setFillColor(HexColor('#4b5563')); s.circle(x + 35, y + 22, 3, stroke=0, fill=1)
    elif key == 'Potenziometro':
        s.setFillColor(HexColor('#1e40af')); s.rect(x + 18, y + 4, 34, 30, stroke=0, fill=1)
        s.setFillColor(HexColor('#e5e7eb')); s.circle(x + 35, y + 19, 10, stroke=0, fill=1)
        s.setStrokeColor(HexColor('#111')); s.setLineWidth(2); s.line(x + 35, y + 19, x + 35, y + 28)
    elif key == 'Fotoresistenza':
        s.setFillColor(HexColor('#f5e6c8')); s.circle(x + 35, y + 24, 12, stroke=0, fill=1)
        s.setStrokeColor(HexColor('#b45309')); s.setLineWidth(1.2)
        pth = s.beginPath(); pth.moveTo(x + 27, y + 24)
        for i in range(8): pth.lineTo(x + 28 + i * 2, y + 24 + (4 if i % 2 else -4))
        s.drawPath(pth, stroke=1, fill=0)
    elif key == 'DHT11':
        s.setFillColor(HexColor('#2563eb')); s.rect(x + 22, y + 2, 26, 38, stroke=0, fill=1)
        s.setFillColor(HexColor('#bfdbfe'))
        for i in range(4):
            for j in range(3): s.rect(x + 25 + j * 7, y + 8 + i * 8, 5, 5, stroke=0, fill=1)
    elif key == 'HC-SR04':
        s.setFillColor(HexColor('#1d4ed8')); s.rect(x + 2, y + 6, 66, 30, stroke=0, fill=1)
        for cx in (x + 18, x + 52):
            s.setFillColor(HexColor('#d1d5db')); s.circle(cx, y + 21, 12, stroke=0, fill=1)
            s.setFillColor(HexColor('#374151')); s.circle(cx, y + 21, 8, stroke=0, fill=1)
    elif key == 'Joystick':
        s.setFillColor(HexColor('#111827')); s.rect(x + 16, y + 2, 38, 38, stroke=0, fill=1)
        s.setFillColor(HexColor('#4b5563')); s.circle(x + 35, y + 21, 13, stroke=0, fill=1)
        s.setFillColor(HexColor('#111')); s.circle(x + 35, y + 21, 7, stroke=0, fill=1)
    elif key == 'Ricevitore':
        s.setFillColor(HexColor('#111827')); s.rect(x + 24, y + 8, 22, 26, stroke=0, fill=1)
        s.setFillColor(HexColor('#374151')); s.circle(x + 35, y + 25, 6, stroke=0, fill=1)
    elif key == 'Servo':
        s.setFillColor(HexColor('#2f6bd8')); s.roundRect(x + 6, y + 8, 50, 26, 3, stroke=0, fill=1)
        s.setFillColor(white); s.circle(x + 44, y + 21, 7, stroke=0, fill=1)
        s.roundRect(x + 41, y + 18, 26, 6, 3, stroke=0, fill=1)
    elif key == 'L293D':
        s.setFillColor(HexColor('#111827')); s.rect(x + 14, y + 10, 42, 22, stroke=0, fill=1)
        s.setFillColor(HexColor('#9ca3af'))
        for i in range(8):
            s.rect(x + 16 + i * 5, y + 32, 2, 5, stroke=0, fill=1); s.rect(x + 16 + i * 5, y + 5, 2, 5, stroke=0, fill=1)
        s.setFillColor(HexColor('#4b5563')); s.circle(x + 14, y + 21, 3, stroke=0, fill=1)
    elif key == 'ULN2003':
        s.setFillColor(HexColor('#15803d')); s.rect(x + 2, y + 6, 32, 32, stroke=0, fill=1)
        s.setFillColor(HexColor('#ef4444'))
        for i in range(4): s.circle(x + 8 + i * 7, y + 32, 2, stroke=0, fill=1)
        s.setFillColor(HexColor('#c0c4cc')); s.circle(x + 52, y + 22, 15, stroke=0, fill=1)
        s.setFillColor(HexColor('#6b7280')); s.circle(x + 52, y + 22, 3, stroke=0, fill=1)
    elif key == 'MAX7219':
        s.setFillColor(HexColor('#111827')); s.rect(x + 14, y, 42, 42, stroke=0, fill=1)
        for i in range(8):
            for j in range(8):
                s.setFillColor(HexColor('#ef4444') if (i + j) % 3 == 0 else HexColor('#4b1d1d'))
                s.circle(x + 18 + j * 4.9, y + 4 + i * 4.9, 1.6, stroke=0, fill=1)
    elif key == 'OLED':
        s.setFillColor(HexColor('#1e3a8a')); s.rect(x + 6, y + 2, 58, 40, stroke=0, fill=1)
        s.setFillColor(HexColor('#0b0f19')); s.rect(x + 10, y + 8, 50, 26, stroke=0, fill=1)
        s.setFillColor(HexColor('#7dd3fc'))
        for i in range(3): s.rect(x + 14, y + 26 - i * 7, 30 - i * 6, 3, stroke=0, fill=1)
    elif key == 'MPU-6050':
        s.setFillColor(HexColor('#1d4ed8')); s.rect(x + 14, y + 4, 42, 34, stroke=0, fill=1)
        s.setFillColor(HexColor('#111827')); s.rect(x + 28, y + 14, 14, 14, stroke=0, fill=1)
    elif key == 'Anello':
        import math
        cols = ['#ef4444', '#f59e0b', '#22c55e', '#06b6d4', '#3b82f6', '#a855f7']
        s.setFillColor(HexColor('#111827')); s.circle(x + 35, y + 22, 20, stroke=0, fill=1)
        s.setFillColor(white); s.circle(x + 35, y + 22, 11, stroke=0, fill=1)
        for i in range(12):
            a = i * math.pi / 6
            s.setFillColor(HexColor(cols[i % 6])); s.circle(x + 35 + 15.5 * math.cos(a), y + 22 + 15.5 * math.sin(a), 2.6, stroke=0, fill=1)
    elif key == 'PIR':
        s.setFillColor(HexColor('#15803d')); s.rect(x + 12, y + 2, 46, 20, stroke=0, fill=1)
        s.setFillColor(HexColor('#f3f4f6')); s.setStrokeColor(HexColor('#d1d5db')); s.setLineWidth(1)
        s.wedge(x + 17, y + 2, x + 53, y + 42, 0, 180, stroke=1, fill=1)
    elif key == 'L298N':
        s.setFillColor(HexColor('#b91c1c')); s.rect(x + 6, y + 2, 58, 40, stroke=0, fill=1)
        s.setFillColor(HexColor('#111827')); s.rect(x + 22, y + 14, 26, 24, stroke=0, fill=1)
        s.setFillColor(HexColor('#374151'))
        for i in range(5): s.rect(x + 23 + i * 5, y + 30, 3, 10, stroke=0, fill=1)
        s.setFillColor(HexColor('#2563eb')); s.rect(x + 8, y + 4, 12, 8, stroke=0, fill=1); s.rect(x + 50, y + 4, 12, 8, stroke=0, fill=1)
    elif key == 'Sensore':
        for bx in (x + 4, x + 38):
            s.setFillColor(HexColor('#1d4ed8')); s.rect(bx, y + 6, 28, 30, stroke=0, fill=1)
            s.setFillColor(HexColor('#111827')); s.circle(bx + 9, y + 14, 4, stroke=0, fill=1)
            s.setFillColor(HexColor('#60a5fa')); s.circle(bx + 19, y + 14, 4, stroke=0, fill=1)
    else:
        s.setFillColor(HexColor('#9ca3af')); s.roundRect(x + 14, y + 6, 42, 30, 5, stroke=0, fill=1)


def scheda(x, y, w, h, evid=None):
    """Scheda ESP32-S3 CAM vista dall'alto. evid: 'led' o 'cam' per evidenziare."""
    c.setFillColor(HexColor('#111827')); c.roundRect(x, y, w, h, 6, stroke=0, fill=1)
    mx, mw = x + 10, w - 20
    c.setFillColor(HexColor('#cbd5e1')); c.roundRect(mx, y + h - 64, mw, 54, 3, stroke=0, fill=1)
    text(x + w / 2, y + h - 40, 'ESP32-S3', 9, 'SB', HexColor('#1f2937'), 'c')
    text(x + w / 2, y + h - 52, 'WROOM-1', 7, 'S', HexColor('#475569'), 'c')
    cy = y + h * 0.42
    c.setFillColor(HexColor('#0f172a')); c.setStrokeColor(HexColor('#64748b')); c.setLineWidth(2.5)
    c.circle(x + w / 2, cy, 13, stroke=1, fill=1)
    c.setFillColor(HexColor('#334155')); c.circle(x + w / 2, cy, 5, stroke=0, fill=1)
    c.setFillColor(HexColor('#94a3b8'))
    c.roundRect(x + w / 2 - 30, y - 3, 22, 10, 3, stroke=0, fill=1); c.roundRect(x + w / 2 + 8, y - 3, 22, 10, 3, stroke=0, fill=1)
    text(x + w / 2 - 19, y - 14, 'UART', 6.5, 'S', GREY, 'c'); text(x + w / 2 + 19, y - 14, 'USB', 6.5, 'S', GREY, 'c')
    c.setFillColor(HexColor('#60a5fa')); c.circle(x + 14, y + 22, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#f8fafc')); c.rect(x + w - 20, y + 18, 7, 7, stroke=0, fill=1)
    c.setFillColor(HexColor('#4b5563')); c.rect(x + 8, y + 6, 10, 7, stroke=0, fill=1); c.rect(x + w - 18, y + 6, 10, 7, stroke=0, fill=1)
    text(x + 13, y + 15, 'RST', 5, 'S', HexColor('#9ca3af'), 'c'); text(x + w - 13, y + 15, 'BOOT', 5, 'S', HexColor('#9ca3af'), 'c')
    spots = {'led': (x + 14, y + 22, 'LED blu'), 'rgb': (x + w - 16, y + 21, 'LED RGB'), 'cam': (x + w / 2, cy, 'fotocamera')}
    return spots


def breakout(x, y, w, h, terms):
    """Breakout con la scheda sopra e i morsetti usati sul lato destro. Ritorna {morsetto: (x, y)}."""
    c.setFillColor(PCB); c.roundRect(x, y, w, h, 12, stroke=0, fill=1)
    c.setFillColor(HexColor('#94a3b8'))
    for cx, cy in ((x + 10, y + 10), (x + w - 10, y + 10), (x + 10, y + h - 10), (x + w - 10, y + h - 10)):
        c.circle(cx, cy, 3.5, stroke=0, fill=1)
    text(x + 16, y + h - 22, 'Freenove Breakout Board', 9, 'SB', HexColor('#e2e8f0'))
    sw, sh = w * 0.42, min(h - 70, 230)
    spots = scheda(x + 16, y + h - 34 - sh, sw, sh)
    pos = {}
    tx = x + w - 34
    step = min(24, (h - 60) / max(1, len(terms)))
    for i, t in enumerate(terms):
        ty = y + h - 44 - i * step
        col = {'GND': '#111827', '3V3': '#dc2626', '5V': '#ea580c'}.get(t, '#16a34a')
        c.setFillColor(HexColor('#1f8a3a')); c.rect(tx, ty - 8, 22, 16, stroke=0, fill=1)
        c.setFillColor(HexColor('#c0c4cc')); c.circle(tx + 11, ty, 4.5, stroke=0, fill=1)
        c.setStrokeColor(HexColor('#6b7280')); c.setLineWidth(1); c.line(tx + 8, ty, tx + 14, ty)
        c.setFillColor(HexColor(col)); c.roundRect(tx - 52, ty - 7, 48, 14, 3, stroke=0, fill=1)
        text(tx - 28, ty - 3.5, t, 8, 'SB', white, 'c')
        pos[t] = (tx + 22, ty)
    return pos, spots


def wire(p0, p1, col, i=0, w=3.2):
    c.setStrokeColor(HexColor(col)); c.setLineWidth(w); c.setLineCap(1)
    mx = p0[0] + 30 + (i % 5) * 10
    c.bezier(p0[0], p0[1], mx + 40, p0[1], p1[0] - 60, p1[1], p1[0], p1[1])
    c.setFillColor(HexColor(col)); c.circle(*p0, 3.3, stroke=0, fill=1); c.circle(*p1, 3.3, stroke=0, fill=1)


def disegno(p, top, bottom):
    comps = componenti(p)
    if not comps:
        return disegno_solo_scheda(p, top, bottom)
    seq = [pn['term'] for cp in comps for pn in cp['pins']]
    terms = []
    for t in seq:
        if t and t not in terms: terms.append(t)
    order = {'5V': -3, '3V3': -2, 'GND': -1}
    def rank(t):
        if t in order: return order[t]
        idx = [i for i, x in enumerate(seq) if x == t]
        return sum(idx) / len(idx)
    terms.sort(key=rank)
    ROW, HEAD = 17, 58
    card_h = [HEAD + len(cp['pins']) * ROW + 8 for cp in comps]
    nat_h = max(sum(card_h) + 10 * (len(comps) - 1), len(terms) * 24 + 120, 300)
    avail = top - bottom
    s = min(1.0, avail / nat_h)
    c.saveState()
    c.translate(0, top - nat_h * s); c.scale(s, s)
    ox = (W / s - W) / 2 if s < 1 else 0
    bx, bw = 36 + ox, 230
    pos, _ = breakout(bx, nat_h - max(len(terms) * 24 + 120, 300), bw, max(len(terms) * 24 + 120, 300), terms)
    cx, cw = 330 + ox, 230
    y = nat_h
    wires = []
    for cp, hh in zip(comps, card_h):
        c.setFillColor(white); c.setStrokeColor(HexColor('#cbd5e1')); c.setLineWidth(1.4)
        c.roundRect(cx, y - hh, cw, hh, 8, stroke=1, fill=1)
        text(cx + 10, y - 18, cp['name'], 10, 'SB')
        icon(cp['key'], cx + cw - 78, y - 50)
        for i, pn in enumerate(cp['pins']):
            py = y - HEAD - i * ROW - 4
            col = HexColor(pn['col'])
            c.setFillColor(col if pn['term'] else white); c.setStrokeColor(col); c.setLineWidth(1.6)
            c.circle(cx, py, 4, stroke=1, fill=1)
            lab = pn['pin'] if pn['term'] else f"{pn['pin']} → {pn['to']}"
            lab = lab if len(lab) <= 46 else lab[:45] + '…'
            text(cx + 10, py - 3, lab, 8, 'S', black if pn['term'] else GREY)
            if pn['term']:
                wires.append((pos[pn['term']], (cx - 4, py), pn['col']))
        y -= hh + 10
    for i, (a, b, col) in enumerate(wires):
        wire(a, b, col, i)
    c.restoreState()


def disegno_solo_scheda(p, top, bottom):
    h = min(290, top - bottom - 50)
    w = h * 0.55
    x = W / 2 - w / 2
    y = bottom + (top - bottom - h) / 2
    spots = scheda(x, y, w, h)
    key = 'cam' if p.get('cam') else ('rgb' if p['id'] == 'rgb' else 'led')
    sx, sy, lab = spots[key]
    c.setStrokeColor(HexColor('#f28c18')); c.setLineWidth(2.5); c.circle(sx, sy, 15, stroke=1, fill=0)
    c.setLineWidth(2); c.bezier(sx + 15, sy + 5, sx + 80, sy + 40, x + w + 40, sy + 60, x + w + 70, sy + 60)
    c.setFont('SB', 9); tw = c.stringWidth(lab, 'SB', 9)
    c.setFillColor(white); c.setStrokeColor(HexColor('#f28c18')); c.setLineWidth(1.2)
    c.roundRect(x + w + 70, sy + 54, tw + 10, 15, 3, stroke=1, fill=1)
    text(x + w + 75, sy + 58, lab, 9, 'SB', HexColor('#b45309'))
    text(W / 2, y - 36, 'La scheda può restare sulla breakout: in questo progetto non servono fili.', 9.5, 'S', GREY, 'c')


# ------------------------------------------------------------------ impaginazione
SICUREZZA = [
    'Fai e modifica i collegamenti con la scheda scollegata (cavo USB e alimentatore staccati).',
    'Nessun segnale a 5 V sui GPIO: l’ESP32 lavora a 3,3 V.',
    'Servo e motori prendono corrente dal 5 V della breakout con alimentatore esterno, dal modulo del kit o dalle batterie; il GND è sempre in comune.',
]


class Flusso:
    def __init__(self, titolo, num, pagina, tot, sotto='Passo passo'):
        self.titolo, self.num, self.pag, self.tot = titolo, num, pagina, tot
        self.testa = ('Componente / piedino', 'Va a')
        self.nuova(sotto)

    def nuova(self, sotto='Passo passo'):
        header(self.titolo, sotto, self.pag, self.tot, self.num)
        self.y = H - 110

    def spazio(self, serve, sotto='Passo passo (continua)'):
        if self.y - serve < 50:
            c.showPage(); self.pag += 1; self.nuova(sotto)

    def sez(self, t):
        self.spazio(60); self.y = titolo_sez(40, self.y, t)

    def passi(self, lista):
        for i, (t, d) in enumerate(lista, 1):
            n = len(simpleSplit(d or '', 'S', 9.4, W - 110)) + len(simpleSplit(t, 'SB', 10.5, W - 110))
            self.spazio(14 + 12.5 * n)
            self.y = passi(40, self.y, W - 80, [(t, d)], i)

    def testo(self, s):
        n = len(simpleSplit(s, 'S', 10, W - 80))
        self.spazio(14 * n + 10)
        self.y = wrap(40, self.y, s, W - 80, 10, 14) - 10

    def tabella(self, righe):
        self.spazio(20 + 15 * min(len(righe), 6))
        resto = list(righe)
        while resto:
            n = max(1, int((self.y - 70) // 15))
            self.y = tabella(self.y, resto[:n], testa=self.testa); resto = resto[n:]
            if resto: c.showPage(); self.pag += 1; self.nuova('Passo passo (continua)')

    def problemi(self, lista):
        for a, b in lista:
            n = len(simpleSplit(b, 'S', 9.4, W - 80))
            self.spazio(22 + 12.5 * n)
            self.y = problemi(self.y, [(a, b)]) + 4

    def nota(self, righe, titolo=None, bg=LIGHT, fg=black):
        self.spazio(riquadro_h(W - 80, righe, titolo))
        self.y = riquadro(40, self.y, W - 80, righe, bg, fg, titolo)

    def codice(self, nome, src):
        c.showPage(); self.pag += 1; self.nuova('Il codice MicroPython')
        self.y = titolo_sez(40, self.y, 'Il codice (' + nome + ')')
        self.y = wrap(40, self.y, 'È già dentro ESP32 Lab: lo trovi in fondo alla pagina del progetto e puoi modificarlo dal telefono.', W - 80, 9.4, 12.5, 'S', GREY) - 8
        for ln in src.rstrip('\n').split('\n'):
            for part in (simpleSplit(ln, MONO, 7.6, W - 80) or ['']):
                if self.y < 50:
                    c.showPage(); self.pag += 1; self.nuova('Il codice MicroPython (continua)')
                text(40, self.y, part, 7.6, MONO, HexColor('#1f2937')); self.y -= 9.6

    def fine(self):
        c.showPage()


def cosa_serve(p, D):
    out = []
    for k in p['parts']:
        it = D['PARTS'][k]
        name = it['name']
        if k == 'board':
            name = 'la scheda Freenove ESP32-S3 WROOM CAM montata sulla Freenove Breakout Board'
        elif k == 'cable':
            name = 'il cavo USB-C dati (e il telefono o il PC con Chrome)'
        elif k == 'psu':
            name = 'il 5 V per i componenti: alimentatore esterno sulla breakout oppure il modulo di alimentazione del kit'
        tag = {'kit': 'kit Elegoo', 'acquisto': 'a parte', 'consigliato': 'a parte'}[it['src']]
        out.append((name, tag))
    if 'cable' not in p['parts']:
        out.append(('il cavo USB-C dati (e il telefono con ESP32 Lab)', 'a parte'))
    return out


def pagina_cosa_serve(y, cosa, info):
    x = 40
    for i, (k, v) in enumerate(info):
        bx = x + i * 172
        c.setFillColor(LIGHT); c.roundRect(bx, y - 34, 160, 40, 6, stroke=0, fill=1)
        text(bx + 10, y - 9, k, 8, 'S', GREY); text(bx + 10, y - 25, v, 10.5, 'SB')
    y -= 58
    y = titolo_sez(40, y, 'Cosa ti serve')
    for s, tag in cosa:
        lines = simpleSplit('•  ' + s, 'S', 10, W - 190)
        for j, ln in enumerate(lines):
            text(48, y, ln, 10)
            if j == 0:
                col = HexColor('#166534') if tag == 'kit Elegoo' else HexColor('#92400e')
                text(W - 40, y, tag, 8, 'SB', col, 'r')
            y -= 14
        y -= 1
    return y - 6


def passi_collegamento(p):
    out = [('Prepara la scheda', 'Con cavo e alimentatore staccati, inserisci la scheda ESP32-S3 sulla breakout rispettando il verso indicato sulla breakout.')]
    comps = componenti(p)
    for cp in comps:
        segm = []
        for pn in cp['pins']:
            segm.append(f"{pn['pin']} → {pn['to']}")
        out.append(('Collega: ' + cp['name'], ' · '.join(segm)))
    if any(pn['term'] == '5V' for cp in comps for pn in cp['pins']):
        out.append(('Alimentazione a 5 V', 'Collega un alimentatore esterno alla breakout (5 V fino a 3 A) oppure prendi il 5 V dal modulo di alimentazione del kit. In ogni caso il GND deve essere comune.'))
    if comps:
        out.append(('Ricontrolla', 'Confronta ogni filo con la tabella «Tutti i collegamenti» qui sotto prima di dare corrente.'))
    return out


def passi_carica(p):
    out = [('Collega il telefono', 'Collega il cavo USB-C (porta «USB» della scheda) o accendi l’alimentazione. Apri ESP32 Lab in Chrome, premi «Collega scheda» e scegli Bluetooth (o USB).')]
    if p.get('wifi'):
        out.append(('Controlla il Wi-Fi', 'Nella pagina Scheda deve esserci la tua rete a 2,4 GHz. Telefono e scheda devono essere sulla stessa rete.'))
    out.append(('Carica il progetto', f'Apri «{p["title"]}» e premi «Carica ed esegui». Dopo pochi secondi lo stato diventa «in esecuzione» e il pannello di controllo si attiva.'))
    return out


def guida(p, D, tot, code):
    g = G.get(p['id'], {})
    lv = {l['n']: l['name'] for l in D['LEVELS']}[p['level']]
    titolo = p['title']
    sotto = g.get('sotto', p['summary'])
    nfili = len([r for r in expand(p['wiring']) if terminal(r[1])])
    header(titolo, sotto, 1, tot, p['n'])
    y = pagina_cosa_serve(H - 104, cosa_serve(p, D), [('Difficoltà', g.get('diff', '—')), ('Tempo', p['time']),
                                                        ('Fili da collegare', str(nfili) if nfili else 'Nessuno')])
    bottom = 60
    extra = g.get('perche')
    if extra:
        bottom = 60 + riquadro_h(W - 80, [extra], 'Perché iniziare da qui')
    disegno(p, y - 10, bottom)
    if extra:
        riquadro(40, bottom - 12, W - 80, [extra], titolo='Perché iniziare da qui')
    text(40, 36, f'Livello {p["level"]} · {lv}' + (' · Wi-Fi' if p.get('wifi') else '') + (' · fotocamera' if p.get('cam') else ''), 8, 'S', GREY)
    c.showPage()

    f = Flusso(titolo, p['n'], 2, tot)
    prima = g.get('prima', []) + p['notes']
    if prima:
        f.nota(prima, 'Prima di iniziare', WARN_BG, WARN_FG)
    f.sez('Passo passo')
    f.passi(passi_collegamento(p) + passi_carica(p) + g.get('uso', []))
    if g.get('vedi'):
        f.sez('Cosa dovresti vedere')
        f.testo(g['vedi'])
    if p['wiring']:
        f.sez('Tutti i collegamenti')
        f.tabella([(a, b, col) for a, b, col in p['wiring']])
    f.sez('Se non funziona')
    f.problemi(g.get('prob', []) + [
        ('Il pannello di controllo è grigio', 'Sulla scheda c’è un altro progetto: premi «Carica ed esegui».'),
        ('Compare un messaggio rosso', 'Leggi «Messaggi dalla scheda»: di solito indica il filo o il componente che non risponde.'),
    ])
    f.nota(SICUREZZA, 'Regole d’oro', WARN_BG, WARN_FG)
    f.codice(p['file'], code)
    f.fine()
    return f.pag


def render(p, D, tot):
    global c
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f'ESP32 Lab {p["n"]} – {p["title"]}'); c.setAuthor('ESP32 Lab')
    code = open(os.path.join(ROOT, 'public/board/projects', p['file']), encoding='utf-8').read()
    pages = guida(p, D, tot, code)
    c.save()
    return buf.getvalue(), pages


def copertina(D):
    global c
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle('ESP32 Lab – manuale')
    c.setFillColor(HexColor('#0f1115')); c.rect(0, H - 220, W, 220, stroke=0, fill=1)
    text(40, H - 90, 'ESP32 LAB', 11, 'SB', HexColor('#7fb2ff'))
    text(40, H - 130, 'Manuale dei progetti', 30, 'SB', white)
    text(40, H - 160, f'{len(D["P"])} progetti MicroPython per Freenove ESP32-S3 WROOM CAM', 12, 'S', HexColor('#b8c0cc'))
    text(40, H - 178, 'con Freenove Breakout Board e kit Elegoo', 12, 'S', HexColor('#b8c0cc'))
    y = H - 260
    y = titolo_sez(40, y, 'Indice')
    for lv in D['LEVELS']:
        text(40, y, f'Livello {lv["n"]} · {lv["name"]}', 10.5, 'SB', ACC); y -= 15
        for p in [q for q in D['P'] if q['level'] == lv['n']]:
            buy = ' (componenti da comprare)' if any(k in p['parts'] for k in ('oled', 'mpu6050', 'ring', 'pir', 'tcrt', 'chassis', 'l298n')) else ''
            text(52, y, f'{p["n"]:>2}.  {p["title"]}{buy}', 9.5); y -= 13
        y -= 5
    c.showPage()
    f = Flusso('Prima di iniziare', '–', 0, 0, 'Le cose da sapere una volta sola')
    f.sez('Primo avvio')
    f.passi([
        ('Monta la scheda sulla breakout', 'Rispetta il verso indicato dalle serigrafie della breakout e dal tutorial Freenove.'),
        ('Installa MicroPython', 'Da Chrome su PC apri ESP32 Lab → Scheda → passo 1. Usa la porta «UART» della scheda.'),
        ('Installa il runtime', 'Sempre dalla pagina Scheda, passo 2, con il cavo USB. Da qui in poi puoi usare il Bluetooth dal telefono.'),
        ('Imposta il Wi-Fi', 'Solo se vuoi i progetti web e fotocamera: rete a 2,4 GHz.'),
    ])
    f.sez('Mappa dei pin')
    f.testa = ('Pin  –  uso nei progetti', 'Stato')
    f.tabella([(f'{g}  –  {u}', s, '#ef4444' if 'NON' in s else '#16a34a') for g, u, s in D['PINMAP']])
    f.nota(SICUREZZA, 'Regole d’oro', WARN_BG, WARN_FG)
    c.showPage()
    c.save()
    return buf.getvalue()


def main():
    D = load()
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith('.pdf'): os.remove(os.path.join(OUT, old))
    manual = PdfWriter()
    for page in PdfReader(io.BytesIO(copertina(D))).pages:
        manual.add_page(page)
    for p in D['P']:
        _, n = render(p, D, 0)
        data, n2 = render(p, D, n)
        name = f'ESP32-Lab-{p["n"]:02d}-{p["id"]}.pdf'
        open(os.path.join(OUT, name), 'wb').write(data)
        for page in PdfReader(io.BytesIO(data)).pages:
            manual.add_page(page)
        print(f'{name}: {n2} pagine')
    with open(os.path.join(OUT, 'ESP32-Lab-manuale.pdf'), 'wb') as fh:
        manual.write(fh)
    print('manuale:', len(manual.pages), 'pagine')


if __name__ == '__main__':
    main()
