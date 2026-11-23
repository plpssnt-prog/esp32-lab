# Macchinina comandata dal telefono (Bluetooth)
# Driver L298N (ponticelli ENA/ENB inseriti):
#   IN1 -> GPIO21, IN2 -> GPIO47 (motore sinistro) ; IN3 -> GPIO14, IN4 -> GPIO1 (motore destro)
#   +12V -> pacco batterie (+), GND -> pacco batterie (-) E GND dell'ESP32
# ESP32 alimentato da un power bank USB (consigliato per iniziare).
from machine import Pin, PWM
import time, asyncio


class Motore:
    def __init__(self, a, b):
        self.a = PWM(Pin(a), freq=1000, duty_u16=0)
        self.b = PWM(Pin(b), freq=1000, duty_u16=0)

    def vai(self, v):                  # v da -100 a 100
        v = max(-100, min(100, int(v)))
        d = abs(v) * 65535 // 100
        self.a.duty_u16(d if v > 0 else 0)
        self.b.duty_u16(d if v < 0 else 0)

    def spegni(self):
        self.a.deinit()
        self.b.deinit()


sx = Motore(21, 47)
dx = Motore(14, 1)
limite = 70       # velocita' massima in %
ultimo_cmd = 0
inverti = False


def guida(x, y):
    global ultimo_cmd
    ultimo_cmd = time.ticks_ms()
    if inverti:
        y = -y
    # guida "a carro armato": somma e differenza di avanti e sterzo
    s = (y + x) * limite // 100
    d = (y - x) * limite // 100
    sx.vai(s)
    dx.vai(d)


def on_joy(v):
    guida(int(v.get('x', 0)), int(v.get('y', 0)))


def on_limite(v):
    global limite
    limite = int(v)


def on_inverti(v):
    global inverti
    inverti = bool(v)


async def main(lab):
    lab.on('joy', on_joy)
    lab.on('limite', on_limite)
    lab.on('inverti', on_inverti)
    try:
        while True:
            # sicurezza: se non arrivano comandi per 1 secondo, mi fermo
            if time.ticks_diff(time.ticks_ms(), ultimo_cmd) > 1000:
                sx.vai(0)
                dx.vai(0)
            await asyncio.sleep_ms(100)
    finally:
        sx.spegni()
        dx.spegni()
