# Macchinina con telecamera (FPV): guidi guardando il video sul telefono
# Collegamenti come la macchinina telecomandata (L298N su GPIO21, 47, 14, 1).
# La fotocamera e' sulla scheda: montala sul davanti della macchinina.
from camera import Camera, PixelFormat, FrameSize
from machine import Pin, PWM
import time, asyncio


def apri_camera(lab, fs, q=80, fs_sw=None):
    """Apre la fotocamera in JPEG. Se il sensore non fa JPEG da solo
    (errore ESP_ERR_NOT_SUPPORTED) usa RGB565 e converte in JPEG via software."""
    try:
        cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=fs, jpeg_quality=q, fb_count=2)
        lab.log('Sensore:', cam.get_sensor_name(), '- JPEG del sensore')
        return cam, None
    except OSError:
        pass
    import jpeg
    ultimo = None
    for pf, fmt in ((PixelFormat.YUV422, 'YCbYCr'), (PixelFormat.RGB565, 'RGB565_BE'),
                    (PixelFormat.GRAYSCALE, 'GRAY')):
        cam = None
        try:
            cam = Camera(pixel_format=pf, frame_size=fs_sw or fs, fb_count=1)
            enc = jpeg.Encoder(width=cam.get_pixel_width(), height=cam.get_pixel_height(),
                               pixel_format=fmt, quality=q)
            lab.log('Sensore:', cam.get_sensor_name(), '- JPEG software da', fmt)
            return cam, enc
        except Exception as e:
            ultimo = e
            lab.log('Formato', fmt, 'non usabile:', e)
            if cam:
                cam.deinit()
    raise ultimo


def scatta(cam, enc):
    img = cam.capture()
    return enc.encode(img) if enc else img


class Motore:
    def __init__(self, a, b):
        self.a = PWM(Pin(a), freq=1000, duty_u16=0)
        self.b = PWM(Pin(b), freq=1000, duty_u16=0)

    def vai(self, v):
        v = max(-100, min(100, int(v)))
        d = abs(v) * 65535 // 100
        self.a.duty_u16(d if v > 0 else 0)
        self.b.duty_u16(d if v < 0 else 0)

    def spegni(self):
        self.a.deinit()
        self.b.deinit()


sx, dx = Motore(21, 47), Motore(14, 1)
ultimo = [0]

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no">
<title>FPV</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:8px;text-align:center;
user-select:none;-webkit-user-select:none}img{width:100%;max-width:640px;border-radius:12px;background:#e5e7eb}
#p{width:220px;height:220px;border-radius:50%;background:#e5e7eb;margin:12px auto;position:relative;touch-action:none}
#k{width:80px;height:80px;border-radius:50%;background:#2563eb;position:absolute;left:70px;top:70px}</style>
<img src="/stream"><div id=p><div id=k></div></div><script>
let x=0,y=0,on=0;const P=p.getBoundingClientRect.bind(p);function mv(e){const r=P(),t=e.touches?e.touches[0]:e;
let dx=t.clientX-r.left-110,dy=t.clientY-r.top-110,m=Math.hypot(dx,dy);if(m>80){dx*=80/m;dy*=80/m}
k.style.left=70+dx+'px';k.style.top=70+dy+'px';x=Math.round(dx*1.25);y=Math.round(-dy*1.25)}
function up(){on=0;x=y=0;k.style.left=k.style.top='70px'}
p.addEventListener('pointerdown',e=>{on=1;mv(e)});addEventListener('pointermove',e=>on&&mv(e));
addEventListener('pointerup',up);setInterval(()=>fetch('/joy?x='+x+'&y='+y).catch(()=>{}),150)</script></html>"""


def guida(x, y):
    ultimo[0] = time.ticks_ms()
    sx.vai((y + x) * 7 // 10)
    dx.vai((y - x) * 7 // 10)


def on_joy(v):
    guida(int(v.get('x', 0)), int(v.get('y', 0)))


async def main(lab):
    lab.on('joy', on_joy)
    cam, enc = apri_camera(lab, FrameSize.QVGA, 75, FrameSize.QVGA)
    try:
        if not await lab.wifi():
            return

        async def pagina(path, q, w):
            if path == '/joy':
                guida(int(q.get('x', 0)), int(q.get('y', 0)))
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
            if time.ticks_diff(time.ticks_ms(), ultimo[0]) > 800:   # sicurezza
                sx.vai(0)
                dx.vai(0)
            await asyncio.sleep_ms(100)
    finally:
        cam.deinit()
        sx.spegni()
        dx.spegni()
