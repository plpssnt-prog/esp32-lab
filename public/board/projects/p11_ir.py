# Telecomando a infrarossi (protocollo NEC, telecomando del kit Elegoo)
# Ricevitore IR: G/- -> GND, R/+ -> 3V3, Y/S (segnale) -> GPIO38
from machine import Pin
from array import array
import time, asyncio

ir = Pin(38, Pin.IN)
fronti = array('I', [0] * 80)
n = [0]

TASTI = {0x45: 'POWER', 0x46: 'VOL+', 0x47: 'FUNC/STOP', 0x44: '|<<', 0x40: '>||',
         0x43: '>>|', 0x07: 'GIU', 0x15: 'VOL-', 0x09: 'SU', 0x16: '0', 0x19: 'EQ',
         0x0D: 'ST/REPT', 0x0C: '1', 0x18: '2', 0x5E: '3', 0x08: '4', 0x1C: '5',
         0x5A: '6', 0x42: '7', 0x52: '8', 0x4A: '9'}


def fronte(p):     # interrupt: salva solo l'istante di ogni cambio di stato
    i = n[0]
    if i < 80:
        fronti[i] = time.ticks_us()
        n[0] = i + 1


def decodifica(k):
    d = [time.ticks_diff(fronti[i + 1], fronti[i]) for i in range(k - 1)]
    if len(d) < 3 or not 8000 < d[0] < 10000:
        return None
    if 1800 < d[1] < 2700:
        return 'ripeti'
    if not 3800 < d[1] < 5200 or len(d) < 66:
        return None
    codice = 0
    for b in range(32):
        if d[3 + 2 * b] > 1000:     # spazio lungo = bit 1
            codice |= 1 << b
    cmd = (codice >> 16) & 0xff
    if cmd ^ ((codice >> 24) & 0xff) != 0xff:
        return None
    return cmd


async def main(lab):
    ir.irq(fronte, Pin.IRQ_FALLING | Pin.IRQ_RISING, hard=True)
    ultimo = None
    try:
        while True:
            k = n[0]
            if k and time.ticks_diff(time.ticks_us(), fronti[k - 1]) > 20000:
                c = decodifica(k)
                n[0] = 0
                if c == 'ripeti' and ultimo is not None:
                    c = ultimo
                if isinstance(c, int):
                    ultimo = c
                    nome = TASTI.get(c, '?')
                    lab.send('tasto', nome)
                    lab.send('codice', '0x%02X' % c)
                    lab.log('Tasto', nome, '0x%02X' % c)
            await asyncio.sleep_ms(10)
    finally:
        ir.irq(handler=None)
