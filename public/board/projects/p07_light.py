# Fotoresistenza e luce notturna automatica
# 3V3 -> fotoresistenza -> GPIO1 -> resistenza 10k -> GND
# Il LED blu integrato (GPIO2) si accende quando e' buio
from machine import Pin, ADC
import asyncio

adc = ADC(Pin(1))
adc.atten(ADC.ATTN_11DB)
led = Pin(2, Pin.OUT)
soglia = 30   # sotto questa percentuale di luce accendo il LED


def on_soglia(v):
    global soglia
    soglia = int(v)


async def main(lab):
    lab.on('soglia', on_soglia)
    try:
        while True:
            # media di 8 letture per un valore piu' stabile
            s = 0
            for _ in range(8):
                s += adc.read_u16()
            luce = s // 8 * 100 // 65535
            led.value(1 if luce < soglia else 0)
            lab.send('luce', luce)
            lab.send('led', led.value())
            await asyncio.sleep_ms(250)
    finally:
        led.value(0)
