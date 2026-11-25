# Fotocamera: scatta una foto e guardala nel browser
# Collegamenti: nessuno (fotocamera OV2640/OV3660 nel connettore della scheda)
# Serve il firmware MicroPython con fotocamera installato dalla PWA.
from camera import Camera, PixelFormat, FrameSize
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

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Foto ESP32</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:16px;text-align:center}
img{max-width:100%;border-radius:12px;background:#e5e7eb;min-height:200px}button{font-size:18px;padding:12px 22px;border:0;
border-radius:10px;background:#2563eb;color:#fff;margin:10px}a{display:block;margin:6px}</style>
<h2>Fotocamera ESP32</h2><img id=i alt="Premi Scatta"><br><button onclick="s()">Scatta</button>
<a id=d download=foto.jpg>Scarica la foto</a>
<script>function s(){const u='/foto.jpg?'+Date.now();i.src=u;d.href=u}</script></html>"""


async def main(lab):
    cam, enc = apri_camera(lab, FrameSize.VGA, 85, FrameSize.VGA)
    try:
        if not await lab.wifi():
            return
        scatti = [0]

        async def pagina(path, q, w):
            if path.startswith('/foto'):
                img = scatta(cam, enc)
                scatti[0] += 1
                lab.send('scatti', scatti[0])
                await lab.reply(w, img, 'image/jpeg')
            else:
                await lab.reply(w, PAGINA)

        await lab.serve(pagina)
        while True:
            await asyncio.sleep(1)
    finally:
        cam.deinit()
