# Robot segui-linea con 2 sensori TCRT5000
# Motori come la macchinina (L298N: IN1 GPIO21, IN2 GPIO47, IN3 GPIO14, IN4 GPIO1)
# Sensore sinistro: VCC -> 3V3, GND -> GND, DO -> GPIO41
# Sensore destro:   VCC -> 3V3, GND -> GND, DO -> GPIO42
# Pista: nastro isolante nero (2 cm) su pavimento chiaro. I sensori a 1 cm da terra, ai lati della linea.
from machine import Pin, PWM
import asyncio


class Motore:
    def __init__(self, a, b):
        self.a = PWM(Pin(a), freq=1000, duty_u16=0)
        self.b = PWM(Pin(b), freq=1000, duty_u16=0)

    def vai(self, v):
        v = max(-100, min(100, int(v)))
        d = abs(v) * 65535 // 100
        self.a.duty_u16(d if v > 0 else 0)
        self.b.duty_u16(d if v < 0 else 0)

    def spegni(self):
        self.a.deinit()
        self.b.deinit()


sx, dx = Motore(21, 47), Motore(14, 1)
s_sx, s_dx = Pin(41, Pin.IN), Pin(42, Pin.IN)
attivo = False
vel = 45
nero = 1          # valore che il sensore da' sul nero (alcuni moduli danno 0)


def on_attivo(v):
    global attivo
    attivo = bool(v)
    if not attivo:
        sx.vai(0)
        dx.vai(0)


def on_vel(v):
    global vel
    vel = int(v)


def on_inverti(v):
    global nero
    nero = 0 if v else 1


async def main(lab):
    lab.on('attivo', on_attivo)
    lab.on('vel', on_vel)
    lab.on('inverti', on_inverti)
    conta = 0
    try:
        while True:
            l = s_sx.value() == nero
            r = s_dx.value() == nero
            if conta % 5 == 0:
                lab.send('sx', int(l))
                lab.send('dx', int(r))
            conta += 1
            if attivo:
                if l and not r:          # la linea e' a sinistra: giro a sinistra
                    sx.vai(-vel // 2)
                    dx.vai(vel)
                elif r and not l:        # la linea e' a destra
                    sx.vai(vel)
                    dx.vai(-vel // 2)
                else:                    # linea in mezzo (o incrocio): dritto
                    sx.vai(vel)
                    dx.vai(vel)
            await asyncio.sleep_ms(10)
    finally:
        sx.spegni()
        dx.spegni()
