# LED RGB integrato (WS2812 / NeoPixel su GPIO48)
# Collegamenti: nessuno
from machine import Pin
import neopixel, asyncio

np = neopixel.NeoPixel(Pin(48), 1)
colore = (0, 40, 120)
modo = 'fisso'
luce = 0.3  # luminosita' 0..1 (il LED e' molto forte!)


def hex_rgb(h):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def ruota(pos):  # arcobaleno: 0..255 -> colore
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def mostra(c):
    np[0] = tuple(int(x * luce) for x in c)
    np.write()


def on_colore(v):
    global colore, modo
    colore = hex_rgb(v)
    modo = 'fisso'


def on_modo(v):
    global modo
    modo = v


def on_luce(v):
    global luce
    luce = int(v) / 100


async def main(lab):
    lab.on('colore', on_colore)
    lab.on('modo', on_modo)
    lab.on('luce', on_luce)
    pos = 0
    try:
        while True:
            if modo == 'arcobaleno':
                pos = (pos + 2) % 256
                mostra(ruota(pos))
            elif modo == 'respiro':
                pos = (pos + 4) % 512
                k = pos if pos < 256 else 511 - pos
                mostra(tuple(x * k // 255 for x in colore))
            else:
                mostra(colore)
            await asyncio.sleep_ms(30)
    finally:
        np[0] = (0, 0, 0)
        np.write()
