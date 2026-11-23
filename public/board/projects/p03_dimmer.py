# Dimmer: luminosita' di un LED esterno con il PWM
# GPIO21 -> resistenza 220 ohm -> LED (gamba lunga) ; gamba corta -> GND
from machine import Pin, PWM
import asyncio

led = PWM(Pin(21), freq=1000, duty_u16=0)
livello = 50
effetto = False


def applica():
    # la vista umana non e' lineare: usiamo il quadrato per una regolazione piu' naturale
    led.duty_u16(livello * livello * 65535 // 10000)


def on_livello(v):
    global livello
    livello = int(v)
    applica()


def on_effetto(v):
    global effetto
    effetto = bool(v)


async def main(lab):
    global livello
    lab.on('livello', on_livello)
    lab.on('effetto', on_effetto)
    applica()
    su = True
    try:
        while True:
            if effetto:   # dissolvenza automatica
                livello += 2 if su else -2
                if livello >= 100:
                    livello, su = 100, False
                elif livello <= 0:
                    livello, su = 0, True
                applica()
                lab.send('pct', livello)
                await asyncio.sleep_ms(30)
            else:
                lab.send('pct', livello)
                await asyncio.sleep_ms(300)
    finally:
        led.deinit()
        Pin(21, Pin.OUT).value(0)
