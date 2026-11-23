# Motore passo-passo 28BYJ-48 con scheda ULN2003
# ULN2003: IN1 -> GPIO21, IN2 -> GPIO47, IN3 -> GPIO14, IN4 -> GPIO1
#          + -> 5V (modulo di alimentazione), - -> GND (comune con l'ESP32)
from machine import Pin
import asyncio

bobine = [Pin(p, Pin.OUT, value=0) for p in (21, 47, 14, 1)]
SEQ = [(1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0), (0, 1, 1, 0),
       (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1)]   # mezzo passo
PASSI_GIRO = 4096
richiesta = 0     # passi ancora da fare (+ orario, - antiorario)
ritardo = 2       # ms tra un passo e l'altro (piu' basso = piu' veloce, minimo ~1)
posizione = 0


def on_gradi(v):
    global richiesta
    richiesta += int(v) * PASSI_GIRO // 360


def on_vel(v):
    global ritardo
    ritardo = max(1, 6 - int(v))


def on_stop(v):
    global richiesta
    richiesta = 0


async def main(lab):
    global richiesta, posizione
    lab.on('gradi', on_gradi)
    lab.on('vel', on_vel)
    lab.on('stop', on_stop)
    fase = 0
    conta = 0
    try:
        while True:
            if richiesta:
                d = 1 if richiesta > 0 else -1
                fase = (fase + d) % 8
                for b, v in zip(bobine, SEQ[fase]):
                    b.value(v)
                richiesta -= d
                posizione += d
                conta += 1
                if conta % 64 == 0 or not richiesta:
                    lab.send('pos', round(posizione * 360 / PASSI_GIRO) % 360)
                await asyncio.sleep_ms(ritardo)
            else:
                for b in bobine:        # bobine spente: il motore non scalda
                    b.value(0)
                await asyncio.sleep_ms(50)
    finally:
        for b in bobine:
            b.value(0)
