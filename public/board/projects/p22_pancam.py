# Telecamera brandeggiabile: video + servo per ruotarla
# Servo: segnale -> GPIO42, rosso -> 5V modulo, marrone -> GND (comune)
# Fissa la scheda (o la fotocamera) sulla squadretta del servo.
from camera import Camera, PixelFormat, FrameSize
from machine import Pin, PWM
import asyncio

servo = PWM(Pin(42), freq=50)

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>PanCam</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px;text-align:center}
img{width:100%;max-width:640px;border-radius:12px;background:#e5e7eb}input{width:90%;max-width:600px}</style>
<img src="/stream"><p>Rotazione: <b id=a>90</b>&deg;</p>
<input type=range min=0 max=180 value=90 oninput="a.textContent=this.value;clearTimeout(window.t);
window.t=setTimeout(()=>fetch('/servo?v='+this.value),60)"></html>"""


def angolo(a):
    servo.duty_ns(500000 + max(0, min(180, int(a))) * 2000000 // 180)


def on_angolo(v):
    angolo(v)


async def main(lab):
    lab.on('angolo', on_angolo)
    angolo(90)
    cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA,
                 jpeg_quality=80, fb_count=2)
    try:
        if not await lab.wifi():
            return

        async def pagina(path, q, w):
            if path == '/servo':
                angolo(q.get('v', 90))
                await lab.reply(w, 'ok', 'text/plain')
            elif path == '/stream':
                w.write(b'HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n')
                while True:
                    img = cam.capture()
                    w.write(('--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(img)).encode())
                    w.write(img)
                    w.write(b'\r\n')
                    await w.drain()
                    await asyncio.sleep_ms(5)
            else:
                await lab.reply(w, PAGINA)

        await lab.serve(pagina)
        while True:
            await asyncio.sleep(1)
    finally:
        cam.deinit()
        servo.deinit()
