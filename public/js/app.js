import { PROJECTS, LEVELS, PARTS, PINMAP, BOARD } from './projects.js';
import { Conn, support } from './conn.js';
import { isApp, hasPush, APK_URL, attivaNotifiche, provaNotifica } from './native.js';
import { buildPanel, h } from './widgets.js';
import { wiringSVG } from './diagram.js';

const conn = new Conn();
const main = document.getElementById('main');
const store = {
  get(k, d) { try { const v = JSON.parse(localStorage.getItem('lab:' + k)); return v ?? d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('lab:' + k, JSON.stringify(v)); } catch (e) { /* */ } },
};
const getNet = () => store.get('net', null);
const byId = Object.fromEntries(PROJECTS.map((p) => [p.id, p]));
let page = { panel: null, onMsg: null, onConsole: null, onInfo: null };

// ---------------------------------------------------------------- utilità
function toast(text, kind = '') {
  const t = h('div', { class: 'toast ' + kind }, text);
  document.getElementById('toasts').append(t);
  setTimeout(() => t.remove(), 4200);
}
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const done = () => store.get('done', {});
const usesBuy = (p) => p.parts.some((x) => ['oled', 'mpu6050', 'ring', 'pir', 'tcrt', 'chassis', 'l298n', 'batt', 'powerbank', 'soil', 'pump12', 'mosfet', 'float', 'solar'].includes(x));

async function getCode(p) {
  const saved = store.get('code:' + p.id, null);
  if (saved) return saved;
  const r = await fetch('board/projects/' + p.file);
  if (!r.ok) throw new Error('Codice non trovato');
  return r.text();
}

async function guard(fn) {
  try { return await fn(); } catch (e) {
    if (e && e.name === 'NotFoundError') return null; // finestra di scelta chiusa
    toast(e.message || String(e), 'err');
    console.error(e);
    return null;
  }
}

// ---------------------------------------------------------------- connessione
function connLabel() {
  if (!conn.connected) return 'Non collegata';
  const via = ({ ble: 'Bluetooth', usb: 'USB', net: 'Internet' }[conn.kind] || '');
  if (!conn.info) return via + ' · runtime assente';
  return via + ' · ' + conn.info.name;
}

function renderHeader() {
  const b = document.getElementById('connBtn');
  b.textContent = conn.connected ? connLabel() : 'Collega scheda';
  b.classList.toggle('on', conn.connected);
}

function openConnect() {
  if (conn.connected) { location.hash = '#/scheda'; return; }
  const dlg = document.getElementById('dlg');
  dlg.innerHTML = '';
  const close = () => dlg.close();
  dlg.append(
    h('h3', {}, 'Collega la scheda'),
    h('button', { class: 'btn big', disabled: support.ble ? null : '', onclick: async () => { close(); await guard(() => conn.connectBLE()); } },
      'Bluetooth', h('small', {}, 'senza fili · per usare i progetti')),
    h('button', { class: 'btn big ghost', disabled: support.serial || support.usb ? null : '', onclick: async () => { close(); await guard(() => conn.connectUSB()); } },
      'Cavo USB', h('small', {}, 'necessario la prima volta · da PC o dal telefono con cavo OTG')),
    h('button', { class: 'btn big ghost', disabled: getNet() ? null : '', onclick: async () => { close(); await guard(() => conn.connectNet(getNet())); } },
      'Internet', h('small', {}, getNet() ? 'da qualsiasi posto · la scheda deve avere Internet attivo' : 'prima attivalo nella pagina Scheda')),
    !support.ble ? h('p', { class: 'hint' }, 'Bluetooth web non disponibile in questo browser: usa Chrome.') : null,
    h('button', { class: 'btn ghost', onclick: close }, 'Annulla'),
  );
  dlg.showModal();
}

conn.addEventListener('status', (e) => { renderHeader(); toast(e.detail.text); if (page.onInfo) page.onInfo(); });
conn.addEventListener('info', () => { renderHeader(); if (page.onInfo) page.onInfo(); });
conn.addEventListener('msg', (e) => {
  const m = e.detail;
  if (m.t === 'state' || m.t === 'ip' || m.t === 'web') { renderHeader(); if (page.onInfo) page.onInfo(); }
  if (page.onMsg) page.onMsg(m);
});
conn.addEventListener('console', (e) => { if (page.onConsole) page.onConsole(e.detail); });

// ---------------------------------------------------------------- home
function homePage() {
  const filter = store.get('filter', 'tutti');
  const d = done();
  const nDone = PROJECTS.filter((p) => d[p.id]).length;
  const filters = [['tutti', 'Tutti'], ['kit', 'Solo kit Elegoo'], ['buy', 'Con componenti da comprare'], ['wifi', 'Wi-Fi'], ['cam', 'Fotocamera']];
  const ok = (p) => filter === 'tutti' || (filter === 'kit' && !usesBuy(p)) || (filter === 'buy' && usesBuy(p)) || (filter === 'wifi' && p.wifi) || (filter === 'cam' && p.cam);

  const steps = [
    ['Procurati la scheda', 'Freenove ESP32-S3 WROOM CAM e un cavo USB-C dati.', '#/componenti'],
    ['Installa MicroPython', 'Una volta sola, dal PC con Chrome (o da Android 17+).', '#/scheda'],
    ['Installa il runtime ESP32 Lab', 'Una volta sola, via USB. Poi tutto anche via Bluetooth.', '#/scheda'],
  ];
  main.append(
    h('section', { class: 'hero' },
      h('h1', {}, 'ESP32 Lab'),
      h('p', {}, `${PROJECTS.length} progetti in MicroPython, dal LED che lampeggia alla macchinina con telecamera. Scegli, collega i fili, carica dal telefono e usa il pannello di controllo.`),
      h('div', { class: 'progress' }, h('div', { style: `width:${nDone * 100 / PROJECTS.length}%` })),
      h('small', {}, `${nDone} di ${PROJECTS.length} completati`),
      h('div', { class: 'btn-row' }, h('a', { class: 'btn ghost small', href: 'pdf/ESP32-Lab-manuale.pdf', download: 'ESP32-Lab-manuale.pdf' }, '📄 Manuale PDF con tutti i progetti')),
    ),
    store.get('setupDone', false) ? null : h('section', { class: 'card setup' },
      h('h2', {}, 'Si comincia da qui'),
      h('ol', {}, steps.map(([t, s, href]) => h('li', {}, h('a', { href }, t), h('br'), h('small', {}, s)))),
      h('button', { class: 'btn ghost small', onclick: (e) => { store.set('setupDone', true); e.target.closest('section').remove(); } }, 'Fatto, nascondi'),
    ),
    h('div', { class: 'chips' }, filters.map(([k, l]) => h('button', {
      class: 'chip' + (k === filter ? ' on' : ''), onclick: () => { store.set('filter', k); route(); },
    }, l))),
  );
  for (const lv of LEVELS) {
    const list = PROJECTS.filter((p) => p.level === lv.n && ok(p));
    if (!list.length) continue;
    main.append(
      h('h2', { class: 'level' }, h('span', { class: 'lvl' }, 'Livello ' + lv.n), ' ', lv.name),
      h('p', { class: 'muted' }, lv.desc),
      h('div', { class: 'grid' }, list.map((p) => h('a', { class: 'pcard' + (d[p.id] ? ' done' : ''), href: '#/p/' + p.id },
        h('div', { class: 'pnum' }, d[p.id] ? '✓' : String(p.n)),
        h('div', {},
          h('h3', {}, p.title),
          h('p', {}, p.summary),
          h('div', { class: 'tags' }, tags(p)),
        ),
      ))),
    );
  }
}

function tags(p) {
  return [
    h('span', { class: 'tag' }, '⏱ ' + p.time),
    usesBuy(p) ? h('span', { class: 'tag buy' }, '🛒 da comprare') : null,
    p.wifi ? h('span', { class: 'tag' }, 'Wi-Fi') : null,
    p.cam ? h('span', { class: 'tag' }, '📷 fotocamera') : null,
  ];
}

// ---------------------------------------------------------------- progetto
async function projectPage(id) {
  const p = byId[id];
  if (!p) { location.hash = '#/'; return; }
  const idx = PROJECTS.indexOf(p);
  const prev = PROJECTS[idx - 1], next = PROJECTS[idx + 1];

  const statusEl = h('div', { class: 'boardstatus' });
  const bar = h('div', { class: 'bar' }, h('div'));
  const logBox = h('pre', { class: 'log' });
  const panelHost = h('div', { class: 'panel-host' });
  const codeArea = h('textarea', { class: 'code', spellcheck: 'false', autocapitalize: 'off', autocomplete: 'off' });
  const mod = h('span', { class: 'tag buy', hidden: '' }, 'modificato');

  const log = (text, kind = '') => {
    const line = h('span', { class: kind }, text + '\n');
    logBox.append(line);
    while (logBox.childNodes.length > 200) logBox.firstChild.remove();
    logBox.scrollTop = logBox.scrollHeight;
  };

  const btnUpload = h('button', { class: 'btn', onclick: () => guard(async () => {
    if (!conn.connected) { openConnect(); return; }
    if (!conn.info) throw new Error('Il runtime ESP32 Lab non risponde: installalo dalla pagina Scheda.');
    if (p.cam && conn.info.cam === false) throw new Error('Il firmware sulla scheda non ha la fotocamera: installa il firmware dalla pagina Scheda.');
    bar.firstChild.style.width = '0%';
    log('Carico ' + p.file + '…');
    await conn.uploadProject(p, codeArea.value);
    log('Caricato e avviato ✓', 'ok');
    toast('Progetto caricato');
  }) }, 'Carica ed esegui');
  const btnRun = h('button', { class: 'btn ghost', onclick: () => guard(() => conn.send({ t: 'run' })) }, 'Riavvia');
  const btnStop = h('button', { class: 'btn ghost', onclick: () => guard(() => conn.send({ t: 'stop' })) }, 'Ferma');

  const updStatus = () => {
    const s = conn.state;
    let txt;
    if (!conn.connected) txt = 'Scheda non collegata.';
    else if (!conn.info) txt = 'Collegata, ma il runtime ESP32 Lab non risponde.';
    else if (!s || !s.id) txt = 'Nessun progetto sulla scheda.';
    else txt = (s.id === p.id ? 'Questo progetto è sulla scheda' : 'Sulla scheda: «' + s.app + '»') + (s.run ? ' · in esecuzione' : ' · fermo');
    statusEl.textContent = txt;
    const mine = conn.state && conn.state.id === p.id;
    panelHost.classList.toggle('inactive', !mine);
    btnRun.disabled = btnStop.disabled = !conn.info;
    btnUpload.disabled = conn.busy;
    if (page.panel) page.panel.update('__info', conn.info);
  };

  const panel = buildPanel(p.panel, {
    conn,
    net: getNet,
    send: (id, v, nc) => {
      if (!conn.connected) return;
      const pr = nc ? conn.send({ t: 'c', c: id, v }) : conn.cmd(id, v);
      pr.catch((e) => log(e.message, 'err'));
    },
  });
  panelHost.append(panel.el, h('p', { class: 'hint inactive-hint' }, 'Carica questo progetto sulla scheda per usare il pannello.'));
  page.panel = panel;
  page.onInfo = updStatus;
  page.onMsg = (m) => {
    if (m.t === 'k') panel.update(m.k, m.v);
    else if (m.t === 'log') log(m.m);
    else if (m.t === 'err') log(m.m, 'err');
    else if (m.t === 'web') log('Pagina della scheda: ' + m.url, 'ok');
    else if (m.t === 'img') panel.update('__img', m.ts);
    updStatus();
  };
  page.onConsole = (line) => log(line, 'muted');
  const onProg = (e) => { bar.firstChild.style.width = (e.detail.done * 100 / e.detail.total) + '%'; };
  conn.addEventListener('progress', onProg);
  const onBusy = () => updStatus();
  conn.addEventListener('busy', onBusy);
  page.cleanup = () => { conn.removeEventListener('progress', onProg); conn.removeEventListener('busy', onBusy); };

  const d = done();
  const doneBox = h('input', { type: 'checkbox' });
  doneBox.checked = !!d[p.id];
  doneBox.addEventListener('change', () => { const x = done(); x[p.id] = doneBox.checked; store.set('done', x); });

  main.append(
    h('a', { class: 'back', href: '#/' }, '← Tutti i progetti'),
    h('h1', {}, h('span', { class: 'pnum inline' }, String(p.n)), ' ', p.title),
    h('div', { class: 'tags' }, h('span', { class: 'tag' }, 'Livello ' + p.level), tags(p)),
    h('p', { class: 'lead' }, p.summary),
    h('div', { class: 'btn-row' },
      h('a', { class: 'btn ghost small', href: 'pdf/' + pdfName(p), download: pdfName(p) }, '📄 Guida PDF con disegni'),
      h('a', { class: 'btn ghost small', href: '#/stampa/' + p.id }, 'Versione da stampare'),
    ),
    h('section', { class: 'card' },
      h('h2', {}, 'Cosa impari'),
      h('ul', {}, p.learn.map((x) => h('li', {}, x))),
    ),
    h('section', { class: 'card' },
      h('h2', {}, 'Componenti'),
      h('ul', { class: 'parts' }, p.parts.map((k) => {
        const it = PARTS[k];
        return h('li', {}, it.name, ' ', h('span', { class: 'src src-' + it.src }, it.src === 'kit' ? 'kit Elegoo' : it.src));
      })),
    ),
    h('section', { class: 'card' },
      h('h2', {}, 'Collegamenti'),
      drawingBox(p),
      h('p', { class: 'hint' }, 'Tocca il disegno per ingrandirlo. Per chiarezza è uno schema: sulla breakout cerca le etichette dei pin.'),
      p.wiring.length ? h('div', { class: 'wiring' }, p.wiring.map(([from, to, color]) =>
        h('div', { class: 'wire' },
          h('span', { class: 'wfrom' }, from),
          h('span', { class: 'wline', style: `background:${color}` }),
          h('span', { class: 'wto', style: `border-color:${color}` }, to)))) :
        h('p', {}, 'Nessun collegamento: basta la scheda col cavo USB (o alimentata).'),
      p.notes.length ? h('div', { class: 'callout' }, p.notes.map((n) => h('p', {}, n))) : null,
      h('p', { class: 'hint' }, 'Collega i fili con la scheda scollegata dall’alimentazione. ', h('a', { href: '#/componenti' }, 'Mappa completa dei pin')),
    ),
    h('section', { class: 'card sticky-actions' },
      h('h2', {}, 'Sulla scheda'),
      statusEl, bar,
      h('div', { class: 'btn-row' }, btnUpload, btnRun, btnStop),
    ),
    h('section', { class: 'card' }, h('h2', {}, 'Pannello di controllo'), panelHost),
    h('section', { class: 'card' }, h('h2', {}, 'Messaggi dalla scheda'), logBox),
    h('details', { class: 'card' },
      h('summary', {}, h('h2', {}, 'Codice MicroPython '), mod),
      h('p', { class: 'hint' }, 'Puoi modificarlo qui: le modifiche restano salvate su questo telefono e vengono caricate con «Carica ed esegui».'),
      codeArea,
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn ghost small', onclick: async () => {
          store.set('code:' + p.id, null); localStorage.removeItem('lab:code:' + p.id);
          codeArea.value = await getCode(p); mod.hidden = true; toast('Codice originale ripristinato');
        } }, 'Ripristina originale'),
        h('button', { class: 'btn ghost small', onclick: () => navigator.clipboard.writeText(codeArea.value).then(() => toast('Copiato')) }, 'Copia'),
      ),
    ),
    h('label', { class: 'card w-toggle' }, h('span', {}, 'Progetto completato'), doneBox),
    h('nav', { class: 'prevnext' },
      prev ? h('a', { href: '#/p/' + prev.id }, '← ' + prev.title) : h('span'),
      next ? h('a', { href: '#/p/' + next.id }, next.title + ' →') : h('span'),
    ),
  );
  updStatus();

  const original = await guard(() => fetch('board/projects/' + p.file).then((r) => r.text()));
  codeArea.value = (await guard(() => getCode(p))) || '';
  mod.hidden = !store.get('code:' + p.id, null);
  let t;
  codeArea.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(() => {
      if (codeArea.value === original) { localStorage.removeItem('lab:code:' + p.id); mod.hidden = true; } else { store.set('code:' + p.id, codeArea.value); mod.hidden = false; }
    }, 400);
  });
  codeArea.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') { e.preventDefault(); document.execCommand('insertText', false, '    '); }
  });
}

// ---------------------------------------------------------------- scheda
async function boardPage() {
  const infoBox = h('div', { class: 'info' });
  const consoleBox = h('pre', { class: 'log' });
  const flashLog = h('pre', { class: 'log small' });
  const flashBar = h('div', { class: 'bar' }, h('div'));
  const erase = h('input', { type: 'checkbox' });
  erase.checked = true;
  const ssid = h('input', { placeholder: 'Nome della rete (SSID)', autocomplete: 'off' });
  const pw = h('input', { type: 'password', placeholder: 'Password', autocomplete: 'off' });
  const bname = h('input', { placeholder: 'ESP32-Lab', maxlength: 20 });
  const replIn = h('input', { placeholder: 'Comando Python, es. import os; print(os.listdir())', autocapitalize: 'off' });

  const clog = (t, k = '') => {
    consoleBox.append(h('span', { class: k }, t + '\n'));
    while (consoleBox.childNodes.length > 300) consoleBox.firstChild.remove();
    consoleBox.scrollTop = consoleBox.scrollHeight;
  };

  const updInfo = () => {
    infoBox.innerHTML = '';
    const i = conn.info;
    const rows = !conn.connected ? [['Stato', 'Non collegata']] : !i ? [['Stato', 'Collegata via ' + ({ ble: 'Bluetooth', usb: 'USB', net: 'Internet' }[conn.kind] || '')], ['Runtime', conn.kind === 'net' ? 'la scheda non è collegata a Internet (è accesa? Internet attivo?)' : 'non risponde (installalo al passo 2)']] : [
      ['Nome', i.name], ['Collegata via', ({ ble: 'Bluetooth', usb: 'USB', net: 'Internet' }[conn.kind] || '')], ['Runtime', 'v' + i.ver + (i.ver < '1.2' ? ' (aggiorna per usare Internet)' : '')],
      ['MicroPython', ((i.mp || '').split(';')[1] || i.mp || '').replace('MicroPython', '').trim().split(' on ')[0]], ['Fotocamera', i.cam ? 'supportata dal firmware' : 'non supportata'],
      ['Memoria libera', Math.round(i.mem / 1024) + ' KB'], ['Wi-Fi', i.ssid ? i.ssid + (i.ip ? ' · ' + i.ip : ' · non collegato') : 'non configurato'],
      ['Internet', i.cloud ? (i.net ? 'attivo e collegato' : 'attivo, in collegamento…') : 'non attivo'],
      ['Progetto', conn.state && conn.state.app ? conn.state.app + (conn.state.run ? ' (in esecuzione)' : ' (fermo)') : 'nessuno'],
    ];
    infoBox.append(h('table', {}, rows.map(([k, v]) => h('tr', {}, h('th', {}, k), h('td', {}, v)))));
    if (i && i.ssid && !ssid.value) ssid.value = i.ssid;
    if (i && !bname.value) bname.value = i.name;
    updStati();
  };
  page.onInfo = updInfo;
  page.onConsole = (l) => clog(l);
  page.onMsg = (m) => { if (m.t === 'log') clog(m.m); else if (m.t === 'err') clog(m.m, 'err'); updInfo(); };

  const stati = {};
  const passo = (titolo, key, ...figli) => {
    stati[key] = h('span', { class: 'stato' });
    return h('details', { class: 'card passo' },
      h('summary', {}, h('span', { class: 'ptit' }, titolo), stati[key]), ...figli);
  };
  const setStato = (key, testo, ok) => {
    if (!stati[key]) return;
    stati[key].textContent = testo || '';
    stati[key].className = 'stato' + (ok === true ? ' ok' : ok === false ? ' no' : '');
  };
  const updStati = () => {
    const i = conn.info;
    if (!i) { ['fw', 'rt', 'wifi', 'net', 'nome'].forEach((k) => setStato(k, '')); return; }
    setStato('fw', 'fatto', true);
    setStato('rt', 'v' + i.ver, i.ver >= '1.4');
    setStato('wifi', i.ssid ? (i.ip ? 'collegato' : 'non collegato') : 'da fare', !!(i.ssid && i.ip));
    setStato('net', i.cloud ? (i.net || conn.kind === 'net' ? 'attivo' : 'in collegamento') : 'non attivo', i.cloud ? true : undefined);
    setStato('nome', i.name);
  };

  const notifBox = () => {
    if (!isApp) {
      return h('p', { class: 'hint' }, 'Le notifiche dalla scheda (es. movimento rilevato) arrivano con l’app Android ESP32 Lab. ',
        /Android/i.test(navigator.userAgent) ? h('a', { href: APK_URL }, 'Scarica l’app') : null);
    }
    const st = h('span', { class: 'hint' }, localStorage.getItem('lab:push') ? ' Attive su questo telefono.' : '');
    return h('div', { class: 'notif' },
      h('h3', {}, 'Notifiche su questo telefono'),
      h('p', { class: 'hint' }, 'La scheda ti avvisa anche con l’app chiusa (es. movimento rilevato, terreno secco). Serve Internet attivo sulla scheda.'),
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn ghost', onclick: () => guard(async () => {
          const net = getNet(); if (!net) throw new Error('Prima attiva Internet su questa scheda');
          await attivaNotifiche(net); st.textContent = ' Attive su questo telefono.'; toast('Notifiche attivate', 'ok');
        }) }, hasPush ? 'Attiva notifiche' : 'Notifiche non disponibili'),
        h('button', { class: 'btn ghost small', onclick: () => guard(async () => {
          const net = getNet(); if (!net) throw new Error('Prima attiva Internet su questa scheda');
          await provaNotifica(net); toast('Notifica di prova inviata');
        }) }, 'Prova'),
        st));
  };

  const needInfo = () => { if (!conn.info) throw new Error('Collega la scheda con il runtime installato'); };
  const netBox = h('p', { class: 'hint' });
  const codeIn = h('input', { placeholder: 'codice:chiave', autocapitalize: 'off', autocomplete: 'off' });
  const updNet = () => {
    const n = getNet();
    netBox.textContent = n ? 'Questo telefono ha il codice della scheda ' + n.dev + '.' : 'Su questo telefono Internet non è ancora configurato.';
  };
  updNet();

  main.append(
    h('h1', {}, 'La scheda'),
    h('section', { class: 'card' },
      h('h2', {}, 'Connessione'),
      infoBox,
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn', onclick: () => guard(() => conn.connectBLE()) }, 'Bluetooth'),
        h('button', { class: 'btn ghost', onclick: () => guard(() => conn.connectUSB()) }, 'USB'),
        'usb' in navigator ? h('button', { class: 'btn ghost', onclick: () => guard(() => conn.connectUSB(true)) }, 'USB (WebUSB)') : null,
        h('button', { class: 'btn ghost', onclick: () => guard(async () => {
          if (!getNet()) throw new Error('Internet non è attivo su questo telefono (vedi «4 · Internet» qui sotto)');
          await conn.connectNet(getNet()); updInfo();
        }) }, 'Internet'),
        h('button', { class: 'btn ghost', onclick: () => guard(() => conn.disconnect()) }, 'Scollega'),
        h('button', { class: 'btn ghost', onclick: () => guard(async () => { await conn.hello(); updInfo(); }) }, 'Aggiorna'),
      ),
    ),
    h('section', { class: 'card' },
      h('h2', {}, 'Console'),
      h('p', { class: 'hint' }, 'Messaggi della scheda. Con il cavo USB puoi anche eseguire comandi Python (il progetto viene interrotto e poi riavviato).'),
      consoleBox,
      h('div', { class: 'row' }, replIn, h('button', { class: 'btn ghost', onclick: () => guard(async () => {
        if (conn.kind !== 'usb') throw new Error('I comandi Python funzionano solo via USB');
        const code = replIn.value;
        clog('>>> ' + code, 'muted');
        try { const out = await conn.replRun(code); if (out) clog(out.trimEnd()); } catch (e) { clog(e.message, 'err'); }
      }) }, 'Esegui')),
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn ghost small', onclick: () => guard(async () => { needInfo(); await conn.send({ t: 'reset' }); toast('Riavvio della scheda…'); }) }, 'Riavvia la scheda'),
        h('button', { class: 'btn ghost small', onclick: () => { consoleBox.textContent = ''; } }, 'Pulisci'),
      ),
    ),
    h('h2', { class: 'sez' }, 'Installazione e impostazioni'),
    h('p', { class: 'hint' }, 'Tocca una voce per aprire le istruzioni.'),
    passo('1 · Installa MicroPython con fotocamera', 'fw',
      h('p', {}, 'Si fa una sola volta (e quando vuoi aggiornare). Firmware: ', BOARD.firmwareInfo, '.'),
      h('ol', {},
        h('li', {}, 'Usa Chrome, sul PC o sul telefono (con hub o adattatore USB-C OTG). Collega il cavo a una delle due porte USB-C della scheda: prima prova quella marcata «USB».'),
        h('li', {}, 'Metti la scheda in modalità download: tieni premuto BOOT, premi e rilascia RST, poi rilascia BOOT.'),
        h('li', {}, 'Premi «Installa MicroPython» e scegli la scheda nella finestra di Chrome. Se non compare o il chip non risponde, prova l’altra porta (UART).'),
        h('li', {}, 'Alla fine premi RST sulla scheda, poi passa al passo 2.'),
      ),
      h('label', { class: 'w-toggle' }, h('span', {}, 'Cancella tutta la memoria prima (consigliato la prima volta)'), erase),
      h('button', { class: 'btn', onclick: () => guard(async () => {
        if (conn.kind === 'usb') await conn.disconnect();
        flashLog.textContent = '';
        const { flashFirmware } = await import('./flash.js');
        await flashFirmware({
          url: BOARD.firmware, eraseAll: erase.checked,
          log: (s) => { flashLog.textContent += s + '\n'; flashLog.scrollTop = flashLog.scrollHeight; },
          progress: (f) => { flashBar.firstChild.style.width = (f * 100).toFixed(1) + '%'; },
        });
        toast('MicroPython installato! Ora il passo 2.', 'ok');
      }) }, 'Installa MicroPython'),
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn ghost small', onclick: () => guard(async () => {
          if (conn.kind === 'usb') await conn.disconnect();
          flashLog.textContent = '';
          const { flashFirmware } = await import('./flash.js');
          await flashFirmware({
            url: BOARD.firmware, eraseAll: erase.checked, webusb: true,
            log: (s) => { flashLog.textContent += s + '\n'; flashLog.scrollTop = flashLog.scrollHeight; },
            progress: (f) => { flashBar.firstChild.style.width = (f * 100).toFixed(1) + '%'; },
          });
          toast('MicroPython installato! Ora il passo 2.', 'ok');
        }) }, 'Installa con WebUSB'),
        h('button', { class: 'btn ghost small', onclick: () => guard(async () => {
          const { usbDiagnosi } = await import('./flash.js');
          flashLog.textContent += '— Diagnosi USB —\n';
          await usbDiagnosi((s) => { flashLog.textContent += s + '\n'; });
        }) }, 'Diagnosi USB'),
      ),
      h('p', { class: 'hint' }, 'La scheda non compare? «Diagnosi USB» mostra tutti i dispositivi che il telefono vede: se la lista è vuota il problema è cavo, hub o alimentazione.'),
      flashBar, flashLog,
      'serial' in navigator ? null : ('usb' in navigator ? h('p', { class: 'hint' }, 'Sul telefono si usa WebUSB: se non funziona, fai questo passo da Chrome su PC.') : h('p', { class: 'callout' }, 'Questo browser non può collegarsi via USB: usa Chrome su PC o su Android.')),
    ),
    passo('2 · Installa il runtime ESP32 Lab', 'rt',
      h('p', {}, 'È il programma fisso della scheda (main.py): attiva il Bluetooth, riceve i progetti e li esegue. Collega la scheda via USB (dopo il passo 1 va bene anche la porta «USB»), poi premi il pulsante.'),
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn', onclick: () => guard(async () => {
          if (!conn.connected) await conn.connectUSB();
          if (!conn.connected) return;
          const code = await (await fetch('board/main.py')).text();
          clog('Installo il runtime…');
          await conn.installRuntime(code);
          clog('Runtime installato ✓', 'ok');
          toast('Runtime installato: ora puoi usare anche il Bluetooth', 'ok');
          updInfo();
        }) }, conn.info ? 'Aggiorna il runtime' : 'Installa il runtime'),
      ),
    ),
    passo('3 · Wi-Fi (per i progetti web e la fotocamera)', 'wifi',
      h('p', { class: 'hint' }, 'La scheda funziona solo con reti a 2,4 GHz. La password resta salvata solo sulla scheda.'),
      ssid, pw,
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn', onclick: () => guard(async () => {
          needInfo();
          await conn.send({ t: 'wifi', ssid: ssid.value.trim(), pw: pw.value });
          pw.value = '';
          toast('Wi-Fi salvato: la scheda si sta collegando…');
          await new Promise((r) => setTimeout(r, 6000));
          await conn.hello(); updInfo();
        }) }, 'Salva e collega'),
        h('button', { class: 'btn ghost', onclick: () => guard(async () => { needInfo(); await conn.send({ t: 'wifi', ssid: '', pw: '' }); await conn.hello(); updInfo(); }) }, 'Rimuovi Wi-Fi'),
      ),
    ),
    passo('4 · Internet (comandi da fuori casa)', 'net',
      h('p', {}, 'La scheda si collega al ponte ESP32 Lab su Cloudflare: da qualsiasi posto puoi usare i pannelli dei progetti, caricare progetti e vedere le foto. Serve il Wi-Fi impostato (passo 3) e il runtime 1.2.'),
      netBox,
      h('div', { class: 'btn-row' },
        h('button', { class: 'btn', onclick: () => guard(async () => {
          needInfo();
          if (!conn.info.ssid) throw new Error('Prima imposta il Wi-Fi (passo 3)');
          if (conn.info.ver < '1.2') throw new Error('Aggiorna il runtime (passo 2) per usare Internet');
          let net = getNet();
          if (!net) {
            const hex = (n) => [...crypto.getRandomValues(new Uint8Array(n))].map((b) => b.toString(16).padStart(2, '0')).join('');
            net = { dev: hex(6), key: hex(16) };
            store.set('net', net);
          }
          await conn.send({ t: 'cloud', url: location.origin, dev: net.dev, key: net.key });
          toast('Internet attivato: la scheda si sta collegando…');
          await new Promise((r) => setTimeout(r, 6000));
          await conn.hello(); updInfo(); updNet();
        }) }, 'Attiva su questa scheda'),
        h('button', { class: 'btn ghost', onclick: () => guard(async () => {
          if (!getNet()) throw new Error('Internet non è attivo su questo telefono');
          await conn.connectNet(getNet()); updInfo();
        }) }, 'Collega via Internet'),
        h('button', { class: 'btn ghost', onclick: () => guard(async () => {
          needInfo();
          await conn.send({ t: 'cloud', url: '' });
          toast('Internet disattivato sulla scheda');
          await conn.hello(); updInfo();
        }) }, 'Disattiva'),
      ),
      notifBox(),
      h('details', {},
        h('summary', {}, 'Usare un altro telefono o PC'),
        h('p', { class: 'hint' }, 'Copia il codice di accoppiamento qui sotto e incollalo nella PWA dell’altro dispositivo. Chi ha il codice può comandare la scheda: non condividerlo.'),
        h('div', { class: 'row' }, codeIn,
          h('button', { class: 'btn ghost', onclick: () => {
            const v = codeIn.value.trim().toLowerCase();
            const m = v.match(/^([0-9a-f]{8,64})[:\s-]+([0-9a-f]{32,64})$/);
            if (!m) { toast('Codice non valido', 'err'); return; }
            store.set('net', { dev: m[1], key: m[2] }); updNet(); toast('Codice salvato: ora puoi collegarti via Internet');
          } }, 'Salva')),
        h('button', { class: 'btn ghost small', onclick: () => {
          const n = getNet(); if (!n) { toast('Nessun codice su questo telefono', 'err'); return; }
          navigator.clipboard.writeText(n.dev + ':' + n.key).then(() => toast('Codice copiato'));
        } }, 'Copia il mio codice'),
      ),
    ),
    passo('Nome Bluetooth', 'nome',
      h('p', { class: 'hint' }, 'Deve iniziare con «ESP32». Utile se hai più schede.'),
      h('div', { class: 'row' }, bname, h('button', { class: 'btn ghost', onclick: () => guard(async () => {
        needInfo();
        let v = bname.value.trim() || 'ESP32-Lab';
        if (!v.startsWith('ESP32')) v = 'ESP32-' + v;
        await conn.send({ t: 'name', v });
        toast('Nome salvato, la scheda si riavvia: ricollegala.');
      }) }, 'Salva')),
    ),
  );
  updInfo();
}

// ---------------------------------------------------------------- componenti
function partsPage() {
  const have = store.get('have', {});
  const usedIn = (k) => PROJECTS.filter((p) => p.parts.includes(k));
  const group = (title, desc, keys) => h('section', { class: 'card' },
    h('h2', {}, title), desc ? h('p', { class: 'hint' }, desc) : null,
    h('ul', { class: 'shop' }, keys.map((k) => {
      const it = PARTS[k];
      const cb = h('input', { type: 'checkbox' });
      cb.checked = !!have[k];
      cb.addEventListener('change', () => { have[k] = cb.checked; store.set('have', have); });
      const u = usedIn(k);
      return h('li', {},
        h('label', {}, cb, h('b', {}, it.name)),
        it.note ? h('div', { class: 'hint' }, it.note) : null,
        u.length ? h('div', { class: 'used' }, 'Usato in: ', u.map((p, i) => [i ? ', ' : '', h('a', { href: '#/p/' + p.id }, p.title)])) : null,
      );
    })),
  );
  const keys = Object.keys(PARTS);
  main.append(
    h('h1', {}, 'Componenti'),
    h('p', { class: 'lead' }, 'Spunta quello che hai: resta salvato su questo telefono.'),
    group('Da acquistare per iniziare', 'Cerca «Freenove ESP32-S3 WROOM CAM» (FNK0085, versione 8 MB con fotocamera). La breakout board rende molto più comodi i collegamenti.', ['board', 'breakout', 'ff', 'cable']),
    group('Consigliati (pochi euro, progetti in più)', 'Display, accelerometro, anello LED, sensori di movimento, di linea, di clima e di gas, contatti magnetici e trasmettitore IR.', keys.filter((k) => PARTS[k].src === 'consigliato' && k !== 'breakout')),
    group('Per il robot', 'Molti kit «2WD smart car» includono telaio, motori, ruote, portabatterie e spesso anche il L298N.', ['chassis', 'l298n', 'batt', 'powerbank']),
    group('Per la casa', 'Striscia LED, irrigazione e altri componenti dei progetti da lasciare montati.', keys.filter((k) => PARTS[k].src === 'acquisto' && !['board', 'ff', 'cable', 'chassis', 'l298n', 'batt', 'powerbank'].includes(k))),
    group('Dal kit Elegoo che hai già', 'Controlla nella scatola: i kit Elegoo cambiano un po’ tra le versioni.', keys.filter((k) => PARTS[k].src === 'kit')),
    h('section', { class: 'card' },
      h('h2', {}, 'Mappa dei pin'),
      h('p', { class: 'hint' }, 'Tutti i progetti usano questi pin, così i collegamenti restano coerenti.'),
      h('table', { class: 'pins' }, PINMAP.map(([g, use, st]) => h('tr', { class: /NON/.test(st) ? 'no' : '' }, h('th', {}, g), h('td', {}, use), h('td', {}, st)))),
    ),
  );
}

// ---------------------------------------------------------------- guida
function guidePage() {
  const sec = (title, ...ps) => h('section', { class: 'card' }, h('h2', {}, title), ...ps);
  main.append(
    h('h1', {}, 'Guida'),
    sec('Come funziona',
      h('p', {}, 'Sulla scheda c’è MicroPython, un Python per microcontrollori. Sopra installi una volta il runtime ESP32 Lab: è lui che riceve i progetti dal telefono (via Bluetooth o USB), li salva come app.py e li esegue. Il progetto resta sulla scheda e riparte anche se la alimenti senza telefono.'),
      h('p', {}, 'Ogni progetto parla con il pannello di controllo della PWA: i cursori e i pulsanti inviano comandi, la scheda risponde con i valori dei sensori.'),
    ),
    sec('App Android',
      h('p', {}, 'Oltre alla PWA c’è l’app Android ESP32 Lab: stesse pagine (si aggiornano da sole), più Bluetooth nativo che resta collegato e si ricollega da solo alla scheda, e le notifiche dalla scheda anche con l’app chiusa.'),
      h('ol', {},
        h('li', {}, 'Dal telefono Android scarica ', h('a', { href: APK_URL }, 'ESP32-Lab.apk'), '.'),
        h('li', {}, 'Aprilo dalle notifiche o da File › Download; se Android lo chiede, consenti a Chrome di installare app sconosciute.'),
        h('li', {}, 'Nell’app: Collega scheda › Bluetooth la prima volta; poi si ricollega da sola ogni volta che la apri.'),
        h('li', {}, 'Per le notifiche: pagina Scheda › 4 · Internet › «Attiva notifiche».'),
      ),
      h('p', { class: 'hint' }, 'Installare MicroPython via USB (passo 1) si fa ancora da Chrome. Per aggiornare l’app basta scaricare di nuovo l’APK e installarlo sopra.'),
    ),
    sec('Collegare il telefono via USB',
      h('p', {}, 'Serve un cavo o adattatore USB-C ↔ USB-C (OTG). Usa la porta «USB» della scheda. Se Chrome non mostra la scheda, la connessione USB dal telefono non è disponibile: usa il PC per i passi 1 e 2, poi il Bluetooth.'),
    ),
    sec('Le regole d’oro dei collegamenti',
      h('ul', {},
        h('li', {}, 'L’ESP32 lavora a 3,3 V: nessun segnale a 5 V sui pin (usa il partitore per l’ECHO dell’HC-SR04).'),
        h('li', {}, 'Servo e motori si alimentano dal modulo di alimentazione o dalle batterie, mai dai pin.'),
        h('li', {}, 'GND comune: il GND di ogni alimentazione va collegato al GND dell’ESP32.'),
        h('li', {}, 'Fai i collegamenti a scheda spenta, poi ricontrolla prima di alimentare.'),
        h('li', {}, 'Non usare i pin della fotocamera (GPIO4–18), della PSRAM (35–37) e della USB (19–20).'),
      ),
    ),
    sec('Comandare la scheda da fuori casa',
      h('p', {}, 'Nella pagina Scheda, al passo 4, premi «Attiva su questa scheda»: la scheda si collega al ponte ESP32 Lab su Cloudflare e da quel momento puoi premere «Collega scheda» → «Internet» da qualsiasi posto, anche in 4G. Funzionano i pannelli di tutti i progetti, il caricamento dei progetti e le foto (riquadro «Foto» nei progetti con la fotocamera).'),
      h('p', {}, 'Le pagine web della scheda (http://IP/) restano solo per casa. Il codice di accoppiamento è come una password: chi lo ha può comandare la scheda.'),
    ),
    sec('Perché la pagina della scheda si apre a parte',
      h('p', {}, 'La PWA è su Internet in https, la scheda nella tua rete di casa in http: per sicurezza il browser non permette di mischiarle. Per questo i progetti Wi-Fi e fotocamera aprono la pagina della scheda in una nuova scheda del browser, all’indirizzo http://IP-della-scheda/.'),
    ),
    sec('Problemi comuni',
      h('ul', {},
        h('li', {}, h('b', {}, 'Non trovo la scheda in Bluetooth: '), 'verifica che il runtime sia installato e che il nome inizi con «ESP32». Il Bluetooth accetta un telefono alla volta.'),
        h('li', {}, h('b', {}, 'Il progetto va in errore: '), 'leggi il messaggio rosso in «Messaggi dalla scheda». Spesso è un filo nel pin sbagliato o un componente non alimentato.'),
        h('li', {}, h('b', {}, 'La scheda si blocca: '), 'premi RST. Per avviarla senza eseguire nulla, tieni premuto BOOT subito dopo il reset (avvio sicuro).'),
        h('li', {}, h('b', {}, 'Wi-Fi non si collega: '), 'solo reti 2,4 GHz; controlla la password e la distanza dal router.'),
        h('li', {}, h('b', {}, 'Il servo trema o la scheda si riavvia: '), 'alimentazione insufficiente: usa il modulo di alimentazione e il GND comune.'),
      ),
    ),
    sec('Crediti',
      h('p', {}, 'Firmware MicroPython con fotocamera: progetto micropython-camera-API (licenza MIT). Installazione via browser: esptool-js di Espressif (Apache 2.0). USB su Android: web-serial-polyfill di Google (Apache 2.0).'),
    ),
  );
}


// ---------------------------------------------------------------- disegni e stampa
const pdfName = (p) => `ESP32-Lab-${String(p.n).padStart(2, '0')}-${p.id}.pdf`;

function svgBox(p) {
  const d = h('div', { class: 'diagram' });
  d.innerHTML = wiringSVG(p);
  return d;
}

// disegno realistico (stile UNO Lab) se esiste, altrimenti lo schema
function drawingBox(p) {
  const d = h('div', { class: 'diagram drawing' });
  const img = h('img', { src: 'img/disegni/' + p.id + '.png', alt: 'Disegno dei collegamenti: ' + p.title, loading: 'lazy' });
  img.addEventListener('error', () => { d.classList.remove('drawing'); d.innerHTML = wiringSVG(p); });
  img.addEventListener('click', () => window.open(img.src, '_blank'));
  d.append(img);
  return d;
}

const WTYPE = {
  toggle: 'interruttore', slider: 'cursore', button: 'pulsante', buttons: 'pulsanti', color: 'scelta colore',
  text: 'campo di testo', value: 'valore', led: 'spia', chart: 'grafico', pad: 'posizione', joystick: 'joystick',
  piano: 'pianoforte', matrix: 'disegno 8×8', radar: 'radar', web: 'link alla pagina della scheda',
};

async function printProject(p, withBreak) {
  const code = await fetch('board/projects/' + p.file).then((r) => r.text()).catch(() => '');
  const lv = LEVELS.find((l) => l.n === p.level);
  return h('article', { class: 'pp' + (withBreak ? ' brk' : '') },
    h('div', { class: 'pp-head' },
      h('span', { class: 'pnum' }, String(p.n)),
      h('div', {}, h('h1', {}, p.title), h('div', { class: 'pp-meta' }, `Livello ${p.level} · ${lv ? lv.name : ''} · ⏱ ${p.time}` + (p.wifi ? ' · Wi-Fi' : '') + (p.cam ? ' · fotocamera' : '') + (usesBuy(p) ? ' · componenti da comprare' : ''))),
    ),
    h('p', { class: 'lead' }, p.summary),
    h('div', { class: 'pp-cols' },
      h('div', {}, h('h2', {}, 'Cosa impari'), h('ul', {}, p.learn.map((x) => h('li', {}, x)))),
      h('div', {}, h('h2', {}, 'Componenti'), h('ul', {}, p.parts.map((k) => h('li', {}, PARTS[k].name, ' ', h('span', { class: 'src src-' + PARTS[k].src }, PARTS[k].src === 'kit' ? 'kit Elegoo' : PARTS[k].src))))),
    ),
    h('h2', {}, 'Collegamenti'),
    p.wiring.length ? svgBox(p) : h('p', {}, 'Nessun collegamento: basta la scheda.'),
    p.wiring.length ? h('table', { class: 'pins' }, h('tr', {}, h('th', {}, 'Componente / piedino'), h('th', {}, 'Va a')),
      p.wiring.map(([f, t, c]) => h('tr', {}, h('td', {}, h('span', { class: 'sw', style: `background:${c}` }), f), h('td', {}, h('b', {}, t))))) : null,
    p.notes.length ? h('div', { class: 'callout' }, p.notes.map((n) => h('p', {}, '⚠ ' + n))) : null,
    h('h2', {}, 'Come si usa'),
    h('ol', {},
      h('li', {}, 'Fai i collegamenti con la scheda spenta e ricontrollali.'),
      h('li', {}, 'Apri ESP32 Lab, collega la scheda (Bluetooth o USB) e premi «Carica ed esegui» nella pagina del progetto.'),
      p.wifi ? h('li', {}, 'Il progetto usa il Wi-Fi: impostalo prima nella pagina Scheda; poi usa «Apri la pagina della scheda».') : null,
      h('li', {}, 'Usa il pannello di controllo: ', p.panel.map((w) => (w.label || WTYPE[w.type]) + ' (' + WTYPE[w.type] + ')').join(', '), '.'),
    ),
    h('h2', { class: 'brk-before' }, 'Codice MicroPython (' + p.file + ')'),
    h('pre', { class: 'pp-code' }, code),
  );
}

async function printPage(id) {
  document.body.classList.add('print');
  const all = id === 'tutti';
  const list = all ? PROJECTS : [byId[id]].filter(Boolean);
  const bar = h('div', { class: 'noprint btn-row' },
    h('a', { class: 'btn ghost small', href: all ? '#/' : '#/p/' + id }, '← Indietro'),
    h('button', { class: 'btn small', onclick: () => window.print() }, 'Stampa / salva PDF'));
  main.append(bar);
  if (all) {
    main.append(
      h('section', { class: 'pp cover' },
        h('h1', {}, 'ESP32 Lab'),
        h('p', { class: 'lead' }, `${PROJECTS.length} progetti in MicroPython per ${BOARD.name} con Freenove Breakout Board, dal LED che lampeggia alla macchinina con telecamera.`),
        h('h2', {}, 'Indice'),
        LEVELS.flatMap((lv) => [h('h3', {}, `Livello ${lv.n} · ${lv.name}`),
          h('ol', { start: PROJECTS.find((p) => p.level === lv.n).n }, PROJECTS.filter((p) => p.level === lv.n).map((p) => h('li', {}, p.title + (usesBuy(p) ? ' 🛒' : ''))))]),
      ),
      h('section', { class: 'pp brk' },
        h('h1', {}, 'Prima di iniziare'),
        h('ol', {},
          h('li', {}, 'Monta la scheda sulla Freenove Breakout Board rispettando il verso indicato sulla breakout.'),
          h('li', {}, 'Dalla pagina Scheda di ESP32 Lab installa MicroPython (una volta, da Chrome su PC) e poi il runtime via USB.'),
          h('li', {}, 'Imposta il Wi-Fi (solo reti a 2,4 GHz) se vuoi fare i progetti web e fotocamera.'),
        ),
        h('h2', {}, 'Regole d’oro'),
        h('ul', {},
          h('li', {}, 'L’ESP32 lavora a 3,3 V: nessun segnale a 5 V sui pin (partitore 1 kΩ / 2 kΩ per l’ECHO dell’HC-SR04).'),
          h('li', {}, 'Servo e motori: con la sola USB le file rosse «5V0» della breakout non danno corrente. Serve un alimentatore 7–12 V nel jack della breakout, oppure il modulo di alimentazione del kit o le batterie, sempre con GND in comune.'),
          h('li', {}, 'GND sempre in comune tra tutte le alimentazioni.'),
          h('li', {}, 'Non usare i pin della fotocamera (GPIO4–18), della PSRAM (35–37) e della USB (19–20).'),
        ),
        h('h2', {}, 'Mappa dei pin'),
        h('table', { class: 'pins' }, PINMAP.map(([g, use, st]) => h('tr', { class: /NON/.test(st) ? 'no' : '' }, h('th', {}, g), h('td', {}, use), h('td', {}, st)))),
      ),
    );
  }
  for (let i = 0; i < list.length; i++) main.append(await printProject(list[i], all || i > 0));
  document.title = all ? 'ESP32 Lab – manuale' : `ESP32 Lab – ${list[0].n}. ${list[0].title}`;
  document.body.dataset.ready = '1';
}

// ---------------------------------------------------------------- routing
function route() {
  if (page.panel) page.panel.destroy();
  if (page.cleanup) page.cleanup();
  page = { panel: null, onMsg: null, onConsole: null, onInfo: null, cleanup: null };
  main.innerHTML = '';
  document.body.classList.remove('print');
  delete document.body.dataset.ready;
  document.title = 'ESP32 Lab';
  const hash = location.hash.slice(1) || '/';
  const sect = hash.startsWith('/p/') ? 'progetti' : hash.slice(1) || 'progetti';
  document.querySelectorAll('nav.tabs a').forEach((a) => a.classList.toggle('on', a.dataset.s === sect));
  if (hash.startsWith('/stampa/')) printPage(decodeURIComponent(hash.slice(8)));
  else if (hash.startsWith('/p/')) projectPage(decodeURIComponent(hash.slice(3)));
  else if (hash === '/scheda') boardPage();
  else if (hash === '/componenti') partsPage();
  else if (hash === '/guida') guidePage();
  else homePage();
  window.scrollTo(0, 0);
}

document.getElementById('connBtn').addEventListener('click', openConnect);
window.addEventListener('hashchange', route);
route();
renderHeader();

const inApp = /ESP32LabApp/.test(navigator.userAgent);
if ('serviceWorker' in navigator) {
  // nell'app Android il service worker impedirebbe al ponte nativo di caricarsi
  if (inApp) navigator.serviceWorker.getRegistrations().then((rs) => rs.forEach((r) => r.unregister())).catch(() => {});
  else navigator.serviceWorker.register('sw.js').catch(() => {});
}
if (isApp) conn.riprendiBLE().catch(() => {});
