# Allarme con foto: il sensore PIR vede un movimento e la fotocamera scatta
# PIR HC-SR501: VCC -> 5V modulo, GND -> GND (comune), OUT -> GPIO41 (l'uscita e' a 3,3 V)
from camera import Camera, PixelFormat, FrameSize
from machine import Pin
import neopixel, time, asyncio


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

pir = Pin(41, Pin.IN)
np = neopixel.NeoPixel(Pin(48), 1)
foto = []            # ultime 5 foto (in memoria PSRAM)
armato = True

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Allarme</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px;text-align:center}
img{width:100%;max-width:520px;border-radius:12px;margin:6px 0;background:#e5e7eb}</style>
<h2>Ultimi movimenti</h2><div id=g></div><script>async function u(){const n=await (await fetch('/n')).json();
g.innerHTML=n.map(x=>'<p>'+x[1]+'<br><img src="/f'+x[0]+'.jpg">').join('')||'Nessun movimento'}u();setInterval(u,5000)</script></html>"""


def on_armato(v):
    global armato
    armato = bool(v)


async def main(lab):
    lab.on('armato', on_armato)
    cam, enc = apri_camera(lab, FrameSize.VGA, 85, FrameSize.VGA)
    lab.on('foto', lambda v: invia_foto(lab, cam, enc))   # foto via Internet
    try:
        if await lab.wifi():
            async def pagina(path, q, w):
                if path == '/n':
                    import json
                    await lab.reply(w, json.dumps([[i, f[1]] for i, f in enumerate(foto)][::-1]), 'application/json')
                elif path.startswith('/f') and path.endswith('.jpg'):
                    i = int(path[2:-4])
                    await lab.reply(w, foto[i][0] if i < len(foto) else b'', 'image/jpeg')
                else:
                    await lab.reply(w, PAGINA)
            await lab.serve(pagina)
        lab.log('Attendi ~30 s: il PIR si stabilizza dopo l\'accensione')
        prima = 0
        n = 0
        while True:
            m = pir.value()
            lab.send('movimento', m)
            if armato and m and not prima:
                n += 1
                img = bytes(scatta(cam, enc))
                getattr(lab, 'foto', lambda x: None)(img)   # anche su Internet
                t = time.localtime()
                foto.append((img, 'Movimento %d alle %02d:%02d:%02d (ora UTC)' % (n, t[3], t[4], t[5])))
                if len(foto) > 5:
                    foto.pop(0)
                lab.send('allarmi', n)
                lab.log('Movimento rilevato! Foto', n)
                np[0] = (80, 0, 0)
                np.write()
            elif not m:
                np[0] = (0, 0, 0)
                np.write()
            prima = m
            await asyncio.sleep_ms(100)
    finally:
        cam.deinit()
        np[0] = (0, 0, 0)
        np.write()
