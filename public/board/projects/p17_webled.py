# Pannello web sulla scheda (Wi-Fi): LED e servo dal browser
# Serve il Wi-Fi configurato nella pagina "Scheda" della PWA.
# Servo opzionale: segnale -> GPIO42 (5V dal modulo di alimentazione)
from machine import Pin, PWM
import asyncio

led = Pin(2, Pin.OUT)
servo = PWM(Pin(42), freq=50)

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>ESP32 Lab</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:20px}
.c{background:#fff;border-radius:14px;padding:18px;margin:0 auto 14px;max-width:420px;box-shadow:0 1px 4px #0001}
button{font-size:18px;padding:12px 18px;border:0;border-radius:10px;background:#2563eb;color:#fff;margin:4px}
button.off{background:#e5e7eb;color:#111}input{width:100%}</style>
<div class=c><h2>LED integrato</h2><button onclick="f('/led?v=1')">Accendi</button>
<button class=off onclick="f('/led?v=0')">Spegni</button></div>
<div class=c><h2>Servo: <span id=a>90</span>&deg;</h2>
<input type=range min=0 max=180 value=90 oninput="a.textContent=this.value;f('/servo?v='+this.value)"></div>
<script>let t;function f(u){clearTimeout(t);t=setTimeout(()=>fetch(u),60)}</script></html>"""


def angolo(a):
    servo.duty_ns(500000 + int(a) * 2000000 // 180)


async def main(lab):
    ip = await lab.wifi()
    if not ip:
        return

    async def pagina(path, q, w):
        if path == '/led':
            led.value(int(q.get('v', 0)))
            lab.send('led', led.value())
            await lab.reply(w, 'ok', 'text/plain')
        elif path == '/servo':
            angolo(q.get('v', 90))
            lab.send('gradi', int(q.get('v', 90)))
            await lab.reply(w, 'ok', 'text/plain')
        else:
            await lab.reply(w, PAGINA)

    angolo(90)
    await lab.serve(pagina)
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        led.value(0)
        servo.deinit()
