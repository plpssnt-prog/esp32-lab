# Fotocamera: scatta una foto e guardala nel browser
# Collegamenti: nessuno (fotocamera OV2640/OV3660 nel connettore della scheda)
# Serve il firmware MicroPython con fotocamera installato dalla PWA.
from camera import Camera, PixelFormat, FrameSize
import asyncio

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Foto ESP32</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:16px;text-align:center}
img{max-width:100%;border-radius:12px;background:#e5e7eb;min-height:200px}button{font-size:18px;padding:12px 22px;border:0;
border-radius:10px;background:#2563eb;color:#fff;margin:10px}a{display:block;margin:6px}</style>
<h2>Fotocamera ESP32</h2><img id=i alt="Premi Scatta"><br><button onclick="s()">Scatta</button>
<a id=d download=foto.jpg>Scarica la foto</a>
<script>function s(){const u='/foto.jpg?'+Date.now();i.src=u;d.href=u}</script></html>"""


async def main(lab):
    cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA,
                 jpeg_quality=85, fb_count=2)
    try:
        if not await lab.wifi():
            return
        scatti = [0]

        async def pagina(path, q, w):
            if path.startswith('/foto'):
                img = cam.capture()
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
