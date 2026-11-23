# Potenziometro: leggere un valore analogico
# Potenziometro: piedino esterno 1 -> 3V3, piedino esterno 2 -> GND, centrale -> GPIO1
from machine import Pin, ADC
import asyncio

adc = ADC(Pin(1))
adc.atten(ADC.ATTN_11DB)   # misura tutto l'intervallo 0..3,3 V


async def main(lab):
    while True:
        grezzo = adc.read_u16()             # 0..65535
        pct = grezzo * 100 // 65535
        lab.send('pct', pct)
        lab.send('volt', round(adc.read_uv() / 1000000, 2))
        await asyncio.sleep_ms(150)
