// Installazione del firmware MicroPython (con fotocamera) tramite esptool-js
import { ESPLoader, Transport } from '../vendor/esptool.js';

export function canFlash() {
  return 'serial' in navigator;
}

export async function flashFirmware({ url, eraseAll = true, log, progress }) {
  if (!canFlash()) throw new Error('Serve Chrome con Web Serial (PC, oppure Android 17 o successivo).');
  const port = await navigator.serial.requestPort();
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
