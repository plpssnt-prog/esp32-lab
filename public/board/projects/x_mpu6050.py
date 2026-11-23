# Accelerometro e giroscopio MPU-6050: una livella a bolla sul telefono
# MPU-6050: VCC -> 3V3, GND -> GND, SDA -> GPIO21, SCL -> GPIO47
from machine import Pin, I2C
import math, struct, asyncio

i2c = I2C(0, sda=Pin(21), scl=Pin(47), freq=400000)
ADDR = 0x68


def leggi():
    d = i2c.readfrom_mem(ADDR, 0x3B, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack('>hhhhhhh', d)
    g = 16384                               # 1 g con fondo scala +-2 g
    return ax / g, ay / g, az / g, temp / 340 + 36.53, gz / 131


async def main(lab):
    if ADDR not in i2c.scan():
        lab.log('MPU-6050 non trovato: controlla i collegamenti')
        return
    i2c.writeto_mem(ADDR, 0x6B, b'\x00')    # sveglia il sensore
    rx = ry = 0
    while True:
        ax, ay, az, temp, gz = leggi()
        roll = math.degrees(math.atan2(ay, az))
        pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
        rx = rx * 0.7 + roll * 0.3            # filtro: movimenti piu' morbidi
        ry = ry * 0.7 + pitch * 0.3
        lab.send('bolla', {'x': max(-100, min(100, int(rx * 100 / 45))),
                           'y': max(-100, min(100, int(ry * 100 / 45)))})
        lab.send('roll', round(rx))
        lab.send('pitch', round(ry))
        lab.send('scossa', 1 if abs(math.sqrt(ax * ax + ay * ay + az * az) - 1) > 0.6 else 0)
        await asyncio.sleep_ms(80)
