# Buzzer passivo: note e melodie
# Buzzer passivo: + a GPIO14, - a GND
from machine import Pin, PWM
import asyncio

bz = PWM(Pin(14), freq=440, duty_u16=0)
VOL = 2000   # duty basso = volume piu' basso

NOTE = {'C4': 262, 'D4': 294, 'E4': 330, 'F4': 349, 'G4': 392, 'A4': 440, 'B4': 494,
        'C5': 523, 'D5': 587, 'E5': 659, 'F5': 698, 'G5': 784, 'R': 0}
MELODIE = {
    'fra_martino': 'C4 D4 E4 C4 C4 D4 E4 C4 E4 F4 G4 R E4 F4 G4 R',
    'tanti_auguri': 'C4 C4 D4 C4 F4 E4 R C4 C4 D4 C4 G4 F4 R',
    'scala': 'C4 D4 E4 F4 G4 A4 B4 C5',
}
coda = []


def suona(f):
    if f:
        bz.freq(int(f))
        bz.duty_u16(VOL)
    else:
        bz.duty_u16(0)


def on_nota(v):        # dal pianoforte della PWA
    coda.append(int(v))


def on_melodia(v):
    for n in MELODIE.get(v, '').split():
        coda.append(NOTE[n])


async def main(lab):
    lab.on('nota', on_nota)
    lab.on('melodia', on_melodia)
    try:
        while True:
            if coda:
                f = coda.pop(0)
                lab.send('hz', f)
                suona(f)
                await asyncio.sleep_ms(250)
                suona(0)
                await asyncio.sleep_ms(40)
            else:
                await asyncio.sleep_ms(20)
    finally:
        bz.deinit()
