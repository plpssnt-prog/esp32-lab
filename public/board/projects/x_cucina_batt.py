# Cucina sicura A BATTERIA: orologio e temperature su display e-paper grande, fornello acceso
# senza nessuno in cucina, foto e avvisi su telefono e Telegram. Niente sensore gas (consuma troppo).
#
# Display e-paper Waveshare 4,2" V2 (400x300, bianco e nero):
#   VCC -> 3V3, GND -> GND, DIN -> GPIO41, CLK -> GPIO40, CS -> GPIO42, DC -> GPIO39, RST -> GPIO38, BUSY -> GPIO46
# Sensori I2C alimentati solo durante la misura (BME280 + MLX90614 in parallelo):
#   VIN -> GPIO45, GND -> GND, SDA -> GPIO21, SCL -> GPIO47
# PIR AM312 (basso consumo): VCC -> 3V3, GND -> GND, OUT -> GPIO1
# Pulsante «ci sono»: un piedino -> GPIO3, l'altro -> 3V3 (tenuto premuto 3 s = manutenzione 10 minuti)
# Buzzer passivo: + -> GPIO14, - -> GND
# Batteria: + -> 100 kohm -> GPIO2 -> 100 kohm -> GND (per leggere la carica)
#
# La scheda dorme quasi sempre (light sleep): si sveglia ogni 30 s per guardare i fornelli,
# subito se si muove qualcuno o si preme il pulsante, e si collega a Internet solo per gli
# allarmi e per un «battito» periodico. Se il battito non arriva, il ponte avvisa i familiari.
from machine import Pin, I2C, ADC, PWM, SPI
import machine, esp32, framebuf, asyncio, time, json, struct, os

LAT, LON = 43.84, 10.50          # per la temperatura esterna (Lucca)
FILE = 'cucina_batt.json'
CFG = {'fornello': 50, 'assenza': 10, 'max_acceso': 90, 'battito': 30, 'avviso_acceso': False}
GIORNI = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')

S = {'ntp': False, 'tin': None, 'uin': None, 'test': None, 'forn': None, 'caldo': False,
     'acceso_da': None, 'presenza': time.ticks_ms(), 'livello': 0, 'avvisato': None,
     'avviso_lungo': False, 'batt': None, 'batt_avvisata': False, 'internet': None}
modificato = [0]

pir = Pin(1, Pin.IN, Pin.PULL_DOWN)
tasto = Pin(3, Pin.IN, Pin.PULL_DOWN)
alim_sensori = Pin(45, Pin.OUT, value=0)
bz = PWM(Pin(14), freq=2000, duty_u16=0)
batt = ADC(Pin(2))
batt.atten(ADC.ATTN_11DB)


# ---------------------------------------------------------------- display e-paper 4,2" V2 (SSD1683)
class EPD:
    W, H = 400, 300

    def __init__(self):
        self.spi = SPI(1, baudrate=4000000, sck=Pin(40), mosi=Pin(41), miso=Pin(0))
        self.cs = Pin(42, Pin.OUT, value=1)
        self.dc = Pin(39, Pin.OUT, value=0)
        self.rst = Pin(38, Pin.OUT, value=1)
        self.busy = Pin(46, Pin.IN)
        self.buf = bytearray(self.W * self.H // 8)
        self.fb = framebuf.FrameBuffer(self.buf, self.W, self.H, framebuf.MONO_HLSB)

    def _cmd(self, c, dati=None):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytes((c,)))
        self.cs(1)
        if dati is not None:
            self.dc(1)
            self.cs(0)
            self.spi.write(dati)
            self.cs(1)

    def _attendi(self, ms):
        t = time.ticks_ms()
        while self.busy.value() and time.ticks_diff(time.ticks_ms(), t) < ms:
            time.sleep_ms(20)

    def _finestra(self):
        self._cmd(0x44, bytes((0, (self.W - 1) >> 3)))
        self._cmd(0x45, bytes((0, 0, (self.H - 1) & 255, (self.H - 1) >> 8)))
        self._cmd(0x4E, b'\x00')
        self._cmd(0x4F, b'\x00\x00')

    def completo(self):
        """Aggiornamento completo (lampeggia qualche secondo, pulisce le ombre)."""
        self.rst(0)
        time.sleep_ms(5)
        self.rst(1)
        time.sleep_ms(20)
        self._attendi(2000)
        self._cmd(0x12)
        self._attendi(2000)
        self._cmd(0x21, b'\x40\x00')
        self._cmd(0x3C, b'\x05')
        self._cmd(0x11, b'\x03')
        self._finestra()
        self._attendi(2000)
        self._cmd(0x24, self.buf)
        self._cmd(0x26, self.buf)
        self._cmd(0x22, b'\xF7')
        self._cmd(0x20)
        self._attendi(8000)

    def parziale(self):
        """Aggiornamento veloce senza lampeggio (per l'ora ogni minuto)."""
        self._cmd(0x3C, b'\x80')
        self._cmd(0x21, b'\x00\x00')
        self._finestra()
        self._cmd(0x24, self.buf)
        self._cmd(0x22, b'\xFF')
        self._cmd(0x20)
        self._attendi(3000)


# ---------------------------------------------------------------- disegno: cifre a 7 segmenti e testo ingrandito
SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
       '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''}
_g = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)


def cifra(fb, ch, x, y, w, h, t):
    m = h // 2
    for s in SEG.get(ch, ''):
        if s == 'a':
            fb.fill_rect(x + t, y, w - 2 * t, t, 0)
        elif s == 'b':
            fb.fill_rect(x + w - t, y + t, t, m - t, 0)
        elif s == 'c':
            fb.fill_rect(x + w - t, y + m, t, h - m - t, 0)
        elif s == 'd':
            fb.fill_rect(x + t, y + h - t, w - 2 * t, t, 0)
        elif s == 'e':
            fb.fill_rect(x, y + m, t, h - m - t, 0)
        elif s == 'f':
            fb.fill_rect(x, y + t, t, m - t, 0)
        elif s == 'g':
            fb.fill_rect(x + t, y + m - t // 2, w - 2 * t, t, 0)


def scritta(fb, s, x, y, k, col=0):
    for ch in s:
        if ch == '°':
            fb.fill_rect(x + k, y, 3 * k, 3 * k, col)
            fb.fill_rect(x + 2 * k, y + k, k, k, 1 - col)
            x += 5 * k
            continue
        _g.fill(0)
        _g.text(ch, 0, 0, 1)
        for yy in range(8):
            for xx in range(8):
                if _g.pixel(xx, yy):
                    fb.fill_rect(x + xx * k, y + yy * k, k, k, col)
        x += 8 * k
    return x


def larghezza(s, k):
    return sum(5 * k if ch == '°' else 8 * k for ch in s)


def gradi(t):
    return '--' if t is None else '%d°' % round(t)


def disegna(epd):
    fb = epd.fb
    fb.fill(1)
    o = ora_italia() if S['ntp'] else None
    # ora grande (cifre alte 150 pixel, circa 4 cm)
    hhmm = '%02d%02d' % (o[3], o[4]) if o else '----'
    w, h, t, sp = 72, 150, 16, 14
    x0 = (400 - (4 * w + 3 * sp + 26)) // 2
    for i, ch in enumerate(hhmm):
        x = x0 + i * (w + sp) + (26 + sp if i >= 2 else 0)
        cifra(fb, ch, x, 12, w, h, t)
    xc = x0 + 2 * (w + sp) - sp // 2 + 4
    fb.fill_rect(xc, 55, 14, 14, 0)
    fb.fill_rect(xc, 105, 14, 14, 0)
    # temperature
    if S['livello']:
        fb.fill_rect(0, 172, 400, 128, 0)
        for i, riga in enumerate(('FORNELLO', 'ACCESO!')):
            scritta(fb, riga, (400 - larghezza(riga, 5)) // 2, 182 + i * 54, 5, 1)
        return
    fb.hline(10, 172, 380, 0)
    scritta(fb, 'CUCINA', 30, 182, 2)
    scritta(fb, gradi(S['tin']), 24, 204, 6)
    scritta(fb, 'FUORI', 228, 182, 2)
    scritta(fb, gradi(S['test']), 222, 204, 6)
    fb.vline(200, 182, 70, 0)
    # riga in basso: data, batteria, Internet
    giu = ('%s %d/%d' % (GIORNI[o[6]], o[2], o[1])) if o else 'ora da Internet...'
    scritta(fb, giu, 10, 272, 2)
    b = '%d%%' % S['batt'] if S['batt'] is not None else ''
    if S['internet'] is False:
        b = 'no rete ' + b
    scritta(fb, b, 390 - larghezza(b, 2), 272, 2)


# ---------------------------------------------------------------- sensori
class BME280:
    def __init__(self, i2c, a):
        self.i2c, self.a = i2c, a
        self.bmp = i2c.readfrom_mem(a, 0xD0, 1)[0] == 0x58
        c = i2c.readfrom_mem(a, 0x88, 6)
        self.T = struct.unpack('<Hhh', c)
        if not self.bmp:
            h1 = i2c.readfrom_mem(a, 0xA1, 1)[0]
            e = i2c.readfrom_mem(a, 0xE1, 7)
            h2, h3 = struct.unpack('<hB', e[0:3])
            h4 = (struct.unpack('b', e[3:4])[0] << 4) | (e[4] & 0x0F)
            h5 = (struct.unpack('b', e[5:6])[0] << 4) | (e[4] >> 4)
            self.H = (h1, h2, h3, h4, h5, struct.unpack('b', e[6:7])[0])
            i2c.writeto_mem(a, 0xF2, b'\x01')
        i2c.writeto_mem(a, 0xF4, b'\x25')          # una misura sola (forced mode)

    def leggi(self):
        time.sleep_ms(12)
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


def misura(lab, i2c, minuto):
    """Accende i sensori, legge fornello (e ogni minuto la stanza), li rispegne."""
    alim_sensori.value(1)
    time.sleep_ms(300)                 # l'MLX90614 da' la prima misura dopo circa 250 ms
    try:
        d = i2c.readfrom_mem(0x5A, 0x07, 3)
        S['forn'] = ((d[1] << 8) | d[0]) * 0.02 - 273.15
    except Exception:
        S['forn'] = None
    if minuto:
        for a in (0x76, 0x77):
            try:
                ti, ui = BME280(i2c, a).leggi()
                S['tin'] = round(ti, 1)
                S['uin'] = None if ui is None else round(ui)
                break
            except Exception:
                pass
        v = batt.read_uv() * 2 / 1e6
        S['batt'] = max(0, min(100, round((v - 3.3) / 0.9 * 100)))
        S['volt'] = round(v, 2)
    alim_sensori.value(0)


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


def riepilogo():
    p = []
    if S['caldo']:
        m = time.ticks_diff(time.ticks_ms(), S['acceso_da']) // 60000 if S['acceso_da'] else 0
        p.append('fornello acceso da %d min (%s°C)' % (m, '-' if S['forn'] is None else round(S['forn'])))
    else:
        p.append('fornello spento')
    a = time.ticks_diff(time.ticks_ms(), S['presenza']) // 60000
    p.append('ultimo movimento %s' % ('adesso' if a < 1 else '%d min fa' % a))
    if S['tin'] is not None:
        p.append('in cucina %.1f°C' % S['tin'])
    if S['batt'] is not None:
        p.append('batteria %d%% (%.2f V)' % (S['batt'], S.get('volt', 0)))
    if S['ntp']:
        o = ora_italia()
        p.append('alle %02d:%02d' % (o[3], o[4]))
    return ' · '.join(p)


def suona(ms=300, f=1500):
    bz.freq(f)
    bz.duty_u16(30000)
    time.sleep_ms(ms)
    bz.duty_u16(0)


def foto(lab):
    try:
        from camera import Camera, PixelFormat, FrameSize
    except ImportError:
        return
    cam = None
    try:
        try:
            cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA, jpeg_quality=80, fb_count=1)
            img = cam.capture()
        except Exception:
            import jpeg
            if cam:
                cam.deinit()
            cam = Camera(pixel_format=PixelFormat.RGB565, frame_size=FrameSize.QVGA, fb_count=1)
            enc = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                               pixel_format='RGB565_BE', quality=80)
            cam.capture()                     # la prima foto dopo l'accensione e' spesso scura
            img = enc.encode(cam.capture())
        getattr(lab, 'foto', lambda x: None)(bytes(img))
    except Exception as e:
        lab.log('Foto non riuscita:', e)
    finally:
        if cam:
            cam.deinit()


# ---------------------------------------------------------------- Internet solo quando serve
async def accendi_rete(lab, attesa=20):
    if not await lab.wifi(timeout=10):
        S['internet'] = False
        return False
    if not S['ntp']:
        try:
            import ntptime
            ntptime.settime()
            S['ntp'] = True
        except Exception:
            pass
    if not lab.cloud_task:
        lab.start_cloud()
    for _ in range(attesa * 10):
        if lab.ws_ok:
            S['internet'] = True
            return True
        await asyncio.sleep_ms(100)
    S['internet'] = False
    return False


async def spegni_rete(lab):
    for _ in range(80):                     # aspetto che i messaggi in coda partano
        if not lab.net_q:
            break
        await asyncio.sleep_ms(100)
    await asyncio.sleep_ms(500)
    if lab.cloud_task:
        lab.cloud_task.cancel()
        lab.cloud_task = None
    lab.ws_ok = False
    await asyncio.sleep_ms(200)
    import network
    network.WLAN(network.STA_IF).active(False)
    lab.ip = None


def invia_stato(lab):
    lab.send('veglia', CFG['battito'] * 2 + 10)       # il ponte avvisa se non mi sente per questo tempo
    lab.send('riepilogo', riepilogo())
    lab.send('stato', 'Fornello acceso, nessuno in cucina' if S['livello'] else 'Tutto a posto')
    for k in ('tin', 'uin', 'batt'):
        lab.send(k, '-' if S[k] is None else S[k])
    lab.send('forn', '-' if S['forn'] is None else round(S['forn']))
    lab.send('test', '-' if S['test'] is None else round(S['test'], 1))
    lab.send('fornello_acceso', S['caldo'])


async def avvisa(lab, titolo, testo, con_foto=True):
    if not await accendi_rete(lab):
        lab.log('Avviso non inviato (niente Internet):', titolo)
        return False
    if con_foto:
        foto(lab)
    msg = json.dumps({'t': 'notify', 'title': titolo[:80], 'body': testo[:300], 'foto': 1 if con_foto else 0})
    lab.net_q.append((1, msg.encode()))
    invia_stato(lab)
    return True


def meteo():
    try:
        import requests
    except ImportError:
        import urequests as requests
    try:
        r = requests.get('http://api.open-meteo.com/v1/forecast?latitude=%.2f&longitude=%.2f&current=temperature_2m'
                         % (LAT, LON), timeout=5)
        S['test'] = r.json()['current']['temperature_2m']
        r.close()
    except Exception:
        pass


# ---------------------------------------------------------------- comandi (funzionano quando la scheda e' collegata)
def on_cfg(k):
    def fn(v):
        CFG[k] = v if isinstance(CFG[k], bool) else int(v)
        modificato[0] = time.ticks_ms() or 1
    return fn


def ci_sono():
    S['presenza'] = time.ticks_ms()
    S['livello'] = 0
    S['avviso_lungo'] = False


# ---------------------------------------------------------------- programma
async def main(lab):
    try:
        with open(FILE) as f:
            CFG.update(json.load(f))
    except Exception:
        pass
    for k in CFG:
        lab.on(k, on_cfg(k))
    lab.on('ci_sono', lambda v: ci_sono())
    lab.on('foto', lambda v: foto(lab))
    lab.on('prova', lambda v: lab.net_q.append((1, json.dumps({'t': 'notify', 'title': 'Prova dalla cucina (batteria)',
                                                                'body': riepilogo(), 'foto': 0}).encode())))
    # manutenzione: dopo l'avvio resto sveglia 2 minuti (10 se richiesta col pulsante)
    try:
        os.remove('manutenzione')
        sveglia_fino = time.ticks_add(time.ticks_ms(), 600000)
        lab.log('Manutenzione: resto sveglia 10 minuti')
    except OSError:
        sveglia_fino = time.ticks_add(time.ticks_ms(), 120000)
        lab.log('Resto sveglia 2 minuti, poi inizio a risparmiare la batteria')
    i2c = I2C(0, sda=Pin(21), scl=Pin(47), freq=100000)
    epd = EPD()
    misura(lab, i2c, True)
    if await accendi_rete(lab):
        meteo()
        invia_stato(lab)
    disegna(epd)
    epd.completo()
    schermo = {'min': None, 'livello': 0, 'completo': time.ticks_ms()}
    battito = time.ticks_ms()
    pir_libero = 0                          # dopo un movimento non mi sveglio col PIR per un minuto
    ultimo_min = None
    try:
        await ciclo(lab, i2c, epd, sveglia_fino, schermo, battito, pir_libero, ultimo_min)
    finally:
        lab.send('veglia', 0)                # progetto fermato: il ponte non deve piu' aspettarmi
        bz.duty_u16(0)
        alim_sensori.value(0)


async def ciclo(lab, i2c, epd, sveglia_fino, schermo, battito, pir_libero, ultimo_min):
    while True:
        ora = time.ticks_ms()
        sveglia = lab.usb or time.ticks_diff(sveglia_fino, ora) > 0
        if pir.value():
            S['presenza'] = ora
        # pulsante: breve = «ci sono», lungo (3 s) = manutenzione
        if tasto.value():
            t0 = time.ticks_ms()
            while tasto.value() and time.ticks_diff(time.ticks_ms(), t0) < 3000:
                time.sleep_ms(20)
            if tasto.value():
                suona(150, 2000); suona(150, 2500)
                with open('manutenzione', 'w') as f:
                    f.write('1')
                machine.reset()
            ci_sono()
            suona(80, 2500)
        # misure (la stanza e la batteria una volta al minuto)
        o = ora_italia() if S['ntp'] else None
        minuto = (o[4] if o else time.ticks_ms() // 60000)
        misura(lab, i2c, minuto != ultimo_min)
        ultimo_min = minuto
        # fornello
        caldo = S['forn'] is not None and (S['forn'] >= CFG['fornello'] or (S['caldo'] and S['forn'] >= CFG['fornello'] - 5))
        if caldo and not S['caldo']:
            S['acceso_da'] = ora
            S['avviso_lungo'] = False
            lab.log('Fornello acceso')
            if CFG['avviso_acceso']:
                await avvisa(lab, 'Cucina: fornello acceso', riepilogo())
        elif not caldo and S['caldo']:
            m = time.ticks_diff(ora, S['acceso_da']) // 60000 if S['acceso_da'] else 0
            lab.log('Fornello spento dopo %d minuti' % m)
            if S['livello'] == 2 or CFG['avviso_acceso']:
                await avvisa(lab, 'Cucina: fornello spento', 'Era acceso da %d minuti' % m, con_foto=False)
            S['livello'] = 0
            S['acceso_da'] = None
        S['caldo'] = caldo
        if caldo:
            assente = time.ticks_diff(ora, S['presenza']) // 60000
            acceso = time.ticks_diff(ora, S['acceso_da']) // 60000
            if S['livello'] == 0 and assente >= CFG['assenza']:
                S['livello'] = 1
            if S['livello'] >= 1 and assente >= CFG['assenza'] + 5:
                if S['livello'] == 1 or (S['avvisato'] and time.ticks_diff(ora, S['avvisato']) > 900000):
                    S['livello'] = 2
                    if await avvisa(lab, 'Cucina: fornello acceso senza nessuno',
                                    'Nessun movimento da %d minuti. %s' % (assente, riepilogo())):
                        S['avvisato'] = ora
                        sveglia_fino = time.ticks_add(ora, 60000)     # un minuto collegata: puoi chiedere /foto
            if acceso >= CFG['max_acceso'] and not S['avviso_lungo']:
                S['avviso_lungo'] = True
                await avvisa(lab, 'Cucina: fornello acceso da %d minuti' % acceso, riepilogo())
        if S['livello']:
            suona(300)
        # batteria quasi scarica
        if S['batt'] is not None and S['batt'] <= 15 and not S['batt_avvisata']:
            S['batt_avvisata'] = await avvisa(lab, 'Cucina: batteria quasi scarica', riepilogo(), con_foto=False)
        elif S['batt'] is not None and S['batt'] >= 30:
            S['batt_avvisata'] = False
        # battito periodico (e meteo)
        if time.ticks_diff(ora, battito) >= CFG['battito'] * 60000:
            battito = ora
            if await accendi_rete(lab):
                meteo()
                invia_stato(lab)
        elif sveglia and lab.ws_ok and minuto != schermo['min']:
            invia_stato(lab)
        # display: ogni minuto (parziale), completo ogni ora o quando cambia l'allarme
        if minuto != schermo['min'] or S['livello'] != schermo['livello']:
            disegna(epd)
            if S['livello'] != schermo['livello'] or time.ticks_diff(ora, schermo['completo']) > 3600000:
                epd.completo()
                schermo['completo'] = ora
            else:
                epd.parziale()
            schermo['min'], schermo['livello'] = minuto, S['livello']
        if modificato[0] and time.ticks_diff(ora, modificato[0]) > 3000:
            modificato[0] = 0
            with open(FILE, 'w') as f:
                json.dump(CFG, f)
        # dormo
        if sveglia:
            await asyncio.sleep(1)
            continue
        if lab.ip or lab.cloud_task:
            await spegni_rete(lab)
        if lab.ble:                          # il Bluetooth torna al prossimo riavvio (manutenzione)
            try:
                lab.ble.ble.active(False)
            except Exception:
                pass
            lab.ble = None
        pausa = 10000 if S['livello'] else 30000
        if o:                                # mi sveglio allo scoccare del minuto per l'orologio
            pausa = min(pausa, (60 - o[5]) * 1000 + 200)
        pin_sveglia = (tasto,) if time.ticks_diff(pir_libero, ora) > 0 else (tasto, pir)
        esp32.wake_on_ext1(pins=pin_sveglia, level=esp32.WAKEUP_ANY_HIGH)
        machine.lightsleep(pausa)
        if pir.value():
            S['presenza'] = time.ticks_ms()
            pir_libero = time.ticks_add(time.ticks_ms(), 60000)
        await asyncio.sleep_ms(0)
