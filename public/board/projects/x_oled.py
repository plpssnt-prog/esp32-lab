# Display OLED 0,96" (SSD1306, I2C) con temperatura e messaggi dal telefono
# OLED: VCC -> 3V3, GND -> GND, SDA -> GPIO21, SCL -> GPIO47
# DHT11 (facoltativo): S -> GPIO39, + -> 3V3, - -> GND
from machine import Pin, I2C
import framebuf, dht, asyncio


class OLED(framebuf.FrameBuffer):
    """Driver minimo SSD1306 128x64."""
    def __init__(self, i2c, w=128, h=64, addr=0x3C):
        self.i2c, self.addr, self.w, self.h = i2c, addr, w, h
        self.buf = bytearray(w * h // 8)
        super().__init__(self.buf, w, h, framebuf.MONO_VLSB)
        for c in (0xAE, 0x20, 0x00, 0x40, 0xA1, 0xA8, h - 1, 0xC8, 0xD3, 0x00,
                  0xDA, 0x12, 0xD5, 0x80, 0xD9, 0xF1, 0xDB, 0x30, 0x81, 0xCF,
                  0xA4, 0xA6, 0x8D, 0x14, 0xAF):
            self.cmd(c)

    def cmd(self, c):
        self.i2c.writeto(self.addr, bytes((0x80, c)))

    def show(self):
        for c in (0x21, 0, self.w - 1, 0x22, 0, self.h // 8 - 1):
            self.cmd(c)
        self.i2c.writevto(self.addr, (b'\x40', self.buf))


i2c = I2C(0, sda=Pin(21), scl=Pin(47), freq=400000)
sens = dht.DHT11(Pin(39))
messaggio = 'Ciao Paolo!'
schermo = None


def on_testo(v):
    global messaggio
    messaggio = str(v)[:40]


async def main(lab):
    global schermo
    trovati = i2c.scan()
    lab.log('Dispositivi I2C trovati:', [hex(a) for a in trovati])
    if 0x3C not in trovati and 0x3D not in trovati:
        lab.log('OLED non trovato: controlla SDA/SCL e alimentazione')
        return
    schermo = OLED(i2c, addr=0x3C if 0x3C in trovati else 0x3D)
    lab.on('testo', on_testo)
    x = 128
    t = h = None
    conta = 0
    try:
        while True:
            if conta % 40 == 0:                 # ogni 2 secondi leggo il DHT11
                try:
                    sens.measure()
                    t, h = sens.temperature(), sens.humidity()
                    lab.send('temp', t)
                except OSError:
                    pass
            conta += 1
            s = schermo
            s.fill(0)
            s.text('ESP32 Lab', 28, 0)
            s.hline(0, 10, 128, 1)
            if t is not None:
                s.text('Temp: %d C' % t, 0, 18)
                s.text('Umid: %d %%' % h, 0, 30)
            else:
                s.text('DHT11 assente', 0, 24)
            s.text(messaggio, x, 50)            # scritta che scorre
            x -= 2
            if x < -8 * len(messaggio):
                x = 128
            s.show()
            await asyncio.sleep_ms(50)
    finally:
        if schermo:
            schermo.cmd(0xAE)                    # spegne il display
