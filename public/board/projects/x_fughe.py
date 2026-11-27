# Sensore di allagamento e di gas/fumo con allarme sonoro e notifica sul telefono
# Sensore livello acqua del kit: S -> GPIO1, + -> GPIO42 (acceso solo durante la misura), - -> GND
# Sensore gas MQ-2: VCC -> 5V, GND -> GND, AO -> 1 kohm -> GPIO3 -> 2 kohm -> GND (partitore: max 3,3 V)
# Buzzer passivo: + -> GPIO14, - -> GND
#
# ATTENZIONE: e' un progetto didattico. Non sostituisce un rilevatore di gas certificato
# (norma UNI EN 50194), obbligatorio dove ci sono caldaia o fornelli a gas.
from machine import Pin, ADC, PWM
import neopixel, asyncio, time, json

FILE = 'fughe.json'
CFG = {'soglia_acqua': 15, 'soglia_gas': 12}
PRERISCALDO = 120                 # secondi: l'MQ-2 deve scaldarsi prima di dare valori stabili

acqua = ADC(Pin(1))
acqua.atten(ADC.ATTN_11DB)
acqua_on = Pin(42, Pin.OUT, value=0)
gas = ADC(Pin(3))
gas.atten(ADC.ATTN_11DB)
bz = PWM(Pin(14), freq=2500, duty_u16=0)
np = neopixel.NeoPixel(Pin(48), 1)

S = {'base': None, 'tacita': 0, 'acqua': False, 'gas': False, 'ntp': False}
EVENTI = []
modificato = [0]


def media(adc, n=16):
    t = 0
    for _ in range(n):
        t += adc.read_u16()
    return t / n * 100 / 65535


async def leggi_acqua():
    acqua_on.value(1)             # alimento il sensore solo per un attimo: si corrode meno
    await asyncio.sleep_ms(10)
    v = media(acqua)
    acqua_on.value(0)
    return v


def ora_italia():
    t = time.time()
    y = time.localtime(t)[0]

    def ultima_domenica(mese):
        for g in range(31, 24, -1):
            s = time.mktime((y, mese, g, 1, 0, 0, 0, 0))
            if time.localtime(s)[6] == 6:
                return s
    legale = ultima_domenica(3) <= t < ultima_domenica(10)
    return time.localtime(t + (7200 if legale else 3600))


def evento(lab, testo):
    if S['ntp']:
        o = ora_italia()
        testo = '%02d/%02d %02d:%02d – %s' % (o[2], o[1], o[3], o[4], testo)
    EVENTI.append(testo)
    if len(EVENTI) > 10:
        EVENTI.pop(0)
    lab.log(testo)
    lab.send('eventi', ' | '.join(reversed(EVENTI[-3:])))


def on_soglia(k):
    def fn(v):
        CFG[k] = int(v)
        modificato[0] = time.ticks_ms() or 1
    return fn


def on_tacita(v):
    S['tacita'] = time.ticks_add(time.ticks_ms(), 600000)      # 10 minuti di silenzio


async def orologio(lab):
    import ntptime
    while True:
        try:
            ntptime.settime()
            S['ntp'] = True
            await asyncio.sleep(6 * 3600)
        except Exception:
            await asyncio.sleep(30)


async def main(lab):
    try:
        with open(FILE) as f:
            CFG.update(json.load(f))
    except Exception:
        pass
    lab.on('soglia_acqua', on_soglia('soglia_acqua'))
    lab.on('soglia_gas', on_soglia('soglia_gas'))
    lab.on('tacita', on_tacita)
    prova = []
    lab.on('prova', lambda v: prova.append(1))
    if await lab.wifi():
        asyncio.create_task(orologio(lab))
    else:
        lab.log('Senza Internet niente notifiche sul telefono: suona solo il buzzer')
    avvio = time.ticks_ms()
    lab.log('MQ-2 in preriscaldamento per %d secondi (la prima volta meglio lasciarlo acceso qualche ora)' % PRERISCALDO)
    avviso = {'acqua': None, 'gas': None}
    t = 0
    try:
        while True:
            t += 1
            ora = time.ticks_ms()
            a = await leggi_acqua()
            g = media(gas)
            pronto = time.ticks_diff(ora, avvio) > PRERISCALDO * 1000
            # base del gas: si adatta piano piano all'aria pulita, ma non a una fuga
            if pronto:
                if S['base'] is None:
                    S['base'] = g
                    evento(lab, 'MQ-2 pronto: aria pulita al %.0f%%' % g)
                elif g < S['base'] + 3:
                    S['base'] += (g - S['base']) * 0.002
            sopra = 0 if S['base'] is None else max(0, g - S['base'])
            nuovo = {'acqua': a >= CFG['soglia_acqua'], 'gas': pronto and sopra >= CFG['soglia_gas']}
            for k, testo in (('acqua', 'Acqua sul pavimento!'), ('gas', 'Gas o fumo nell’aria!')):
                if nuovo[k] and not S[k]:
                    evento(lab, testo)
                if not nuovo[k] and S[k]:
                    evento(lab, 'Fine allarme ' + k)
                if nuovo[k]:
                    # notifica subito, poi ogni 10 minuti finche' dura
                    if avviso[k] is None or time.ticks_diff(ora, avviso[k]) > 600000:
                        if lab.notifica(testo, 'Acqua %.0f%% · gas +%.0f sopra l’aria pulita' % (a, sopra)):
                            avviso[k] = ora
                else:
                    avviso[k] = None
                S[k] = nuovo[k]
            allarme = S['acqua'] or S['gas']
            muto = S['tacita'] and time.ticks_diff(S['tacita'], ora) > 0
            if prova:
                prova.clear()
                evento(lab, 'Prova allarme')
                lab.notifica('Prova', 'Le notifiche del sensore di fughe funzionano')
                for f in (2500, 0, 2500, 0):
                    bz.freq(2500)
                    bz.duty_u16(30000 if f else 0)
                    await asyncio.sleep_ms(200)
            # buzzer e LED
            if allarme and not muto:
                bz.freq(2500 if S['gas'] else 1500)
                bz.duty_u16(30000 if t % 2 else 0)
            else:
                bz.duty_u16(0)
            if allarme:
                np[0] = (120, 0, 0) if t % 2 else ((0, 0, 120) if S['acqua'] else (60, 30, 0))
            else:
                np[0] = (0, 10, 0) if pronto else (20, 12, 0)
            np.write()
            if t % 4 == 0:
                lab.send('acqua', round(a))
                lab.send('gas', round(sopra) if pronto else 'riscaldamento…')
                lab.send('allarme_acqua', S['acqua'])
                lab.send('allarme_gas', S['gas'])
                lab.send('stato', ('ALLARME ' + ' e '.join(k for k in ('acqua', 'gas') if S[k]) + (' (silenziato)' if muto else ''))
                         if allarme else ('Tutto a posto' if pronto else 'MQ-2 in preriscaldamento'))
            if modificato[0] and time.ticks_diff(ora, modificato[0]) > 5000:
                modificato[0] = 0
                with open(FILE, 'w') as f:
                    json.dump(CFG, f)
            await asyncio.sleep_ms(500)
    finally:
        bz.duty_u16(0)
        acqua_on.value(0)
        np[0] = (0, 0, 0)
        np.write()
