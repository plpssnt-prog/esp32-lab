# Blink: il LED integrato lampeggia
# Collegamenti: nessuno (LED blu sulla scheda, GPIO2)
from machine import Pin
import asyncio

led = Pin(2, Pin.OUT)
attivo = True
pausa = 500  # millisecondi


def on_attivo(v):
    global attivo
    attivo = bool(v)


def on_pausa(v):
    global pausa
    pausa = int(v)


async def main(lab):
    lab.on('attivo', on_attivo)
    lab.on('pausa', on_pausa)
    lab.log('Blink avviato')
    try:
        while True:
            if attivo:
                led.value(not led.value())   # inverte lo stato del LED
            else:
                led.value(0)
            lab.send('led', led.value())
            await asyncio.sleep_ms(pausa)
    finally:
        led.value(0)
