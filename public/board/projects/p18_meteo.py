# Stazione meteo Wi-Fi: DHT11 + fotoresistenza, con grafico nel browser
# DHT11: S -> GPIO39, + -> 3V3, - -> GND
# Fotoresistenza: 3V3 -> LDR -> GPIO1 -> 10k -> GND
from machine import Pin, ADC
import dht, asyncio, json

sens = dht.DHT11(Pin(39))
ldr = ADC(Pin(1))
ldr.atten(ADC.ATTN_11DB)
storico = []      # ultime 120 misure (una ogni 30 s = 1 ora)

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Meteo ESP32</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:16px}
.c{background:#fff;border-radius:14px;padding:16px;max-width:520px;margin:0 auto 12px;box-shadow:0 1px 4px #0001}
.n{font-size:34px;font-weight:700}.g{display:flex;gap:10px}.g>div{flex:1}canvas{width:100%;height:180px}</style>
<div class=c><div class=g><div>Temperatura<div class=n id=t>-</div></div><div>Umidit&agrave;<div class=n id=h>-</div></div>
<div>Luce<div class=n id=l>-</div></div></div></div><div class=c><canvas id=g width=500 height=180></canvas>
<small>Rosso: temperatura &middot; Blu: umidit&agrave; (ultima ora)</small></div>
<script>async function u(){const d=await (await fetch('/dati')).json();const s=d.s,x=s[s.length-1]||[0,0,0];
t.textContent=x[0]+'°C';h.textContent=x[1]+'%';l.textContent=x[2]+'%';const c=g.getContext('2d');c.clearRect(0,0,500,180);
[[0,'#dc2626',50],[1,'#2563eb',100]].forEach(([i,col,m])=>{c.strokeStyle=col;c.lineWidth=2;c.beginPath();
s.forEach((p,j)=>{const X=j*500/Math.max(1,s.length-1),Y=175-p[i]*170/m;j?c.lineTo(X,Y):c.moveTo(X,Y)});c.stroke()})}
u();setInterval(u,10000)</script></html>"""


def leggi():
    try:
        sens.measure()
        t, h = sens.temperature(), sens.humidity()
    except OSError:
        return None
    return [t, h, ldr.read_u16() * 100 // 65535]


async def main(lab):
    ip = await lab.wifi()

    async def pagina(path, q, w):
        if path == '/dati':
            await lab.reply(w, json.dumps({'s': storico}), 'application/json')
        else:
            await lab.reply(w, PAGINA)

    if ip:
        await lab.serve(pagina)
    conta = 0
    while True:
        m = leggi()
        if m:
            lab.send('temp', m[0])
            lab.send('umid', m[1])
            lab.send('luce', m[2])
            if conta % 15 == 0:            # ogni 30 secondi nello storico
                storico.append(m)
                if len(storico) > 120:
                    storico.pop(0)
        conta += 1
        await asyncio.sleep(2)
