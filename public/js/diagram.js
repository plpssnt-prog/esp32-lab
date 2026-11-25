// Disegno dei collegamenti (SVG) generato dai dati "wiring" di ogni progetto.
// A sinistra: scheda ESP32-S3 CAM montata sulla Freenove Breakout Board, con i morsetti usati.
// A destra: i componenti con i loro piedini. In mezzo: i fili colorati.

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const cut = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

const ALIAS = { Sensori: 'Sensore', Connettore: 'ULN2003' };
const NICE = {
  LED: 'LED', Pulsante: 'Pulsante', Buzzer: 'Buzzer passivo', Potenziometro: 'Potenziometro',
  Fotoresistenza: 'Fotoresistenza', DHT11: 'DHT11', 'HC-SR04': 'HC-SR04 ultrasuoni', Joystick: 'Joystick',
  Ricevitore: 'Ricevitore IR', Servo: 'Servo SG90', L293D: 'Driver L293D', ULN2003: 'Driver ULN2003 + 28BYJ-48',
  MAX7219: 'Matrice 8×8 MAX7219', OLED: 'Display OLED', 'MPU-6050': 'MPU-6050', Anello: 'Anello LED WS2812',
  PIR: 'Sensore PIR', L298N: 'Driver motori L298N', Sensore: 'Sensori di linea TCRT5000', Partitore: 'Partitore (resistenze)',
  Resistenza: 'Resistenza 10 kΩ', Umidità: 'Sensori umidità A e B', MOSFET: 'Moduli MOSFET D4184', Batteria: 'Batteria 12 V (via 100 kΩ)',
};

// destinazione sulla breakout? restituisce il nome del morsetto oppure null
function terminal(to) {
  if (/^GPIO\d+$/.test(to)) return to;
  if (to === 'GND' || to === '3V3') return to;
  if (/^5V( |$)/.test(to) && !/L298N/.test(to)) return '5V';
  return null;
}

// espande le righe tipo ['L298N IN1 / IN2', 'GPIO21 / GPIO47']
function expand(wiring) {
  const out = [];
  for (const [from, to, color] of wiring) {
    const tos = to.split(' / ');
    if (tos.length > 1 && tos.every((t) => /^GPIO\d+$/.test(t))) {
      const parts = from.split(' / ');
      const first = parts[0].split(' ');
      const prefix = first.length > 1 ? first.slice(0, -1).join(' ') + ' ' : '';
      const ALT = { '#2563eb': '#16a34a', '#9333ea': '#0891b2' };
      tos.forEach((t, i) => out.push([i === 0 ? parts[0] : prefix + (parts[i] || parts[0]), t, i ? (ALT[color] || color) : color]));
    } else out.push([from, to, color]);
  }
  return out;
}

function split(from) {
  const w = from.split(' ');
  let comp = w[0];
  let pin = w.slice(1).join(' ');
  if (/^GPIO\d+/.test(comp)) { comp = 'Partitore'; pin = from; }
  comp = ALIAS[comp] || comp;
  return { comp, pin: pin || from };
}

export function wiringSVG(p) {
  const rows = expand(p.wiring || []);
  // morsetti usati
  const termOrder = ['5V', '3V3', 'GND'];
  const terms = [];
  for (const [, to] of rows) { const t = terminal(to); if (t && !terms.includes(t)) terms.push(t); }
  // componenti
  const comps = [];
  const byName = {};
  for (const r of rows) {
    const { comp, pin } = split(r[0]);
    if (!byName[comp]) { byName[comp] = { name: NICE[comp] || comp, pins: [] }; comps.push(byName[comp]); }
    byName[comp].pins.push({ pin, to: r[1], color: r[2], term: terminal(r[1]) });
  }

  // ordino i morsetti come i piedini dei componenti: meno incroci tra i fili
  const seq = [];
  comps.forEach((c) => c.pins.forEach((pn) => seq.push(pn.term)));
  const rank = (t) => {
    const idx = seq.map((x, i) => (x === t ? i : -1)).filter((i) => i >= 0);
    const m = idx.reduce((a, b) => a + b, 0) / idx.length;
    return t === 'GND' || t === '5V' || t === '3V3' ? -100 + termOrder.indexOf(t) : m;
  };
  terms.sort((a, b) => rank(a) - rank(b));

  const W = 820, TOP = 56, ROW = 30, TERM_H = 26;
  const compH = comps.reduce((s, c) => s + 40 + c.pins.length * ROW + 14, 0);
  const boardH = Math.max(300, terms.length * (TERM_H + 8) + 120);
  const H = Math.max(boardH, compH) + TOP + 40;

  const o = [];
  o.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Schema dei collegamenti: ${esc(p.title)}" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">`);
  o.push(`<rect width="${W}" height="${H}" fill="#ffffff"/>`);
  // --- breakout
  const bx = 20, by = TOP, bw = 290, bh = H - TOP - 24;
  o.push(`<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="14" fill="#eef2f7" stroke="#94a3b8" stroke-width="2"/>`);
  o.push(`<text x="${bx + 14}" y="${by - 12}" font-size="15" font-weight="700" fill="#334155">Freenove Breakout Board</text>`);
  // scheda ESP32 sopra la breakout
  const ex = bx + 22, ey = by + 22, ew = 120, eh = Math.min(230, bh - 44);
  o.push(`<rect x="${ex}" y="${ey}" width="${ew}" height="${eh}" rx="8" fill="#1f2937"/>`);
  o.push(`<rect x="${ex + 16}" y="${ey + 14}" width="${ew - 32}" height="${Math.min(70, eh / 3)}" rx="4" fill="#cbd5e1"/>`);
  o.push(`<text x="${ex + ew / 2}" y="${ey + 14 + Math.min(70, eh / 3) / 2 + 4}" font-size="11" text-anchor="middle" fill="#1f2937">ESP32-S3</text>`);
  o.push(`<circle cx="${ex + ew / 2}" cy="${ey + eh * 0.58}" r="15" fill="#0f172a" stroke="#64748b" stroke-width="3"/>`);
  o.push(`<circle cx="${ex + ew / 2}" cy="${ey + eh * 0.58}" r="5" fill="#334155"/>`);
  o.push(`<text x="${ex + ew / 2}" y="${ey + eh * 0.58 + 32}" font-size="10" text-anchor="middle" fill="#cbd5e1">fotocamera</text>`);
  o.push(`<rect x="${ex + ew / 2 - 34}" y="${ey + eh - 12}" width="22" height="12" rx="3" fill="#94a3b8"/><rect x="${ex + ew / 2 + 12}" y="${ey + eh - 12}" width="22" height="12" rx="3" fill="#94a3b8"/>`);
  o.push(`<text x="${ex + ew / 2}" y="${ey + eh + 16}" font-size="10" text-anchor="middle" fill="#64748b">2 porte USB-C</text>`);
  // morsetti usati
  const tx = bx + bw - 112, tw = 96;
  const termY = {};
  const t0 = by + 22;
  terms.forEach((t, i) => {
    const y = t0 + i * (TERM_H + 8);
    termY[t] = y + TERM_H / 2;
    const fill = t === 'GND' ? '#1f2937' : t === '3V3' ? '#dc2626' : t === '5V' ? '#ea580c' : '#16a34a';
    o.push(`<rect x="${tx}" y="${y}" width="${tw}" height="${TERM_H}" rx="5" fill="${fill}"/>`);
    o.push(`<text x="${tx + tw / 2}" y="${y + 17}" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">${esc(t)}</text>`);
    o.push(`<circle cx="${tx + tw}" cy="${y + TERM_H / 2}" r="4" fill="#fff" stroke="${fill}" stroke-width="2"/>`);
  });
  if (!terms.length) {
    o.push(`<text x="${tx + tw / 2}" y="${t0 + 20}" font-size="12" text-anchor="middle" fill="#64748b">nessun filo</text>`);
  }
  o.push(`<text x="${bx + 14}" y="${by + bh - 12}" font-size="11" fill="#64748b">Morsetti: cerca l’etichetta stampata sulla breakout</text>`);

  // --- componenti e fili
  const cx = 500, cw = 300;
  let y = TOP;
  const wires = [];
  for (const c of comps) {
    const h = 40 + c.pins.length * ROW;
    o.push(`<rect x="${cx}" y="${y}" width="${cw}" height="${h}" rx="12" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>`);
    o.push(`<text x="${cx + 14}" y="${y + 25}" font-size="14" font-weight="700" fill="#1f2937">${esc(c.name)}</text>`);
    c.pins.forEach((pn, i) => {
      const py = y + 40 + i * ROW + ROW / 2 - 4;
      o.push(`<circle cx="${cx}" cy="${py}" r="5" fill="${pn.term ? pn.color : '#fff'}" stroke="${pn.color}" stroke-width="2"/>`);
      const label = pn.term ? pn.pin : `${pn.pin} → ${pn.to}`;
      o.push(`<text x="${cx + 14}" y="${py + 4}" font-size="12" fill="${pn.term ? '#334155' : '#6b7280'}">${esc(cut(label, 44))}</text>`);
      if (pn.term) wires.push({ y1: termY[pn.term], y2: py, color: pn.color });
    });
    y += h + 14;
  }
  // fili (sotto le etichette ma sopra gli sfondi)
  const x1 = tx + tw, x2 = cx;
  const paths = wires.map((wi, i) => {
    const mx = x1 + 40 + (i % 6) * 14;
    return `<path d="M${x1} ${wi.y1} C${mx + 40} ${wi.y1} ${mx} ${wi.y2} ${x2} ${wi.y2}" fill="none" stroke="${wi.color}" stroke-width="3" stroke-linecap="round" opacity=".9"/>`;
  });
  // inserisco i fili subito dopo i morsetti (prima dei riquadri dei componenti non conta: sono a destra)
  o.push(...paths);
  o.push(`<text x="${W - 20}" y="${H - 8}" font-size="11" text-anchor="end" fill="#64748b">5V (file rosse «5V0»): solo con alimentatore 7–12 V nel jack della breakout, oppure modulo del kit · GND sempre in comune</text>`);
  o.push('</svg>');
  return o.join('');
}
