# Sensore di distanza a ultrasuoni HC-SR04 (sensore di parcheggio)
# HC-SR04: VCC -> 5V (modulo alimentazione), GND -> GND, TRIG -> GPIO41
# ECHO -> resistenza 1k -> GPIO40 ; GPIO40 -> resistenza 2k -> GND  (partitore: 5V -> 3,3V)
# Buzzer passivo opzionale: + -> GPIO14, - -> GND
from machine import Pin, PWM, time_pulse_us
import time, asyncio

trig = Pin(41, Pin.OUT, value=0)
echo = Pin(40, Pin.IN)
bz = PWM(Pin(14), freq=2000, duty_u16=0)
suono = True


def misura_cm():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 30000)   # durata dell'eco in microsecondi
    if t < 0:
        return None                     # nessun eco (oltre ~5 m)
    return round(t / 58, 1)             # suono: andata e ritorno -> diviso 58


def on_suono(v):
    global suono
    suono = bool(v)


async def main(lab):
    lab.on('suono', on_suono)
    t_bip = 0
    try:
        while True:
            d = misura_cm()
            lab.send('cm', d if d is not None else -1)
            ora = time.ticks_ms()
            if suono and d is not None and d < 50:
                # piu' sei vicino, piu' i bip sono frequenti
                intervallo = max(60, int(d * 12))
                if time.ticks_diff(ora, t_bip) > intervallo:
                    t_bip = ora
                    bz.duty_u16(3000)
                    await asyncio.sleep_ms(40)
                    bz.duty_u16(0)
            await asyncio.sleep_ms(60)
    finally:
        bz.deinit()
