"""Disegni realistici dei collegamenti per le guide PDF di ESP32 Lab (stile UNO Lab).

Coordinate: ogni disegno lavora in un riquadro naturale FW x FH punti; guide.py lo
scala e lo posiziona nello spazio libero della pagina.
I primitivi della breadboard vengono da UNO Lab (plpssnt-prog/elegoo, strumenti/guide.py).
"""
import math
from reportlab.lib.colors import HexColor, white, black

c = None          # canvas, impostato da guide.py
FW, FH = 515, 530

RED = HexColor('#d62828'); ORANGE = HexColor('#f28c18'); BROWN = HexColor('#7a4a21')
GREEN = HexColor('#2a9d3a'); BLUEW = HexColor('#1f5fd1'); YEL = HexColor('#d4a100')
BLK = HexColor('#222222'); GREY = HexColor('#555b66'); ACC = HexColor('#1f6fd1')
VIOLA = HexColor('#7b3fc4'); CYAN = HexColor('#0891b2'); PINK = HexColor('#db2777')
SERVO = HexColor('#2f6bd8')

B220 = ['#d62828', '#d62828', '#111111', '#111111', '#7a4a21']
B10K = ['#7a4a21', '#111111', '#111111', '#d62828', '#7a4a21']
B1K = ['#7a4a21', '#111111', '#111111', '#7a4a21', '#7a4a21']
B2K = ['#d62828', '#111111', '#111111', '#7a4a21', '#7a4a21']
B100K = ['#7a4a21', '#111111', '#111111', '#ea580c', '#7a4a21']


def text(x, y, s, size=10, font='S', color=black, anchor='l'):
    c.setFont(font, size); c.setFillColor(color)
    {'c': c.drawCentredString, 'r': c.drawRightString}.get(anchor, c.drawString)(x, y, s)


def wire(p0, p1, col, c1=None, c2=None, w=3.0):
    c.setStrokeColor(col); c.setLineWidth(w); c.setLineCap(1)
    if c1 is None:
        c.line(*p0, *p1)
    else:
        c.bezier(*p0, *c1, *c2, *p1)
    c.setFillColor(col)
    c.circle(*p0, 3.0, stroke=0, fill=1); c.circle(*p1, 3.0, stroke=0, fill=1)


DIRS = {'l': (-1, 0), 'r': (1, 0), 'u': (0, 1), 'd': (0, -1)}


def filo(a, b, col, da='u', a_='d', k=60, k2=None, w=3.0):
    """Filo curvo: esce da a nella direzione da, entra in b dalla direzione a_."""
    k2 = k if k2 is None else k2
    d1, d2 = DIRS[da], DIRS[a_]
    wire(a, b, col, (a[0] + d1[0] * k, a[1] + d1[1] * k), (b[0] - d2[0] * k2, b[1] - d2[1] * k2), w)


def etichetta(x, y, s, col, anchor='c', size=8):
    c.setFont('SB', size)
    tw = c.stringWidth(s, 'SB', size)
    bx = x - tw / 2 - 4 if anchor == 'c' else (x - tw - 8 if anchor == 'r' else x)
    c.setFillColor(white); c.setStrokeColor(col); c.setLineWidth(1.2)
    c.roundRect(bx, y - 4, tw + 8, size + 5, 3, stroke=1, fill=1)
    text(bx + 4, y, s, size, 'SB', col)


def resistenza(p1, p2, bande):
    c.setStrokeColor(HexColor('#8a8a8a')); c.setLineWidth(1.6); c.line(*p1, *p2)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
    c.saveState(); c.translate(mx, my); c.rotate(ang)
    c.setFillColor(HexColor('#d9c49a')); c.roundRect(-16, -5.5, 32, 11, 5, stroke=0, fill=1)
    for i, col in enumerate(bande):
        c.setFillColor(HexColor(col)); c.rect(-11 + i * 5, -5.5, 2.6, 11, stroke=0, fill=1)
    c.restoreState()
    c.setFillColor(HexColor('#8a8a8a')); c.circle(*p1, 2.2, stroke=0, fill=1); c.circle(*p2, 2.2, stroke=0, fill=1)


# ------------------------------------------------------------------ breadboard (da UNO Lab)
SP = 16
RIGHE = 'abcdefghij'
ETICHETTA_RIGA = dict(zip('abcdefghij', 'jihgfedcba'))


def bb(x0, y0, ncol=20, sopra=False, sotto=True):
    """Breadboard. foro(col, riga): riga in 'abcdefghij' oppure '+s','-s','+b','-b'.
    Righe a-e = meta' alta, f-j = meta' bassa (vicino alle righe + e – in basso)."""
    w, h = ncol * SP + 44, 11 * SP + 52
    top = y0 + h - 26

    def foro(col, r):
        x = x0 + 30 + (col - 1) * SP
        if r == '-s': return (x, y0 + h + 14)
        if r == '+s': return (x, y0 + h + 30)
        if r == '-b': return (x, y0 - 14)
        if r == '+b': return (x, y0 - 30)
        k = RIGHE.index(r)
        return (x, top - (k if k < 5 else k + 2) * SP)

    c.setFillColor(HexColor('#f6f6f3')); c.setStrokeColor(HexColor('#c8c8c0')); c.setLineWidth(1)
    c.roundRect(x0, y0 - (40 if sotto else 0), w, h + (40 if sotto else 0) + (40 if sopra else 0), 6, stroke=1, fill=1)
    ce = (foro(1, 'e')[1] + foro(1, 'f')[1]) / 2
    c.setFillColor(HexColor('#e2e2dc')); c.rect(x0 + 6, ce - 5, w - 12, 10, stroke=0, fill=1)
    rails = (['-s', '+s'] if sopra else []) + (['-b', '+b'] if sotto else [])
    for r in rails:
        yy = foro(1, r)[1]
        col = RED if r[0] == '+' else ACC
        c.setStrokeColor(col); c.setLineWidth(1)
        off = 7 if (r in ('+s', '-b')) else -7
        c.line(x0 + 10, yy + off, x0 + w - 24, yy + off)
        text(x0 + w - 10, yy - 4, '+' if r[0] == '+' else '–', 11, 'SB', col, 'c')
        for i in range(1, ncol + 1):
            fx, fy = foro(i, r)
            c.setFillColor(HexColor('#9a9a92')); c.rect(fx - 2, fy - 2, 4, 4, stroke=0, fill=1)
    for col in range(1, ncol + 1):
        for r in RIGHE:
            fx, fy = foro(col, r)
            c.setFillColor(HexColor('#9a9a92')); c.rect(fx - 2, fy - 2, 4, 4, stroke=0, fill=1)
        fx, fy = foro(col, 'a'); text(fx, fy + 9, str(col), 6, 'S', GREY, 'c')
        fx, fy = foro(col, 'j'); text(fx, fy - 15, str(col), 6, 'S', GREY, 'c')
    for r in RIGHE:
        fx, fy = foro(1, r); text(fx - 12, fy - 2.5, ETICHETTA_RIGA[r], 7, 'S', GREY, 'c')
    return foro


def ponticello(p0, p1, col=BLK):
    wire(p0, p1, col, w=2.4)


def led_bb(foro, ca, colore, nome=None, gambe='h', corpo='f'):
    """LED nella meta' bassa: anodo (lungo) in colonna ca, catodo in ca+1."""
    pa, pk = foro(ca, gambe), foro(ca + 1, gambe)
    cx, cy = (pa[0] + pk[0]) / 2, foro(ca, corpo)[1] + 4
    c.setStrokeColor(HexColor('#9a9a9a')); c.setLineWidth(1.8)
    c.line(pa[0], cy, pa[0], pa[1]); c.line(pk[0], cy, pk[0], pk[1])
    c.setFillColor(HexColor('#9a9a9a')); c.circle(*pa, 2.2, stroke=0, fill=1); c.circle(*pk, 2.2, stroke=0, fill=1)
    c.setFillColor(HexColor(colore)); c.setStrokeColor(HexColor('#555555')); c.setLineWidth(0.6)
    c.circle(cx, cy, 10, stroke=1, fill=1)
    c.setFillColor(white); c.circle(cx - 3, cy + 3, 2.5, stroke=0, fill=1)
    text(pa[0] - 5, cy - 18, '+', 8, 'SB', RED, 'c')
    if nome: text(cx, cy + 14, nome, 7, 'SB', GREY, 'c')


def res_vert(foro, col, r_da='j', r_a='-b', bande=None):
    resistenza(foro(col, r_da), foro(col, r_a), bande or B220)


def pulsante_bb(foro, col):
    pts = [foro(col, 'e'), foro(col + 2, 'e'), foro(col, 'f'), foro(col + 2, 'f')]
    x0, x1 = pts[0][0] - 6, pts[1][0] + 6
    y0, y1 = pts[2][1] - 6, pts[0][1] + 6
    c.setFillColor(HexColor('#2b2b2b')); c.roundRect(x0, y0, x1 - x0, y1 - y0, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#555555')); c.circle((x0 + x1) / 2, (y0 + y1) / 2, 9, stroke=0, fill=1)
    for p in pts:
        c.setFillColor(HexColor('#bbbbbb')); c.circle(*p, 2.3, stroke=0, fill=1)


def due_piedini(foro, c1, c2, riga, corpo, etich=None):
    p1, p2 = foro(c1, riga), foro(c2, riga)
    cx, cy = (p1[0] + p2[0]) / 2, foro(c1, 'f')[1] + 2
    c.setStrokeColor(HexColor('#9a9a9a')); c.setLineWidth(1.8)
    c.line(p1[0], cy, p1[0], p1[1]); c.line(p2[0], cy, p2[0], p2[1])
    c.setFillColor(HexColor('#9a9a9a')); c.circle(*p1, 2.2, stroke=0, fill=1); c.circle(*p2, 2.2, stroke=0, fill=1)
    corpo(cx, cy)
    if etich: text(cx, cy + 18, etich, 7, 'SB', GREY, 'c')


def corpo_buzzer(cx, cy):
    c.setFillColor(HexColor('#1e1e1e')); c.circle(cx, cy, 13, stroke=0, fill=1)
    c.setFillColor(HexColor('#3d3d3d')); c.circle(cx, cy, 4, stroke=0, fill=1)
    text(cx - 9, cy + 9, '+', 7, 'SB', RED, 'c')


def corpo_ldr(cx, cy):
    c.setFillColor(HexColor('#f3e3c3')); c.circle(cx, cy, 9, stroke=0, fill=1)
    c.setStrokeColor(HexColor('#b45309')); c.setLineWidth(1.1)
    p = c.beginPath(); p.moveTo(cx - 6, cy)
    for i in range(7): p.lineTo(cx - 5 + i * 1.8, cy + (3 if i % 2 else -3))
    c.drawPath(p, stroke=1, fill=0)


def potenziometro_bb(foro, col, riga='h'):
    pts = [foro(col + 2 * i, riga) for i in range(3)]
    cx, cy = pts[1][0], foro(col, 'f')[1] + 4
    c.setStrokeColor(HexColor('#9a9a9a')); c.setLineWidth(1.8)
    for p in pts: c.line(p[0], cy, p[0], p[1])
    c.setFillColor(HexColor('#2a5fb0')); c.roundRect(cx - 24, cy - 8, 48, 22, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#222222')); c.circle(cx, cy + 3, 9, stroke=0, fill=1)
    c.setFillColor(white); c.rect(cx - 1, cy + 3, 2, 8, stroke=0, fill=1)
    for p in pts: c.setFillColor(HexColor('#9a9a9a')); c.circle(*p, 2.2, stroke=0, fill=1)
    return pts


def chip_bb(foro, col, nome):
    """Chip DIP16 a cavallo della scanalatura, tacca a sinistra. pin(n) -> (colonna, riga)."""
    def pin(n):
        if n <= 8: return (col + n - 1, 'f')
        return (col + 16 - n, 'e')
    xa, xb = foro(col, 'e')[0] - 7, foro(col + 7, 'e')[0] + 7
    ya, yb = foro(col, 'f')[1] - 2, foro(col, 'e')[1] + 2
    c.setFillColor(HexColor('#1b1b1b')); c.rect(xa, ya, xb - xa, yb - ya, stroke=0, fill=1)
    c.setFillColor(HexColor('#555555')); c.circle(xa, (ya + yb) / 2, 5, stroke=0, fill=1)
    text((xa + xb) / 2, (ya + yb) / 2 - 3, nome, 7.5, 'SB', white, 'c')
    for n in range(1, 17):
        cc, r = pin(n)
        fx, fy = foro(cc, r)
        c.setFillColor(HexColor('#c0c0c0')); c.rect(fx - 3, fy - 3, 6, 6, stroke=0, fill=1)
        text(fx, fy + (-13 if r == 'f' else 7), str(n), 6, 'SB', HexColor('#c03030'), 'c')
    return pin


def wire_res(p0, p1, col, c1=None, c2=None, bande=None):
    wire(p0, p1, col, c1, c2, w=2.4)
    if c1 is None:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    else:
        t = 0.5
        bz = lambda a, b, cc, d: (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * cc + t ** 3 * d
        mx, my = bz(p0[0], c1[0], c2[0], p1[0]), bz(p0[1], c1[1], c2[1], p1[1])
        ang = math.atan2(c2[1] - c1[1], c2[0] - c1[0])
    c.saveState(); c.translate(mx, my); c.rotate(math.degrees(ang))
    c.setFillColor(HexColor('#d9c49a')); c.roundRect(-12, -4.5, 24, 9, 4, stroke=0, fill=1)
    for i, cl in enumerate(bande or B220):
        c.setFillColor(HexColor(cl)); c.rect(-8 + i * 3.6, -4.5, 1.8, 9, stroke=0, fill=1)
    c.restoreState()


def modulo(x, y, w, hh, nome, pin_nomi, colore='#1f4fa8', sotto=True, nome_col=white, step=13):
    """Modulo con i piedini in basso (o in alto). Ritorna dict nome -> punta del piedino."""
    c.setFillColor(HexColor(colore)); c.roundRect(x, y, w, hh, 4, stroke=0, fill=1)
    text(x + w / 2, y + hh - 14 if sotto else y + 8, nome, 8, 'SB', nome_col, 'c')
    n = len(pin_nomi)
    x0 = x + w / 2 - (n - 1) * step / 2
    pins = {}
    for i, pn in enumerate(pin_nomi):
        px = x0 + i * step
        py = y if sotto else y + hh
        c.saveState(); c.translate(px + 2.5, (y + 6) if sotto else (y + hh - 6)); c.rotate(90)
        c.setFont('S', 5.5); c.setFillColor(nome_col)
        (c.drawString if sotto else c.drawRightString)(0, 0, pn); c.restoreState()
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8)
        c.line(px, py, px, py - 12 if sotto else py + 12)
        pins[pn] = (px, py - 12 if sotto else py + 12)
    return pins


def hcsr04(x, y):
    c.setFillColor(HexColor('#1f4fa8')); c.roundRect(x, y, 150, 62, 4, stroke=0, fill=1)
    for cx in (x + 33, x + 117):
        c.setFillColor(HexColor('#c9ccd1')); c.circle(cx, y + 36, 24, stroke=0, fill=1)
        c.setFillColor(HexColor('#3a3f47')); c.circle(cx, y + 36, 18, stroke=0, fill=1)
    text(x + 75, y + 50, 'HC-SR04', 7, 'SB', white, 'c')
    nomi = ['Vcc', 'Trig', 'Echo', 'Gnd']
    pins = []
    for i, n in enumerate(nomi):
        px = x + 55 + i * 13
        c.saveState(); c.translate(px + 2.5, y + 8); c.rotate(90)
        c.setFont('S', 5.5); c.setFillColor(white); c.drawString(0, 0, n); c.restoreState()
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8); c.line(px, y, px, y - 14)
        pins.append((px, y - 14))
    return dict(zip(nomi, pins))


def servo(cx, cy, cavo=70):
    """Servo SG90 con il cavo a 3 fili che termina nello spinotto. Ritorna i 3 punti dello spinotto
    (marrone, rosso, arancione) e la funzione per disegnare lo spinotto in una posizione."""
    c.setFillColor(SERVO); c.roundRect(cx - 45, cy - 22, 90, 44, 4, stroke=0, fill=1)
    c.roundRect(cx - 60, cy - 6, 120, 12, 3, stroke=0, fill=1)
    c.setFillColor(white); c.circle(cx + 20, cy, 9, stroke=0, fill=1)
    c.roundRect(cx + 14, cy - 4, 48, 8, 4, stroke=0, fill=1)
    text(cx, cy + 28, 'Servo SG90', 9, 'SB', black, 'c')
    return {'arancione': (cx - 45, cy + 6), 'rosso': (cx - 45, cy), 'marrone': (cx - 45, cy - 6)}


def motore_dc(cx, cy, nome='motore'):
    c.setFillColor(HexColor('#c0c4cc')); c.roundRect(cx - 22, cy - 15, 44, 30, 8, stroke=0, fill=1)
    c.setFillColor(HexColor('#9aa0aa')); c.rect(cx + 22, cy - 3, 12, 6, stroke=0, fill=1)
    text(cx, cy - 27, nome, 7, 'SB', GREY, 'c')
    return (cx - 22, cy + 8), (cx - 22, cy - 8)


def motoriduttore(cx, cy, nome):
    c.setFillColor(HexColor('#222222')); c.roundRect(cx - 14, cy + 12, 28, 18, 4, stroke=0, fill=1)
    c.setFillColor(HexColor('#f2c230')); c.roundRect(cx - 28, cy - 12, 56, 24, 3, stroke=0, fill=1)
    text(cx, cy - 2, nome, 7, 'SB', black, 'c')
    return (cx - 28, cy + 5), (cx - 28, cy - 5)


def batterie(x, y, nome='4×AA 6 V'):
    c.setFillColor(HexColor('#2b2b2b')); c.roundRect(x, y, 70, 40, 4, stroke=0, fill=1)
    for i in range(4):
        c.setFillColor(HexColor('#c9a227')); c.roundRect(x + 6 + i * 16, y + 8, 12, 24, 3, stroke=0, fill=1)
    text(x + 35, y - 10, nome, 7, 'SB', GREY, 'c')
    return {'+': (x + 70, y + 30), '-': (x + 70, y + 10)}


def powerbank(x, y):
    c.setFillColor(HexColor('#4b5563')); c.roundRect(x, y, 80, 34, 6, stroke=0, fill=1)
    text(x + 40, y + 14, 'power bank', 7, 'SB', white, 'c')
    return (x + 80, y + 17)


# ------------------------------------------------------------------ breakout Freenove
SINISTRA = ['3V3', 'EN', '4', '5', '6', '7', '15', '16', '17', '18', '8', '3', '46', '9', '10', '11', '12', '13', '14', '5V']
DESTRA = ['TX', 'RX', '1', '2', '42', '41', '40', '39', '38', '37', '36', '35', '0', '45', '48', '47', '21', '20', '19', 'GND']
BW, BH, RS = 280, 260, 10


def breakout(x, y, usati=(), alim=False, evid=None):
    """Breakout Freenove con la scheda ESP32-S3 sopra (vista dall'alto, USB in basso).
    Ogni riga: morsetto verde, piedino giallo S (segnale), rosso V (5V0), nero G (GND).
    Ritorna P: P['S','42'], P['V','42'], P['G','42'], P['3V3'][i], P['JACK'], P['LED'], P['RGB'], P['CAM']."""
    P = {}
    c.setFillColor(HexColor('#15191e')); c.roundRect(x, y, BW, BH, 10, stroke=0, fill=1)
    for hx, hy in ((x + 9, y + 9), (x + BW - 9, y + 9), (x + 9, y + BH - 9), (x + BW - 9, y + BH - 9)):
        c.setFillColor(HexColor('#c9ccd1')); c.circle(hx, hy, 4, stroke=0, fill=1)
        c.setFillColor(HexColor('#15191e')); c.circle(hx, hy, 2, stroke=0, fill=1)
    text(x + BW / 2, y + BH - 13, 'FREENOVE  Breakout Board ESP32-S3', 6.5, 'SB', HexColor('#cbd5e1'), 'c')
    top = y + BH - 30
    ys = [top - i * RS for i in range(20)]

    def colonna(nomi, lato):
        if lato == 'l':
            xt, xs, xv, xg, xl = x + 12, x + 31, x + 41, x + 51, x + 66
        else:
            xt, xs, xv, xg, xl = x + BW - 12, x + BW - 31, x + BW - 41, x + BW - 51, x + BW - 66
        c.setFillColor(HexColor('#2f9e57'))
        c.rect(xt - 7, ys[-1] - 6, 14, ys[0] - ys[-1] + 12, stroke=0, fill=1)
        for nome, yy in zip(nomi, ys):
            c.setFillColor(HexColor('#cfd6dc')); c.circle(xt, yy, 3.2, stroke=0, fill=1)
            c.setStrokeColor(HexColor('#6b7280')); c.setLineWidth(0.8); c.line(xt - 2, yy, xt + 2, yy)
            for xx, col in ((xs, '#e8c547'), (xv, '#e05a5a'), (xg, '#3a3a3a')):
                c.setFillColor(HexColor(col)); c.rect(xx - 3.2, yy - 3.2, 6.4, 6.4, stroke=0, fill=1)
                c.setFillColor(HexColor('#d9d9d9')); c.rect(xx - 1, yy - 1, 2, 2, stroke=0, fill=1)
            on = nome in usati
            text(xl, yy - 2.3, nome, 6.2, 'SB' if on else 'S', HexColor('#ffd166') if on else HexColor('#cbd5e1'), 'c')
            P['S', nome] = (xs, yy); P['V', nome] = (xv, yy); P['G', nome] = (xg, yy); P['T', nome] = (xt, yy)
            if on:
                c.setStrokeColor(HexColor('#ffd166')); c.setLineWidth(1.2)
                c.roundRect(xl - 9, yy - 5, 18, 10, 2, stroke=1, fill=0)
        # intestazioni colonne
        for xx, lab in ((xs, 'S'), (xv, '5V0'), (xg, 'GND')):
            text(xx, ys[-1] - 15, lab, 4.6, 'SB', HexColor('#94a3b8'), 'c')

    colonna(SINISTRA, 'l')
    colonna(DESTRA, 'r')
    # scheda ESP32-S3 CAM al centro
    ex, ew = x + 84, BW - 168
    ey, eh = y + 44, BH - 66
    c.setFillColor(HexColor('#0b0d10')); c.roundRect(ex, ey, ew, eh, 5, stroke=0, fill=1)
    c.setFillColor(HexColor('#cbd5e1')); c.roundRect(ex + 10, ey + eh - 70, ew - 20, 62, 3, stroke=0, fill=1)
    text(ex + ew / 2, ey + eh - 30, 'ESP32-S3', 8, 'SB', HexColor('#1f2937'), 'c')
    text(ex + ew / 2, ey + eh - 41, 'WROOM-1', 6, 'S', HexColor('#475569'), 'c')
    cy = ey + eh - 95
    c.setFillColor(HexColor('#111827')); c.setStrokeColor(HexColor('#64748b')); c.setLineWidth(2.2)
    c.circle(ex + ew / 2, cy, 12, stroke=1, fill=1)
    c.setFillColor(HexColor('#334155')); c.circle(ex + ew / 2, cy, 4.5, stroke=0, fill=1)
    c.setFillColor(HexColor('#e85d04')); c.rect(ex + ew / 2 - 6, cy - 34, 12, 22, stroke=0, fill=1)
    P['CAM'] = (ex + ew / 2, cy)
    # pulsanti, LED e USB
    c.setFillColor(HexColor('#4b5563')); c.rect(ex + 6, ey + 26, 12, 9, stroke=0, fill=1); c.rect(ex + ew - 18, ey + 26, 12, 9, stroke=0, fill=1)
    text(ex + 12, ey + 38, 'RST', 4.8, 'S', HexColor('#9ca3af'), 'c'); text(ex + ew - 12, ey + 38, 'BOOT', 4.8, 'S', HexColor('#9ca3af'), 'c')
    led_x = ex + ew / 2 - 14
    for i, col in enumerate(('#22c55e', '#e5e7eb', '#e5e7eb', '#60a5fa', '#f8fafc')):
        c.setFillColor(HexColor(col)); c.rect(led_x + i * 7, ey + 28, 4, 4, stroke=0, fill=1)
    P['LED'] = (led_x + 3 * 7 + 2, ey + 30); P['RGB'] = (led_x + 4 * 7 + 2, ey + 30)
    for ux in (ex + ew / 2 - 22, ex + ew / 2 + 6):
        c.setFillColor(HexColor('#9ca3af')); c.roundRect(ux, ey - 4, 16, 14, 3, stroke=0, fill=1)
    P['USB'] = (ex + ew / 2 + 14, ey + 4)
    text(ex + ew / 2 - 14, ey - 13, 'UART', 5, 'S', HexColor('#94a3b8'), 'c'); text(ex + ew / 2 + 14, ey - 13, 'USB', 5, 'S', HexColor('#94a3b8'), 'c')
    # in basso: GND (sx), jack 7-12 V e 3.3V (dx)
    gx, gy = x + 24, y + 14
    for i in range(4):
        for j in range(2):
            c.setFillColor(HexColor('#3a3a3a')); c.rect(gx + i * 9 - 3, gy + j * 9 - 3, 6, 6, stroke=0, fill=1)
    text(gx + 13, gy - 9, 'GND', 5.5, 'SB', HexColor('#cbd5e1'), 'c')
    P['GNDb'] = [(gx + i * 9, gy + 9) for i in range(4)]
    jx, jy = x + BW - 112, y + 6
    c.setFillColor(HexColor('#111111')); c.rect(jx, jy, 26, 30, stroke=0, fill=1)
    c.setFillColor(HexColor('#3f3f46')); c.circle(jx + 13, jy + 15, 6, stroke=0, fill=1)
    text(jx + 13, jy - 4, '7–12V', 5.5, 'SB', HexColor('#cbd5e1'), 'c')
    P['JACK'] = (jx + 13, jy + 2)
    px, py = x + BW - 70, y + 14
    for i in range(4):
        for j in range(2):
            c.setFillColor(HexColor('#f0a0b4')); c.rect(px + i * 9 - 3, py + j * 9 - 3, 6, 6, stroke=0, fill=1)
    text(px + 13, py - 9, '3.3V', 5.5, 'SB', HexColor('#cbd5e1'), 'c')
    P['3V3'] = [(px + i * 9, py + 9) for i in range(4)]
    if alim:
        alimentatore(P['JACK'])
    if evid:
        sx, sy = P[evid]
        lab = {'LED': 'LED blu (GPIO2)', 'RGB': 'LED RGB (GPIO48)', 'CAM': 'fotocamera'}[evid]
        c.setStrokeColor(ORANGE); c.setLineWidth(2.4); c.circle(sx, sy, 10 if evid != 'CAM' else 16, stroke=1, fill=0)
        c.setLineWidth(2); c.bezier(sx + 10, sy, sx + 90, sy + 10, x + BW + 20, sy + 40, x + BW + 40, sy + 40)
        etichetta(x + BW + 44, sy + 37, lab, ORANGE, 'l', 9)
    return P


def alimentatore(jack):
    """Alimentatore 12 V con spinotto nel jack della breakout."""
    jx, jy = jack
    ax, ay = jx + 150, jy - 2
    c.setStrokeColor(BLK); c.setLineWidth(3)
    c.bezier(jx, jy, jx, jy - 12, ax - 40, ay + 14, ax, ay + 14)
    c.setFillColor(HexColor('#1f2937')); c.roundRect(ax, ay, 60, 30, 5, stroke=0, fill=1)
    text(ax + 30, ay + 17, '12 V', 8, 'SB', white, 'c')
    text(ax + 30, ay + 6, 'alimentatore', 5.5, 'S', HexColor('#cbd5e1'), 'c')


def lab_pin(P, nome, col, lato='r', dx=0):
    """Etichetta del GPIO accanto al morsetto."""
    x, y = P['T', nome]
    etichetta(x + (14 if lato == 'r' else -14) + dx, y - 3, nome, col, 'l' if lato == 'r' else 'r', 7)


# ------------------------------------------------------------------ disegni dei progetti
D = {}


def disegno(fn):
    D[fn.__name__[2:]] = fn
    return fn


BX, BY = 0, 0           # breakout in basso a sinistra (280 x 260)


def bb_std(ncol=16, x0=210):
    """Breadboard in alto a destra."""
    return bb(x0, 300, ncol)


def gnd_bb(P, foro, row='19', col=1):
    filo(P['G', row], foro(col, '-b'), BLK, 'r', 'd', 30, 40)


@disegno
def d_blink():
    breakout(100, 150, evid='LED')


@disegno
def d_rgb():
    breakout(100, 150, evid='RGB')


@disegno
def d_photo():
    breakout(100, 150, evid='CAM')


@disegno
def d_stream():
    breakout(100, 150, evid='CAM')


@disegno
def d_dimmer():
    P = breakout(BX, BY, usati=('21',))
    foro = bb_std()
    led_bb(foro, 6, '#e33b3b', 'LED')
    res_vert(foro, 7)
    filo(P['S', '21'], foro(6, 'j'), BLUEW, 'r', 'd', 70, 120)
    gnd_bb(P, foro, '20', 3)


@disegno
def d_button():
    P = breakout(BX, BY, usati=('47',))
    foro = bb_std()
    pulsante_bb(foro, 6)
    filo(P['S', '47'], foro(6, 'j'), GREEN, 'r', 'd', 70, 120)
    filo(foro(8, 'j'), foro(8, '-b'), BLK, 'd', 'd', 4, 4)
    gnd_bb(P, foro, '20', 3)


def _buzzer(P, foro, c1=8):
    due_piedini(foro, c1, c1 + 2, 'h', corpo_buzzer, 'buzzer passivo')
    filo(P['S', '14'], foro(c1, 'j'), VIOLA, 'l', 'd', 20, 330)
    filo(foro(c1 + 2, 'j'), foro(c1 + 2, '-b'), BLK, 'd', 'd', 4, 4)
    lab_pin(P, '14', VIOLA, 'l')


@disegno
def d_buzzer():
    P = breakout(BX, BY, usati=('14',))
    foro = bb_std()
    _buzzer(P, foro)
    gnd_bb(P, foro, '20', 3)


@disegno
def d_clock():
    d_buzzer()


@disegno
def d_pot():
    P = breakout(BX, BY, usati=('1',))
    foro = bb_std()
    potenziometro_bb(foro, 6)
    filo(P['3V3'][3], foro(6, 'j'), RED, 'r', 'd', 60, 150)
    filo(P['S', '1'], foro(8, 'j'), CYAN, 'r', 'd', 60, 60)
    filo(foro(10, 'j'), foro(10, '-b'), BLK, 'd', 'd', 4, 4)
    gnd_bb(P, foro, '20', 3)
    etichetta(P['3V3'][0][0] + 12, P['3V3'][0][1] + 12, '3.3V', RED, 'c', 6)


def _ldr(P, foro, col=6, segn='1'):
    due_piedini(foro, col, col + 2, 'h', corpo_ldr, 'fotoresistenza')
    filo(P['3V3'][3], foro(col, 'j'), RED, 'r', 'd', 60, 150)
    res_vert(foro, col + 2, 'i', '-b', B10K)
    filo(P['S', segn], foro(col + 2, 'g'), CYAN, 'r', 'd', 50, 90)
    etichetta(P['3V3'][0][0] + 12, P['3V3'][0][1] + 12, '3.3V', RED, 'c', 6)


@disegno
def d_light():
    P = breakout(BX, BY, usati=('1',))
    foro = bb_std()
    _ldr(P, foro)
    gnd_bb(P, foro, '20', 3)


def dht11(x, y):
    c.setFillColor(HexColor('#1f4fa8')); c.roundRect(x, y, 46, 30, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#2563eb')); c.roundRect(x + 8, y + 30, 30, 34, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#bfdbfe'))
    for i in range(4):
        for j in range(3): c.rect(x + 12 + j * 8, y + 36 + i * 7, 5, 4, stroke=0, fill=1)
    text(x + 23, y + 16, 'DHT11', 6.5, 'SB', white, 'c')
    pins = {}
    for i, n in enumerate(['S', '+', '–']):
        px = x + 10 + i * 13
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8); c.line(px, y, px, y - 12)
        text(px, y + 3, n, 6, 'SB', white, 'c')
        pins[n] = (px, y - 12)
    return pins


@disegno
def d_dht():
    P = breakout(BX, BY, usati=('39',))
    d = dht11(390, 300)
    filo(P['S', '39'], d['S'], GREEN, 'r', 'd', 80, 90)
    filo(P['3V3'][3], d['+'], RED, 'r', 'd', 60, 140)
    filo(P['G', '37'], d['–'], BLK, 'r', 'd', 120, 70)


@disegno
def d_distance():
    P = breakout(BX, BY, usati=('41', '40', '14'), alim=True)
    foro = bb_std()
    h = hcsr04(330, 120)
    filo(h['Vcc'], P['V', '41'], RED, 'd', 'r', 30, 60)
    filo(h['Trig'], P['S', '41'], BLUEW, 'd', 'r', 40, 50)
    wire_res(h['Echo'], foro(11, 'j'), ORANGE, (h['Echo'][0] + 10, 210), (foro(11, 'j')[0], 200), B1K)
    res_vert(foro, 11, 'i', '-b', B2K)
    filo(foro(11, 'g'), P['S', '40'], YEL, 'l', 'r', 60, 90)
    filo(h['Gnd'], P['G', '40'], BLK, 'd', 'r', 50, 40)
    _buzzer(P, foro, 4)
    gnd_bb(P, foro, '20', 2)


@disegno
def d_joystick():
    P = breakout(BX, BY, usati=('1', '3', '47'))
    m = modulo(340, 330, 130, 80, 'Joystick', ['GND', '+5V', 'VRx', 'VRy', 'SW'], '#111827', step=16)
    c.setFillColor(HexColor('#4b5563')); c.circle(405, 382, 18, stroke=0, fill=1)
    c.setFillColor(HexColor('#111')); c.circle(405, 382, 9, stroke=0, fill=1)
    filo(P['G', '2'], m['GND'], BLK, 'r', 'd', 60, 120)
    filo(P['3V3'][3], m['+5V'], RED, 'r', 'd', 50, 200)
    filo(P['S', '1'], m['VRx'], CYAN, 'r', 'd', 80, 140)
    filo(P['S', '3'], m['VRy'], BLUEW, 'l', 'u', 20, 30)
    filo(P['S', '47'], m['SW'], GREEN, 'r', 'd', 120, 220)
    lab_pin(P, '3', BLUEW, 'l')
    text(404, 270, '+5V del joystick → 3.3V della breakout', 7, 'S', GREY, 'c')


@disegno
def d_ir():
    P = breakout(BX, BY, usati=('38',))
    m = modulo(390, 300, 70, 50, 'IR', ['G', 'R', 'Y'], '#111827', step=16)
    c.setFillColor(HexColor('#374151')); c.circle(425, 330, 9, stroke=0, fill=1)
    filo(P['G', '36'], m['G'], BLK, 'r', 'd', 90, 70)
    filo(P['3V3'][3], m['R'], RED, 'r', 'd', 60, 160)
    filo(P['S', '38'], m['Y'], GREEN, 'r', 'd', 110, 100)


@disegno
def d_mpu6050():
    P = breakout(BX, BY, usati=('21', '47'))
    m = modulo(350, 330, 120, 60, 'MPU-6050 (GY-521)', ['VCC', 'GND', 'SCL', 'SDA', 'XDA', 'XCL', 'AD0', 'INT'], '#1d4ed8', step=12)
    filo(P['3V3'][3], m['VCC'], RED, 'r', 'd', 50, 200)
    filo(P['G', '2'], m['GND'], BLK, 'r', 'd', 60, 120)
    filo(P['S', '47'], m['SCL'], GREEN, 'r', 'd', 80, 200)
    filo(P['S', '21'], m['SDA'], BLUEW, 'r', 'd', 100, 220)


def servo_spinotto(P, riga, sx=430, sy=330):
    s = servo(sx, sy)
    g, v, si = P['G', riga], P['V', riga], P['S', riga]
    c.setFillColor(HexColor('#111111')); c.rect(g[0] - 5, g[1] - 6, (si[0] - g[0]) + 10, 12, stroke=0, fill=1)
    for (a, col, k) in ((si, ORANGE, 0), (v, RED, 1), (g, BROWN, 2)):
        b = s[['arancione', 'rosso', 'marrone'][k]]
        wire(a, b, col, (a[0] + 60 - k * 6, a[1] + 40), (b[0] - 70, b[1]), w=2.6)
    etichetta(sx, sy - 40, 'spinotto nella riga ' + riga + ' (marrone su nero)', ORANGE, 'c', 7)


@disegno
def d_servo():
    P = breakout(BX, BY, usati=('42',), alim=True)
    servo_spinotto(P, '42')


@disegno
def d_webled():
    d_servo()


@disegno
def d_pancam():
    P = breakout(BX, BY, usati=('42',), alim=True)
    servo_spinotto(P, '42')
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.circle(*P['CAM'], 16, stroke=1, fill=0)


@disegno
def d_radar():
    P = breakout(BX, BY, usati=('42', '41', '40'), alim=True)
    s = servo(420, 80)
    for (k, col) in ((0, ORANGE), (1, RED), (2, BROWN)):
        a = P[['S', 'V', 'G'][k], '42']
        b = s[['arancione', 'rosso', 'marrone'][k]]
        wire(a, b, col, (a[0] + 50 + k * 6, a[1] - 20), (b[0] - 60, b[1]), w=2.4)
    foro = bb(270, 310, 12)
    h = hcsr04(330, 150)
    filo(h['Vcc'], P['V', '41'], RED, 'd', 'r', 20, 50)
    filo(h['Trig'], P['S', '41'], BLUEW, 'd', 'r', 26, 60)
    wire_res(h['Echo'], foro(7, 'j'), ORANGE, (h['Echo'][0], 230), (foro(7, 'j')[0], 210), B1K)
    res_vert(foro, 7, 'i', '-b', B2K)
    filo(foro(7, 'g'), P['S', '40'], YEL, 'l', 'r', 70, 100)
    filo(h['Gnd'], P['G', '40'], BLK, 'd', 'r', 30, 50)
    filo(P['G', '20'], foro(2, '-b'), BLK, 'r', 'd', 40, 40)
    text(420, 230, 'sensore fissato sopra il servo', 7, 'S', GREY, 'c')


@disegno
def d_dcmotor():
    P = breakout(BX, BY, usati=('21', '47'), alim=True)
    foro = bb(200, 300, 16)
    pin = chip_bb(foro, 5, 'L293D')
    col = lambda n: pin(n)[0]
    filo(P['V', '19'], foro(1, '+b'), RED, 'r', 'd', 30, 40)
    filo(P['G', '20'], foro(2, '-b'), BLK, 'r', 'd', 30, 40)
    for n, r in ((1, '+b'), (8, '+b'), (4, '-b'), (5, '-b')):
        filo(foro(col(n), 'j'), foro(col(n), r), RED if r == '+b' else BLK, 'd', 'd', 4, 4)
    filo(foro(col(16), 'a'), foro(15, 'a'), RED, 'u', 'u', 18, 18)
    filo(foro(15, 'j'), foro(15, '+b'), RED, 'd', 'd', 4, 4)
    filo(P['S', '21'], foro(col(2), 'i'), BLUEW, 'r', 'd', 60, 90)
    filo(P['S', '47'], foro(col(7), 'i'), GREEN, 'r', 'd', 80, 100)
    m1, m2 = motore_dc(450, 150, 'motore + elica')
    filo(foro(col(3), 'h'), m1, HexColor('#6b7280'), 'd', 'l', 120, 60, w=2.4)
    filo(foro(col(6), 'h'), m2, HexColor('#6b7280'), 'd', 'l', 110, 50, w=2.4)


@disegno
def d_stepper():
    P = breakout(BX, BY, usati=('21', '47', '14', '1'), alim=True)
    m = modulo(320, 320, 150, 90, 'ULN2003', ['IN1', 'IN2', 'IN3', 'IN4', '+', '–'], '#15803d', step=16)
    for i in range(4):
        c.setFillColor(HexColor('#ef4444')); c.circle(340 + i * 12, 395, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#c0c4cc')); c.circle(460, 450, 30, stroke=0, fill=1)
    c.setFillColor(HexColor('#6b7280')); c.circle(460, 450, 5, stroke=0, fill=1)
    text(400, 450, '28BYJ-48', 7, 'SB', GREY, 'c')
    filo(P['S', '21'], m['IN1'], BLUEW, 'r', 'd', 50, 150)
    filo(P['S', '47'], m['IN2'], GREEN, 'r', 'd', 70, 150)
    filo(P['S', '14'], m['IN3'], VIOLA, 'l', 'u', 20, 60)
    filo(P['S', '1'], m['IN4'], CYAN, 'r', 'd', 60, 200)
    filo(P['V', '19'], m['+'], RED, 'r', 'd', 90, 140)
    filo(P['G', '20'], m['–'], BLK, 'r', 'd', 110, 150)
    lab_pin(P, '14', VIOLA, 'l')


@disegno
def d_matrix():
    P = breakout(BX, BY, usati=('21', '47', '14'), alim=True)
    c.setFillColor(HexColor('#111827')); c.rect(350, 340, 110, 110, stroke=0, fill=1)
    for i in range(8):
        for j in range(8):
            c.setFillColor(HexColor('#ef4444') if (i + j) % 3 == 0 else HexColor('#4b1d1d'))
            c.circle(358 + j * 13.5, 348 + i * 13.5, 4, stroke=0, fill=1)
    m = modulo(350, 300, 110, 40, 'MAX7219', ['VCC', 'GND', 'DIN', 'CS', 'CLK'], '#1d4ed8', step=16)
    filo(P['V', '19'], m['VCC'], RED, 'r', 'd', 60, 120)
    filo(P['G', '20'], m['GND'], BLK, 'r', 'd', 80, 120)
    filo(P['S', '21'], m['DIN'], BLUEW, 'r', 'd', 100, 150)
    filo(P['S', '47'], m['CS'], GREEN, 'r', 'd', 120, 150)
    filo(P['S', '14'], m['CLK'], VIOLA, 'l', 'u', 20, 60)
    lab_pin(P, '14', VIOLA, 'l')


@disegno
def d_oled():
    P = breakout(BX, BY, usati=('21', '47', '39'))
    c.setFillColor(HexColor('#1e3a8a')); c.roundRect(320, 380, 100, 70, 4, stroke=0, fill=1)
    c.setFillColor(HexColor('#0b0f19')); c.rect(328, 390, 84, 48, stroke=0, fill=1)
    c.setFillColor(HexColor('#7dd3fc'))
    for i in range(3): c.rect(334, 426 - i * 12, 60 - i * 12, 4, stroke=0, fill=1)
    m = modulo(320, 360, 100, 20, 'OLED', ['GND', 'VCC', 'SCL', 'SDA'], '#1e3a8a', step=16)
    filo(P['G', '2'], m['GND'], BLK, 'r', 'd', 50, 160)
    filo(P['3V3'][3], m['VCC'], RED, 'r', 'd', 40, 240)
    filo(P['S', '47'], m['SCL'], GREEN, 'r', 'd', 70, 200)
    filo(P['S', '21'], m['SDA'], BLUEW, 'r', 'd', 90, 210)
    d = dht11(450, 220)
    filo(P['S', '39'], d['S'], CYAN, 'r', 'd', 80, 60)
    filo(P['3V3'][2], d['+'], RED, 'r', 'd', 30, 140)
    filo(P['G', '37'], d['–'], BLK, 'r', 'd', 120, 50)
    text(473, 300, 'facoltativo', 6.5, 'S', GREY, 'c')


@disegno
def d_ring():
    P = breakout(BX, BY, usati=('21',), alim=True)
    cx, cy = 420, 380
    c.setFillColor(HexColor('#111827')); c.circle(cx, cy, 52, stroke=0, fill=1)
    c.setFillColor(white); c.circle(cx, cy, 30, stroke=0, fill=1)
    cols = ['#ef4444', '#f59e0b', '#22c55e', '#06b6d4', '#3b82f6', '#a855f7']
    for i in range(16):
        a = i * math.pi / 8
        c.setFillColor(HexColor(cols[i % 6])); c.circle(cx + 41 * math.cos(a), cy + 41 * math.sin(a), 5, stroke=0, fill=1)
    m = modulo(380, 310, 80, 20, '', ['5V', 'GND', 'DIN'], '#111827', step=18)
    filo(P['V', '21'], m['5V'], RED, 'r', 'd', 60, 100)
    filo(P['G', '19'], m['GND'], BLK, 'r', 'd', 80, 110)
    filo(P['S', '21'], m['DIN'], BLUEW, 'r', 'd', 100, 120)


@disegno
def d_meteo():
    P = breakout(BX, BY, usati=('39', '1'))
    foro = bb(200, 300, 11)
    _ldr(P, foro, 4)
    gnd_bb(P, foro, '20', 2)
    d = dht11(450, 330)
    filo(P['S', '39'], d['S'], GREEN, 'r', 'd', 140, 160)
    filo(P['3V3'][2], d['+'], RED, 'r', 'd', 140, 200)
    filo(P['G', '37'], d['–'], BLK, 'r', 'd', 160, 170)


def pir(x, y):
    c.setFillColor(HexColor('#15803d')); c.rect(x, y, 70, 40, stroke=0, fill=1)
    c.setFillColor(HexColor('#f3f4f6')); c.setStrokeColor(HexColor('#d1d5db')); c.setLineWidth(1)
    c.wedge(x + 8, y + 10, x + 62, y + 64, 0, 180, stroke=1, fill=1)
    pins = {}
    for i, n in enumerate(['VCC', 'OUT', 'GND']):
        px = x + 19 + i * 16
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8); c.line(px, y, px, y - 12)
        text(px, y + 3, n, 5.5, 'SB', white, 'c')
        pins[n] = (px, y - 12)
    text(x + 35, y + 70, 'sensore PIR', 7, 'SB', GREY, 'c')
    return pins


@disegno
def d_pircam():
    P = breakout(BX, BY, usati=('41',), alim=True)
    m = pir(390, 300)
    filo(P['V', '41'], m['VCC'], RED, 'r', 'd', 60, 90)
    filo(P['S', '41'], m['OUT'], GREEN, 'r', 'd', 80, 100)
    filo(P['G', '41'], m['GND'], BLK, 'r', 'd', 100, 110)
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.circle(*P['CAM'], 16, stroke=1, fill=0)


def l298n(x, y):
    c.setFillColor(HexColor('#b91c1c')); c.roundRect(x, y, 140, 110, 5, stroke=0, fill=1)
    c.setFillColor(HexColor('#111827')); c.rect(x + 50, y + 45, 40, 50, stroke=0, fill=1)
    for i in range(6):
        c.setFillColor(HexColor('#374151')); c.rect(x + 52 + i * 6, y + 80, 4, 20, stroke=0, fill=1)
    text(x + 70, y + 34, 'L298N', 8, 'SB', white, 'c')
    pins = {}
    for n, px, py in (('OUT1', x, y + 86), ('OUT2', x, y + 70), ('OUT3', x + 140, y + 86), ('OUT4', x + 140, y + 70)):
        c.setFillColor(HexColor('#2563eb')); c.rect(px - 5, py - 5, 10, 10, stroke=0, fill=1)
        pins[n] = (px + (-5 if px == x else 5), py)
    for i, n in enumerate(['+12V', 'GND', '+5V']):
        px = x + 14 + i * 14
        c.setFillColor(HexColor('#2563eb')); c.rect(px - 5, y + 2, 10, 12, stroke=0, fill=1)
        text(px, y + 18, n, 5, 'SB', white, 'c')
        pins[n] = (px, y + 2)
    for i, n in enumerate(['ENA', 'IN1', 'IN2', 'IN3', 'IN4', 'ENB']):
        px = x + 70 + i * 11
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.6); c.line(px, y, px, y - 10)
        c.saveState(); c.translate(px + 2, y + 4); c.rotate(90); c.setFont('S', 5); c.setFillColor(white)
        c.drawString(0, 0, n); c.restoreState()
        pins[n] = (px, y - 10)
    for px in (pins['ENA'], pins['ENB']):
        c.setFillColor(HexColor('#111111')); c.rect(px[0] - 3, px[1] - 4, 6, 10, stroke=0, fill=1)
    return pins


def _robot(P, motori_y=430):
    m = l298n(330, 150)
    ma = motoriduttore(300, motori_y, 'motore SX')
    mb = motoriduttore(470, motori_y, 'motore DX')
    grey = HexColor('#6b7280')
    filo(m['OUT1'], ma[1], grey, 'l', 'l', 30, 40, w=2.4)
    filo(m['OUT2'], ma[0], grey, 'l', 'l', 50, 50, w=2.4)
    filo(m['OUT3'], (mb[1][0] + 56, mb[1][1]), grey, 'r', 'r', 20, 20, w=2.4)
    filo(m['OUT4'], (mb[0][0] + 56, mb[0][1]), grey, 'r', 'r', 30, 30, w=2.4)
    b = batterie(300, 40)
    filo(b['+'], m['+12V'], RED, 'r', 'd', 20, 60)
    filo(b['-'], m['GND'], BLK, 'r', 'd', 30, 70)
    filo(P['S', '21'], m['IN1'], BLUEW, 'r', 'd', 40, 60)
    filo(P['S', '47'], m['IN2'], GREEN, 'r', 'd', 50, 70)
    filo(P['S', '14'], m['IN3'], VIOLA, 'l', 'd', 20, 150)
    filo(P['S', '1'], m['IN4'], CYAN, 'r', 'd', 60, 90)
    filo(P['G', '20'], m['GND'], BLK, 'r', 'd', 40, 90)
    lab_pin(P, '14', VIOLA, 'l')
    pb = powerbank(170, 300)
    usb = P['USB'] if 'USB' in P else (BX + BW / 2 + 14, BY + 44)
    c.setStrokeColor(HexColor('#9ca3af')); c.setLineWidth(3)
    c.bezier(pb[0] - 40, 300, pb[0] - 40, 250, usb[0], usb[1] + 60, usb[0], usb[1])
    text(210, 345, 'power bank → porta USB della scheda', 6.5, 'S', GREY, 'c')
    return m


@disegno
def d_car():
    P = breakout(BX, BY, usati=('21', '47', '14', '1'))
    _robot(P)


@disegno
def d_fpvcar():
    P = breakout(BX, BY, usati=('21', '47', '14', '1'))
    _robot(P)
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.circle(*P['CAM'], 16, stroke=1, fill=0)


@disegno
def d_autocar():
    P = breakout(BX, BY, usati=('21', '47', '14', '1', '42', '41', '40'))
    m = _robot(P, motori_y=490)
    s = servo(410, 330)
    filo(P['S', '42'], s['arancione'], ORANGE, 'r', 'r', 70, 60, w=2.4)
    filo(m['+5V'], s['rosso'], RED, 'd', 'r', 30, 90, w=2.4)
    filo(P['G', '42'], s['marrone'], BROWN, 'r', 'r', 80, 70, w=2.4)
    c.setFillColor(HexColor('#1f4fa8')); c.roundRect(370, 395, 80, 30, 3, stroke=0, fill=1)
    for cx in (388, 432):
        c.setFillColor(HexColor('#c9ccd1')); c.circle(cx, 410, 11, stroke=0, fill=1)
    text(410, 429, 'HC-SR04 sul servo', 6.5, 'SB', GREY, 'c')
    hp = {'Vcc': (392, 395), 'Trig': (402, 395), 'Echo': (416, 395), 'Gnd': (428, 395)}
    filo(hp['Trig'], P['S', '41'], BLUEW, 'd', 'r', 40, 140, w=2.2)
    wire_res(hp['Echo'], P['S', '40'], YEL, (hp['Echo'][0], 280), (P['S', '40'][0] + 150, P['S', '40'][1]), B1K)
    filo(hp['Vcc'], m['+5V'], RED, 'd', 'd', 60, 40, w=2.2)
    filo(hp['Gnd'], P['G', '41'], BLK, 'd', 'r', 60, 170, w=2.2)
    text(410, 135, 'ECHO: 1 kΩ verso GPIO40, poi 2 kΩ da GPIO40 a GND', 6.5, 'S', GREY, 'c')


def tcrt(x, y, nome):
    c.setFillColor(HexColor('#1d4ed8')); c.roundRect(x, y, 46, 50, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#111827')); c.circle(x + 15, y + 38, 5, stroke=0, fill=1)
    c.setFillColor(HexColor('#60a5fa')); c.circle(x + 31, y + 38, 5, stroke=0, fill=1)
    text(x + 23, y + 56, nome, 6.5, 'SB', GREY, 'c')
    pins = {}
    for i, n in enumerate(['VCC', 'GND', 'DO']):
        px = x + 9 + i * 14
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8); c.line(px, y, px, y - 12)
        text(px, y + 4, n, 5, 'SB', white, 'c')
        pins[n] = (px, y - 12)
    return pins


@disegno
def d_line():
    P = breakout(BX, BY, usati=('21', '47', '14', '1', '41', '42'))
    _robot(P)
    a = tcrt(40, 400, 'sensore SX')
    b = tcrt(110, 400, 'sensore DX')
    filo(P['S', '41'], a['DO'], GREEN, 'r', 'd', 30, 60, w=2.4)
    filo(P['S', '42'], b['DO'], YEL, 'r', 'd', 20, 50, w=2.4)
    filo(P['3V3'][3], a['VCC'], RED, 'r', 'd', 20, 240, w=2.2)
    filo(P['3V3'][2], b['VCC'], RED, 'r', 'd', 15, 230, w=2.2)
    filo(P['G', '35'], a['GND'], BLK, 'r', 'd', 15, 80, w=2.2)
    filo(P['G', '36'], b['GND'], BLK, 'r', 'd', 10, 70, w=2.2)


# ------------------------------------------------------------------ domotica
def bme280(x, y):
    m = modulo(x, y, 64, 52, 'BME280', ['VIN', 'GND', 'SCL', 'SDA'], '#7c3aed', step=13)
    c.setFillColor(HexColor('#d1d5db')); c.rect(x + 26, y + 18, 12, 12, stroke=0, fill=1)
    c.setFillColor(HexColor('#111827')); c.circle(x + 35, y + 21, 1.4, stroke=0, fill=1)
    return m


@disegno
def d_clima():
    P = breakout(BX, BY, usati=('21', '47'))
    m = bme280(380, 340)
    filo(P['3V3'][3], m['VIN'], RED, 'r', 'd', 60, 200)
    filo(P['G', '20'], m['GND'], BLK, 'r', 'd', 70, 160)
    filo(P['S', '47'], m['SCL'], GREEN, 'r', 'd', 90, 190)
    filo(P['S', '21'], m['SDA'], BLUEW, 'r', 'd', 110, 200)
    text(412, 420, 'lontano dalla scheda: scalda', 6.5, 'S', GREY, 'c')


def contatto(x, y, nome):
    """Contatto magnetico MC-38: corpo con due fili + magnete separato."""
    c.setFillColor(HexColor('#f3f4f6')); c.setStrokeColor(HexColor('#9ca3af')); c.setLineWidth(1)
    c.roundRect(x, y, 56, 16, 3, stroke=1, fill=1)
    c.roundRect(x, y + 22, 56, 12, 3, stroke=1, fill=1)
    text(x + 28, y + 25, 'magnete', 5.5, 'S', GREY, 'c')
    text(x + 28, y + 42, nome, 7, 'SB', GREY, 'c')
    return {'1': (x + 18, y), '2': (x + 38, y)}


def _buzzer_volante(P, x, y):
    c.setFillColor(HexColor('#1e1e1e')); c.circle(x, y, 14, stroke=0, fill=1)
    c.setFillColor(HexColor('#3d3d3d')); c.circle(x, y, 4, stroke=0, fill=1)
    text(x - 10, y + 10, '+', 7, 'SB', RED, 'c')
    text(x, y + 20, 'buzzer passivo', 6.5, 'SB', GREY, 'c')
    pp, pm = (x - 5, y - 26), (x + 5, y - 26)
    c.setStrokeColor(HexColor('#9a9a9a')); c.setLineWidth(1.8)
    c.line(x - 5, y - 13, *pp); c.line(x + 5, y - 13, *pm)
    return pp, pm


@disegno
def d_allarme():
    P = breakout(BX, BY, usati=('39', '40', '41', '14'), alim=True)
    a = contatto(320, 440, 'porta')
    b = contatto(420, 440, 'finestra')
    filo(P['S', '39'], a['1'], GREEN, 'r', 'd', 60, 120)
    filo(P['G', '39'], a['2'], BLK, 'r', 'd', 80, 110)
    filo(P['S', '40'], b['1'], BLUEW, 'r', 'd', 120, 140)
    filo(P['G', '40'], b['2'], BLK, 'r', 'd', 140, 130)
    m = pir(410, 300)
    filo(P['V', '41'], m['VCC'], RED, 'r', 'd', 50, 70)
    filo(P['S', '41'], m['OUT'], YEL, 'r', 'd', 70, 80)
    filo(P['G', '41'], m['GND'], BLK, 'r', 'd', 90, 90)
    pp, pm = _buzzer_volante(P, 120, 340)
    filo(P['S', '14'], pp, VIOLA, 'r', 'd', 40, 60)
    filo(P['G', '14'], pm, BLK, 'r', 'd', 30, 70)
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.circle(*P['CAM'], 16, stroke=1, fill=0)


def alimentatore5v(x, y):
    c.setFillColor(HexColor('#1f2937')); c.roundRect(x, y, 70, 34, 5, stroke=0, fill=1)
    text(x + 35, y + 20, '5 V  3 A', 8, 'SB', white, 'c')
    text(x + 35, y + 8, 'alimentatore', 5.5, 'S', HexColor('#cbd5e1'), 'c')
    c.setFillColor(HexColor('#2563eb')); c.rect(x + 74, y + 4, 22, 26, stroke=0, fill=1)
    text(x + 85, y + 22, '+', 7, 'SB', white, 'c'); text(x + 85, y + 8, '−', 7, 'SB', white, 'c')
    return {'+': (x + 96, y + 22), '-': (x + 96, y + 10)}


@disegno
def d_luci():
    P = breakout(BX, BY, usati=('21',))
    # striscia LED
    sx, sy = 300, 420
    c.setFillColor(HexColor('#f8fafc')); c.setStrokeColor(HexColor('#cbd5e1')); c.setLineWidth(1)
    c.rect(sx, sy, 205, 22, stroke=1, fill=1)
    cols = ['#f59e0b', '#fbbf24', '#f97316', '#fb923c']
    for i in range(8):
        c.setFillColor(HexColor('#fde68a')); c.rect(sx + 34 + i * 21, sy + 5, 12, 12, stroke=0, fill=1)
        c.setFillColor(HexColor(cols[i % 4])); c.circle(sx + 40 + i * 21, sy + 11, 3.5, stroke=0, fill=1)
    for i, n in enumerate(['5V', 'DIN', 'GND']):
        c.setFillColor(HexColor('#d4a100')); c.rect(sx + 4, sy + 16 - i * 7, 8, 5, stroke=0, fill=1)
        text(sx + 22, sy + 16 - i * 7, n, 4.8, 'SB', GREY, 'c')
    text(sx + 140, sy + 30, 'striscia WS2812B  →', 7, 'SB', GREY, 'c')
    pin = {'5V': (sx + 4, sy + 18.5), 'DIN': (sx + 4, sy + 11.5), 'GND': (sx + 4, sy + 4.5)}
    al = alimentatore5v(330, 300)
    filo(al['+'], pin['5V'], RED, 'r', 'l', 40, 60)
    filo(al['-'], pin['GND'], BLK, 'r', 'l', 30, 50)
    wire_res(P['S', '21'], pin['DIN'], GREEN, (P['S', '21'][0] + 80, P['S', '21'][1]), (pin['DIN'][0] - 60, pin['DIN'][1]), B220)
    filo(P['G', '20'], al['-'], BLK, 'r', 'd', 50, 90)
    # condensatore tra 5V e GND
    cx, cy = sx - 18, sy + 50
    c.setFillColor(HexColor('#1e3a8a')); c.roundRect(cx - 8, cy, 16, 24, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#cbd5e1')); c.rect(cx + 3, cy, 4, 24, stroke=0, fill=1)
    text(cx, cy + 30, '1000 µF', 6, 'SB', GREY, 'c')
    filo((cx - 4, cy), pin['5V'], RED, 'd', 'l', 10, 20, w=1.8)
    filo((cx + 4, cy), pin['GND'], BLK, 'd', 'l', 14, 14, w=1.8)
    text(420, 280, 'GND alimentatore = GND breakout', 6.5, 'S', GREY, 'c')


def trasmettitore_ir(x, y):
    m = modulo(x, y, 54, 40, 'IR TX', ['S', '+', '−'], '#111827', step=14)
    c.setFillColor(HexColor('#a5b4fc')); c.circle(x + 27, y + 46, 7, stroke=0, fill=1)
    c.rect(x + 20, y + 38, 14, 8, stroke=0, fill=1)
    return m


@disegno
def d_ircomando():
    P = breakout(BX, BY, usati=('38', '42'))
    m = modulo(320, 360, 70, 50, 'IR RX', ['G', 'R', 'Y'], '#111827', step=16)
    c.setFillColor(HexColor('#374151')); c.circle(355, 390, 9, stroke=0, fill=1)
    filo(P['G', '36'], m['G'], BLK, 'r', 'd', 60, 70)
    filo(P['3V3'][3], m['R'], RED, 'r', 'd', 50, 200)
    filo(P['S', '38'], m['Y'], GREEN, 'r', 'd', 80, 90)
    t = trasmettitore_ir(430, 360)
    filo(P['S', '42'], t['S'], VIOLA, 'r', 'd', 120, 130)
    filo(P['G', '42'], t['−'], BLK, 'r', 'd', 150, 140)
    text(355, 440, 'ricevitore (impara)', 6.5, 'SB', GREY, 'c')
    text(457, 440, 'trasmettitore (invia)', 6.5, 'SB', GREY, 'c')


def sensore_acqua(x, y):
    c.setFillColor(HexColor('#b91c1c')); c.roundRect(x, y, 36, 90, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#e5c07b'))
    for i in range(7):
        c.rect(x + 6 + i * 4, y + 30, 1.8, 54, stroke=0, fill=1)
    pins = {}
    for i, n in enumerate(['S', '+', '–']):
        px = x + 6 + i * 12
        c.setStrokeColor(HexColor('#a0a0a0')); c.setLineWidth(1.8); c.line(px, y, px, y - 12)
        text(px, y + 4, n, 6, 'SB', white, 'c')
        pins[n] = (px, y - 12)
    text(x + 18, y + 96, 'sensore acqua', 6.5, 'SB', GREY, 'c')
    return pins


def mq2(x, y):
    m = modulo(x, y, 70, 56, 'MQ-2', ['VCC', 'GND', 'DO', 'AO'], '#1d4ed8', step=13)
    c.setFillColor(HexColor('#9ca3af')); c.circle(x + 35, y + 72, 16, stroke=0, fill=1)
    c.setFillColor(HexColor('#6b7280'))
    for i in range(-2, 3):
        for j in range(-2, 3):
            if i * i + j * j < 6:
                c.circle(x + 35 + i * 5, y + 72 + j * 5, 1.2, stroke=0, fill=1)
    return m


@disegno
def d_fughe():
    P = breakout(BX, BY, usati=('1', '42', '3', '14'), alim=True)
    w = sensore_acqua(440, 380)
    filo(P['S', '1'], w['S'], CYAN, 'r', 'd', 80, 160)
    filo(P['S', '42'], w['+'], RED, 'r', 'd', 100, 150)
    filo(P['G', '42'], w['–'], BLK, 'r', 'd', 120, 140)
    m = mq2(30, 360)
    filo(m['VCC'], P['V', '3'], RED, 'd', 'l', 60, 40)
    filo(m['GND'], P['G', '3'], BLK, 'd', 'l', 50, 30)
    wire_res(m['AO'], P['S', '3'], YEL, (m['AO'][0], 300), (P['S', '3'][0] - 60, P['S', '3'][1]), B1K)
    t3, g = P['T', '3'], P['GNDb'][0]
    wire_res(t3, g, BLK, (t3[0] - 8, t3[1] - 50), (g[0] - 8, g[1] + 60), B2K)
    text(150, 500, 'AO → 1 kΩ → GPIO3 · dal morsetto di GPIO3: 2 kΩ → GND', 6.5, 'S', GREY, 'c')
    pp, pm = _buzzer_volante(P, 200, 340)
    filo(P['S', '14'], pp, VIOLA, 'r', 'd', 40, 60)
    filo(P['G', '14'], pm, BLK, 'r', 'd', 30, 70)

def display_tm1637(x, y):
    m = modulo(x, y, 150, 58, '', ['VCC', 'CLK', 'DIO', 'GND'], '#111827', step=16)
    c.setFillColor(HexColor('#1f2937')); c.rect(x + 8, y + 14, 134, 40, stroke=0, fill=1)
    c.setFont('SB', 30); c.setFillColor(HexColor('#ef4444')); c.drawCentredString(x + 75, y + 22, '12:34')
    return m


def pulsante_volante(x, y):
    c.setFillColor(HexColor('#2b2b2b')); c.roundRect(x - 11, y - 11, 22, 22, 3, stroke=0, fill=1)
    c.setFillColor(HexColor('#555555')); c.circle(x, y, 7, stroke=0, fill=1)
    text(x, y + 16, 'ci sono', 6.5, 'SB', GREY, 'c')
    c.setStrokeColor(HexColor('#9a9a9a')); c.setLineWidth(1.8)
    c.line(x - 6, y - 11, x - 6, y - 22); c.line(x + 6, y - 11, x + 6, y - 22)
    return (x - 6, y - 22), (x + 6, y - 22)


@disegno
def d_cucina():
    P = breakout(BX, BY, usati=('42', '41', '40', '1', '21', '47', '3', '14'), alim=True)
    # display e traslatore di livello
    d = display_tm1637(150, 452)
    t = modulo(205, 352, 120, 46, 'traslatore', ['HV', 'H1', 'H2', 'GND', 'LV', 'L1', 'L2'], '#334155', step=15)
    filo(P['3V3'][2], t['LV'], RED, 'r', 'd', 40, 140)
    filo(P['S', '42'], t['L1'], VIOLA, 'r', 'd', 40, 90)
    filo(P['S', '41'], t['L2'], YEL, 'r', 'd', 50, 85)
    filo(P['G', '42'], t['GND'], BLK, 'r', 'd', 60, 80)
    filo(P['V', '41'], t['HV'], RED, 'r', 'd', 70, 100)
    filo(t['H1'], d['CLK'], VIOLA, 'd', 'd', 20, 20, w=1.8)
    filo(t['H2'], d['DIO'], YEL, 'd', 'd', 26, 26, w=1.8)
    filo(t['HV'], d['VCC'], RED, 'd', 'd', 32, 32, w=1.8)
    filo(t['GND'], d['GND'], BLK, 'd', 'd', 38, 38, w=1.8)
    # sensori I2C in parallelo
    b = modulo(345, 440, 58, 46, 'BME280', ['VIN', 'GND', 'SCL', 'SDA'], '#7c3aed', step=12)
    m = modulo(420, 440, 70, 46, 'MLX90614', ['VIN', 'GND', 'SCL', 'SDA'], '#0f766e', step=12)
    filo(P['3V3'][3], b['VIN'], RED, 'r', 'd', 90, 120)
    filo(P['G', '20'], b['GND'], BLK, 'r', 'd', 110, 110)
    filo(P['S', '47'], b['SCL'], GREEN, 'r', 'd', 120, 130)
    filo(P['S', '21'], b['SDA'], BLUEW, 'r', 'd', 135, 125)
    for k, col in (('VIN', RED), ('GND', BLK), ('SCL', GREEN), ('SDA', BLUEW)):
        filo(b[k], m[k], col, 'd', 'd', 14, 14, w=1.8)
    # PIR e pulsante
    pi = pir(430, 330)
    filo(P['V', '40'], pi['VCC'], RED, 'r', 'd', 120, 60)
    filo(P['S', '40'], pi['OUT'], CYAN, 'r', 'd', 135, 55)
    filo(P['G', '40'], pi['GND'], BLK, 'r', 'd', 150, 50)
    p1, p2 = pulsante_volante(360, 320)
    filo(P['S', '1'], p1, GREEN, 'r', 'd', 60, 40)
    filo(P['G', '1'], p2, BLK, 'r', 'd', 70, 40)
    # MQ-2 con partitore e buzzer a sinistra
    q = mq2(15, 330)
    filo(q['VCC'], P['V', '3'], RED, 'd', 'l', 50, 40)
    filo(q['GND'], P['G', '3'], BLK, 'd', 'l', 40, 30)
    wire_res(q['AO'], P['S', '3'], ORANGE, (q['AO'][0], 290), (P['S', '3'][0] - 50, P['S', '3'][1]), B1K)
    t3, g = P['T', '3'], P['GNDb'][0]
    wire_res(t3, g, BLK, (t3[0] - 8, t3[1] - 50), (g[0] - 8, g[1] + 60), B2K)
    pp, pm = _buzzer_volante(P, 120, 300)
    filo(P['S', '14'], pp, VIOLA, 'r', 'd', 40, 60)
    filo(P['G', '14'], pm, BLK, 'r', 'd', 30, 70)
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.circle(*P['CAM'], 16, stroke=1, fill=0)


def disegna(pid, top, bottom, x0=40, width=515):
    """Disegna il progetto nel riquadro; True se esiste un disegno dedicato."""
    fn = D.get(pid)
    if not fn:
        return False
    s = min(1.0, (top - bottom) / FH, width / FW)
    c.saveState()
    c.translate(x0 + (width - FW * s) / 2, bottom + (top - bottom - FH * s) / 2)
    c.scale(s, s)
    fn()
    c.restoreState()
    return True
