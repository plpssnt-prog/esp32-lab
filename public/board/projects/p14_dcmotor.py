# Motore DC con il driver L293D (+ ventola)
# L293D: pin1 (EN1) -> 5V, pin2 (IN1) -> GPIO21, pin3 (OUT1) -> motore,
#        pin4/5 -> GND, pin6 (OUT2) -> motore, pin7 (IN2) -> GPIO47,
#        pin8 (alim. motore) -> 5V modulo, pin16 (logica) -> 5V modulo
# Mai collegare il motore direttamente ai pin dell'ESP32!
from machine import Pin, PWM
import asyncio

in1 = PWM(Pin(21), freq=1000, duty_u16=0)
in2 = PWM(Pin(47), freq=1000, duty_u16=0)
vel = 0   # -100..100 (negativo = indietro)


def applica(v):
    d = abs(v) * 65535 // 100
    if v >= 0:
        in2.duty_u16(0)
        in1.duty_u16(d)
    else:
        in1.duty_u16(0)
        in2.duty_u16(d)


def on_vel(v):
    global vel
    vel = max(-100, min(100, int(v)))
    applica(vel)


def on_stop(v):
    on_vel(0)


async def main(lab):
    lab.on('vel', on_vel)
    lab.on('stop', on_stop)
    try:
        while True:
            lab.send('stato', 'avanti' if vel > 0 else 'indietro' if vel < 0 else 'fermo')
            await asyncio.sleep_ms(400)
    finally:
        in1.deinit()
        in2.deinit()
        Pin(21, Pin.OUT).value(0)
        Pin(47, Pin.OUT).value(0)
