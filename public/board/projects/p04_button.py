# Pulsante: leggere un ingresso digitale
# Pulsante: un piedino a GPIO47, quello opposto (in diagonale) a GND
# Usiamo la resistenza di pull-up interna: non premuto = 1, premuto = 0
from machine import Pin
import asyncio

btn = Pin(47, Pin.IN, Pin.PULL_UP)
led = Pin(2, Pin.OUT)
conteggio = 0
modo = 'tieni'   # 'tieni' = LED acceso finche' premi, 'interruttore' = ogni pressione cambia


def on_modo(v):
    global modo
    modo = v


def on_azzera(v):
    global conteggio
    conteggio = 0


async def main(lab):
    global conteggio
    lab.on('modo', on_modo)
    lab.on('azzera', on_azzera)
    prima = 1
    try:
        while True:
            ora = btn.value()
            if prima == 1 and ora == 0:          # fronte di discesa = appena premuto
                conteggio += 1
                lab.send('conteggio', conteggio)
                if modo == 'interruttore':
                    led.value(not led.value())
            if modo == 'tieni':
                led.value(1 if ora == 0 else 0)
            if ora != prima:
                lab.send('premuto', 1 if ora == 0 else 0)
                lab.send('led', led.value())
            prima = ora
            await asyncio.sleep_ms(20)           # 20 ms bastano anche come anti-rimbalzo
    finally:
        led.value(0)
