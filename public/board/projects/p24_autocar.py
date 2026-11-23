# Macchinina che evita gli ostacoli
# Come la macchinina telecomandata, piu':
#   HC-SR04 sul davanti, montato sul servo: TRIG -> GPIO41, ECHO -> partitore 1k/2k -> GPIO40, VCC 5V
#   Servo: segnale -> GPIO42 (5V dal modulo o dal 5V del L298N)
from machine import Pin, PWM, time_pulse_us
import time, asyncio


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
servo = PWM(Pin(42), freq=50)
trig = Pin(41, Pin.OUT, value=0)
echo = Pin(40, Pin.IN)
attivo = False
vel = 55
distanza_min = 25


def guarda(a):
    servo.duty_ns(500000 + a * 2000000 // 180)


def cm():
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 25000)
    return 400 if t < 0 else t / 58


def ferma():
    sx.vai(0)
    dx.vai(0)


def on_attivo(v):
    global attivo
    attivo = bool(v)
    if not attivo:
        ferma()


def on_vel(v):
    global vel
    vel = int(v)


def on_dist(v):
    global distanza_min
    distanza_min = int(v)


async def main(lab):
    lab.on('attivo', on_attivo)
    lab.on('vel', on_vel)
    lab.on('dist', on_dist)
    guarda(90)
    try:
        while True:
            d = cm()
            lab.send('cm', round(d))
            if not attivo:
                await asyncio.sleep_ms(200)
                continue
            if d > distanza_min:
                sx.vai(vel)
                dx.vai(vel)
                lab.send('azione', 'avanti')
                await asyncio.sleep_ms(60)
                continue
            # ostacolo: fermati, indietreggia, guarda a destra e a sinistra
            ferma()
            lab.send('azione', 'ostacolo!')
            sx.vai(-vel)
            dx.vai(-vel)
            await asyncio.sleep_ms(300)
            ferma()
            guarda(20)
            await asyncio.sleep_ms(350)
            destra = cm()
            guarda(160)
            await asyncio.sleep_ms(450)
            sinistra = cm()
            guarda(90)
            await asyncio.sleep_ms(250)
            if sinistra > destra:
                lab.send('azione', 'giro a sinistra')
                sx.vai(-vel)
                dx.vai(vel)
            else:
                lab.send('azione', 'giro a destra')
                sx.vai(vel)
                dx.vai(-vel)
            await asyncio.sleep_ms(350)
            ferma()
    finally:
        sx.spegni()
        dx.spegni()
        servo.deinit()
