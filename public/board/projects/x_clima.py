# Clima di casa: temperatura, umidita' e pressione con storico di 24 ore e avvisi sul telefono
# BME280 (I2C): VIN/VCC -> 3V3, GND -> GND, SDA -> GPIO21, SCL -> GPIO47
# Senza BME280 funziona anche con il DHT11 del kit: S -> GPIO39, + -> 3V3, - -> GND
#
# La pagina della scheda (http://IP/) mostra i valori, il minimo e il massimo
# e i grafici delle ultime 24 ore. Le soglie restano salvate nella scheda.
from machine import Pin, I2C
import asyncio, time, json, struct, math

FILE = 'clima.json'
CFG = {'caldo': 27, 'freddo': 18, 'umido': 65, 'secco': 35, 'avvisi': True}
STORICO = []          # [ora, temperatura, umidita', pressione] ogni 10 minuti (24 ore)
S = {'t': None, 'u': None, 'p': None, 'sensore': '-', 'ntp': False}
modificato = [0]      # istante dell'ultima modifica delle soglie (salvataggio ritardato)


# ---------------------------------------------------------------- sensori
class BME280:
    """Driver minimo per BME280 (e BMP280, che non misura l'umidita')."""

    def __init__(self, i2c, addr):
        self.i2c, self.a = i2c, addr
        chip = i2c.readfrom_mem(addr, 0xD0, 1)[0]
        if chip not in (0x60, 0x58):
            raise OSError('chip sconosciuto 0x%02X' % chip)
        self.bmp = chip == 0x58
        c = i2c.readfrom_mem(addr, 0x88, 24)
        self.T = struct.unpack('<Hhh', c[0:6])
        self.P = struct.unpack('<Hhhhhhhhh', c[6:24])
        if not self.bmp:
            h1 = i2c.readfrom_mem(addr, 0xA1, 1)[0]
            e = i2c.readfrom_mem(addr, 0xE1, 7)
            h2, h3 = struct.unpack('<hB', e[0:3])
            h4 = (struct.unpack('b', e[3:4])[0] << 4) | (e[4] & 0x0F)
            h5 = (struct.unpack('b', e[5:6])[0] << 4) | (e[4] >> 4)
            h6 = struct.unpack('b', e[6:7])[0]
            self.H = (h1, h2, h3, h4, h5, h6)
            i2c.writeto_mem(addr, 0xF2, b'\x01')      # umidita' x1 (prima di 0xF4)
        i2c.writeto_mem(addr, 0xF5, b'\xa0')          # una misura al secondo
        i2c.writeto_mem(addr, 0xF4, b'\x27')          # temperatura e pressione x1, modo continuo

    def leggi(self):
        d = self.i2c.readfrom_mem(self.a, 0xF7, 8)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        adc_h = (d[6] << 8) | d[7]
        T1, T2, T3 = self.T
        tf = (adc_t / 16384 - T1 / 1024) * T2 + (adc_t / 131072 - T1 / 8192) ** 2 * T3
        t = tf / 5120
        P1, P2, P3, P4, P5, P6, P7, P8, P9 = self.P
        v1 = tf / 2 - 64000
        v2 = v1 * v1 * P6 / 32768 + v1 * P5 * 2
        v2 = v2 / 4 + P4 * 65536
        v1 = (1 + (P3 * v1 * v1 / 524288 + P2 * v1) / 524288 / 32768) * P1
        p = None
        if v1:
            p = (1048576 - adc_p - v2 / 4096) * 6250 / v1
            p = (p + (P9 * p * p / 2147483648 + p * P8 / 32768 + P7) / 16) / 100   # hPa
        u = None
        if not self.bmp:
            H1, H2, H3, H4, H5, H6 = self.H
            x = tf - 76800
            x = (adc_h - (H4 * 64 + H5 / 16384 * x)) * (H2 / 65536 * (1 + H6 / 67108864 * x * (1 + H3 / 67108864 * x)))
            x = x * (1 - H1 * x / 524288)
            u = max(0, min(100, x))
        return t, u, p


class DHT:
    def __init__(self):
        import dht
        self.s = dht.DHT11(Pin(39))
        self.s.measure()

    def leggi(self):
        self.s.measure()
        return self.s.temperature(), self.s.humidity(), None


def apri_sensore(lab):
    try:
        i2c = I2C(0, sda=Pin(21), scl=Pin(47), freq=100000)
        for a in (0x76, 0x77):
            if a in i2c.scan():
                s = BME280(i2c, a)
                S['sensore'] = 'BMP280 (senza umidità)' if s.bmp else 'BME280'
                lab.log('Sensore trovato:', S['sensore'], 'all\'indirizzo 0x%02X' % a)
                return s
    except Exception as e:
        lab.log('BME280 non trovato:', e)
    try:
        s = DHT()
        S['sensore'] = 'DHT11'
        lab.log('Uso il DHT11 su GPIO39 (niente pressione)')
        return s
    except Exception:
        pass
    lab.log('Nessun sensore: controlla i collegamenti (BME280 su GPIO21/47 o DHT11 su GPIO39)')
    return None


# ---------------------------------------------------------------- calcoli
def rugiada(t, u):
    if t is None or not u:
        return None
    a, b = 17.62, 243.12
    g = math.log(u / 100) + a * t / (b + t)
    return b * g / (a - g)


def giudizio(t, u):
    if t is None:
        return 'Nessuna misura'
    out = []
    if t >= CFG['caldo']:
        out.append('Troppo caldo')
    elif t <= CFG['freddo']:
        out.append('Troppo freddo')
    if u is not None:
        if u >= CFG['umido']:
            out.append('Troppo umido: cambia l’aria')
        elif u <= CFG['secco']:
            out.append('Aria secca')
    return ' · '.join(out) or 'Confortevole'


def tendenza():
    """Pressione rispetto a 3 ore fa (18 misure da 10 minuti)."""
    if len(STORICO) < 19 or STORICO[-1][3] is None or STORICO[-19][3] is None:
        return 'Servono 3 ore di misure'
    d = STORICO[-1][3] - STORICO[-19][3]
    if d <= -1.5:
        return 'In calo (%.1f hPa): possibile pioggia' % d
    if d >= 1.5:
        return 'In salita (+%.1f hPa): tempo in miglioramento' % d
    return 'Stabile (%+.1f hPa in 3 ore)' % d


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


# ---------------------------------------------------------------- impostazioni
def carica():
    try:
        with open(FILE) as f:
            d = json.load(f)
        CFG.update(d.get('cfg', {}))
        STORICO.extend(d.get('storico', [])[-144:])
    except Exception:
        pass


def salva():
    try:
        with open(FILE, 'w') as f:
            json.dump({'cfg': CFG, 'storico': STORICO}, f)
    except Exception:
        pass


def imposta(chiave):
    def fn(v):
        CFG[chiave] = v if chiave == 'avvisi' else float(v)
        modificato[0] = time.ticks_ms() or 1
    return fn


def stato():
    t, u, p = S['t'], S['u'], S['p']
    tt = [x[1] for x in STORICO if x[1] is not None] + ([t] if t is not None else [])
    uu = [x[2] for x in STORICO if x[2] is not None] + ([u] if u is not None else [])
    r = rugiada(t, u)
    return {'t': t, 'u': u, 'p': p, 'rugiada': None if r is None else round(r, 1),
            'giudizio': giudizio(t, u), 'tendenza': tendenza() if p is not None else '',
            'tmin': min(tt) if tt else None, 'tmax': max(tt) if tt else None,
            'umin': min(uu) if uu else None, 'umax': max(uu) if uu else None,
            'sensore': S['sensore'], 'cfg': CFG}


PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Clima di casa</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:14px}
.c{background:#fff;border-radius:14px;padding:14px;max-width:560px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
.g{display:flex;gap:10px;flex-wrap:wrap}.g>div{flex:1;min-width:120px}.n{font-size:30px;font-weight:700}
small{color:#6b7280}canvas{width:100%;height:150px}h3{margin:0 0 6px;font-size:15px}#gi{font-size:18px;font-weight:600}</style>
<div class=c><div id=gi>-</div><small id=te></small></div>
<div class=c><div class=g><div>Temperatura<div class=n id=t>-</div><small id=tr></small></div>
<div>Umidit&agrave;<div class=n id=u>-</div><small id=ur></small></div>
<div>Pressione<div class=n id=p>-</div><small id=ru></small></div></div></div>
<div class=c><h3>Temperatura (24 ore)</h3><canvas id=c1 width=540 height=150></canvas></div>
<div class=c><h3>Umidit&agrave; (24 ore)</h3><canvas id=c2 width=540 height=150></canvas></div>
<div class=c id=bp><h3>Pressione (24 ore)</h3><canvas id=c3 width=540 height=150></canvas></div>
<div class=c><small id=so></small></div>
<script>const f=(v,d,u)=>v==null?'-':v.toFixed(d)+u;
function gr(cv,s,i,col){const c=cv.getContext('2d'),W=cv.width,H=cv.height;c.clearRect(0,0,W,H);
const v=s.map(x=>x[i]).filter(x=>x!=null);if(v.length<2)return;let lo=Math.min(...v),hi=Math.max(...v);
if(hi-lo<2){lo-=1;hi+=1}c.fillStyle='#6b7280';c.font='12px system-ui';c.fillText(hi.toFixed(1),2,12);c.fillText(lo.toFixed(1),2,H-4);
c.fillText(s[0][0],40,H-4);c.fillText(s[s.length-1][0],W-40,H-4);c.strokeStyle=col;c.lineWidth=2.5;c.beginPath();let k=0;
s.forEach((x,j)=>{if(x[i]==null)return;const X=j*W/(s.length-1),Y=H-16-(x[i]-lo)*(H-30)/(hi-lo);k++?c.lineTo(X,Y):c.moveTo(X,Y)});c.stroke()}
async function u_(){const d=await(await fetch('/stato')).json(),s=await(await fetch('/storico')).json();
gi.textContent=d.giudizio;te.textContent=d.tendenza?'Pressione: '+d.tendenza:'';
t.textContent=f(d.t,1,'°C');u.textContent=f(d.u,0,'%');p.textContent=f(d.p,0,' hPa');
tr.textContent='min '+f(d.tmin,1,'°')+' · max '+f(d.tmax,1,'°');ur.textContent='min '+f(d.umin,0,'%')+' · max '+f(d.umax,0,'%');
ru.textContent=d.rugiada==null?'':'Punto di rugiada '+d.rugiada+'°C';
so.textContent='Sensore: '+d.sensore+' · Comfort tra '+d.cfg.freddo+' e '+d.cfg.caldo+'°C, umidità tra '+d.cfg.secco+' e '+d.cfg.umido+'%';
gr(c1,s,1,'#dc2626');gr(c2,s,2,'#2563eb');if(d.p==null)bp.style.display='none';else gr(c3,s,3,'#16a34a')}
u_();setInterval(u_,15000)</script></html>"""


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
    for k in ('caldo', 'freddo', 'umido', 'secco', 'avvisi'):
        lab.on(k, imposta(k))
    sens = apri_sensore(lab)
    if await lab.wifi():
        asyncio.create_task(orologio(lab))

        async def pagina(path, q, w):
            if path == '/stato':
                await lab.reply(w, json.dumps(stato()), 'application/json')
            elif path == '/storico':
                await lab.reply(w, json.dumps(STORICO), 'application/json')
            else:
                await lab.reply(w, PAGINA)
        await lab.serve(pagina)
    lab.send('sensore', S['sensore'])
    ultimo_avviso = {}            # tipo di avviso -> istante (al massimo uno ogni 3 ore)
    prossimo = time.ticks_ms()    # prossima misura per lo storico
    salvato = time.ticks_ms()
    try:
        while True:
            if sens:
                try:
                    t, u, p = sens.leggi()
                    S['t'] = round(t, 1)
                    S['u'] = None if u is None else round(u)
                    S['p'] = None if p is None else round(p, 1)
                except Exception as e:
                    lab.log('Lettura non riuscita:', e)
            t, u, p = S['t'], S['u'], S['p']
            if t is not None:
                lab.send('temp', t)
                lab.send('umid', '-' if u is None else u)
                lab.send('press', '-' if p is None else p)
                r = rugiada(t, u)
                lab.send('rugiada', '-' if r is None else round(r, 1))
                g = giudizio(t, u)
                lab.send('comfort', g)
                if p is not None:
                    lab.send('tendenza', tendenza())
                lab.send('soglie', '%g–%g °C · %g–%g %%' % (CFG['freddo'], CFG['caldo'], CFG['secco'], CFG['umido']))
                # avvisi sul telefono quando si esce dalla zona di comfort
                if CFG['avvisi'] and g != 'Confortevole':
                    for tipo in g.split(' · '):
                        prima = ultimo_avviso.get(tipo)
                        if prima is None or time.ticks_diff(time.ticks_ms(), prima) > 3 * 3600 * 1000:
                            if lab.notifica('Clima di casa: ' + tipo.split(':')[0],
                                            '%.1f °C, umidità %s%%' % (t, '-' if u is None else u)):
                                ultimo_avviso[tipo] = time.ticks_ms()
                # storico ogni 10 minuti
                if time.ticks_diff(time.ticks_ms(), prossimo) >= 0:
                    prossimo = time.ticks_add(time.ticks_ms(), 600000)
                    o = ora_italia() if S['ntp'] else None
                    STORICO.append(['%02d:%02d' % (o[3], o[4]) if o else '', t, u, p])
                    if len(STORICO) > 144:
                        STORICO.pop(0)
            # salvataggio: soglie modificate da 5 s, storico ogni ora
            if modificato[0] and time.ticks_diff(time.ticks_ms(), modificato[0]) > 5000:
                modificato[0] = 0
                salva()
                lab.log('Soglie salvate')
            elif time.ticks_diff(time.ticks_ms(), salvato) > 3600000:
                salvato = time.ticks_ms()
                salva()
            await asyncio.sleep(5)
    finally:
        salva()
