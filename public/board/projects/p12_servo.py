# Servomotore SG90
# Servo: marrone -> GND, rosso -> 5V (modulo di alimentazione), arancione -> GPIO42
# IMPORTANTE: GND del modulo di alimentazione collegato al GND dell'ESP32
from machine import Pin, PWM
import asyncio

servo = PWM(Pin(42), freq=50)
angolo = 90
sweep = False


def vai(a):
    # 0 gradi = impulso 0,5 ms ; 180 gradi = 2,5 ms (ogni 20 ms)
    a = max(0, min(180, int(a)))
    servo.duty_ns(500000 + a * 2000000 // 180)
    return a


def on_angolo(v):
    global angolo, sweep
    sweep = False
    angolo = vai(v)


def on_sweep(v):
    global sweep
    sweep = bool(v)


async def main(lab):
    global angolo
    lab.on('angolo', on_angolo)
    lab.on('sweep', on_sweep)
    vai(angolo)
    passo = 3
    try:
        while True:
            if sweep:
                angolo += passo
                if angolo >= 180 or angolo <= 0:
                    passo = -passo
                angolo = vai(angolo)
                lab.send('gradi', angolo)
                await asyncio.sleep_ms(30)
            else:
                lab.send('gradi', angolo)
                await asyncio.sleep_ms(250)
    finally:
        servo.deinit()
