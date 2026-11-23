# ESP32 Lab

PWA (tema chiaro, in italiano) con **30 progetti MicroPython** per ESP32-S3, dal LED che lampeggia alla macchinina con telecamera. Dal telefono scegli il progetto, vedi componenti e collegamenti, carichi il codice sulla scheda (Bluetooth o USB) e lo comandi dal pannello di controllo.

Scheda di riferimento: **Freenove ESP32-S3 WROOM CAM** (N8R8, fotocamera OV2640/OV3660), con i componenti del kit Elegoo UNO R3 Super Starter più alcuni componenti consigliati.

## Come funziona

```
PWA (Chrome, Cloudflare Worker)
  ├─ Web Bluetooth (Nordic UART) ─┐
  └─ Web Serial / WebUSB ─────────┴─► runtime ESP32 Lab (main.py) ─► app.py (progetto)
```

1. **Firmware**: MicroPython 1.27 con fotocamera (`public/fw/`, build `FREENOVE_ESP32S3_CAM` di [micropython-camera-API](https://github.com/cnadler86/micropython-camera-API) v0.6.2, MIT). Si installa dalla pagina *Scheda* con [esptool-js](https://github.com/espressif/esptool-js) (serve Web Serial: Chrome su PC o Android 17+).
2. **Runtime** (`public/board/main.py`): installato una volta via USB. Avvia il BLE, riceve i file e i comandi (righe JSON), esegue `app.py` come task asyncio, inoltra log ed errori.
3. **Progetti** (`public/board/projects/*.py`): ogni progetto espone `async def main(lab)`.

### API per i progetti

| Funzione | Uso |
|---|---|
| `lab.on(nome, fn)` | `fn(valore)` chiamata quando la PWA invia il comando `nome` |
| `lab.send(chiave, valore)` | aggiorna i widget collegati a `chiave` |
| `lab.log(...)` | messaggio nella PWA |
| `await lab.wifi()` | collega il Wi-Fi salvato, restituisce l'IP o `None` |
| `await lab.serve(handler)` | server web: `async handler(path, query, writer)` |
| `await lab.reply(w, body, ctype)` | risposta HTTP |

Pulizia: usa `try/finally` in `main`; quando il progetto viene fermato il task riceve `CancelledError`.

### Protocollo (righe JSON, `\n`)

PWA → scheda: `hello`, `put {f,o,d(base64),end}`, `meta {id,name}`, `run`, `stop`, `c {c,v}`, `wifi {ssid,pw}`, `name {v}`, `reset`.
Scheda → PWA: `info`, `state`, `k {k,v}`, `log`, `err`, `ack`, `ip`, `web`. Via USB le righe della scheda hanno il prefisso `@@`; il caricamento via USB usa la raw REPL.

## Struttura

```
public/
  index.html, css/, js/          PWA (app.js, conn.js, widgets.js, flash.js, projects.js)
  board/main.py                  runtime della scheda
  board/projects/                codice MicroPython dei progetti
  fw/                            firmware MicroPython + fotocamera
  vendor/                        esptool-js 0.7.1, web-serial-polyfill 1.0.15
  sw.js, manifest.webmanifest    PWA offline
wrangler.jsonc                   Worker Cloudflare (solo asset statici)
```

## Aggiungere un progetto

1. Crea `public/board/projects/nome.py` con `async def main(lab)`.
2. Aggiungi la voce in `public/js/projects.js` (`PROJECTS`): livello, componenti, collegamenti, note, widget del pannello.
3. Widget disponibili: `toggle`, `slider`, `button`, `buttons`, `color`, `text`, `value`, `led`, `chart`, `pad`, `joystick`, `piano`, `matrix`, `radar`, `web`.
4. Se aggiungi file, aggiornali nell'elenco `SHELL` di `sw.js` e incrementa `VERSION`.

## Pubblicazione

Worker Cloudflare collegato a questo repo (Workers → Create → Import a repository). Nessun build: `wrangler.jsonc` pubblica la cartella `public`.

## Limiti noti

- La PWA è in https, la scheda in http sulla rete locale: le pagine Wi-Fi/fotocamera si aprono in una scheda separata (`http://IP/`).
- USB dal telefono: Web Serial su Android 17+, altrimenti WebUSB con polyfill (porta USB nativa, classe CDC). Il flash del firmware richiede Web Serial.
- Codice dei progetti scritto per la scheda Freenove ma non ancora provato sull'hardware: i pin sono nella pagina *Componenti*.
