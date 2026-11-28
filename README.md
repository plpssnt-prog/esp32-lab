# ESP32 Lab

PWA (tema chiaro, in italiano) con **38 progetti MicroPython** per ESP32-S3, dal LED che lampeggia alla macchinina con telecamera, alla domotica (clima, antifurto, luci, telecomando IR, fughe di acqua e gas, cucina sicura con orologio, gas, fornello e telecamera, anche a batteria) e all’irrigazione del terrazzo a energia solare. Dal telefono scegli il progetto, vedi componenti e collegamenti, carichi il codice sulla scheda (Bluetooth o USB) e lo comandi dal pannello di controllo.

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

## Internet (comandi da fuori casa)

`src/index.js` è il Worker: serve la PWA (asset) e sotto `/api/` fa da ponte con un Durable Object per scheda (`Relay`, SQLite).
- La scheda (runtime ≥ 1.2) apre un WebSocket `wss://…/api/ws?role=board&dev=…&key=…` e lo tiene vivo con un ping ogni 30 s.
- La PWA apre `wss://…/api/ws?role=app&dev=…&key=…`: i messaggi JSON del protocollo passano invariati nei due sensi.
- Il primo collegamento registra l'hash SHA-256 della chiave; poi una chiave diversa riceve 403.
- `lab.foto(jpeg)` manda una foto (frame binario): l'ultima resta in `/api/img`, `/api/img?meta=1` dà l'ora dello scatto.
- Il codice `dev:key` si genera nella pagina Scheda (passo 4) e si può copiare su altri telefoni.

### Allarmi su Telegram (familiari)
- Una volta sola: crea un bot con @BotFather su Telegram e salva il token come secret `TG_TOKEN` del Worker
  (dashboard Cloudflare › Workers › esp32-lab › Settings › Variables and Secrets).
- Pagina Scheda › 4 · Internet › «Crea link di invito»: il Worker imposta da solo il webhook `/tg` (protetto da un segreto
  ricavato dal token) e dà un link `t.me/<bot>?start=<dev>-<codice>` valido 7 giorni. Chi lo apre riceve gli allarmi.
- Ogni notifica della scheda (`{"t":"notify",…}`) va anche su Telegram; con `"foto":1` segue l'ultima foto della scheda.
- Comandi nel bot: `/foto` (scatta e manda una foto), `/stato` (ultimo `riepilogo` inviato dalla scheda), `/stop`.
- Battito: se la scheda manda `veglia` (minuti), il Durable Object avvisa (app e Telegram) quando non riceve `riepilogo` per quel tempo e nessuna scheda è collegata; `veglia` 0 lo spegne.
- Endpoint: `POST /api/tg/invito`, `GET /api/tg/persone`, `POST /api/tg/rimuovi`.

## Struttura

```
public/
  index.html, css/, js/          PWA (app.js, conn.js, widgets.js, flash.js, projects.js)
  board/main.py                  runtime della scheda
  board/projects/                codice MicroPython dei progetti
  fw/                            firmware MicroPython + fotocamera
  vendor/                        esptool-js 0.7.1, web-serial-polyfill 1.0.15
  pdf/                           PDF dei progetti e manuale
  sw.js, manifest.webmanifest    PWA offline
src/index.js                     Worker: asset + ponte Internet (Durable Object Relay)
wrangler.jsonc                   configurazione Worker, binding RELAY e migrazione SQLite
```

## Aggiungere un progetto

1. Crea `public/board/projects/nome.py` con `async def main(lab)`.
2. Aggiungi la voce in `public/js/projects.js` (`PROJECTS`): livello, componenti, collegamenti, note, widget del pannello.
3. Widget disponibili: `toggle`, `slider`, `button`, `buttons`, `color`, `text`, `value`, `led`, `chart`, `pad`, `joystick`, `piano`, `matrix`, `radar`, `web`.
4. Se aggiungi file, aggiornali nell'elenco `SHELL` di `sw.js` e incrementa `VERSION`.

## Disegni e PDF

- Ogni progetto ha uno schema dei collegamenti generato da `public/js/diagram.js` a partire dai dati `wiring` (scheda sulla Freenove Breakout Board FNK0091 → componenti).
- Vista di stampa: `#/stampa/<id>` (singolo progetto) e `#/stampa/tutti` (manuale).
- Guide PDF in `public/pdf/` (una per progetto, stile UNO Lab: disegno, cosa serve, passo passo, se non funziona, codice + `ESP32-Lab-manuale.pdf`). Contenuti specifici in `tools/guide_data.py`, disegni realistici (breakout Freenove + breadboard, stile UNO Lab) in `tools/disegni.py`; le stesse immagini finiscono in `public/img/disegni/` per la PWA (serve `pdftoppm`). Dopo aver modificato i progetti:
  ```
  python3 tools/guide.py
  ```
  cd public && python3 -m http.server 8765 &
  python3 tools/make_pdfs.py
  ```

## Pubblicazione

Worker Cloudflare collegato a questo repo (Workers → Create → Import a repository). Nessun build: `npx wrangler deploy` pubblica `src/index.js`, la cartella `public` e crea il Durable Object.

## Limiti noti

- La PWA è in https, la scheda in http sulla rete locale: le pagine Wi-Fi/fotocamera si aprono in una scheda separata (`http://IP/`).
- USB dal telefono: Web Serial su Android 17+, altrimenti WebUSB con polyfill (porta USB nativa, classe CDC). Il flash del firmware richiede Web Serial.
- Codice dei progetti scritto per la scheda Freenove ma non ancora provato sull'hardware: i pin sono nella pagina *Componenti*.

## App Android (Capacitor)

La cartella `app/` contiene l'app Android: apre il sito (quindi si aggiorna da sola come la PWA) e aggiunge
- **Bluetooth nativo** (`@capacitor-community/bluetooth-le`): resta collegato, ricorda l'ultima scheda e si ricollega da solo;
- **notifiche dalla scheda** (`@capacitor/push-notifications`, Firebase Cloud Messaging): nel progetto si usa `lab.notifica(titolo, testo)` (runtime 1.4).

GitHub Actions (`.github/workflows/android.yml`) costruisce l'APK a ogni modifica di `app/` e lo pubblica nella release
[`app-latest`](https://github.com/plpssnt-prog/esp32-lab/releases/download/app-latest/ESP32-Lab.apk). La chiave di firma
`esp32lab-debug.keystore` è nel repo apposta, così ogni APK si installa sopra il precedente.

Notifiche: serve `app/android/app/google-services.json` (progetto Firebase, pacchetto `dev.plpssnt.esp32lab`) e, nel Worker,
il secret `FCM_SA` con il JSON del service account Firebase. Endpoint: `POST /api/push` (registra il telefono), `POST /api/push/prova`.
