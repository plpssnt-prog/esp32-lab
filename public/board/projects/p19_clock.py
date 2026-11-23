# Orologio da Internet (NTP) con sveglia
# Buzzer passivo: + -> GPIO14, - -> GND. LED RGB integrato per il lampeggio.
from machine import Pin, PWM, RTC
import neopixel, time, asyncio

bz = PWM(Pin(14), freq=1000, duty_u16=0)
np = neopixel.NeoPixel(Pin(48), 1)
sveglia = None      # (ore, minuti)
suona = False


def ora_italia():
    # l'RTC e' in UTC: aggiungo 1 ora (CET) o 2 ore (ora legale CEST)
    t = time.time()
    y = time.localtime(t)[0]

    def ultima_domenica(mese):
        # ultima domenica del mese alle 01:00 UTC
        for g in range(31, 24, -1):
            s = time.mktime((y, mese, g, 1, 0, 0, 0, 0))
            if time.localtime(s)[6] == 6:
                return s
    legale = ultima_domenica(3) <= t < ultima_domenica(10)
    return time.localtime(t + (7200 if legale else 3600))


def on_sveglia(v):
    global sveglia
    try:
        h, m = v.split(':')
        sveglia = (int(h), int(m))
    except Exception:
        sveglia = None


def on_spegni(v):
    global suona
    suona = False


async def main(lab):
    global suona
    lab.on('sveglia', on_sveglia)
    lab.on('spegni', on_spegni)
    if not await lab.wifi():
        return
    import ntptime
    for _ in range(3):
        try:
            ntptime.settime()
            break
        except Exception:
            await asyncio.sleep(2)
    lab.log('Ora sincronizzata da Internet')
    ultimo = None
    try:
        while True:
            t = ora_italia()
            lab.send('ora', '%02d:%02d:%02d' % (t[3], t[4], t[5]))
            lab.send('data', '%02d/%02d/%04d' % (t[2], t[1], t[0]))
            if sveglia and (t[3], t[4]) == sveglia and ultimo != t[4]:
                ultimo = t[4]
                suona = True
                lab.log('Sveglia!')
            if suona:
                for f in (880, 0, 880, 0):
                    bz.freq(f or 880)
                    bz.duty_u16(3000 if f else 0)
                    np[0] = (60, 0, 0) if f else (0, 0, 0)
                    np.write()
                    await asyncio.sleep_ms(120)
                await asyncio.sleep_ms(500)
            else:
                bz.duty_u16(0)
                await asyncio.sleep_ms(1000)
    finally:
        bz.deinit()
        np[0] = (0, 0, 0)
        np.write()
