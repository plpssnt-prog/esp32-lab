// Installazione del firmware MicroPython (con fotocamera) tramite esptool-js
import { ESPLoader, Transport } from '../vendor/esptool.js';

export function canFlash() {
  return 'serial' in navigator || 'usb' in navigator;
}

export async function flashFirmware({ url, eraseAll = true, log, progress, webusb = false }) {
  if (!canFlash()) throw new Error('Questo browser non può collegarsi alla scheda via USB: usa Chrome.');
  let port;
  if ('serial' in navigator && !webusb) {
    port = await navigator.serial.requestPort();
  } else {
    // telefono Android senza Web Serial: WebUSB con il polyfill (dispositivi USB di classe CDC)
    log('Uso WebUSB (modalità alternativa)');
    const { serial } = await import('../vendor/serial-polyfill.js');
    port = await serial.requestPort();
  }
  const transport = new Transport(port, true);
  const term = { clean() {}, writeLine: (s) => log(s), write: (s) => log(s) };
  const loader = new ESPLoader({ transport, baudrate: 460800, terminal: term, debugLogging: false });
  try {
    log('Collegamento al chip…');
    const chip = await loader.main();
    log('Chip: ' + chip);
    if (!/ESP32-S3/i.test(chip)) throw new Error('Questo firmware è per ESP32-S3, trovato: ' + chip);
    log('Scarico il firmware…');
    const data = new Uint8Array(await (await fetch(url)).arrayBuffer());
    log('Firmware: ' + (data.length / 1024).toFixed(0) + ' KB');
    if (eraseAll) log('Cancello la memoria (circa 30 secondi)…');
    await loader.writeFlash({
      fileArray: [{ data, address: 0x0 }],
      flashMode: 'keep', flashFreq: 'keep', flashSize: 'keep',
      eraseAll, compress: true,
      reportProgress: (i, written, total) => progress(written / total),
    });
    log('Scrittura completata. Riavvio…');
    await loader.after('hard_reset');
  } finally {
    try { await transport.disconnect(); } catch (e) { /* */ }
  }
}

// Elenca qualsiasi dispositivo USB che il telefono vede (per capire se cavo e hub funzionano)
export async function usbDiagnosi(log) {
  if (!('usb' in navigator)) throw new Error('WebUSB non disponibile in questo browser');
  const d = await navigator.usb.requestDevice({ filters: [] });
  const hex = (n) => n.toString(16).padStart(4, '0');
  log(`Trovato: ${d.manufacturerName || '?'} ${d.productName || ''} (VID ${hex(d.vendorId)}, PID ${hex(d.productId)})`);
  const known = { '303a': 'ESP32-S3 (USB nativa)', '1a86': 'chip WCH CH34x (porta UART)', '10c4': 'chip CP210x' };
  log('Tipo: ' + (known[hex(d.vendorId)] || 'sconosciuto'));
  try {
    for (const conf of d.configurations || []) for (const itf of conf.interfaces) {
      const a = itf.alternates[0];
      log(`  interfaccia ${itf.interfaceNumber}: classe ${a.interfaceClass}${a.interfaceClass === 2 || a.interfaceClass === 10 ? ' (seriale CDC)' : a.interfaceClass === 255 ? ' (del produttore)' : ''}`);
    }
  } catch (e) { /* */ }
}
