# Telecomando universale: impara i tasti dei tuoi telecomandi (condizionatore, TV...) e li ripete
# Ricevitore IR del kit: G/- -> GND, R/+ -> 3V3, Y/S -> GPIO38
# Trasmettitore IR (LED 940 nm o modulo): S/segnale -> GPIO42, - -> GND (+ del modulo a 5V se ce l'ha)
#
# 6 tasti memorizzati nella scheda. Dalla pagina della scheda puoi dare un nome a ogni tasto.
# Con l'ora da Internet il tasto 1 puo' partire a un orario (es. accendi il clima) e il tasto 2 a un altro.
from machine import Pin
from array import array
from esp32 import RMT
import asyncio, time, json

FILE = 'ircodici.json'
MAXF = 700                       # fronti registrabili (i condizionatori mandano messaggi lunghi)
NOMI = ['Clima acceso', 'Clima spento', 'TV accesa/spenta', 'Volume +', 'Volume −', 'Extra']
TASTI = [None] * 6               # durate in microsecondi: impulso, pausa, impulso, ...
CFG = {'nomi': NOMI[:], 'accendi': '', 'spegni': ''}
S = {'ntp': False, 'fatto': {}, 'msg': 'Pronto', 'orari': ''}
comandi = []

rx = Pin(38, Pin.IN)
fronti = array('I', [0] * MAXF)
n = [0]
try:
    tx = RMT(pin=Pin(42), resolution_hz=1000000, idle_level=False, tx_carrier=(38000, 33, 1))
except TypeError:                # firmware MicroPython piu' vecchio
    tx = RMT(0, pin=Pin(42), clock_div=80, idle_level=False, tx_carrier=(38000, 33, 1))
PMAX = min(getattr(RMT, 'PULSE_MAX', 32767), 32767)


def fronte(p):                   # interrupt: salva solo l'istante di ogni cambio
    i = n[0]
    if i < MAXF:
        fronti[i] = time.ticks_us()
        n[0] = i + 1


# ---------------------------------------------------------------- memoria
def carica():
    try:
        with open(FILE) as f:
            d = json.load(f)
        for i, x in enumerate(d.get('tasti', [])[:6]):
            TASTI[i] = x
        CFG.update(d.get('cfg', {}))
    except Exception:
        pass


def salva():
    with open(FILE, 'w') as f:
        json.dump({'tasti': TASTI, 'cfg': CFG}, f)


def elenco():
    return ' · '.join('%d %s%s' % (i + 1, CFG['nomi'][i], '' if TASTI[i] else ' (vuoto)') for i in range(6))


def dire(lab, msg):
    S['msg'] = msg               # lo mostra anche la pagina web
    dire(lab, msg)


# ---------------------------------------------------------------- imparare e trasmettere
async def impara(lab, i):
    dire(lab, 'Punta il telecomando verso il ricevitore e premi il tasto «%s»' % CFG['nomi'][i])
    lab.log('In ascolto per 10 secondi…')
    n[0] = 0
    rx.irq(fronte, Pin.IRQ_FALLING | Pin.IRQ_RISING, hard=True)
    fine = time.ticks_add(time.ticks_ms(), 10000)
    try:
        while time.ticks_diff(fine, time.ticks_ms()) > 0:
            k = n[0]
            # il messaggio e' finito quando non arriva nulla per 150 ms
            if k and time.ticks_diff(time.ticks_us(), fronti[k - 1]) > 150000:
                break
            await asyncio.sleep_ms(20)
    finally:
        rx.irq(handler=None)
    k = n[0]
    if k < 16:
        dire(lab, 'Nessun segnale ricevuto: riprova più vicino')
        return
    d = [time.ticks_diff(fronti[j + 1], fronti[j]) for j in range(k - 1)]
    if len(d) % 2 == 0:          # deve finire con un impulso
        d.pop()
    TASTI[i] = d
    salva()
    dire(lab, 'Tasto «%s» imparato (%d impulsi)%s' % (CFG['nomi'][i], len(d), ' – messaggio molto lungo, forse troncato' if k >= MAXF else ''))
    lab.send('tasti', elenco())


def trasmetti(lab, i):
    d = TASTI[i]
    if not d:
        dire(lab, 'Il tasto %d è vuoto: prima fallo imparare' % (i + 1))
        return False
    durate, livelli = [], []
    for j, x in enumerate(d):
        lv = 1 if j % 2 == 0 else 0
        x = max(1, x)
        while x > PMAX:          # pause lunghe: le spezzo in piu' parti
            durate.append(PMAX)
            livelli.append(lv)
            x -= PMAX
        durate.append(x)
        livelli.append(lv)
    tx.write_pulses(durate, livelli)
    tx.wait_done(timeout=2000)
    dire(lab, 'Inviato «%s»' % CFG['nomi'][i])
    return True


# ---------------------------------------------------------------- comandi
def on_impara(v):
    comandi.append(('impara', int(v)))


def on_invia(v):
    comandi.append(('invia', int(v)))


def on_orario(k):
    def fn(v):
        try:
            h, m = v.split(':')
            CFG[k] = '%02d:%02d' % (int(h), int(m))
        except Exception:
            CFG[k] = ''
        salva()
    return fn


def ora_italia():
    t = time.time()
    y = time.localtime(t)[0]

    def ultima_domenica(mese):
        for g in range(31, 24, -1):
            s = time.mktime((y, mese, g, 1, 0, 0, 0, 0))
            if time.localtime(s)[6] == 6:
                return s
    legale = ultima_domenica(3) <= t < ultima_domenica(10)
    return time.localtime(t + (7200 if legale else 3600))


async def orologio(lab):
    import ntptime
    while True:
        try:
            ntptime.settime()
            S['ntp'] = True
            await asyncio.sleep(6 * 3600)
        except Exception:
            await asyncio.sleep(30)


PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Telecomando</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px}
.c{background:#fff;border-radius:14px;padding:14px;max-width:520px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
.r{display:flex;gap:6px;align-items:center;margin:8px 0}.r input{flex:1;padding:8px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}
button{padding:9px 12px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-size:15px}button.g{background:#e5e7eb;color:#1f2937}
#s{color:#374151;min-height:1.4em}small{color:#6b7280}</style>
<div class=c><b>Telecomando universale</b><div id=s></div></div><div class=c id=l></div>
<div class=c><small>«Impara»: entro 10 secondi premi il tasto del telecomando vero puntato verso il ricevitore.
Scrivi un nome e tocca ✓ per rinominare.</small></div>
<script>async function g(u){const d=await(await fetch(u)).json();s.textContent=d.stato||'';return d}
async function u(){const d=await g('/elenco');l.innerHTML=d.tasti.map((t,i)=>'<div class=r><input id=n'+i+' value="'+t.nome.replace(/"/g,'')+'">'+
'<button class=g onclick="r('+i+')">✓</button><button class=g onclick="g(\\'/impara?i='+i+'\\')">Impara</button>'+
'<button '+(t.ok?'':'disabled style=opacity:.4 ')+'onclick="g(\\'/invia?i='+i+'\\')">Invia</button></div>').join('')}
function r(i){g('/nome?i='+i+'&n='+encodeURIComponent(document.getElementById('n'+i).value)).then(u)}
u();setInterval(async()=>{const d=await(await fetch('/elenco')).json();s.textContent=d.stato||''},2000)</script></html>"""


async def main(lab):
    carica()
    lab.on('impara', on_impara)
    lab.on('invia', on_invia)
    lab.on('accendi', on_orario('accendi'))
    lab.on('spegni', on_orario('spegni'))
    try:
        if await lab.wifi():
            asyncio.create_task(orologio(lab))

            async def pagina(path, q, w):
                i = int(q.get('i', '0') or 0) % 6
                if path == '/impara':
                    comandi.append(('impara', i))
                elif path == '/invia':
                    comandi.append(('invia', i))
                elif path == '/nome' and q.get('n'):
                    CFG['nomi'][i] = q['n'][:24]
                    salva()
                    lab.send('tasti', elenco())
                if path == '/':
                    await lab.reply(w, PAGINA)
                else:
                    d = {'stato': S['msg'], 'tasti': [{'nome': CFG['nomi'][j], 'ok': bool(TASTI[j])} for j in range(6)]}
                    await lab.reply(w, json.dumps(d), 'application/json')
            await lab.serve(pagina)
        lab.send('tasti', elenco())
        dire(lab, 'Pronto')
        while True:
            while comandi:
                cosa, i = comandi.pop(0)
                if cosa == 'impara':
                    await impara(lab, i % 6)
                else:
                    trasmetti(lab, i % 6)
            if S['ntp']:
                o = ora_italia()
                adesso = '%02d:%02d' % (o[3], o[4])
                for k, tasto in (('accendi', 0), ('spegni', 1)):
                    if CFG[k] == adesso and S['fatto'].get(k) != o[7]:
                        S['fatto'][k] = o[7]
                        lab.log('Orario %s: invio «%s»' % (adesso, CFG['nomi'][tasto]))
                        trasmetti(lab, tasto)
            orari = 'Tasto 1 alle %s · tasto 2 alle %s' % (CFG['accendi'] or '—', CFG['spegni'] or '—')
            orari += '' if S['ntp'] or not (CFG['accendi'] or CFG['spegni']) else ' (manca l’ora da Internet)'
            if orari != S['orari']:
                S['orari'] = orari
                lab.send('orari', orari)
            await asyncio.sleep_ms(200)
    finally:
        rx.irq(handler=None)
        tx.deinit()
