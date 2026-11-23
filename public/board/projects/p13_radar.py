# Radar: servo + sensore a ultrasuoni
# Servo: segnale -> GPIO42 (alimentazione 5V dal modulo)
# HC-SR04 fissato sopra il servo: TRIG -> GPIO41, ECHO -> partitore 1k/2k -> GPIO40, VCC 5V
from machine import Pin, PWM, time_pulse_us
import time, asyncio

servo = PWM(Pin(42), freq=50)
trig = Pin(41, Pin.OUT, value=0)
echo = Pin(40, Pin.IN)
attivo = True


def vai(a):
    servo.duty_ns(500000 + a * 2000000 // 180)


def misura_cm():
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 25000)
    return -1 if t < 0 else round(t / 58)


def on_attivo(v):
    global attivo
    attivo = bool(v)


async def main(lab):
    lab.on('attivo', on_attivo)
    a, passo = 15, 3
    try:
        while True:
            if attivo:
                vai(a)
                await asyncio.sleep_ms(35)     # tempo per far arrivare il servo
                lab.send('radar', {'a': a, 'd': misura_cm()})
                a += passo
                if a >= 165 or a <= 15:
                    passo = -passo
            else:
                await asyncio.sleep_ms(200)
    finally:
        servo.deinit()
