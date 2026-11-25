# Telecamera brandeggiabile: video + servo per ruotarla
# Servo: segnale -> GPIO42, rosso -> 5V modulo, marrone -> GND (comune)
# Fissa la scheda (o la fotocamera) sulla squadretta del servo.
from camera import Camera, PixelFormat, FrameSize
from machine import Pin, PWM
import asyncio


def apri_camera(lab, fs, q=80, fs_sw=None):
    """Apre la fotocamera in JPEG. Se il sensore non fa JPEG da solo
    (errore ESP_ERR_NOT_SUPPORTED) usa RGB565 e converte in JPEG via software."""
    enc = None
    try:
        cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=fs, jpeg_quality=q, fb_count=2)
    except OSError:
        import jpeg
        cam = Camera(pixel_format=PixelFormat.RGB565, frame_size=fs_sw or fs, fb_count=1)
        enc = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                           pixel_format='RGB565', quality=q)
    try:
        lab.log('Sensore:', cam.get_sensor_name(), '- JPEG software' if enc else '- JPEG del sensore')
    except Exception:
        pass
    return cam, enc


def scatta(cam, enc):
    img = cam.capture()
    return enc.encode(img) if enc else img

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
    cam, enc = apri_camera(lab, FrameSize.VGA, 80, FrameSize.QVGA)
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
                    img = scatta(cam, enc)
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
