# Angolo sicuro in cucina: orologio e meteo a cifre rosse grandi, gas e fumo, fornello acceso
# senza nessuno in cucina, telecamera con foto e video, allarmi sul telefono e su Telegram.
#
# Display TM1637 rosso 1,2" (alimentato a 5 V) attraverso il traslatore di livello:
#   traslatore LV -> 3V3, HV -> 5V, GND -> GND
#   CLK display -> HV1 ... LV1 -> GPIO42      DIO display -> HV2 ... LV2 -> GPIO41
# Bus I2C (BME280 e MLX90614 insieme): SDA -> GPIO21, SCL -> GPIO47, VIN -> 3V3, GND -> GND
#   (senza BME280 va bene il DHT11 del kit: S -> GPIO39)
# MQ-2: VCC -> 5V, GND -> GND, AO -> 1 kohm -> GPIO3 -> 2 kohm -> GND
# PIR HC-SR501: VCC -> 5V, GND -> GND, OUT -> GPIO40
# Pulsante «ci sono» (kit): un piedino -> GPIO1, l'altro -> GND
# Buzzer passivo: + -> GPIO14, - -> GND
#
# ATTENZIONE: e' un aiuto in piu', non sostituisce un rilevatore di gas certificato
# (UNI EN 50194) con elettrovalvola ne' un rilevatore di fumo.
from machine import Pin, I2C, ADC, PWM
import neopixel, asyncio, time, json, struct

try:
    from camera import Camera, PixelFormat, FrameSize
except ImportError:
    Camera = None

LAT, LON = 43.84, 10.50          # posizione per la temperatura esterna (Lucca): cambiala se serve
FILE = 'cucina.json'
CFG = {'soglia_gas': 12, 'fornello': 50, 'assenza': 10, 'max_acceso': 90, 'luce': 5, 'avviso_acceso': False}
PRERISCALDO = 120                # secondi di riscaldamento dell'MQ-2

S = {'ntp': False, 'tin': None, 'uin': None, 'test': None, 'forn': None, 'gas': 0, 'base': None,
     'allarme_gas': False, 'caldo': False, 'acceso_da': None, 'presenza': time.ticks_ms(),
     'livello': 0, 'avvisato': None, 'avviso_lungo': False, 'meteo_ok': False, 'sensore': '-'}
EVENTI = []
modificato = [0]

pir = Pin(40, Pin.IN, Pin.PULL_DOWN)
tasto = Pin(1, Pin.IN, Pin.PULL_UP)
bz = PWM(Pin(14), freq=2500, duty_u16=0)
np = neopixel.NeoPixel(Pin(48), 1)
gas = ADC(Pin(3))
gas.atten(ADC.ATTN_11DB)
cam = enc = None


# ---------------------------------------------------------------- display TM1637
CIFRE = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]
LETTERE = {' ': 0, '-': 0x40, 'o': 0x63, 'C': 0x39, 'E': 0x79, 'G': 0x3D, 'A': 0x77, 'S': 0x6D,
           'F': 0x71, 'U': 0x3E, 'O': 0x3F, 'n': 0x54, 'r': 0x50, 'H': 0x76, 'L': 0x38}


class TM1637:
    def __init__(self, clk, dio):
        self.clk = Pin(clk, Pin.OPEN_DRAIN, value=1)
        self.dio = Pin(dio, Pin.OPEN_DRAIN, value=1)

    def _b(self, b):
        for i in range(8):
            self.dio((b >> i) & 1)
            time.sleep_us(5)
            self.clk(1)
            time.sleep_us(5)
            self.clk(0)
        self.dio(1)                      # il display risponde (ack): lascio libera la linea
        time.sleep_us(5)
        self.clk(1)
        time.sleep_us(5)
        self.clk(0)

    def _cmd(self, *bb):
        self.dio(0)                      # start
        time.sleep_us(5)
        self.clk(0)
        for b in bb:
            self._b(b)
        self.dio(0)                      # stop
        time.sleep_us(5)
        self.clk(1)
        time.sleep_us(5)
        self.dio(1)

    def mostra(self, segs, luce):
        self._cmd(0x40)
        self._cmd(0xC0, *segs)
        self._cmd(0x88 | max(0, min(7, luce)) if luce >= 0 else 0x80)


def testo4(s, due_punti=False):
    out = []
    for ch in s[:4]:
        out.append(CIFRE[ord(ch) - 48] if '0' <= ch <= '9' else LETTERE.get(ch, 0))
    while len(out) < 4:
        out.insert(0, 0)
    if due_punti:
        out[1] |= 0x80
    return out


def gradi(t, prefisso=''):
    if t is None:
        return prefisso + '--o'
    v = round(t)
    if prefisso:                         # esterno: E 8o, E12o, E-3o, E-12
        s = '%d' % v
        return (prefisso + ' ' * (2 - len(s)) + s + 'o') if len(s) <= 2 else (prefisso + s)[:4]
    s = '%d' % v                         # interno: 21oC
    return (' ' * (2 - len(s)) + s + 'oC') if len(s) <= 2 else s + 'o'


# ---------------------------------------------------------------- sensori
class BME280:
    def __init__(self, i2c, a):
        self.i2c, self.a = i2c, a
        self.bmp = i2c.readfrom_mem(a, 0xD0, 1)[0] == 0x58
        c = i2c.readfrom_mem(a, 0x88, 24)
        self.T = struct.unpack('<Hhh', c[0:6])
        if not self.bmp:
            h1 = i2c.readfrom_mem(a, 0xA1, 1)[0]
            e = i2c.readfrom_mem(a, 0xE1, 7)
            h2, h3 = struct.unpack('<hB', e[0:3])
            h4 = (struct.unpack('b', e[3:4])[0] << 4) | (e[4] & 0x0F)
            h5 = (struct.unpack('b', e[5:6])[0] << 4) | (e[4] >> 4)
            self.H = (h1, h2, h3, h4, h5, struct.unpack('b', e[6:7])[0])
            i2c.writeto_mem(a, 0xF2, b'\x01')
        i2c.writeto_mem(a, 0xF5, b'\xa0')
        i2c.writeto_mem(a, 0xF4, b'\x27')

    def leggi(self):
        d = self.i2c.readfrom_mem(self.a, 0xFA, 5)
        adc_t = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        T1, T2, T3 = self.T
        tf = (adc_t / 16384 - T1 / 1024) * T2 + (adc_t / 131072 - T1 / 8192) ** 2 * T3
        u = None
        if not self.bmp:
            adc_h = (d[3] << 8) | d[4]
            H1, H2, H3, H4, H5, H6 = self.H
            x = tf - 76800
            x = (adc_h - (H4 * 64 + H5 / 16384 * x)) * (H2 / 65536 * (1 + H6 / 67108864 * x * (1 + H3 / 67108864 * x)))
            u = max(0, min(100, x * (1 - H1 * x / 524288)))
        return tf / 5120, u


class DHT:
    def __init__(self):
        import dht
        self.s = dht.DHT11(Pin(39))
        self.s.measure()

    def leggi(self):
        self.s.measure()
        return self.s.temperature(), self.s.humidity()


def mlx(i2c, reg):
    d = i2c.readfrom_mem(0x5A, reg, 3)
    return ((d[1] << 8) | d[0]) * 0.02 - 273.15


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


def evento(lab, testo):
    if S['ntp']:
        o = ora_italia()
        testo = '%02d/%02d %02d:%02d – %s' % (o[2], o[1], o[3], o[4], testo)
    EVENTI.append(testo)
    if len(EVENTI) > 30:
        EVENTI.pop(0)
    lab.log(testo)
    lab.send('evento', testo)


def suona(f, duty=30000):
    if f:
        bz.freq(f)
        bz.duty_u16(duty)
    else:
        bz.duty_u16(0)


def apri_camera(lab):
    global cam, enc
    if Camera is None:
        lab.log('Firmware senza fotocamera')
        return
    try:
        cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA, jpeg_quality=80, fb_count=2)
        return
    except Exception:
        cam = None
    try:
        import jpeg
    except ImportError:
        return
    for pf, fmt in (('YUV422', 'YCbYCr'), ('RGB565', 'RGB565_BE'), ('GRAYSCALE', 'GRAY')):
        try:
            cam = Camera(pixel_format=getattr(PixelFormat, pf), frame_size=FrameSize.QVGA, fb_count=1)
            enc = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                               pixel_format=fmt, quality=80)
            lab.log('Fotocamera:', cam.get_sensor_name(), '- JPEG software')
            return
        except Exception as e:
            if cam:
                cam.deinit()
            cam = enc = None
            lab.log('Formato', fmt, 'non usabile:', e)


def scatta():
    if cam is None:
        return None
    try:
        img = cam.capture()
        return bytes(enc.encode(img) if enc else img)
    except Exception:
        return None


def invia_foto(lab):
    img = scatta()
    if img:
        getattr(lab, 'foto', lambda x: None)(img)
    return bool(img)


def avvisa(lab, titolo, testo, foto=True):
    """Notifica sull'app e su Telegram; con foto=True il ponte manda su Telegram anche la foto."""
    if foto:
        invia_foto(lab)
    if not getattr(lab, 'ws_ok', False):
        lab.log('Avviso non inviato (Internet non attivo):', titolo)
        return False
    msg = json.dumps({'t': 'notify', 'title': titolo[:80], 'body': testo[:300], 'foto': 1 if foto else 0})
    lab.net_q.append((1, msg.encode()))
    return True


def riepilogo():
    p = []
    if S['allarme_gas']:
        p.append('ALLARME GAS/FUMO')
    if S['caldo']:
        m = time.ticks_diff(time.ticks_ms(), S['acceso_da']) // 60000 if S['acceso_da'] else 0
        p.append('fornello acceso da %d min (%s°C)' % (m, '-' if S['forn'] is None else round(S['forn'])))
    else:
        p.append('fornello spento')
    a = time.ticks_diff(time.ticks_ms(), S['presenza']) // 60000
    p.append('ultimo movimento %s' % ('adesso' if a < 1 else '%d min fa' % a))
    if S['tin'] is not None:
        p.append('in cucina %.1f°C' % S['tin'])
    if S['test'] is not None:
        p.append('fuori %.0f°C' % S['test'])
    return ' · '.join(p)


# ---------------------------------------------------------------- comandi
def on_cfg(k):
    def fn(v):
        CFG[k] = v if isinstance(CFG[k], bool) else int(v)
        modificato[0] = time.ticks_ms() or 1
    return fn


def ci_sono():
    S['presenza'] = time.ticks_ms()
    if S['livello']:
        S['livello'] = 0
        S['avviso_lungo'] = False
        suona(0)


PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Cucina</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px}
.c{background:#fff;border-radius:14px;padding:14px;max-width:640px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
#o{font-size:56px;font-weight:800;color:#dc2626;text-align:center;letter-spacing:2px}
.g{display:flex;gap:10px;flex-wrap:wrap}.g>div{flex:1;min-width:130px}.n{font-size:24px;font-weight:700}
img{width:100%;border-radius:12px;background:#e5e7eb}#s{font-size:18px;font-weight:600}.a{color:#dc2626}
li{margin:3px 0}small{color:#6b7280}</style>
<div class=c><div id=o>--:--</div><div id=s></div></div>
<div class=c><img src="/video" alt="Video in diretta"><small>Video in diretta (solo sulla rete di casa)</small></div>
<div class=c><div class=g><div>In cucina<div class=n id=ti>-</div></div><div>Fuori<div class=n id=te>-</div></div>
<div>Fornelli<div class=n id=fo>-</div></div><div>Gas sopra l'aria pulita<div class=n id=ga>-</div></div></div></div>
<div class=c><b>Ultimi eventi</b><ul id=ev></ul></div>
<script>async function u(){const d=await(await fetch('/stato')).json();o.textContent=d.ora||'--:--';
s.textContent=d.riepilogo;s.className=d.allarme?'a':'';ti.textContent=d.tin==null?'-':d.tin.toFixed(1)+'°C'+(d.uin==null?'':' · '+d.uin+'%');
te.textContent=d.test==null?'-':d.test.toFixed(0)+'°C';fo.textContent=d.forn==null?'-':d.forn.toFixed(0)+'°C';ga.textContent=d.gas;
ev.innerHTML=d.eventi.slice().reverse().map(x=>'<li>'+x).join('')||'<li>Nessun evento'}u();setInterval(u,3000)</script></html>"""


# ---------------------------------------------------------------- attivita' in parallelo
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


async def meteo(lab):
    try:
        import requests
    except ImportError:
        import urequests as requests
    url = ('http://api.open-meteo.com/v1/forecast?latitude=%.2f&longitude=%.2f&current=temperature_2m'
           % (LAT, LON))
    while True:
        try:
            r = requests.get(url, timeout=5)
            S['test'] = r.json()['current']['temperature_2m']
            r.close()
            if not S['meteo_ok']:
                S['meteo_ok'] = True
                lab.log('Temperatura esterna da Internet: %.1f °C' % S['test'])
            await asyncio.sleep(900)
        except Exception as e:
            lab.log('Meteo non disponibile:', e)
            await asyncio.sleep(120)


async def schermo(lab, disp):
    """Ora per 10 s, poi temperatura in cucina e fuori per 4 s ciascuna. Allarmi lampeggianti."""
    t = 0
    while True:
        t += 1
        if S['allarme_gas'] or S['livello']:
            scritta = 'GAS ' if S['allarme_gas'] else 'FUOC'
            segs = testo4(scritta) if t % 2 else testo4('    ')
            luce = 7
        else:
            ciclo = (t // 2) % 18          # secondi: 0-9 ora, 10-13 cucina, 14-17 fuori
            if ciclo < 10 or not S['ntp']:
                if S['ntp']:
                    o = ora_italia()
                    segs = testo4('%02d%02d' % (o[3], o[4]), due_punti=(t // 2) % 2 == 0)
                else:
                    segs = testo4(gradi(S['tin']))
            elif ciclo < 14:
                segs = testo4(gradi(S['tin']))
            else:
                segs = testo4(gradi(S['test'], 'E')) if S['test'] is not None else testo4(gradi(S['tin']))
            luce = CFG['luce']
        if disp:
            try:
                disp.mostra(segs, luce)
            except Exception:
                pass
        await asyncio.sleep_ms(500)


# ---------------------------------------------------------------- programma
async def main(lab):
    try:
        with open(FILE) as f:
            CFG.update(json.load(f))
    except Exception:
        pass
    for k in CFG:
        lab.on(k, on_cfg(k))
    lab.on('foto', lambda v: invia_foto(lab))
    lab.on('ci_sono', lambda v: ci_sono())
    lab.on('prova', lambda v: avvisa(lab, 'Prova dalla cucina', 'Se leggi questo messaggio gli avvisi funzionano. ' + riepilogo()))

    disp = TM1637(42, 41)
    i2c = I2C(0, sda=Pin(21), scl=Pin(47), freq=100000)
    trovati = i2c.scan()
    amb = None
    for a in (0x76, 0x77):
        if a in trovati:
            try:
                amb = BME280(i2c, a)
                S['sensore'] = 'BME280'
            except Exception as e:
                lab.log('BME280:', e)
    if amb is None:
        try:
            amb = DHT()
            S['sensore'] = 'DHT11'
        except Exception:
            lab.log('Nessun sensore di temperatura (BME280 su GPIO21/47 o DHT11 su GPIO39)')
    ha_mlx = 0x5A in trovati
    if not ha_mlx:
        lab.log('MLX90614 non trovato: niente controllo del fornello (SDA GPIO21, SCL GPIO47)')
    apri_camera(lab)

    asyncio.create_task(schermo(lab, disp))
    if await lab.wifi():
        asyncio.create_task(orologio(lab))
        asyncio.create_task(meteo(lab))

        async def pagina(path, q, w):
            if path == '/stato':
                o = ora_italia() if S['ntp'] else None
                d = {'ora': '%02d:%02d' % (o[3], o[4]) if o else None, 'riepilogo': riepilogo(),
                     'allarme': S['allarme_gas'] or bool(S['livello']), 'tin': S['tin'], 'uin': S['uin'],
                     'test': S['test'], 'forn': S['forn'], 'gas': S['gas'] if S['base'] is not None else 'riscaldamento',
                     'eventi': EVENTI}
                await lab.reply(w, json.dumps(d), 'application/json')
            elif path == '/foto.jpg':
                await lab.reply(w, scatta() or b'', 'image/jpeg')
            elif path == '/video' and cam:
                w.write(b'HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n'
                        b'Cache-Control: no-store\r\n\r\n')
                while True:
                    img = scatta()
                    if img:
                        w.write(('--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(img)).encode())
                        w.write(img)
                        w.write(b'\r\n')
                        await w.drain()
                    await asyncio.sleep_ms(80)
            else:
                await lab.reply(w, PAGINA)
        await lab.serve(pagina)
    else:
        lab.log('Senza Wi-Fi: niente ora esatta, meteo esterno e avvisi sul telefono')

    avvio = time.ticks_ms()
    ultimo_gas = None
    lab.log('MQ-2 in preriscaldamento per %d secondi' % PRERISCALDO)
    t = 0
    try:
        while True:
            t += 1
            ora = time.ticks_ms()
            # --- presenza: sensore di movimento o pulsante «ci sono»
            if pir.value():
                S['presenza'] = ora
            premuto = not tasto.value()
            if premuto and not S.get('tasto'):
                ci_sono()
                lab.send('evento', 'Premuto «ci sono»')
            S['tasto'] = premuto
            # --- temperatura e umidita' in cucina (ogni 5 s)
            if t % 10 == 0 and amb:
                try:
                    ti, ui = amb.leggi()
                    S['tin'] = round(ti, 1)
                    S['uin'] = None if ui is None else round(ui)
                except Exception:
                    pass
            # --- gas e fumo
            g = 0
            for _ in range(8):
                g += gas.read_u16()
            g = g / 8 * 100 / 65535
            if time.ticks_diff(ora, avvio) > PRERISCALDO * 1000:
                if S['base'] is None:
                    S['base'] = g
                    evento(lab, 'Sensore gas pronto')
                elif g < S['base'] + 3:
                    S['base'] += (g - S['base']) * 0.001
                S['gas'] = round(max(0, g - S['base']))
                allarme = S['gas'] >= CFG['soglia_gas']
                if allarme and not S['allarme_gas']:
                    evento(lab, 'ALLARME gas o fumo!')
                if not allarme and S['allarme_gas']:
                    evento(lab, 'Fine allarme gas')
                    avvisa(lab, 'Cucina: fine allarme gas', riepilogo(), foto=False)
                    ultimo_gas = None
                S['allarme_gas'] = allarme
                if allarme and (ultimo_gas is None or time.ticks_diff(ora, ultimo_gas) > 600000):
                    if avvisa(lab, 'ALLARME GAS O FUMO in cucina', riepilogo()):
                        ultimo_gas = ora
            # --- fornello (ogni secondo)
            if ha_mlx and t % 2 == 0:
                try:
                    S['forn'] = mlx(i2c, 0x07)
                except Exception:
                    pass
                caldo = S['forn'] is not None and S['forn'] >= CFG['fornello']
                if caldo and not S['caldo']:
                    S['acceso_da'] = ora
                    S['avviso_lungo'] = False
                    evento(lab, 'Fornello acceso (%.0f°C)' % S['forn'])
                    if CFG['avviso_acceso']:
                        avvisa(lab, 'Cucina: fornello acceso', riepilogo(), foto=True)
                elif not caldo and S['caldo'] and S['forn'] < CFG['fornello'] - 5:
                    m = time.ticks_diff(ora, S['acceso_da']) // 60000
                    evento(lab, 'Fornello spento dopo %d minuti' % m)
                    if S['livello'] == 2 or CFG['avviso_acceso']:
                        avvisa(lab, 'Cucina: fornello spento', 'Era acceso da %d minuti' % m, foto=False)
                    S['livello'] = 0
                    S['acceso_da'] = None
                    suona(0)
                else:
                    caldo = caldo or (S['caldo'] and S['forn'] is not None and S['forn'] >= CFG['fornello'] - 5)
                S['caldo'] = caldo
                if caldo:
                    assente = time.ticks_diff(ora, S['presenza']) // 60000
                    acceso = time.ticks_diff(ora, S['acceso_da']) // 60000
                    # livello 1: nessuno in cucina da «assenza» minuti -> bip e FUOC sul display
                    if S['livello'] == 0 and assente >= CFG['assenza']:
                        S['livello'] = 1
                        evento(lab, 'Fornello acceso e nessuno in cucina da %d minuti' % assente)
                    # livello 2: dopo altri 5 minuti avviso ai familiari, ripetuto ogni 15 minuti
                    if S['livello'] >= 1 and assente >= CFG['assenza'] + 5:
                        if S['livello'] == 1 or (S['avvisato'] and time.ticks_diff(ora, S['avvisato']) > 900000):
                            S['livello'] = 2
                            if avvisa(lab, 'Cucina: fornello acceso senza nessuno',
                                      'Nessun movimento da %d minuti. %s' % (assente, riepilogo())):
                                S['avvisato'] = ora
                    if acceso >= CFG['max_acceso'] and not S['avviso_lungo']:
                        S['avviso_lungo'] = True
                        evento(lab, 'Fornello acceso da %d minuti' % acceso)
                        avvisa(lab, 'Cucina: fornello acceso da %d minuti' % acceso, riepilogo())
            # --- suoni e LED
            if S['allarme_gas']:
                suona(2600 if t % 2 else 1900, 32000)
                np[0] = (150, 0, 0) if t % 2 else (0, 0, 0)
            elif S['livello']:
                suona(1500 if t % 10 < 2 else 0)        # bip ogni 5 secondi
                np[0] = (120, 40, 0) if t % 2 else (0, 0, 0)
            else:
                suona(0)
                np[0] = (0, 10, 0) if S['base'] is not None else (20, 12, 0)
            np.write()
            # --- pannello dell'app
            if t % 4 == 0:
                lab.send('tin', '-' if S['tin'] is None else S['tin'])
                lab.send('uin', '-' if S['uin'] is None else S['uin'])
                lab.send('test', '-' if S['test'] is None else round(S['test'], 1))
                lab.send('forn', '-' if S['forn'] is None else round(S['forn']))
                lab.send('gas', S['gas'] if S['base'] is not None else 'riscaldamento…')
                lab.send('allarme_gas', S['allarme_gas'])
                lab.send('fornello_acceso', S['caldo'])
                lab.send('movimento', time.ticks_diff(ora, S['presenza']) < 60000)
                lab.send('stato', ('ALLARME GAS O FUMO' if S['allarme_gas'] else
                                   'Fornello acceso, nessuno in cucina' if S['livello'] else 'Tutto a posto'))
            if t % 60 == 0:
                lab.send('riepilogo', riepilogo())
            if modificato[0] and time.ticks_diff(ora, modificato[0]) > 5000:
                modificato[0] = 0
                with open(FILE, 'w') as f:
                    json.dump(CFG, f)
            await asyncio.sleep_ms(500)
    finally:
        suona(0)
        np[0] = (0, 0, 0)
        np.write()
        try:
            disp.mostra([0, 0, 0, 0], -1)
        except Exception:
            pass
        if cam:
            cam.deinit()
