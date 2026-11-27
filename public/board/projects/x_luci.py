# Luci di casa con striscia LED WS2812B: scene, accensione al tramonto, spegnimento e sveglia con l'alba
# Striscia: DIN -> resistenza 220 ohm -> GPIO21 · 5V e GND -> alimentatore 5 V separato
# GND dell'alimentatore collegato anche al GND della breakout (massa in comune!)
# Condensatore 1000 uF tra 5V e GND all'inizio della striscia.
#
# Le impostazioni e l'ultima scena restano salvate: dopo un'interruzione di corrente
# le luci tornano come prima. Gli orari usano l'ora da Internet.
from machine import Pin
import neopixel, asyncio, time, json, math, random

FILE = 'luci.json'
LAT, LON = 43.84, 10.50          # Lucca: serve per calcolare l'ora del tramonto
CFG = {'n': 60, 'ampere': 3, 'scena': 'spento', 'colore': [255, 150, 60], 'luce': 60, 'effetto': 'fisso',
       'tramonto': False, 'scena_tramonto': 'relax', 'spegni': '', 'alba': ''}
SCENE = {   # colore, luminosita' %, effetto
    'lettura': ((255, 190, 120), 100, 'fisso'),
    'relax': ((255, 110, 25), 40, 'fisso'),
    'cinema': ((40, 60, 255), 8, 'fisso'),
    'notte': ((255, 25, 0), 3, 'fisso'),
    'festa': ((255, 255, 255), 60, 'arcobaleno'),
    'candela': ((255, 100, 15), 45, 'candela'),
}
S = {'liv': 0.0, 'ntp': False, 'alba': None, 'fatto': {}}
modificato = [0]
np = None


# ---------------------------------------------------------------- ora e tramonto
def offset_italia(t):
    y = time.localtime(t)[0]

    def ultima_domenica(mese):
        for g in range(31, 24, -1):
            s = time.mktime((y, mese, g, 1, 0, 0, 0, 0))
            if time.localtime(s)[6] == 6:
                return s
    return 7200 if ultima_domenica(3) <= t < ultima_domenica(10) else 3600


def ora_italia():
    t = time.time()
    return time.localtime(t + offset_italia(t))


def sole(o):
    """Minuti dalla mezzanotte (ora italiana) di alba e tramonto del giorno o (formule NOAA)."""
    g = 2 * math.pi / 365 * (o[7] - 1)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
           + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(LAT)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(dec))
                                - math.tan(la) * math.tan(dec)))
    off = offset_italia(time.time()) // 60
    return 720 - 4 * (LON + ha) - eqt + off, 720 - 4 * (LON - ha) - eqt + off


def minuti(hhmm):
    try:
        h, m = hhmm.split(':')
        return int(h) * 60 + int(m)
    except Exception:
        return None


def hhmm(m):
    m = int(m) % 1440
    return '%02d:%02d' % (m // 60, m % 60)


# ---------------------------------------------------------------- impostazioni
def carica():
    try:
        with open(FILE) as f:
            CFG.update(json.load(f))
    except Exception:
        pass


def salva_dopo():
    modificato[0] = time.ticks_ms() or 1


def striscia(n):
    global np
    if np:
        np.fill((0, 0, 0))
        np.write()
    np = neopixel.NeoPixel(Pin(21), n)


def applica_scena(nome):
    CFG['scena'] = nome
    if nome in SCENE:
        col, luce, eff = SCENE[nome]
        CFG['colore'], CFG['luce'], CFG['effetto'] = list(col), luce, eff
    salva_dopo()


def on_scena(v):
    S['alba'] = None
    applica_scena(v)


def on_colore(v):
    h = v.lstrip('#')
    CFG['colore'] = [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]
    CFG['effetto'] = 'fisso'
    CFG['scena'] = 'personale'
    salva_dopo()


def on_luce(v):
    CFG['luce'] = int(v)
    if CFG['scena'] == 'spento':
        CFG['scena'] = 'personale'
    salva_dopo()


def on_effetto(v):
    CFG['effetto'] = v
    if CFG['scena'] == 'spento':
        CFG['scena'] = 'personale'
    salva_dopo()


def on_n(v):
    CFG['n'] = max(1, min(300, int(v)))
    striscia(CFG['n'])
    salva_dopo()


def on_ampere(v):
    CFG['ampere'] = int(v)
    salva_dopo()


def on_tramonto(v):
    CFG['tramonto'] = bool(v)
    salva_dopo()


def on_orario(k):
    def fn(v):
        CFG[k] = v if minuti(v or '') is not None else ''
        salva_dopo()
    return fn


# ---------------------------------------------------------------- colori
def ruota(p):
    p %= 256
    if p < 85:
        return (255 - p * 3, p * 3, 0)
    if p < 170:
        p -= 85
        return (0, 255 - p * 3, p * 3)
    p -= 170
    return (p * 3, 0, 255 - p * 3)


def limite(col, k):
    """Riduce la luminosita' perche' la striscia non chieda piu' corrente dell'alimentatore."""
    ma = CFG['n'] * sum(col) / 765 * 60 * k          # circa 60 mA per LED bianco al massimo
    lim = CFG['ampere'] * 1000 * 0.85
    return k * lim / ma if ma > lim else k


def colore_alba(f):
    """f da 0 a 1: rosso scuro -> arancio -> bianco caldo."""
    if f < 0.5:
        x = f * 2
        return (255, int(20 + 100 * x), int(5 * x)), 0.02 + 0.3 * x
    x = (f - 0.5) * 2
    return (255, int(120 + 80 * x), int(5 + 135 * x)), 0.32 + 0.68 * x


# ---------------------------------------------------------------- programmi a orario
def programmi(lab, o):
    m = o[3] * 60 + o[4]
    oggi = o[7]
    alba, tram = sole(o)
    lab.send('sole', 'Alba %s · tramonto %s' % (hhmm(alba), hhmm(tram)))

    def una_volta(nome, quando):
        if quando is not None and m == quando and S['fatto'].get(nome) != oggi:
            S['fatto'][nome] = oggi
            return True
        return False

    if CFG['tramonto'] and una_volta('tramonto', int(tram)) and CFG['scena'] == 'spento':
        applica_scena(CFG['scena_tramonto'])
        lab.log('Tramonto: luci accese')
    if una_volta('spegni', minuti(CFG['spegni'])):
        S['alba'] = None
        applica_scena('spento')
        lab.log('Orario di spegnimento: luci spente')
    a = minuti(CFG['alba'])
    if a is not None and una_volta('alba', (a - 20) % 1440):
        S['alba'] = time.ticks_ms()
        CFG['scena'] = 'alba'
        lab.log('Sveglia: l’alba dura 20 minuti')
    prog = []
    if CFG['tramonto']:
        prog.append('accende al tramonto')
    if CFG['spegni']:
        prog.append('spegne alle ' + CFG['spegni'])
    if CFG['alba']:
        prog.append('alba per le ' + CFG['alba'])
    lab.send('programmi', ', '.join(prog) or 'Nessun programma')


async def orologio(lab):
    import ntptime
    while True:
        try:
            ntptime.settime()
            if not S['ntp']:
                S['ntp'] = True
                lab.log('Ora sincronizzata da Internet')
            await asyncio.sleep(6 * 3600)
        except Exception:
            await asyncio.sleep(30)


async def main(lab):
    carica()
    striscia(CFG['n'])
    lab.on('scena', on_scena)
    lab.on('colore', on_colore)
    lab.on('luce', on_luce)
    lab.on('effetto', on_effetto)
    lab.on('nled', on_n)
    lab.on('ampere', on_ampere)
    lab.on('tramonto', on_tramonto)
    lab.on('spegni', on_orario('spegni'))
    lab.on('alba', on_orario('alba'))
    if await lab.wifi():
        asyncio.create_task(orologio(lab))
    else:
        lab.log('Senza Wi-Fi le scene funzionano, gli orari no')
    t = 0
    ultimo = None
    prog = time.ticks_ms()
    try:
        while True:
            t += 1
            # programmi: controllo ogni 5 secondi
            if S['ntp'] and time.ticks_diff(time.ticks_ms(), prog) >= 0:
                prog = time.ticks_add(time.ticks_ms(), 5000)
                programmi(lab, ora_italia())
            # luminosita' obiettivo con dissolvenza
            if CFG['scena'] == 'alba' and S['alba'] is not None:
                f = min(1, time.ticks_diff(time.ticks_ms(), S['alba']) / 1200000)
                col, obiettivo = colore_alba(f)
                if time.ticks_diff(time.ticks_ms(), S['alba']) > 3600000:     # dopo un'ora si spegne
                    S['alba'] = None
                    applica_scena('spento')
            else:
                col = tuple(CFG['colore'])
                obiettivo = 0 if CFG['scena'] == 'spento' else (CFG['luce'] / 100) ** 2
            S['liv'] += (obiettivo - S['liv']) * 0.08
            if abs(obiettivo - S['liv']) < 0.002:
                S['liv'] = obiettivo
            k = limite(col, S['liv'])
            eff = CFG['effetto'] if CFG['scena'] not in ('spento', 'alba') else 'fisso'
            n = CFG['n']
            if eff == 'arcobaleno':
                for i in range(n):
                    np[i] = tuple(int(x * k) for x in ruota(i * 256 // n + t * 2))
            elif eff == 'candela':
                for i in range(n):
                    q = k * (0.6 + random.random() * 0.4)
                    np[i] = tuple(int(x * q) for x in col)
            else:
                p = tuple(int(x * k) for x in col)
                if p != ultimo:          # colore fisso: scrivo solo quando cambia
                    ultimo = p
                    np.fill(p)
                    np.write()
            if eff != 'fisso':
                ultimo = None
                np.write()
            if t % 25 == 0:
                lab.send('stato', '%s · %d%%' % (CFG['scena'].capitalize(), round(S['liv'] ** 0.5 * 100)))
                lab.send('consumo', round(n * sum(col) / 765 * 60 * k))
            if modificato[0] and time.ticks_diff(time.ticks_ms(), modificato[0]) > 5000:
                modificato[0] = 0
                with open(FILE, 'w') as f:
                    json.dump(CFG, f)
            await asyncio.sleep_ms(40)
    finally:
        np.fill((0, 0, 0))
        np.write()
