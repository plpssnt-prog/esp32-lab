# Video in diretta (streaming MJPEG) sul telefono
# Collegamenti: nessuno. Apri la pagina della scheda dalla PWA.
from camera import Camera, PixelFormat, FrameSize
import asyncio, time

PAGINA = """<!doctype html><html lang=it><meta name=viewport content="width=device-width,initial-scale=1">
<title>Video ESP32</title><style>body{font-family:system-ui;background:#f6f7fb;color:#1f2937;margin:0;padding:12px;text-align:center}
img{width:100%;max-width:640px;border-radius:12px;background:#e5e7eb}label{margin:8px;display:inline-block}</style>
<h2>Video in diretta</h2><img id=v src="/stream"><br>
<label><input type=checkbox onchange="v.style.transform=this.checked?'rotate(180deg)':''"> Capovolgi</label></html>"""


async def main(lab):
    cam = Camera(pixel_format=PixelFormat.JPEG, frame_size=FrameSize.VGA,
                 jpeg_quality=80, fb_count=2)
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
                img = cam.capture()
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
