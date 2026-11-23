# Matrice LED 8x8 con MAX7219: disegna dal telefono
# Modulo MAX7219: VCC -> 5V, GND -> GND, DIN -> GPIO21, CS -> GPIO47, CLK -> GPIO14
from machine import Pin
import asyncio

din = Pin(21, Pin.OUT, value=0)
cs = Pin(47, Pin.OUT, value=1)
clk = Pin(14, Pin.OUT, value=0)
righe = [0] * 8
luce = 4

ICONE = {
    'cuore': [0x00, 0x66, 0xFF, 0xFF, 0x7E, 0x3C, 0x18, 0x00],
    'sorriso': [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C],
    'freccia': [0x18, 0x3C, 0x7E, 0xFF, 0x18, 0x18, 0x18, 0x18],
    'vuoto': [0] * 8,
}


def scrivi(reg, val):
    cs.value(0)
    for byte in (reg, val):
        for i in range(8):
            clk.value(0)
            din.value((byte >> (7 - i)) & 1)
            clk.value(1)
    cs.value(1)


def aggiorna():
    for r in range(8):
        scrivi(r + 1, righe[r])


def init():
    for reg, val in ((0x0F, 0), (0x09, 0), (0x0B, 7), (0x0A, luce), (0x0C, 1)):
        scrivi(reg, val)
    aggiorna()


def on_disegno(v):          # lista di 8 numeri (una riga ciascuno)
    global righe
    righe = [int(x) & 0xFF for x in v][:8]
    aggiorna()


def on_icona(v):
    on_disegno(ICONE.get(v, ICONE['vuoto']))


def on_luce(v):
    global luce
    luce = int(v)
    scrivi(0x0A, luce)


async def main(lab):
    lab.on('disegno', on_disegno)
    lab.on('icona', on_icona)
    lab.on('luce', on_luce)
    init()
    on_icona('cuore')
    lab.send('matrice', righe)
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        scrivi(0x0C, 0)   # spegne la matrice
