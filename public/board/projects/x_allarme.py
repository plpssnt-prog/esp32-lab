# Antifurto per porte e finestre: contatti magnetici, sensore PIR, sirena, foto e notifiche
# Contatto magnetico porta:    un filo -> GPIO39, l'altro -> GND (chiuso = porta chiusa)
# Contatto magnetico finestra: un filo -> GPIO40, l'altro -> GND
# PIR HC-SR501 (facoltativo): VCC -> 5V, GND -> GND, OUT -> GPIO41
# Buzzer passivo (sirena):    + -> GPIO14, - -> GND
# Sirena vera 12 V (facoltativa): modulo MOSFET SIG -> GPIO42
#
# Modi: Inserito (tutti i sensori) · Notte (porta e finestre, PIR escluso) · Disinserito.
# La porta ha un ritardo d'ingresso per darti il tempo di disinserire dal telefono.
# Dopo un'interruzione di corrente l'antifurto riparte nello stesso modo.
from machine import Pin, PWM
import neopixel, asyncio, time, json

try:
    from camera import Camera, PixelFormat, FrameSize
except ImportError:
    Camera = None

FILE = 'allarme.json'
CFG = {'modo': 'spento', 'porta': True, 'finestra': True, 'pir': False, 'campanello': True,
       'uscita': 30, 'ingresso': 20, 'sirena': 120}

porta = Pin(39, Pin.IN, Pin.PULL_UP)
finestra = Pin(40, Pin.IN, Pin.PULL_UP)
pir = Pin(41, Pin.IN, Pin.PULL_DOWN)
sirena12 = Pin(42, Pin.OUT, value=0)
bz = PWM(Pin(14), freq=2000, duty_u16=0)
np = neopixel.NeoPixel(Pin(48), 1)

S = {'stato': 'spento', 'fine': 0, 'causa': '', 'ntp': False, 'n': 0}
EVENTI = []      # ultimi 20 eventi: 'ora - testo'
FOTO = []        # ultime 6 foto: (jpeg, etichetta)
cam = enc = None
richiesta = []   # comandi dal telefono da eseguire nel ciclo principale
NOMI = {'spento': 'Disinserito', 'uscita': 'Uscita in corso', 'inserito': 'Inserito',
        'notte': 'Inserito (notte)', 'ingresso': 'Ingresso: disinserisci!', 'allarme': 'ALLARME'}


# ---------------------------------------------------------------- utilita'
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


def adesso():
    if not S['ntp']:
        return ''
    o = ora_italia()
    return '%02d/%02d %02d:%02d:%02d' % (o[2], o[1], o[3], o[4], o[5])


def evento(lab, testo):
    EVENTI.append((adesso() + ' – ' if S['ntp'] else '') + testo)
    if len(EVENTI) > 20:
        EVENTI.pop(0)
    lab.log(testo)
    lab.send('evento', testo)


def carica():
    try:
        with open(FILE) as f:
            CFG.update(json.load(f))
    except Exception:
        pass


def salva():
    try:
        with open(FILE, 'w') as f:
            json.dump(CFG, f)
    except Exception:
        pass


def suono(f=0, duty=0):
    if f:
        bz.freq(f)
    bz.duty_u16(duty)


def led(r, g, b):
    np[0] = (r, g, b)
    np.write()


# ---------------------------------------------------------------- fotocamera
def apri_camera(lab):
    """JPEG del sensore se possibile, altrimenti JPEG via software (es. sensore GC0308)."""
    global cam, enc
    if Camera is None:
        lab.log('Firmware senza fotocamera: niente foto')
        return
    try:
        cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA, jpeg_quality=85, fb_count=2)
        return
    except Exception:
        cam = None
    try:
        import jpeg
    except ImportError:
        lab.log('Fotocamera senza JPEG: niente foto')
        return
    for pf, fmt in (('YUV422', 'YCbYCr'), ('RGB565', 'RGB565_BE'), ('GRAYSCALE', 'GRAY')):
        try:
            cam = Camera(pixel_format=getattr(PixelFormat, pf), frame_size=FrameSize.VGA, fb_count=1)
            enc = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                               pixel_format=fmt, quality=80)
            lab.log('Fotocamera:', cam.get_sensor_name(), '- JPEG software da', fmt)
            return
        except Exception as e:
            if cam:
                cam.deinit()
            cam = enc = None
            ultimo = e
    lab.log('Fotocamera non disponibile:', ultimo)


def scatta(lab, etichetta):
    if cam is None:
        return
    try:
        img = cam.capture()
        img = bytes(enc.encode(img) if enc else img)
    except Exception as e:
        lab.log('Foto non riuscita:', e)
        return
    FOTO.append((img, (adesso() + ' – ' if S['ntp'] else '') + etichetta))
    if len(FOTO) > 6:
        FOTO.pop(0)
    getattr(lab, 'foto', lambda x: None)(img)      # anche da fuori casa


# ---------------------------------------------------------------- comandi
def on_modo(v):
    richiesta.append(('modo', v))


def on_opzione(k):
    def fn(v):
        CFG[k] = bool(v)
        salva()
    return fn


def on_valore(k):
    def fn(v):
        CFG[k] = int(v)
        salva()
    return fn


def aperti():
    """Sensori attivi che in questo momento segnalano qualcosa."""
    a = []
    if CFG['porta'] and porta.value():
        a.append('porta')
    if CFG['finestra'] and finestra.value():
        a.append('finestra')
    return a


def vai(lab, nuovo, causa=''):
    S['stato'] = nuovo
    S['causa'] = causa
    lab.send('stato', NOMI[nuovo] + (': ' + causa if causa else ''))
    lab.send('inserito', nuovo not in ('spento',))


def esegui(lab, cmd):
    if cmd in ('inserisci', 'notte'):
        a = aperti()
        if a:
            evento(lab, 'Non inserito: ' + ' e '.join(a) + ' aperta. Chiudi o disattiva il sensore')
            lab.notifica('Antifurto NON inserito', ' e '.join(a).capitalize() + ' aperta')
            return
        CFG['modo'] = 'inserito' if cmd == 'inserisci' else 'notte'
        salva()
        S['fine'] = time.ticks_add(time.ticks_ms(), CFG['uscita'] * 1000)
        vai(lab, 'uscita')
        evento(lab, 'Inserimento: hai %d secondi per uscire' % CFG['uscita'])
    elif cmd == 'disinserisci':
        prima = S['stato']
        CFG['modo'] = 'spento'
        salva()
        suono()
        sirena12.value(0)
        vai(lab, 'spento')
        evento(lab, 'Disinserito')
        if prima == 'allarme':
            lab.notifica('Antifurto disinserito', 'Allarme fermato dal telefono')
    elif cmd == 'test':
        evento(lab, 'Prova sirena')
        for f in (1800, 1200, 1800, 1200):
            suono(f, 30000)
            time.sleep_ms(250)
        suono()
    elif cmd == 'foto':
        scatta(lab, 'Foto a richiesta')


def scatta_allarme(lab, causa):
    vai(lab, 'allarme', causa)
    S['fine'] = time.ticks_add(time.ticks_ms(), CFG['sirena'] * 1000)
    S['n'] = 0
    evento(lab, 'ALLARME: ' + causa)
    lab.notifica('ALLARME: ' + causa, 'Apri ESP32 Lab per vedere la foto e disinserire')
    scatta(lab, 'Allarme: ' + causa)


# ---------------------------------------------------------------- pagina web (solo lettura)
PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Antifurto</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px}
.c{background:#fff;border-radius:14px;padding:14px;max-width:560px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
#s{font-size:24px;font-weight:700}.a{color:#dc2626}.ok{color:#16a34a}img{width:100%;border-radius:10px;margin-top:6px;background:#e5e7eb}
li{margin:3px 0}small{color:#6b7280}</style>
<div class=c><div id=s>-</div><div id=se></div><small>Per inserire o disinserire usa l'app ESP32 Lab.</small></div>
<div class=c><b>Ultimi eventi</b><ul id=ev></ul></div><div class=c><b>Ultime foto</b><div id=fo></div></div>
<script>async function u(){const d=await(await fetch('/stato')).json();s.textContent=d.stato;
s.className=d.allarme?'a':(d.inserito?'ok':'');se.textContent='Porta '+d.porta+' · Finestra '+d.finestra+' · Movimento '+d.pir;
ev.innerHTML=d.eventi.slice().reverse().map(x=>'<li>'+x).join('')||'<li>Nessun evento';
fo.innerHTML=d.foto.map(x=>'<p><small>'+x[1]+'</small><img src="/f'+x[0]+'.jpg?'+encodeURIComponent(x[1])+'">').reverse().join('')||'Nessuna foto'}
u();setInterval(u,4000)</script></html>"""


async def orologio(lab):
    import ntptime
    while True:
        try:
            ntptime.settime()
            S['ntp'] = True
            await asyncio.sleep(6 * 3600)
        except Exception:
            await asyncio.sleep(30)


async def main(lab):
    carica()
    lab.on('modo', on_modo)
    lab.on('foto', lambda v: richiesta.append(('modo', 'foto')))
    for k in ('porta', 'finestra', 'pir', 'campanello'):
        lab.on(k, on_opzione(k))
    for k in ('uscita', 'ingresso', 'sirena'):
        lab.on(k, on_valore(k))
    apri_camera(lab)
    if await lab.wifi():
        asyncio.create_task(orologio(lab))

        async def pagina(path, q, w):
            if path == '/stato':
                d = {'stato': NOMI[S['stato']] + (': ' + S['causa'] if S['causa'] else ''),
                     'allarme': S['stato'] in ('allarme', 'ingresso'), 'inserito': S['stato'] != 'spento',
                     'porta': 'aperta' if porta.value() else 'chiusa',
                     'finestra': 'aperta' if finestra.value() else 'chiusa',
                     'pir': 'sì' if pir.value() else 'no',
                     'eventi': EVENTI, 'foto': [[i, f[1]] for i, f in enumerate(FOTO)]}
                await lab.reply(w, json.dumps(d), 'application/json')
            elif path.startswith('/f') and path.endswith('.jpg'):
                i = int(path[2:-4])
                await lab.reply(w, FOTO[i][0] if i < len(FOTO) else b'', 'image/jpeg')
            else:
                await lab.reply(w, PAGINA)
        await lab.serve(pagina)

    # riparte come prima dell'interruzione di corrente
    if CFG['modo'] in ('inserito', 'notte'):
        vai(lab, CFG['modo'])
        evento(lab, 'Riavvio: antifurto di nuovo inserito')
        lab.notifica('Antifurto riavviato', 'Mancanza di corrente? L’antifurto è di nuovo inserito')
    else:
        vai(lab, 'spento')
    if CFG['pir']:
        lab.log('Il PIR si stabilizza in circa 30 secondi dopo l’accensione')

    prima = {'porta': porta.value(), 'finestra': finestra.value(), 'pir': 0}
    for k in prima:
        lab.send(k, prima[k])
    try:
        while True:
            while richiesta:
                esegui(lab, richiesta.pop(0)[1])
            ora = time.ticks_ms()
            v = {'porta': porta.value(), 'finestra': finestra.value(), 'pir': pir.value() if CFG['pir'] else 0}
            for k in v:
                if v[k] != prima[k]:
                    lab.send(k, v[k])
            st = S['stato']
            if st == 'spento':
                if CFG['campanello'] and CFG['porta'] and v['porta'] and not prima['porta']:
                    suono(1319, 20000); await asyncio.sleep_ms(180)
                    suono(1047, 20000); await asyncio.sleep_ms(300)
                    suono()
                led(0, 8, 0)
            elif st == 'uscita':
                rimasti = time.ticks_diff(S['fine'], ora)
                if rimasti <= 0:
                    suono()
                    vai(lab, CFG['modo'])
                    evento(lab, NOMI[CFG['modo']])
                else:
                    lab.send('stato', 'Uscita: %d s' % (rimasti // 1000 + 1))
                    suono(2000, 15000 if (rimasti // 500) % 2 else 0)
                    led(30, 20, 0)
            elif st in ('inserito', 'notte'):
                led(0, 0, 20 if (ora // 1000) % 3 == 0 else 0)
                if CFG['porta'] and v['porta'] and not prima['porta']:
                    S['fine'] = time.ticks_add(ora, CFG['ingresso'] * 1000)
                    vai(lab, 'ingresso', 'porta aperta')
                    evento(lab, 'Porta aperta: %d secondi per disinserire' % CFG['ingresso'])
                    scatta(lab, 'Porta aperta')
                elif CFG['finestra'] and v['finestra'] and not prima['finestra']:
                    scatta_allarme(lab, 'finestra aperta')
                elif st == 'inserito' and v['pir'] and not prima['pir']:
                    scatta_allarme(lab, 'movimento in casa')
            elif st == 'ingresso':
                rimasti = time.ticks_diff(S['fine'], ora)
                if rimasti <= 0:
                    suono()
                    scatta_allarme(lab, 'porta aperta e non disinserito')
                else:
                    lab.send('stato', 'Ingresso: disinserisci entro %d s' % (rimasti // 1000 + 1))
                    suono(2500, 15000 if (rimasti // 250) % 2 else 0)
                    led(60, 30, 0)
            elif st == 'allarme':
                if time.ticks_diff(S['fine'], ora) <= 0:
                    suono()
                    sirena12.value(0)
                    vai(lab, CFG['modo'] if CFG['modo'] != 'spento' else 'spento')
                    evento(lab, 'Sirena spenta dopo %d s: antifurto ancora inserito' % CFG['sirena'])
                else:
                    sirena12.value(1)
                    alto = (ora // 300) % 2
                    suono(1800 if alto else 1200, 32000)
                    led(120 if alto else 0, 0, 0 if alto else 120)
                    S['n'] += 1
                    if S['n'] == 60:              # una seconda foto 3 secondi dopo
                        scatta(lab, 'Allarme: ' + S['causa'])
            prima = v
            await asyncio.sleep_ms(50)
    finally:
        suono()
        sirena12.value(0)
        led(0, 0, 0)
        if cam:
            cam.deinit()
