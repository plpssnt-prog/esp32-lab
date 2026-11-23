// Widget del pannello di controllo. Ogni widget invia comandi con send(id, valore)
// e si aggiorna con i valori della scheda (messaggi {t:'k', k:chiave, v:valore}).

const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) el.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
};
export { h };

const NOTES = [['Do', 262], ['Re', 294], ['Mi', 330], ['Fa', 349], ['Sol', 392], ['La', 440], ['Si', 494], ['Do', 523]];

function card(w, ...body) {
  return h('div', { class: 'w w-' + w.type }, w.label ? h('div', { class: 'w-label' }, w.label) : null, ...body);
}

function fmt(v, unit) {
  if (v === null || v === undefined || v === -1 && unit === 'cm') return '—';
  return v + (unit ? ' ' + unit : '');
}

// ctx: { send(id, v), conn }
export function buildPanel(panel, ctx) {
  const listeners = {};       // chiave -> [fn]
  const on = (k, fn) => { (listeners[k] = listeners[k] || []).push(fn); };
  const cleanups = [];
  const root = h('div', { class: 'panel' });

  for (const w of panel) {
    let el;
    switch (w.type) {
      case 'toggle': {
        const inp = h('input', { type: 'checkbox', role: 'switch' });
        inp.checked = !!w.value;
        inp.addEventListener('change', () => ctx.send(w.id, inp.checked));
        el = h('label', { class: 'w w-toggle' }, h('span', {}, w.label), inp);
        break;
      }
      case 'slider': {
        const out = h('b', {}, fmt(w.value, w.unit));
        const inp = h('input', { type: 'range', min: w.min, max: w.max, step: w.step || 1, value: w.value });
        inp.addEventListener('input', () => { out.textContent = fmt(inp.value, w.unit); ctx.send(w.id, Number(inp.value)); });
        el = h('div', { class: 'w w-slider' }, h('div', { class: 'w-label' }, w.label, ' ', out), inp);
        break;
      }
      case 'button':
        el = h('div', { class: 'w' }, h('button', { class: w.danger ? 'btn danger' : 'btn', onclick: () => ctx.send(w.id, w.v, true) }, w.label));
        break;
      case 'buttons':
        el = card(w, h('div', { class: 'btn-row' },
          w.options.map(([label, v]) => h('button', { class: 'btn ghost', onclick: () => ctx.send(w.id, v, true) }, label))));
        break;
      case 'color': {
        const inp = h('input', { type: 'color', value: w.value || '#ffffff' });
        inp.addEventListener('input', () => ctx.send(w.id, inp.value));
        el = h('label', { class: 'w w-toggle' }, h('span', {}, w.label), inp);
        break;
      }
      case 'text': {
        const inp = h('input', { type: w.input || 'text', placeholder: w.placeholder || '' });
        const go = () => ctx.send(w.id, inp.value, true);
        inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
        el = card(w, h('div', { class: 'row' }, inp, h('button', { class: 'btn', onclick: go }, 'Invia')));
        break;
      }
      case 'value': {
        const v = h('div', { class: w.big ? 'val big' : 'val' }, '—');
        on(w.key, (x) => { v.textContent = fmt(typeof x === 'number' ? x : x, w.unit); });
        el = card(w, v);
        break;
      }
      case 'led': {
        const dot = h('span', { class: 'dot' });
        on(w.key, (x) => dot.classList.toggle('on', !!x));
        el = h('div', { class: 'w w-toggle' }, h('span', {}, w.label), dot);
        break;
      }
      case 'chart': {
        const c = h('canvas', { width: 600, height: 160 });
        const val = h('b', {}, '');
        const pts = [];
        const draw = () => {
          const g = c.getContext('2d');
          const W = c.width, H = c.height;
          g.clearRect(0, 0, W, H);
          g.strokeStyle = '#e5e7eb'; g.lineWidth = 1;
          for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(0, H * i / 4); g.lineTo(W, H * i / 4); g.stroke(); }
          if (!pts.length) return;
          const lo = w.min ?? Math.min(...pts), hi = Math.max(w.max ?? Math.max(...pts), lo + 1);
          g.strokeStyle = '#2563eb'; g.lineWidth = 3; g.beginPath();
          pts.forEach((p, i) => {
            const x = i * W / 99, y = H - 6 - (Math.min(hi, Math.max(lo, p)) - lo) * (H - 12) / (hi - lo);
            i ? g.lineTo(x, y) : g.moveTo(x, y);
          });
          g.stroke();
        };
        on(w.key, (x) => {
          if (typeof x !== 'number' || x < 0 && w.unit === 'cm') return;
          pts.push(x); if (pts.length > 100) pts.shift();
          val.textContent = fmt(x, w.unit); draw();
        });
        el = h('div', { class: 'w w-chart' }, h('div', { class: 'w-label' }, w.label, ' ', val), c);
        draw();
        break;
      }
      case 'pad': {
        const dot = h('div', { class: 'pad-dot' });
        on(w.key, (p) => {
          dot.style.left = (50 + (p.x || 0) / 2) + '%';
          dot.style.top = (50 - (p.y || 0) / 2) + '%';
        });
        el = card(w, h('div', { class: 'pad' }, h('div', { class: 'pad-cross' }), dot));
        break;
      }
      case 'joystick': {
        const knob = h('div', { class: 'joy-knob' });
        const base = h('div', { class: 'joy' }, knob);
        let x = 0, y = 0, active = false;
        const move = (e) => {
          const r = base.getBoundingClientRect();
          const R = r.width / 2;
          let dx = e.clientX - r.left - R, dy = e.clientY - r.top - R;
          const m = Math.hypot(dx, dy), lim = R * 0.62;
          if (m > lim) { dx *= lim / m; dy *= lim / m; }
          knob.style.transform = `translate(${dx}px, ${dy}px)`;
          x = Math.round(dx / lim * 100); y = Math.round(-dy / lim * 100);
        };
        base.addEventListener('pointerdown', (e) => { active = true; base.setPointerCapture(e.pointerId); move(e); });
        base.addEventListener('pointermove', (e) => active && move(e));
        const end = () => { active = false; x = y = 0; knob.style.transform = ''; ctx.send(w.id, { x: 0, y: 0 }); };
        base.addEventListener('pointerup', end);
        base.addEventListener('pointercancel', end);
        const timer = setInterval(() => { if (active) ctx.send(w.id, { x, y }); }, 120);
        cleanups.push(() => clearInterval(timer));
        el = card(w, base, h('p', { class: 'hint' }, 'Tieni premuto e trascina. Se lasci, la macchinina si ferma.'));
        break;
      }
      case 'piano':
        el = card(w, h('div', { class: 'piano' },
          NOTES.map(([n, f]) => h('button', { class: 'key', onpointerdown: () => ctx.send(w.id, f, true) }, n))));
        break;
      case 'matrix': {
        const rows = [0, 0, 0, 0, 0, 0, 0, 0];
        const cells = [];
        const grid = h('div', { class: 'matrix' });
        const paint = () => cells.forEach((c, i) => c.classList.toggle('on', !!(rows[i >> 3] & (0x80 >> (i & 7)))));
        let drawMode = null;
        for (let i = 0; i < 64; i++) {
          const c = h('div', { class: 'cell' });
          const set = () => {
            const r = i >> 3, bit = 0x80 >> (i & 7);
            rows[r] = drawMode ? rows[r] | bit : rows[r] & ~bit;
            paint(); ctx.send(w.id, rows.slice());
          };
          c.addEventListener('pointerdown', (e) => { e.preventDefault(); drawMode = !(rows[i >> 3] & (0x80 >> (i & 7))); set(); });
          c.addEventListener('pointerenter', () => { if (drawMode !== null) set(); });
          cells.push(c); grid.append(c);
        }
        const stop = () => { drawMode = null; };
        window.addEventListener('pointerup', stop);
        cleanups.push(() => window.removeEventListener('pointerup', stop));
        on(w.key, (v) => { if (Array.isArray(v)) { v.forEach((x, i) => { rows[i] = x; }); paint(); } });
        el = card(w, grid);
        break;
      }
      case 'radar': {
        const c = h('canvas', { width: 600, height: 320 });
        const dist = new Map();
        let last = 90;
        const draw = () => {
          const g = c.getContext('2d'), W = c.width, H = c.height, cx = W / 2, R = H - 16;
          g.clearRect(0, 0, W, H);
          g.strokeStyle = '#d1d5db'; g.lineWidth = 1;
          for (let k = 1; k <= 4; k++) { g.beginPath(); g.arc(cx, H - 4, R * k / 4, Math.PI, 2 * Math.PI); g.stroke(); }
          g.fillStyle = '#6b7280'; g.font = '16px system-ui';
          for (let k = 1; k <= 4; k++) g.fillText((w.max * k / 4) + ' cm', cx + 4, H - 8 - R * k / 4);
          const rad = (a) => Math.PI - a * Math.PI / 180;
          g.strokeStyle = '#16a34a'; g.lineWidth = 2; g.beginPath();
          g.moveTo(cx, H - 4); g.lineTo(cx + R * Math.cos(rad(last)), H - 4 - R * Math.sin(rad(last))); g.stroke();
          g.fillStyle = '#dc2626';
          for (const [a, d] of dist) {
            if (d < 0 || d > w.max) continue;
            const r = d / w.max * R;
            g.beginPath(); g.arc(cx + r * Math.cos(rad(a)), H - 4 - r * Math.sin(rad(a)), 6, 0, 7); g.fill();
          }
        };
        on(w.key, (p) => { last = p.a; dist.set(p.a, p.d); draw(); });
        el = card(w, c);
        draw();
        break;
      }
      case 'web': {
        const btn = h('a', { class: 'btn', target: '_blank', rel: 'noopener' }, 'Apri la pagina della scheda');
        const hint = h('p', { class: 'hint' }, '');
        const upd = () => {
          const i = ctx.conn.info || {};
          const url = i.web || (i.ip ? 'http://' + i.ip + '/' : null);
          if (url) { btn.href = url; btn.classList.remove('disabled'); hint.textContent = url + ' — telefono e scheda devono essere sulla stessa rete Wi-Fi.'; }
          else { btn.removeAttribute('href'); btn.classList.add('disabled'); hint.textContent = i.ssid ? 'In attesa del Wi-Fi… avvia il progetto.' : 'Prima imposta il Wi-Fi nella pagina Scheda.'; }
        };
        on('__info', upd);
        upd();
        el = card(w, btn, hint);
        break;
      }
      default:
        el = card(w, '(widget sconosciuto: ' + w.type + ')');
    }
    root.append(el);
  }

  return {
    el: root,
    update(k, v) { (listeners[k] || []).forEach((fn) => fn(v)); },
    destroy() { cleanups.forEach((f) => f()); },
  };
}
