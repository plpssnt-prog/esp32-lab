// Connessione alla scheda: Bluetooth (Web Bluetooth, Nordic UART) oppure USB (Web Serial / WebUSB)
// Protocollo: righe JSON. Via USB i messaggi della scheda iniziano con "@@".

const NUS = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
const NUS_RX = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'; // scriviamo qui
const NUS_TX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // notifiche dalla scheda

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const enc = new TextEncoder();

function b64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

export const support = {
  ble: 'bluetooth' in navigator,
  serial: 'serial' in navigator,
  usb: 'usb' in navigator,
};

export class Conn extends EventTarget {
  constructor() {
    super();
    this.kind = null;       // 'ble' | 'usb'
    this.info = null;       // ultimo messaggio info dalla scheda
    this.state = null;      // {run, id, app}
    this.busy = false;
    this._lineBuf = '';
    this._queue = Promise.resolve();
    this._pendingCoalesce = new Map();
    this._waiters = [];
    this._repl = false;
    this._replBuf = '';
  }

  get connected() { return !!this.kind; }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }

  // ---------------- Bluetooth ----------------
  async connectBLE() {
    if (!support.ble) throw new Error('Questo browser non supporta il Bluetooth web. Usa Chrome su Android o PC.');
    const dev = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: 'ESP32' }],
      optionalServices: [NUS],
    });
    this.emit('status', { text: 'Collegamento a ' + dev.name + '…' });
    const gatt = await dev.gatt.connect();
    const svc = await gatt.getPrimaryService(NUS);
    this._rx = await svc.getCharacteristic(NUS_RX);
    const tx = await svc.getCharacteristic(NUS_TX);
    const dec = new TextDecoder();
    tx.addEventListener('characteristicvaluechanged', (e) => {
      this._onText(dec.decode(e.target.value, { stream: true }), 'ble');
    });
    await tx.startNotifications();
    this._dev = dev;
    dev.addEventListener('gattserverdisconnected', () => this._closed('Bluetooth scollegato'));
    this.kind = 'ble';
    this.devName = dev.name;
    this.emit('status', { text: 'Collegato via Bluetooth' });
    await this.hello();
  }

  _bleChunk() {
    const m = this.info && this.info.mtu ? this.info.mtu : 23;
    return Math.max(20, Math.min(240, m - 3));
  }

  async _bleWrite(str) {
    const bytes = enc.encode(str);
    const n = this._bleChunk();
    for (let i = 0; i < bytes.length; i += n) {
      await this._rx.writeValueWithResponse(bytes.slice(i, i + n));
    }
  }

  // ---------------- Internet (ponte Worker) ----------------
  async connectNet(net) {
    if (!net || !net.dev || !net.key) throw new Error('Internet non configurato: attivalo nella pagina Scheda');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/api/ws?role=app&dev=${net.dev}&key=${net.key}`);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = () => reject(new Error('Impossibile raggiungere il ponte Internet'));
    });
    ws.onmessage = (e) => { if (typeof e.data === 'string') this._onText(e.data.endsWith('\n') ? e.data : e.data + '\n', 'net'); };
    ws.onclose = () => { if (this.kind === 'net') this._closed('Internet scollegato'); };
    this._ws = ws;
    this.kind = 'net';
    this.emit('status', { text: 'Collegato via Internet' });
    const info = await this.hello();
    if (!info) this.emit('status', { text: 'Ponte collegato, ma la scheda non risponde: è accesa e con Internet attivo?' });
  }

  // ---------------- USB ----------------
  async connectUSB(webusb = false) {
    let port;
    // Su Android Web Serial non vede il chip CH343 della porta UART: usiamo WebUSB
    if (support.usb && /Android/i.test(navigator.userAgent)) webusb = true;
    if (support.serial && !webusb) {
      port = await navigator.serial.requestPort();
    } else if (support.usb) {
      const { serial } = await import('../vendor/serial-polyfill.js');
      port = await serial.requestPort();
    } else {
      throw new Error('Questo browser non supporta la connessione USB. Usa Chrome.');
    }
    await port.open({ baudRate: 115200 });
    // Porta UART (chip CH343/CP210x): DTR e RTS sono collegati a BOOT/RST della scheda,
    // quindi vanno lasciati disattivati, altrimenti GPIO0 resta basso (come BOOT premuto).
    // Porta USB nativa (VID 303a): DTR attivo serve per ricevere i messaggi.
    let vid = 0;
    try { vid = (port.getInfo() || {}).usbVendorId || 0; } catch (e) { /* */ }
    const native = vid === 0x303a;
    try { await port.setSignals({ dataTerminalReady: native, requestToSend: false }); } catch (e) { /* non sempre supportato */ }
    this._port = port;
    this._writer = port.writable.getWriter();
    this.kind = 'usb';
    this.emit('status', { text: 'Collegato via USB' });
    this._readLoop();
    await sleep(300);
    await this.hello();
  }

  async _readLoop() {
    const dec = new TextDecoder();
    try {
      while (this._port && this._port.readable) {
        this._reader = this._port.readable.getReader();
        try {
          for (;;) {
            const { value, done } = await this._reader.read();
            if (done) break;
            this._onText(dec.decode(value, { stream: true }), 'usb');
          }
        } finally {
          try { this._reader.releaseLock(); } catch (e) { /* */ }
        }
        if (!this.kind) break;
      }
    } catch (e) {
      this._closed('USB scollegato');
    }
  }

  async _usbWrite(data) {
    await this._writer.write(typeof data === 'string' ? enc.encode(data) : data);
  }

  // ---------------- comune ----------------
  async disconnect() {
    const k = this.kind;
    this.kind = null;
    try {
      if (k === 'ble' && this._dev && this._dev.gatt.connected) this._dev.gatt.disconnect();
      if (k === 'net' && this._ws) this._ws.close();
      if (k === 'usb' && this._port) {
        try { await this._reader.cancel(); } catch (e) { /* */ }
        try { this._writer.releaseLock(); } catch (e) { /* */ }
        await this._port.close();
      }
    } catch (e) { /* */ }
    this._closed('Scollegato');
  }

  _closed(text) {
    this.kind = null;
    this._port = null;
    this.info = null;
    this.state = null;
    this._repl = false;
    this._waiters.forEach((w) => w.reject(new Error('Connessione chiusa')));
    this._waiters = [];
    this.emit('status', { text });
  }

  _onText(text, src) {
    if (this._repl && src === 'usb') { this._replBuf += text; return; }
    this._lineBuf += text;
    let i;
    while ((i = this._lineBuf.indexOf('\n')) >= 0) {
      const line = this._lineBuf.slice(0, i).replace(/\r$/, '');
      this._lineBuf = this._lineBuf.slice(i + 1);
      if (src === 'ble' || src === 'net' || line.startsWith('@@')) {
        try { this._onMsg(JSON.parse(line.startsWith('@@') ? line.slice(2) : line)); } catch (e) { this.emit('console', line); }
      } else if (line.trim()) {
        this.emit('console', line);
      }
    }
    if (this._lineBuf.length > 4096) this._lineBuf = '';
  }

  _onMsg(m) {
    if (m.t === 'info') {
      this.info = m;
      this.state = { run: m.run, id: m.id, app: m.app };
    } else if (m.t === 'state') {
      this.state = { run: m.run, id: m.id, app: m.app };
    } else if (m.t === 'ip' && this.info) {
      this.info.ip = m.ip;
    } else if (m.t === 'web' && this.info) {
      this.info.web = m.url;
    } else if (m.t === 'net' && this.kind === 'net') {
      this.boardOnline = !!m.board;
      if (!m.board) { this.info = null; this.state = null; this.emit('info', null); }
      else this.hello();
    }
    this._waiters = this._waiters.filter((w) => {
      if (w.match(m)) { w.resolve(m); clearTimeout(w.timer); return false; }
      return true;
    });
    this.emit('msg', m);
  }

  waitMsg(match, timeout = 5000) {
    return new Promise((resolve, reject) => {
      const w = { match, resolve, reject };
      w.timer = setTimeout(() => {
        this._waiters = this._waiters.filter((x) => x !== w);
        reject(new Error('La scheda non risponde'));
      }, timeout);
      this._waiters.push(w);
    });
  }

  // invio di un oggetto JSON (serializzato in coda). coalesce: scarta i valori vecchi con la stessa chiave
  send(obj, coalesce) {
    if (!this.kind) return Promise.reject(new Error('Scheda non collegata'));
    if (coalesce) {
      const had = this._pendingCoalesce.has(coalesce);
      this._pendingCoalesce.set(coalesce, obj);
      if (had) return Promise.resolve();
    }
    const p = this._queue.then(async () => {
      let o = obj;
      if (coalesce) { o = this._pendingCoalesce.get(coalesce); this._pendingCoalesce.delete(coalesce); }
      const line = JSON.stringify(o) + '\n';
      if (this.kind === 'ble') await this._bleWrite(line);
      else if (this.kind === 'net') this._ws.send(line);
      else if (this.kind === 'usb' && !this._repl) await this._usbWrite(line);
    });
    this._queue = p.catch(() => {});
    return p;
  }

  cmd(c, v) { return this.send({ t: 'c', c, v }, 'c:' + c); }

  async hello() {
    for (let i = 0; i < 3; i++) {
      try {
        const w = this.waitMsg((m) => m.t === 'info', 2500);
        await this.send({ t: 'hello' });
        const info = await w;
        this.emit('info', info);
        return info;
      } catch (e) { /* riprova */ }
    }
    this.info = null;
    this.emit('info', null);
    return null;
  }

  // ---------------- REPL grezza (solo USB) ----------------
  async _waitRepl(pred, timeout = 5000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      if (pred(this._replBuf)) return this._replBuf;
      await sleep(20);
    }
    throw new Error('La scheda non risponde sulla REPL. Premi RST sulla scheda e riprova.');
  }

  async enterRaw() {
    this._repl = true;
    this._replBuf = '';
    await this._usbWrite('\r\x03');
    await sleep(150);
    await this._usbWrite('\x03');
    await sleep(400);
    this._replBuf = '';
    await this._usbWrite('\r\x01');
    await this._waitRepl((b) => b.includes('raw REPL') && b.trimEnd().endsWith('>'), 4000);
  }

  async exec(code, timeout = 10000) {
    this._replBuf = '';
    const bytes = enc.encode(code);
    for (let i = 0; i < bytes.length; i += 256) {
      await this._usbWrite(bytes.slice(i, i + 256));
      await sleep(5);
    }
    await this._usbWrite('\x04');
    const buf = await this._waitRepl((b) => {
      if (b.startsWith('OK')) { const p = b.split('\x04'); return p.length >= 3 && p[2].includes('>'); }
      return b.length > 0 && !'OK'.startsWith(b.slice(0, 2));
    }, timeout);
    if (!buf.startsWith('OK')) throw new Error('Risposta inattesa dalla REPL: ' + buf.slice(0, 80));
    const [out, err] = buf.slice(2).split('\x04');
    if (err && err.trim()) throw new Error(err.trim());
    return out;
  }

  async exitRawAndReset() {
    await this._usbWrite('\x02');
    await sleep(150);
    this._replBuf = '';
    this._repl = false;          // da qui i messaggi di avvio finiscono nella console
    this._lineBuf = '';
    await this._usbWrite('\x04'); // soft reset: riparte main.py
    await sleep(2500);
    return this.hello();
  }

  async _putUSB(name, bytes) {
    await this.exec(`import binascii as _b\n_f=open('${name}.tmp','wb')`);
    const n = 768;
    for (let i = 0; i < bytes.length; i += n) {
      await this.exec(`_f.write(_b.a2b_base64('${b64(bytes.slice(i, i + n))}'))`);
      this.emit('progress', { file: name, done: Math.min(bytes.length, i + n), total: bytes.length });
    }
    await this.exec(`_f.close()\nimport os\ntry:\n os.remove('${name}')\nexcept OSError:\n pass\nos.rename('${name}.tmp','${name}')`);
  }

  async _putBLE(name, bytes, sys = false) {
    const n = 360;
    if (bytes.length === 0) bytes = enc.encode('\n');
    for (let o = 0; o < bytes.length; o += n) {
      const part = bytes.slice(o, o + n);
      const end = o + n >= bytes.length;
      const ack = this.waitMsg((m) => m.t === 'ack' && m.f === name && m.o === o + part.length, 10000);
      await this.send({ t: 'put', f: name, o, d: b64(part), end, sys });
      await ack;
      this.emit('progress', { file: name, done: o + part.length, total: bytes.length });
    }
  }

  async _withBusy(fn) {
    if (this.busy) throw new Error('Operazione già in corso');
    this.busy = true;
    this.emit('busy', true);
    try { return await fn(); } finally { this.busy = false; this.emit('busy', false); }
  }

  // Carica il progetto come app.py e lo avvia
  uploadProject(project, code) {
    const bytes = enc.encode(code);
    return this._withBusy(async () => {
      if (this.kind === 'usb') {
        await this.enterRaw();
        try {
          await this._putUSB('app.py', bytes);
          await this.exec(
            "import json\ntry:\n c=json.load(open('lab.json'))\nexcept Exception:\n c={}\n" +
            `c['app_id']=${JSON.stringify(project.id)}\nc['app_name']=${JSON.stringify(project.title)}\n` +
            "json.dump(c,open('lab.json','w'))");
        } finally {
          await this.exitRawAndReset();
        }
      } else if (this.kind === 'ble' || this.kind === 'net') {
        await this.send({ t: 'stop' });
        await this._putBLE('app.py', bytes);
        await this.send({ t: 'meta', id: project.id, name: project.title });
        await this.send({ t: 'run' });
        await this.hello();
      } else {
        throw new Error('Collega prima la scheda');
      }
    });
  }

  // Installa/aggiorna il runtime (main.py)
  installRuntime(code) {
    const bytes = enc.encode(code);
    return this._withBusy(async () => {
      if (this.kind === 'usb') {
        await this.enterRaw();
        let ok = false;
        try {
          await this.exec('import sys\nprint(sys.implementation.name)');
          await this._putUSB('main.py', bytes);
          ok = true;
        } finally {
          await this.exitRawAndReset();
        }
        return ok;
      }
      if ((this.kind === 'ble' || this.kind === 'net') && this.info) {
        await this._putBLE('main.py', bytes, true);
        await this.send({ t: 'reset' });
        return true;
      }
      if (this.kind === 'net') throw new Error('La scheda non risponde via Internet: aspetta un minuto e ricollegati, oppure usa Bluetooth/USB');
      if (this.kind === 'ble') throw new Error('La scheda non risponde: premi RST sulla scheda e ricollegati');
      throw new Error('Per la prima installazione collega la scheda via USB');
    });
  }

  // Comando libero nella REPL (solo USB, per la console)
  async replRun(code) {
    return this._withBusy(async () => {
      await this.enterRaw();
      try { return await this.exec(code, 15000); } finally { await this.exitRawAndReset(); }
    });
  }
}
