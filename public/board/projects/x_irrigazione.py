# Irrigazione automatica del terrazzo: 2 zone, serbatoio, pannello solare e fotocamera
# Zona A = piante che vogliono piu' acqua, zona B = piante che ne vogliono meno.
# Una pompa 12 V per zona, comandata da un modulo MOSFET.
#
# Sensore umidita' capacitivo A: AOUT -> GPIO1, VCC -> 3V3, GND -> GND
# Sensore umidita' capacitivo B: AOUT -> GPIO3, VCC -> 3V3, GND -> GND
# Modulo MOSFET pompa A: SIG -> GPIO21 · pompa B: SIG -> GPIO47 · GND in comune
# Galleggiante del serbatoio: un filo -> GPIO41, l'altro -> GND (contatto chiuso = c'e' acqua)
# Batteria 12 V: + -> 100 kohm -> GPIO2 -> 10 kohm -> GND (partitore, facoltativo)
# DHT11 (facoltativo): S -> GPIO39, + -> 3V3, - -> GND
#
# La pagina della scheda (http://IP/) mostra umidita', serbatoio, batteria e fotocamera
# e permette di regolare orari, soglie e durate. Le impostazioni restano salvate.
from machine import Pin, ADC
import asyncio, json, time

try:
    from camera import Camera, PixelFormat, FrameSize
except ImportError:
    Camera = None

FILE = 'irrigazione.json'
MAX_SEC = 300                 # nessuna pompa resta accesa piu' di 5 minuti

CFG = {
    'zone': [
        {'nome': 'Più acqua', 'orari': '07:00,19:00', 'sensore': True, 'soglia': 45, 'durata': 40,
         'attiva': True, 'secco': 52000, 'bagnato': 24000},
        {'nome': 'Meno acqua', 'orari': '07:30', 'sensore': True, 'soglia': 30, 'durata': 20,
         'attiva': True, 'secco': 52000, 'bagnato': 24000},
    ],
    'pausa': False,            # sospende i programmi (es. quando piove)
    'galleggiante': True,      # False se il galleggiante non e' ancora montato
    'k_batt': 11.0,            # (100k + 10k) / 10k; si corregge con «Calibra batteria»
    'timelapse': True,         # una foto all'ora dalle 7 alle 19
}

SENS = [ADC(Pin(1)), ADC(Pin(3))]
for _a in SENS:
    _a.atten(ADC.ATTN_11DB)
POMPA = [Pin(21, Pin.OUT, value=0), Pin(47, Pin.OUT, value=0)]
LIVELLO = Pin(41, Pin.IN, Pin.PULL_UP)
BATT = ADC(Pin(2))
BATT.atten(ADC.ATTN_11DB)
try:
    import dht
    ARIA = dht.DHT11(Pin(39))
except Exception:
    ARIA = None

S = {'umid': [0, 0], 'raw': [0, 0], 'pompa': [False, False], 'ultima': ['mai', 'mai'],
     'batt': None, 'aria': None, 'ntp': False, 'stop': False}
coda = []          # irrigazioni in attesa: (zona, secondi, motivo)
LOG = []           # ultimi eventi
STORICO = []       # [ora, umidita' A, umidita' B] ogni 10 minuti (24 ore)
TL = []            # timelapse: (jpeg, etichetta)
cam = None
cam_usata = 0


# ---------------------------------------------------------------- impostazioni
def carica():
    try:
        with open(FILE) as f:
            d = json.load(f)
        for i, z in enumerate(d.get('zone', [])[:2]):
            CFG['zone'][i].update(z)
        for k in ('pausa', 'galleggiante', 'k_batt', 'timelapse'):
            if k in d:
                CFG[k] = d[k]
    except Exception:
        pass


def salva():
    with open(FILE, 'w') as f:
        json.dump(CFG, f)


def orari(z):
    out = []
    for x in z['orari'].replace(' ', '').split(','):
        if ':' in x:
            h, m = x.split(':', 1)
            out.append('%02d:%02d' % (int(h), int(m)))
    return out


# ---------------------------------------------------------------- ora italiana
def ora_italia():
    # l'RTC e' in UTC: +1 ora (CET) o +2 ore (ora legale)
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
        return 'ora non sincronizzata'
    t = ora_italia()
    return '%02d/%02d %02d:%02d' % (t[2], t[1], t[3], t[4])


def evento(lab, msg):
    m = adesso() + ' · ' + msg
    LOG.append(m)
    if len(LOG) > 40:
        LOG.pop(0)
    lab.log(msg)


# ---------------------------------------------------------------- sensori
def grezzo(i):
    s = 0
    for _ in range(16):
        s += SENS[i].read_u16()
    return s // 16


def percento(i, raw):
    z = CFG['zone'][i]
    span = z['secco'] - z['bagnato']
    if span == 0:
        return 0
    return max(0, min(100, (z['secco'] - raw) * 100 // span))


def acqua_ok():
    return (not CFG['galleggiante']) or LIVELLO.value() == 0


def batteria():
    try:
        uv = 0
        for _ in range(8):
            uv += BATT.read_uv()
        v = uv / 8 / 1e6 * CFG['k_batt']
    except Exception:
        return None, 0
    return (round(v, 2) if v > 3 else None), uv / 8


# ---------------------------------------------------------------- fotocamera
cam_enc = [None]   # convertitore JPEG software, se il sensore non fa JPEG

async def foto():
    global cam, cam_usata
    if Camera is None:
        return None
    if cam is None:
        try:
            cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA, jpeg_quality=85, fb_count=1)
            cam_enc[0] = None
        except OSError:
            # sensore senza JPEG (es. GC0308): YUV422 + JPEG software
            import jpeg
            cam = Camera(pixel_format=PixelFormat.YUV422, frame_size=FrameSize.VGA, fb_count=1)
            cam_enc[0] = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                                      pixel_format='YCbYCr', quality=85)
        for _ in range(3):           # i primi scatti servono all'esposizione automatica
            cam.capture()
            await asyncio.sleep_ms(150)
    cam_usata = time.ticks_ms()
    img = cam.capture()
    if not img:
        return None
    return cam_enc[0].encode(img) if cam_enc[0] else bytes(img)


def spegni_cam():
    global cam
    if cam is not None:
        try:
            cam.deinit()
        except Exception:
            pass
        cam = None


# ---------------------------------------------------------------- pompe
def accoda(i, sec, motivo):
    if S['pompa'][i] or any(c[0] == i for c in coda):
        return False
    coda.append((i, max(1, min(MAX_SEC, int(sec))), motivo))
    return True


def ferma():
    del coda[:]
    if S['pompa'][0] or S['pompa'][1]:
        S['stop'] = True


async def irriga(lab):
    while True:
        if not coda:
            await asyncio.sleep_ms(200)
            continue
        i, sec, motivo = coda.pop(0)
        z = CFG['zone'][i]
        if not acqua_ok():
            evento(lab, '%s: serbatoio vuoto, non irrigo' % z['nome'])
            getattr(lab, 'notifica', lambda *a: None)('Serbatoio vuoto', '%s: non posso irrigare, riempi il serbatoio' % z['nome'])
            continue
        S['stop'] = False
        POMPA[i].on()
        S['pompa'][i] = True
        lab.send('pompa%d' % i, 1)
        t0 = time.ticks_ms()
        nota = ''
        try:
            while time.ticks_diff(time.ticks_ms(), t0) < sec * 1000:
                if S['stop']:
                    nota = ', fermata a mano'
                    break
                if not acqua_ok():
                    nota = ', serbatoio finito'
                    break
                await asyncio.sleep_ms(100)
        finally:
            POMPA[i].off()
            S['pompa'][i] = False
            lab.send('pompa%d' % i, 0)
        S['stop'] = False
        S['ultima'][i] = adesso()
        evento(lab, '%s: %d s (%s%s)' % (z['nome'], time.ticks_diff(time.ticks_ms(), t0) // 1000, motivo, nota))
        await asyncio.sleep(3)          # pausa tra una pompa e l'altra


# ---------------------------------------------------------------- compiti periodici
async def programma(lab):
    fatti = set()
    while True:
        if S['ntp'] and not CFG['pausa']:
            t = ora_italia()
            ora = '%02d:%02d' % (t[3], t[4])
            for i, z in enumerate(CFG['zone']):
                if not z['attiva']:
                    continue
                for o in orari(z):
                    k = '%d-%d-%s' % (t[7], i, o)
                    if o != ora or k in fatti:
                        continue
                    fatti.add(k)
                    u = S['umid'][i]
                    if z['sensore'] and u >= z['soglia']:
                        evento(lab, '%s: terra umida (%d%%), salto il turno delle %s' % (z['nome'], u, o))
                    else:
                        accoda(i, z['durata'], 'programma delle %s' % o + (', umidita\' %d%%' % u if z['sensore'] else ''))
            if len(fatti) > 30:
                fatti = set(k for k in fatti if k.startswith('%d-' % t[7]))
        await asyncio.sleep(15)


async def misure(lab):
    n = 0
    while True:
        for i in (0, 1):
            S['raw'][i] = grezzo(i)
            S['umid'][i] = percento(i, S['raw'][i])
            lab.send('umid%d' % i, S['umid'][i])
        lab.send('acqua', 1 if acqua_ok() else 0)
        S['batt'] = batteria()[0]
        lab.send('batt', S['batt'] if S['batt'] else '—')
        if ARIA and n % 6 == 0:
            try:
                ARIA.measure()
                S['aria'] = [ARIA.temperature(), ARIA.humidity()]
            except OSError:
                pass
        if n % 120 == 0:                 # ogni 10 minuti nello storico
            t = ora_italia() if S['ntp'] else None
            STORICO.append(['%02d:%02d' % (t[3], t[4]) if t else '', S['umid'][0], S['umid'][1]])
            if len(STORICO) > 144:
                STORICO.pop(0)
        if cam is not None and time.ticks_diff(time.ticks_ms(), cam_usata) > 60000:
            spegni_cam()                 # risparmia energia quando nessuno guarda
        n += 1
        await asyncio.sleep(5)


async def orologio(lab):
    import ntptime
    while True:
        try:
            ntptime.settime()
            if not S['ntp']:
                S['ntp'] = True
                evento(lab, 'Ora sincronizzata da Internet')
            await asyncio.sleep(6 * 3600)
        except Exception:
            if not S['ntp']:
                lab.log('Ora da Internet non disponibile: i programmi partono quando arriva')
            await asyncio.sleep(600)


async def timelapse(lab):
    ultima = -1
    while True:
        if S['ntp'] and CFG['timelapse']:
            t = ora_italia()
            if 7 <= t[3] <= 19 and t[3] != ultima:
                ultima = t[3]
                try:
                    img = await foto()
                    if img:
                        TL.append((img, '%02d/%02d %02d:00' % (t[2], t[1], t[3])))
                        getattr(lab, 'foto', lambda x: None)(img)   # anche su Internet
                        if len(TL) > 13:
                            TL.pop(0)
                except Exception as e:
                    lab.log('Foto non riuscita:', e)
        await asyncio.sleep(60)


async def rete(lab):
    import network
    w = network.WLAN(network.STA_IF)
    try:
        w.config(pm=w.PM_POWERSAVE)      # meno consumo dal pannello solare
    except Exception:
        pass
    while True:
        await asyncio.sleep(60)
        if not w.isconnected():
            lab.ip = None
            await lab.wifi()


# ---------------------------------------------------------------- pagina web
def stato():
    zone = []
    for i, z in enumerate(CFG['zone']):
        d = dict(z)
        d.update({'umid': S['umid'][i], 'raw': S['raw'][i], 'pompa': S['pompa'][i],
                  'ultima': S['ultima'][i], 'coda': any(c[0] == i for c in coda)})
        zone.append(d)
    return {'ora': adesso(), 'acqua': acqua_ok(), 'batt': S['batt'], 'aria': S['aria'],
            'pausa': CFG['pausa'], 'galleggiante': CFG['galleggiante'], 'timelapse': CFG['timelapse'],
            'cam': Camera is not None, 'zone': zone, 'log': LOG[::-1][:20], 'tl': [x[1] for x in TL]}


def si(v):
    return v in ('1', 'true', 'on')


def imposta(q):
    if 'z' in q:
        z = CFG['zone'][int(q['z']) & 1]
        if 'nome' in q:
            z['nome'] = q['nome'][:24] or z['nome']
        if 'orari' in q:
            # normalizza "7:5, 19:00" in "07:05,19:00"; errore se il formato non e' HH:MM
            z['orari'] = ','.join(orari({'orari': q['orari']}))
        if 'soglia' in q:
            z['soglia'] = max(0, min(100, int(q['soglia'])))
        if 'durata' in q:
            z['durata'] = max(1, min(MAX_SEC, int(q['durata'])))
        for k in ('sensore', 'attiva'):
            if k in q:
                z[k] = si(q[k])
    for k in ('pausa', 'galleggiante', 'timelapse'):
        if k in q:
            CFG[k] = si(q[k])
    if 'vbatt' in q:                      # tensione misurata con il tester
        uv = batteria()[1]
        if uv > 0:
            CFG['k_batt'] = round(float(q['vbatt'].replace(',', '.')) * 1e6 / uv, 3)
    salva()


PAGINA = """<!doctype html><html lang=it><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Irrigazione terrazzo</title><style>
body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px}
.c{background:#fff;border-radius:14px;padding:14px;max-width:560px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
h1{font-size:20px;margin:4px 0}h2{font-size:17px;margin:0 0 8px}small,.m{color:#6b7280}
.pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.p{padding:4px 10px;border-radius:99px;background:#eef2ff;font-size:14px}
.ok{background:#dcfce7;color:#166534}.ko{background:#fee2e2;color:#991b1b}.wa{background:#fef3c7;color:#92400e}
img.f{width:100%;border-radius:10px;background:#e5e7eb;min-height:180px;display:block}
.tl{display:flex;gap:6px;overflow-x:auto;margin-top:8px}.tl button{flex:0 0 auto;font-size:13px;padding:6px 10px}
.n{font-size:38px;font-weight:700}.bar{height:12px;background:#e5e7eb;border-radius:6px;position:relative;margin:6px 0}
.bar i{display:block;height:100%;border-radius:6px;background:#0ea5e9}.bar b{position:absolute;top:-4px;width:3px;height:20px;background:#dc2626}
button{font-size:16px;padding:10px 14px;border:0;border-radius:10px;background:#2563eb;color:#fff;cursor:pointer}
button.g{background:#e5e7eb;color:#1f2937}button.r{background:#dc2626}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
label{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:8px 0}
input[type=text],input[type=number]{font-size:16px;padding:8px;border:1px solid #d1d5db;border-radius:8px;width:9em}
input[type=range]{width:100%}details summary{cursor:pointer;color:#2563eb;margin-top:8px}
canvas{width:100%;height:170px}ul{padding-left:18px;margin:0}li{margin:3px 0;font-size:14px}
</style>
<div class=c><h1>Irrigazione terrazzo</h1><small id=ora></small><div class=pills id=pills></div></div>
<div class=c id=fc><h2>Fotocamera</h2><img class=f id=img alt="Premi Scatta ora"><div class=row>
<button onclick="scatta()">Scatta ora</button><small id=fl></small></div><div class=tl id=tl></div></div>
<div id=zone></div>
<div class=c><h2>Generale</h2>
<label>Sospendi i programmi (pioggia) <input type=checkbox id=pausa onchange="imp({pausa:this.checked?1:0})"></label>
<label>Usa il galleggiante del serbatoio <input type=checkbox id=gall onchange="imp({galleggiante:this.checked?1:0})"></label>
<label>Una foto all'ora (7-19) <input type=checkbox id=tlo onchange="imp({timelapse:this.checked?1:0})"></label>
<div class=row><span>Batteria misurata col tester</span><input type=number step=0.01 id=vb placeholder="12.80"> V
<button class=g onclick="imp({vbatt:vb.value})">Calibra</button></div>
<div class=row><button class=r onclick="get('/ferma')">Ferma tutto</button></div></div>
<div class=c><h2>Umidit&agrave; ultime 24 ore</h2><canvas id=gr width=520 height=170></canvas>
<small><span style="color:#0284c7">&#9632;</span> zona A &nbsp; <span style="color:#16a34a">&#9632;</span> zona B &nbsp; un punto ogni 10 minuti</small></div>
<div class=c><h2>Registro</h2><ul id=log></ul></div>
<script>
const $=id=>document.getElementById(id);let D=null,pronto=false;
const get=u=>fetch(u).then(r=>r.json()).then(x=>{if(x.err)alert(x.err);upd()}).catch(()=>{});
const imp=o=>get('/imposta?'+new URLSearchParams(o));
function scatta(){$('img').src='/foto.jpg?'+Date.now();$('fl').textContent='ora'}
function zona(i,z){const L='AB'[i];return `<div class=c><h2>Zona ${L} &middot; <span id=nm${i}></span></h2>
<div class=row style="justify-content:space-between"><div><div class=n id=u${i}>-</div><small>umidit&agrave; terra</small></div>
<div style="text-align:right"><div id=st${i}></div><small id=ul${i}></small></div></div>
<div class=bar><i id=bi${i}></i><b id=bs${i}></b></div><small>La linea rossa &egrave; la soglia</small>
<div class=row><button onclick="get('/annaffia?z=${i}&s='+$('du${i}').value)">Annaffia ora</button><small id=ne${i}></small></div>
<details><summary>Impostazioni zona ${L}</summary>
<label>Nome <input type=text id=no${i} value="${z.nome}"></label>
<label>Orari (es. 07:00,19:00) <input type=text id=or${i} value="${z.orari}"></label>
<label>Durata (secondi) <input type=number id=du${i} min=1 max=300 value="${z.durata}"></label>
<label>Controlla l'umidit&agrave; prima <input type=checkbox id=se${i} ${z.sensore?'checked':''}></label>
<div>Irriga solo sotto il <b id=sv${i}>${z.soglia}</b>%<input type=range id=so${i} min=0 max=100 value="${z.soglia}" oninput="$('sv${i}').textContent=this.value"></div>
<label>Zona attiva <input type=checkbox id=at${i} ${z.attiva?'checked':''}></label>
<div class=row><button onclick="salva(${i})">Salva</button></div>
<p class=m>Taratura del sensore: lettura attuale <b id=rw${i}></b></p><div class=row>
<button class=g onclick="get('/calibra?z=${i}&t=secco')">Sensore all'aria (asciutto)</button>
<button class=g onclick="get('/calibra?z=${i}&t=bagnato')">Sensore in acqua</button></div></details></div>`}
function salva(i){imp({z:i,nome:$('no'+i).value,orari:$('or'+i).value,durata:$('du'+i).value,
sensore:$('se'+i).checked?1:0,soglia:$('so'+i).value,attiva:$('at'+i).checked?1:0})}
function pill(t,c){return `<span class="p ${c||''}">${t}</span>`}
async function upd(){try{D=await (await fetch('/stato')).json()}catch(e){$('ora').textContent='Scheda non raggiungibile';return}
$('ora').textContent=D.ora;
$('pills').innerHTML=pill(D.acqua?'Serbatoio: acqua OK':'Serbatoio VUOTO',D.acqua?'ok':'ko')+
(D.batt?pill('Batteria '+D.batt.toFixed(1)+' V',D.batt<11.8?'ko':D.batt<12.2?'wa':'ok'):'')+
(D.aria?pill('Aria '+D.aria[0]+'&deg;C &middot; '+D.aria[1]+'%'):'')+(D.pausa?pill('Programmi sospesi','wa'):'');
if(!pronto){$('zone').innerHTML=D.zone.map((z,i)=>zona(i,z)).join('');$('pausa').checked=D.pausa;
$('gall').checked=D.galleggiante;$('tlo').checked=D.timelapse;if(!D.cam)$('fc').style.display='none';else scatta();pronto=true}
D.zone.forEach((z,i)=>{$('nm'+i).textContent=z.nome;$('u'+i).textContent=z.umid+'%';$('bi'+i).style.width=z.umid+'%';
$('bs'+i).style.left=z.soglia+'%';$('st'+i).innerHTML=z.pompa?pill('Pompa accesa','ok'):z.coda?pill('In coda','wa'):pill(z.attiva?'Pompa spenta':'Zona disattivata');
$('ul'+i).textContent='Ultima: '+z.ultima;$('ne'+i).textContent=z.orari?'Programmi: '+z.orari:'';$('rw'+i).textContent=z.raw})
$('tl').innerHTML=D.tl.map((t,i)=>`<button class=g onclick="$('img').src='/tl/${i}.jpg';$('fl').textContent='${t}'">${t.slice(6)}</button>`).join('');
$('log').innerHTML=D.log.map(x=>'<li>'+x+'</li>').join('')||'<li>Nessun evento</li>'}
async function graf(){try{const s=await (await fetch('/storico')).json(),c=$('gr').getContext('2d'),W=520,H=170;
c.clearRect(0,0,W,H);c.strokeStyle='#e5e7eb';for(let k=1;k<4;k++){c.beginPath();c.moveTo(0,H*k/4);c.lineTo(W,H*k/4);c.stroke()}
[[1,'#0284c7'],[2,'#16a34a']].forEach(([j,col])=>{c.strokeStyle=col;c.lineWidth=2.5;c.beginPath();
s.forEach((p,k)=>{const x=k*W/143,y=H-4-p[j]*(H-8)/100;k?c.lineTo(x,y):c.moveTo(x,y)});c.stroke()})}catch(e){}}
upd();graf();setInterval(upd,3000);setInterval(graf,60000)
</script></html>"""


def on_annaffia(i):
    def f(v):
        accoda(i, CFG['zone'][i]['durata'], 'a mano dal telefono')
    return f


def on_pausa(v):
    CFG['pausa'] = bool(v)
    salva()


async def foto_internet(lab):
    img = await foto()
    if img:
        getattr(lab, 'foto', lambda x: None)(img)


async def main(lab):
    carica()
    lab.on('foto', lambda v: foto_internet(lab))   # foto su richiesta via Internet
    lab.on('annaffiaA', on_annaffia(0))
    lab.on('annaffiaB', on_annaffia(1))
    lab.on('ferma', lambda v: ferma())
    lab.on('pausa', on_pausa)
    lab.send('pausa', CFG['pausa'])
    compiti = [asyncio.create_task(f(lab)) for f in (irriga, programma, misure, timelapse)]
    try:
        if await lab.wifi():
            compiti += [asyncio.create_task(orologio(lab)), asyncio.create_task(rete(lab))]

            async def pagina(path, q, w):
                try:
                    if path == '/stato':
                        await lab.reply(w, json.dumps(stato()), 'application/json')
                    elif path == '/storico':
                        await lab.reply(w, json.dumps(STORICO), 'application/json')
                    elif path == '/foto.jpg':
                        await lab.reply(w, (await foto()) or b'', 'image/jpeg')
                    elif path.startswith('/tl/'):
                        i = int(path[4:].split('.')[0])
                        await lab.reply(w, TL[i][0] if i < len(TL) else b'', 'image/jpeg')
                    elif path == '/annaffia':
                        i = int(q.get('z', 0)) & 1
                        ok = accoda(i, int(q.get('s') or CFG['zone'][i]['durata']), 'a mano dalla pagina')
                        await lab.reply(w, json.dumps({} if ok else {'err': 'Zona gia\' in corso o in coda'}), 'application/json')
                    elif path == '/ferma':
                        ferma()
                        evento(lab, 'Fermato tutto dalla pagina')
                        await lab.reply(w, '{}', 'application/json')
                    elif path == '/calibra':
                        i = int(q.get('z', 0)) & 1
                        CFG['zone'][i]['secco' if q.get('t') == 'secco' else 'bagnato'] = grezzo(i)
                        salva()
                        await lab.reply(w, '{}', 'application/json')
                    elif path == '/imposta':
                        imposta(q)
                        await lab.reply(w, '{}', 'application/json')
                    else:
                        await lab.reply(w, PAGINA)
                except Exception as e:
                    await lab.reply(w, json.dumps({'err': 'Valore non valido: %s' % e}), 'application/json')

            await lab.serve(pagina)
        else:
            lab.log('Senza Wi-Fi niente pagina e niente orari: funzionano solo i pulsanti del telefono')
        if not acqua_ok():
            lab.log('Il serbatoio risulta vuoto. Se il galleggiante non e\' ancora montato, disattivalo nella pagina')
        while True:
            await asyncio.sleep(1)
    finally:
        for t in compiti:
            t.cancel()
        for p in POMPA:
            p.off()
        spegni_cam()
