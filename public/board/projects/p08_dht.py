# Temperatura e umidita' con il DHT11
# Modulo DHT11: S (segnale) -> GPIO39, + -> 3V3, - -> GND
from machine import Pin
import dht, asyncio

sensore = dht.DHT11(Pin(39))


async def main(lab):
    while True:
        try:
            sensore.measure()
            t = sensore.temperature()
            h = sensore.humidity()
            lab.send('temp', t)
            lab.send('umid', h)
        except OSError:
            lab.log('DHT11 non risponde: controlla i collegamenti')
        await asyncio.sleep(2)     # il DHT11 non va letto piu' spesso di 1 volta al secondo
