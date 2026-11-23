# Anello di LED WS2812 (8, 12 o 16 LED): lampada con effetti
# Anello: 5V/VCC -> 5V modulo di alimentazione, GND -> GND (comune), DIN/IN -> GPIO21
from machine import Pin
import neopixel, asyncio

N = 16                       # cambia se il tuo anello ha 8 o 12 LED
np = neopixel.NeoPixel(Pin(21), N)
colore = (255, 120, 20)
modo = 'fisso'
luce = 0.25


def ruota(p):
    p %= 256
    if p < 85:
        return (255 - p * 3, p * 3, 0)
    if p < 170:
        p -= 85
        return (0, 255 - p * 3, p * 3)
    p -= 170
    return (p * 3, 0, 255 - p * 3)


def scala(c, k=1.0):
    return tuple(int(x * luce * k) for x in c)


def on_colore(v):
    global colore
    h = v.lstrip('#')
    colore = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
    t = 0
    try:
        while True:
            t += 1
            for i in range(N):
                if modo == 'arcobaleno':
                    np[i] = scala(ruota(i * 256 // N + t * 3))
                elif modo == 'giro':      # un punto luminoso con la scia
                    dist = (t // 2 - i) % N
                    np[i] = scala(colore, max(0, 1 - dist * 0.25))
                elif modo == 'candela':   # tremolio casuale
                    import random
                    np[i] = scala(colore, 0.6 + random.random() * 0.4)
                else:
                    np[i] = scala(colore)
            np.write()
            await asyncio.sleep_ms(40)
    finally:
        np.fill((0, 0, 0))
        np.write()
