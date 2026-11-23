# Joystick analogico
# Joystick: GND -> GND, +5V -> 3V3 (non 5V!), VRx -> GPIO1, VRy -> GPIO3, SW -> GPIO47
from machine import Pin, ADC
import asyncio

ax = ADC(Pin(1))
ay = ADC(Pin(3))
ax.atten(ADC.ATTN_11DB)
ay.atten(ADC.ATTN_11DB)
sw = Pin(47, Pin.IN, Pin.PULL_UP)


def scala(v, centro):
    # converte la lettura in -100..100 partendo dal centro misurato all'avvio
    if v >= centro:
        r = (v - centro) * 100 // max(1, 65535 - centro)
    else:
        r = (v - centro) * 100 // max(1, centro)
    return 0 if abs(r) < 6 else r      # zona morta al centro


async def main(lab):
    cx, cy = ax.read_u16(), ay.read_u16()   # non toccare il joystick all'avvio!
    lab.log('Centro calibrato:', cx, cy)
    while True:
        x = scala(ax.read_u16(), cx)
        y = -scala(ay.read_u16(), cy)
        lab.send('pos', {'x': x, 'y': y})
        lab.send('premuto', 1 - sw.value())
        await asyncio.sleep_ms(80)
