// Ponte verso le parti native dell'app Android (Capacitor). Nella PWA in Chrome tutto questo è spento.
const cap = window.Capacitor;

export const isApp = !!(cap && typeof cap.nativePromise === 'function');
export const hasPush = isApp && / fcm\b/.test(navigator.userAgent);
export const APK_URL = 'https://github.com/plpssnt-prog/esp32-lab/releases/download/app-latest/ESP32-Lab.apk';

const call = (plugin, method, options = {}) => cap.nativePromise(plugin, method, options);
const listen = (plugin, event, cb) => cap.addListener(plugin, event, cb);

// ---------------- Bluetooth LE nativo (@capacitor-community/bluetooth-le) ----------------
const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
const unhex = (s) => {
  const out = new Uint8Array(s.length >> 1);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(s.substr(i * 2, 2), 16);
  return out;
};

let bleInit = null;
const listeners = new Map();

async function on(event, cb) {
  const old = listeners.get(event);
  if (old) await old.remove();
  listeners.set(event, listen('BluetoothLe', event, cb));
}

export const ble = {
  async init() {
    if (!bleInit) bleInit = call('BluetoothLe', 'initialize', {}).catch((e) => { bleInit = null; throw e; });
    return bleInit;
  },
  // finestra nativa con l'elenco delle schede "ESP32…"
  async scegli(service) {
    await ble.init();
    return call('BluetoothLe', 'requestDevice', { namePrefix: 'ESP32', optionalServices: [service] });
  },
  async collega(deviceId, onDisconnect) {
    await ble.init();
    await on(`disconnected|${deviceId}`, () => onDisconnect && onDisconnect());
    try {
      await call('BluetoothLe', 'connect', { deviceId, timeout: 12000 });
    } catch (e) {
      // dopo un ricaricamento della pagina il collegamento nativo può essere ancora aperto
      try { await call('BluetoothLe', 'disconnect', { deviceId }); } catch (e2) { /* */ }
      await call('BluetoothLe', 'connect', { deviceId, timeout: 12000 });
    }
  },
  async notifiche(deviceId, service, characteristic, cb) {
    await on(`notification|${deviceId}|${service}|${characteristic}`, (ev) => cb(unhex((ev && ev.value) || '')));
    await call('BluetoothLe', 'startNotifications', { deviceId, service, characteristic });
  },
  scrivi(deviceId, service, characteristic, bytes) {
    return call('BluetoothLe', 'write', { deviceId, service, characteristic, value: hex(bytes) });
  },
  async mtu(deviceId) {
    try { return (await call('BluetoothLe', 'getMtu', { deviceId })).value; } catch (e) { return 23; }
  },
  scollega(deviceId) {
    return call('BluetoothLe', 'disconnect', { deviceId });
  },
};

// ---------------- Notifiche push (Firebase Cloud Messaging) ----------------
export async function attivaNotifiche(net) {
  if (!hasPush) throw new Error('Questa versione dell’app non ha le notifiche: aggiornala');
  const perm = await call('PushNotifications', 'requestPermissions');
  if (perm.receive !== 'granted') throw new Error('Permesso notifiche negato: abilitalo nelle impostazioni di Android');
  const token = await new Promise((resolve, reject) => {
    const ok = listen('PushNotifications', 'registration', (t) => { ok.remove(); ko.remove(); resolve(t.value); });
    const ko = listen('PushNotifications', 'registrationError', (e) => { ok.remove(); ko.remove(); reject(new Error(e.error || 'Registrazione non riuscita')); });
    call('PushNotifications', 'register').catch(reject);
  });
  const r = await fetch(`/api/push?dev=${net.dev}&key=${net.key}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ token }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || 'Il server non ha accettato la registrazione');
  localStorage.setItem('lab:push', net.dev);
  return j;
}

export async function provaNotifica(net) {
  const r = await fetch(`/api/push/prova?dev=${net.dev}&key=${net.key}`, { method: 'POST' });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || 'Invio non riuscito');
  return j;
}
