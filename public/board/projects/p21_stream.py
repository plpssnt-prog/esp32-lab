# Video in diretta (streaming MJPEG) sul telefono
# Collegamenti: nessuno. Apri la pagina della scheda dalla PWA.
from camera import Camera, PixelFormat, FrameSize
import asyncio, time


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


def invia_foto(lab, cam, enc):
    """Manda una foto al ponte Internet (serve il runtime 1.2)."""
    f = getattr(lab, 'foto', None)
    if f:
        f(scatta(cam, enc))


def scatta(cam, enc):
    img = cam.capture()
    return enc.encode(img) if enc else img

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Video ESP32</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px;text-align:center}
img{width:100%;max-width:640px;border-radius:12px;background:#e5e7eb}label{margin:8px;display:inline-block}</style>
<h2>Video in diretta</h2><img id=v src="/stream"><br>
<label><input type=checkbox onchange="v.style.transform=this.checked?'rotate(180deg)':''"> Capovolgi</label></html>"""


async def main(lab):
    cam, enc = apri_camera(lab, FrameSize.VGA, 80, FrameSize.QVGA)
    lab.on('foto', lambda v: invia_foto(lab, cam, enc))   # foto via Internet
    try:
        if not await lab.wifi():
            return

        async def pagina(path, q, w):
            if path != '/stream':
                await lab.reply(w, PAGINA)
                return
            w.write(b'HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n'
                    b'Cache-Control: no-store\r\n\r\n')
            n, t0 = 0, time.ticks_ms()
            while True:
                img = scatta(cam, enc)
                w.write(('--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(img)).encode())
                w.write(img)
                w.write(b'\r\n')
                await w.drain()          # se il browser si chiude, qui arriva un errore e si esce
                n += 1
                if n % 20 == 0:
                    lab.send('fps', round(20000 / max(1, time.ticks_diff(time.ticks_ms(), t0)), 1))
                    t0 = time.ticks_ms()
                await asyncio.sleep_ms(5)

        await lab.serve(pagina)
        while True:
            await asyncio.sleep(1)
    finally:
        cam.deinit()
