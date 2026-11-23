# ESP32 Lab - runtime della scheda (main.py)
# Si installa una volta sola dalla pagina "Scheda" della PWA.
# Avvia il Bluetooth (BLE), ascolta i comandi della PWA via BLE o USB
# ed esegue il progetto caricato (app.py).
# Avvio sicuro: tieni premuto BOOT subito dopo il reset per saltare il runtime.

import sys, gc, os, json, time, machine, binascii
import asyncio

VER = '1.0'
CFG = 'lab.json'
NUS = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
NUS_TX = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'
NUS_RX = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'


def _load():
    try:
        with open(CFG) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(c):
    with open(CFG, 'w') as f:
        json.dump(c, f)


def _unq(s):
    s = s.replace('+', ' ')
    out = bytearray()
    i = 0
    b = s.encode()
    while i < len(b):
        if b[i] == 37 and i + 3 <= len(b):
            try:
                out.append(int(b[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(b[i])
        i += 1
    return out.decode()


class BLEUart:
    def __init__(self, name):
        import bluetooth
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        try:
            self.ble.config(gap_name=name)
            self.ble.config(mtu=247)
        except Exception:
            pass
        U = bluetooth.UUID
        svc = (U(NUS), (
            (U(NUS_TX), bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
            (U(NUS_RX), bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE),
        ))
        ((self.tx, self.rx),) = self.ble.gatts_register_services((svc,))
        self.ble.gatts_set_buffer(self.rx, 512, True)
        self.name = name
        self.conns = {}
        self.buf = b''
        self.pending = []
        self.ble.irq(self._irq)
        self.adv()

    def adv(self):
        n = self.name.encode()[:26]
        self.ble.gap_advertise(100000, adv_data=bytes((2, 1, 6, len(n) + 1, 9)) + n)

    def _irq(self, ev, data):
        if ev == 1:  # connessione
            self.conns[data[0]] = 23
            try:
                self.ble.gattc_exchange_mtu(data[0])
            except Exception:
                pass
        elif ev == 2:  # disconnessione
            self.conns.pop(data[0], None)
            self.buf = b''
            self.adv()
        elif ev == 3:  # scrittura dalla PWA
            if data[1] == self.rx:
                self.buf += self.ble.gatts_read(self.rx)
                while b'\n' in self.buf:
                    line, self.buf = self.buf.split(b'\n', 1)
                    self.pending.append(line)
        elif ev == 21:  # MTU negoziato
            self.conns[data[0]] = data[1]

    def mtu(self):
        return max(self.conns.values()) if self.conns else 23

    def send(self, b):
        for c, m in list(self.conns.items()):
            n = max(20, m - 3)
            for i in range(0, len(b), n):
                for _ in range(30):
                    try:
                        self.ble.gatts_notify(c, self.tx, b[i:i + n])
                        break
                    except OSError:
                        time.sleep_ms(5)


async def reply(w, body, ctype='text/html; charset=utf-8', status='200 OK'):
    """Risposta HTTP semplice (per i progetti Wi-Fi)."""
    if isinstance(body, str):
        body = body.encode()
    w.write(('HTTP/1.0 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
             'Cache-Control: no-store\r\nAccess-Control-Allow-Origin: *\r\n\r\n'
             % (status, ctype, len(body))).encode())
    w.write(body)
    await w.drain()


class Lab:
    def __init__(self):
        self.cfg = _load()
        self.name = self.cfg.get('name') or 'ESP32-Lab'
        self.handlers = {}
        self.task = None
        self.server = None
        self.ip = None
        self.usb = False
        self.running = False
        self.ble = None
        self.reply = reply
        try:
            self.ble = BLEUart(self.name)
        except Exception as e:
            print('BLE non disponibile:', e)

    # ---------- API per i progetti ----------
    def on(self, name, fn):
        """Registra la funzione chiamata quando la PWA invia il comando 'name'."""
        self.handlers[name] = fn

    def send(self, key, value):
        """Invia un valore alla PWA (aggiorna il widget collegato a 'key')."""
        self._out({'t': 'k', 'k': key, 'v': value})

    def log(self, *a):
        m = ' '.join(str(x) for x in a)
        if not self.usb:
            print(m)
        self._out({'t': 'log', 'm': m})

    async def wifi(self, timeout=15):
        """Collega il Wi-Fi salvato e restituisce l'IP (o None)."""
        if self.ip:
            return self.ip
        ssid = self.cfg.get('ssid')
        if not ssid:
            self.log('Wi-Fi non configurato: impostalo nella pagina Scheda della PWA')
            return None
        import network
        w = network.WLAN(network.STA_IF)
        w.active(True)
        if not w.isconnected():
            try:
                w.connect(ssid, self.cfg.get('pw', ''))
            except OSError:
                pass
            for _ in range(timeout * 4):
                if w.isconnected():
                    break
                await asyncio.sleep_ms(250)
        if w.isconnected():
            self.ip = w.ifconfig()[0]
            self._out({'t': 'ip', 'ip': self.ip})
            return self.ip
        self.log('Wi-Fi: connessione non riuscita a', ssid)
        return None

    async def serve(self, handler, port=80):
        """Avvia un server web. handler(path, query, writer) e' una funzione async."""
        async def cb(r, w):
            try:
                line = await r.readline()
                if not line:
                    return
                parts = line.decode().split(' ')
                path = parts[1] if len(parts) > 1 else '/'
                while True:
                    h = await r.readline()
                    if not h or h == b'\r\n':
                        break
                q = {}
                if '?' in path:
                    path, qs = path.split('?', 1)
                    for kv in qs.split('&'):
                        if '=' in kv:
                            k, v = kv.split('=', 1)
                            q[k] = _unq(v)
                await handler(path, q, w)
            except Exception:
                pass
            finally:
                try:
                    w.close()
                    await w.wait_closed()
                except Exception:
                    pass
        self.server = await asyncio.start_server(cb, '0.0.0.0', port)
        self.log('Pagina web della scheda: http://%s/' % self.ip)
        self._out({'t': 'web', 'url': 'http://%s/' % self.ip})

    # ---------- interni ----------
    def _out(self, d):
        try:
            s = json.dumps(d)
        except Exception:
            return
        if self.ble and self.ble.conns:
            self.ble.send(s.encode() + b'\n')
        if self.usb:
            print('@@' + s)

    def _err(self, e):
        import io
        s = io.StringIO()
        sys.print_exception(e, s)
        self._out({'t': 'err', 'm': s.getvalue()})
        if not self.usb:
            sys.print_exception(e)

    def _state(self):
        self._out({'t': 'state', 'run': self.running,
                   'id': self.cfg.get('app_id'), 'app': self.cfg.get('app_name')})

    def _info(self):
        try:
            import camera  # noqa
            cam = True
        except ImportError:
            cam = False
        gc.collect()
        self._out({'t': 'info', 'ver': VER, 'name': self.name,
                   'id': self.cfg.get('app_id'), 'app': self.cfg.get('app_name'),
                   'run': self.running, 'ip': self.ip, 'ssid': self.cfg.get('ssid'),
                   'mtu': self.ble.mtu() if self.ble else 0,
                   'mem': gc.mem_free(), 'cam': cam,
                   'mp': sys.version, 'board': sys.implementation._machine})

    async def start(self):
        await self.stop()
        self.handlers = {}
        gc.collect()
        try:
            os.stat('app.py')
        except OSError:
            self.log('Nessun progetto caricato: scegline uno nella PWA')
            return
        try:
            sys.modules.pop('app', None)
            mod = __import__('app')
        except Exception as e:
            self._err(e)
            return
        self.task = asyncio.create_task(self._run(mod))

    async def _run(self, mod):
        self.running = True
        self._state()
        try:
            await mod.main(self)
            self.log('Progetto terminato')
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._err(e)
        finally:
            self.running = False
            self.handlers = {}
            self._state()

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except BaseException:
                pass
            self.task = None
        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
            except Exception:
                pass
            self.server = None
        gc.collect()

    async def handle(self, line, src):
        try:
            await self._handle(line, src)
        except Exception as e:   # un comando sbagliato non deve fermare il runtime
            self._err(e)

    async def _handle(self, line, src):
        try:
            d = json.loads(line)
        except Exception:
            return
        t = d.get('t')
        if src == 'usb':
            self.usb = True
        if t == 'hello':
            self._info()
        elif t == 'c':
            fn = self.handlers.get(d.get('c'))
            if fn:
                try:
                    r = fn(d.get('v'))
                    if hasattr(r, 'send'):
                        await r
                except Exception as e:
                    self._err(e)
        elif t == 'put':
            f = d.get('f', '')
            if '/' in f or f in ('main.py', 'boot.py', CFG) and not d.get('sys'):
                self._out({'t': 'err', 'm': 'File non consentito: ' + f})
                return
            o = d.get('o', 0)
            data = binascii.a2b_base64(d.get('d', ''))
            with open(f + '.tmp', 'wb' if o == 0 else 'ab') as fh:
                fh.write(data)
            if d.get('end'):
                try:
                    os.remove(f)
                except OSError:
                    pass
                os.rename(f + '.tmp', f)
            self._out({'t': 'ack', 'f': f, 'o': o + len(data)})
        elif t == 'meta':
            self.cfg['app_id'] = d.get('id')
            self.cfg['app_name'] = d.get('name')
            _save(self.cfg)
        elif t == 'run':
            await self.start()
        elif t == 'stop':
            await self.stop()
            self.running = False
            self._state()
        elif t == 'wifi':
            self.cfg['ssid'] = d.get('ssid', '')
            self.cfg['pw'] = d.get('pw', '')
            _save(self.cfg)
            self.ip = None
            try:
                import network
                network.WLAN(network.STA_IF).disconnect()
            except Exception:
                pass
            if self.cfg['ssid']:
                asyncio.create_task(self._wifi_info())
        elif t == 'name':
            self.cfg['name'] = (d.get('v') or 'ESP32-Lab')[:20]
            _save(self.cfg)
            self.log('Nome salvato: riavvio...')
            await asyncio.sleep_ms(300)
            machine.reset()
        elif t == 'reset':
            await asyncio.sleep_ms(200)
            machine.reset()

    async def _wifi_info(self):
        await self.wifi()
        self._info()

    async def usb_reader(self):
        import select
        p = select.poll()
        p.register(sys.stdin, select.POLLIN)
        b = ''
        while True:
            while p.poll(0):
                ch = sys.stdin.read(1)
                if ch == '\n' or ch == '\r':
                    if b.startswith('{'):
                        await self.handle(b, 'usb')
                    b = ''
                elif len(b) < 2048:
                    b += ch
            await asyncio.sleep_ms(20)

    async def loop(self):
        asyncio.create_task(self.usb_reader())
        if self.cfg.get('ssid'):
            asyncio.create_task(self.wifi())
        await self.start()
        while True:
            if self.ble and self.ble.pending:
                await self.handle(self.ble.pending.pop(0), 'ble')
            else:
                await asyncio.sleep_ms(10)


def run():
    if machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP).value() == 0:
        print('Avvio sicuro: runtime ESP32 Lab non avviato')
        return
    print('ESP32 Lab runtime', VER, '- Ctrl+C per la REPL')
    try:
        asyncio.run(Lab().loop())
    finally:
        asyncio.new_event_loop()


run()
