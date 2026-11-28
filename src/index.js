// ESP32 Lab - Worker: serve la PWA e fa da ponte su Internet tra la scheda e il telefono.
// Ogni scheda ha un codice (dev) e una chiave segreta (key); un Durable Object per scheda
// inoltra i messaggi JSON tra la scheda (role=board) e le app (role=app) via WebSocket.
import { DurableObject } from 'cloudflare:workers';

const HEX = /^[0-9a-f]{8,64}$/;

const json = (o, status = 200) => new Response(JSON.stringify(o), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
});

const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const b64urlStr = (s) => b64url(new TextEncoder().encode(s));

// ---- Firebase Cloud Messaging (notifiche all'app Android). Secret del Worker: FCM_SA = JSON del service account
let fcmCache = null;   // { token, exp }
function fcmSA(env) {
  if (!env.FCM_SA) return null;
  try { return JSON.parse(env.FCM_SA); } catch (e) { return null; }
}
async function fcmAccessToken(sa) {
  const now = Math.floor(Date.now() / 1000);
  if (fcmCache && fcmCache.exp > now + 60) return fcmCache.token;
  const head = b64urlStr(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const body = b64urlStr(JSON.stringify({
    iss: sa.client_email, scope: 'https://www.googleapis.com/auth/firebase.messaging',
    aud: 'https://oauth2.googleapis.com/token', iat: now, exp: now + 3600,
  }));
  const pem = sa.private_key.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const k = await crypto.subtle.importKey('pkcs8', der, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', k, new TextEncoder().encode(head + '.' + body));
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=' + head + '.' + body + '.' + b64url(sig),
  });
  const j = await r.json();
  if (!j.access_token) throw new Error('FCM: autorizzazione non riuscita');
  fcmCache = { token: j.access_token, exp: now + (j.expires_in || 3600) };
  return fcmCache.token;
}

async function sha256(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');
}

// ---- Telegram (allarmi ai familiari). Secret del Worker: TG_TOKEN = token del bot preso da @BotFather
const tgApi = (env, metodo, corpo) => fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/${metodo}`, corpo instanceof FormData
  ? { method: 'POST', body: corpo }
  : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(corpo || {}) });
const tgSegreto = async (env) => (await sha256('tg:' + env.TG_TOKEN)).slice(0, 32);
const tgIndice = (env) => env.RELAY.get(env.RELAY.idFromName('__telegram__'));
const interna = (stub, path, dati) => stub.fetch(new Request('https://interno' + path, { method: 'POST', body: JSON.stringify(dati) }));

async function telegramWebhook(req, env) {
  if (!env.TG_TOKEN || req.headers.get('x-telegram-bot-api-secret-token') !== await tgSegreto(env)) return new Response('no', { status: 403 });
  const u = await req.json().catch(() => ({}));
  const m = u.message;
  if (!m || !m.chat || typeof m.text !== 'string') return new Response('ok');
  const chat = m.chat.id;
  const nome = [m.from && m.from.first_name, m.from && m.from.last_name].filter(Boolean).join(' ') || 'Telegram';
  const rispondi = (text) => tgApi(env, 'sendMessage', { chat_id: chat, text });
  const [cmd, arg] = m.text.trim().split(/\s+/, 2);
  if (cmd === '/start' && arg && /^[0-9a-f]{8,64}-[0-9a-f]{16}$/.test(arg)) {
    const [dev, codice] = arg.split('-');
    const r = await (await interna(env.RELAY.get(env.RELAY.idFromName(dev)), '/tg/unisci', { codice, chat, nome })).json();
    if (r.ok) await interna(tgIndice(env), '/tg/indice', { chat, dev });
    await rispondi(r.ok ? `Ciao ${nome}! Da adesso ricevi qui gli allarmi della scheda «${r.scheda}».\n/foto  una foto adesso\n/stato  come va\n/stop  non ricevere più gli allarmi`
      : 'Link di invito non valido o scaduto: chiedine uno nuovo.');
    return new Response('ok');
  }
  const { dev } = await (await interna(tgIndice(env), '/tg/indice', { chat })).json();
  if (!dev) { await rispondi('Per ricevere gli allarmi apri il link di invito che ti hanno mandato.'); return new Response('ok'); }
  const stub = env.RELAY.get(env.RELAY.idFromName(dev));
  if (cmd === '/stop') {
    await interna(stub, '/tg/esci', { chat });
    await interna(tgIndice(env), '/tg/indice', { chat, dev: null });
    await rispondi('Fatto: non riceverai più gli allarmi. Per ricominciare riapri il link di invito.');
  } else if (cmd === '/foto' || cmd === '/stato') {
    const r = await (await interna(stub, '/tg/comando', { chat, cmd })).json();
    if (r.text) await rispondi(r.text);
  } else {
    await rispondi('Comandi: /foto  una foto adesso · /stato  come va · /stop  non ricevere più gli allarmi');
  }
  return new Response('ok');
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === '/tg' && req.method === 'POST') return telegramWebhook(req, env);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(req);
    const dev = url.searchParams.get('dev') || '';
    const key = url.searchParams.get('key') || '';
    if (!HEX.test(dev) || !HEX.test(key) || key.length < 32) return json({ error: 'codice non valido' }, 400);
    const stub = env.RELAY.get(env.RELAY.idFromName(dev));
    return stub.fetch(req);
  },
};

export class Relay extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    // il ping della scheda riceve risposta senza svegliare l'oggetto
    ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair('{"t":"ping"}', '{"t":"pong"}'));
  }

  async fetch(req) {
    const url = new URL(req.url);
    if (url.hostname === 'interno') return this.interna(url.pathname, await req.json());
    const h = await sha256(url.searchParams.get('key') || '');
    let stored = await this.ctx.storage.get('key');
    if (!stored) { await this.ctx.storage.put('key', h); stored = h; }   // il primo collegamento registra la chiave
    if (stored !== h) return json({ error: 'chiave errata' }, 403);

    if (url.pathname === '/api/ws') {
      if (req.headers.get('Upgrade') !== 'websocket') return json({ error: 'serve un WebSocket' }, 426);
      const role = url.searchParams.get('role') === 'board' ? 'board' : 'app';
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      if (role === 'board') {
        for (const ws of this.ctx.getWebSockets('board')) { try { ws.close(1000, 'sostituita'); } catch (e) { /* */ } }
      }
      this.ctx.acceptWebSocket(server, [role]);
      if (role === 'board') this.toApps('{"t":"net","board":true}');
      else server.send(JSON.stringify({ t: 'net', board: this.boards().length > 0 }));
      return new Response(null, { status: 101, webSocket: client });
    }

    if (url.pathname === '/api/img') {
      const ts = (await this.ctx.storage.get('imgts')) || 0;
      if (url.searchParams.has('meta')) return json({ ts });
      const img = await this.ctx.storage.get('img');
      if (!img) return json({ error: 'nessuna foto' }, 404);
      return new Response(img, { headers: { 'content-type': 'image/jpeg', 'cache-control': 'no-store', 'x-ts': String(ts) } });
    }

    if (url.pathname === '/api/push' && req.method === 'POST') {
      if (!fcmSA(this.env)) return json({ error: 'Notifiche non configurate sul server (manca FCM_SA)' }, 501);
      const { token } = await req.json().catch(() => ({}));
      if (!token || typeof token !== 'string' || token.length > 4096) return json({ error: 'token non valido' }, 400);
      const tokens = ((await this.ctx.storage.get('tokens')) || []).filter((t) => t !== token);
      tokens.push(token);
      await this.ctx.storage.put('tokens', tokens.slice(-10));
      return json({ ok: true, telefoni: Math.min(tokens.length, 10) });
    }
    if (url.pathname === '/api/push/prova' && req.method === 'POST') {
      const n = await this.notifica('ESP32 Lab', 'Notifica di prova: funziona!', true);
      if (n.error) return json(n, 502);
      return json(n);
    }

    if (url.pathname === '/api/tg/invito' && req.method === 'POST') {
      if (!this.env.TG_TOKEN) return json({ error: 'Telegram non configurato sul server (manca il secret TG_TOKEN)' }, 501);
      const me = await (await tgApi(this.env, 'getMe')).json();
      if (!me.ok) return json({ error: 'Token del bot non valido' }, 502);
      const hook = url.origin + '/tg';
      if ((await this.ctx.storage.get('tghook')) !== hook) {
        const r = await (await tgApi(this.env, 'setWebhook', { url: hook, secret_token: await tgSegreto(this.env), allowed_updates: ['message'] })).json();
        if (!r.ok) return json({ error: 'Telegram: ' + (r.description || 'webhook non impostato') }, 502);
        await this.ctx.storage.put('tghook', hook);
      }
      const { nome } = await req.json().catch(() => ({}));
      if (nome) await this.ctx.storage.put('nome', String(nome).slice(0, 40));
      const codice = [...crypto.getRandomValues(new Uint8Array(8))].map((x) => x.toString(16).padStart(2, '0')).join('');
      await this.ctx.storage.put('tginvito', { codice, scade: Date.now() + 7 * 86400000 });
      return json({ link: `https://t.me/${me.result.username}?start=${url.searchParams.get('dev')}-${codice}`, bot: me.result.username, persone: await this.tgChats() });
    }
    if (url.pathname === '/api/tg/persone') return json({ configurato: !!this.env.TG_TOKEN, persone: await this.tgChats() });
    if (url.pathname === '/api/tg/rimuovi' && req.method === 'POST') {
      const { chat } = await req.json().catch(() => ({}));
      await this.ctx.storage.put('tgchats', (await this.tgChats()).filter((p) => p.chat !== chat));
      await tgApi(this.env, 'sendMessage', { chat_id: chat, text: 'Non riceverai più gli allarmi di questa scheda.' }).catch(() => {});
      return json({ persone: await this.tgChats() });
    }

    if (url.pathname === '/api/stato') return json({ board: this.boards().length > 0, apps: this.ctx.getWebSockets('app').length });
    return json({ error: 'non trovato' }, 404);
  }

  async tgChats() { return (await this.ctx.storage.get('tgchats')) || []; }

  // «veglia»: la scheda a batteria si fa sentire ogni tot minuti; se smette, avviso tutti
  async contatto() {
    const veglia = (await this.ctx.storage.get('veglia')) || 0;
    if (!veglia) return;
    await this.ctx.storage.put('contatto', Date.now());
    if (await this.ctx.storage.get('vegliaAvvisata')) {
      await this.ctx.storage.delete('vegliaAvvisata');
      await this.notifica('Cucina: la scheda è di nuovo collegata', (await this.ctx.storage.get('riepilogo')) || '', true);
    }
    await this.ctx.storage.setAlarm(Date.now() + veglia * 60000);
  }

  async alarm() {
    const veglia = (await this.ctx.storage.get('veglia')) || 0;
    if (!veglia) return;
    const min = Math.round((Date.now() - ((await this.ctx.storage.get('contatto')) || 0)) / 60000);
    if (min < veglia || this.boards().length) {   // collegata adesso: nessun problema
      await this.ctx.storage.setAlarm(Date.now() + Math.max(5, veglia - min) * 60000); return;
    }
    await this.ctx.storage.put('vegliaAvvisata', true);
    await this.notifica('Cucina: la scheda non si fa sentire', `Nessun contatto da ${min} minuti: batteria scarica, scheda spenta o Wi-Fi assente?`, true);
    await this.ctx.storage.setAlarm(Date.now() + 6 * 3600000);     // ripeto ogni 6 ore
  }

  // richieste interne: dal webhook di Telegram (mai da Internet direttamente)
  async interna(path, d) {
    if (path === '/tg/indice') {           // solo nell'oggetto «__telegram__»: chat -> scheda
      if ('dev' in d) { if (d.dev) await this.ctx.storage.put('c' + d.chat, d.dev); else await this.ctx.storage.delete('c' + d.chat); return json({ ok: true }); }
      return json({ dev: (await this.ctx.storage.get('c' + d.chat)) || null });
    }
    if (path === '/tg/unisci') {
      const inv = await this.ctx.storage.get('tginvito');
      if (!inv || inv.codice !== d.codice || inv.scade < Date.now()) return json({ ok: false });
      const persone = (await this.tgChats()).filter((p) => p.chat !== d.chat);
      persone.push({ chat: d.chat, nome: String(d.nome).slice(0, 60) });
      await this.ctx.storage.put('tgchats', persone.slice(-10));
      return json({ ok: true, scheda: (await this.ctx.storage.get('nome')) || 'ESP32 Lab' });
    }
    if (path === '/tg/esci') {
      await this.ctx.storage.put('tgchats', (await this.tgChats()).filter((p) => p.chat !== d.chat));
      return json({ ok: true });
    }
    if (path === '/tg/comando') {
      if (!(await this.tgChats()).some((p) => p.chat === d.chat)) return json({ text: 'Non sei più nell’elenco: chiedi un nuovo invito.' });
      const online = this.boards().length > 0;
      if (d.cmd === '/stato') {
        const r = await this.ctx.storage.get('riepilogo');
        return json({ text: (online ? 'Scheda collegata.' : 'ATTENZIONE: la scheda non è collegata a Internet.') + (r ? '\n' + r : '') });
      }
      if (!online) return json({ text: 'La scheda non è collegata a Internet: niente foto adesso.' });
      await this.ctx.storage.put('tgfoto', { chats: [d.chat], caption: 'Foto di adesso', ts: Date.now() });
      for (const b of this.boards()) { try { b.send('{"t":"c","c":"foto","v":1}'); } catch (e) { /* */ } }
      return json({ text: 'Scatto la foto…' });
    }
    return json({ error: 'non trovato' }, 404);
  }

  // manda testo (e se c'e' la foto) a tutte le persone collegate su Telegram
  async telegram(title, body, foto) {
    if (!this.env.TG_TOKEN) return 0;
    const persone = await this.tgChats();
    for (const p of persone) await tgApi(this.env, 'sendMessage', { chat_id: p.chat, text: '⚠️ ' + title + (body ? '\n' + body : '') }).catch(() => {});
    if (foto && persone.length) {
      const ts = (await this.ctx.storage.get('imgts')) || 0;
      const att = { chats: persone.map((p) => p.chat), caption: title, ts: Date.now() };
      if (Date.now() - ts < 20000) await this.tgFoto(att);          // la foto e' gia' arrivata
      else await this.ctx.storage.put('tgfoto', att);              // la mando appena arriva
    }
    return persone.length;
  }

  async tgFoto(att) {
    const img = await this.ctx.storage.get('img');
    if (!img) return;
    for (const chat of att.chats) {
      const f = new FormData();
      f.append('chat_id', String(chat));
      f.append('caption', att.caption);
      f.append('photo', new Blob([img], { type: 'image/jpeg' }), 'cucina.jpg');
      await tgApi(this.env, 'sendPhoto', f).catch(() => {});
    }
  }

  // invia una notifica a tutti i telefoni registrati per questa scheda (al massimo una ogni 15 s)
  async notifica(title, body, forza = false, foto = false) {
    const now = Date.now();
    if (!forza && now - (this.ultimaNotifica || 0) < 15000) return { saltata: true };
    this.ultimaNotifica = now;
    const tg = await this.telegram(title, body, foto);
    const sa = fcmSA(this.env);
    if (!sa) return tg ? { telegram: tg } : { error: 'Notifiche non configurate sul server (manca FCM_SA)' };
    const tokens = (await this.ctx.storage.get('tokens')) || [];
    if (!tokens.length) return tg ? { telegram: tg } : { error: 'Nessun telefono registrato: premi «Attiva notifiche» nell’app' };
    let access;
    try { access = await fcmAccessToken(sa); } catch (e) { return { error: e.message }; }
    const validi = [];
    let inviate = 0;
    for (const token of tokens) {
      const r = await fetch(`https://fcm.googleapis.com/v1/projects/${sa.project_id}/messages:send`, {
        method: 'POST',
        headers: { authorization: 'Bearer ' + access, 'content-type': 'application/json' },
        body: JSON.stringify({ message: { token, notification: { title, body }, android: { priority: 'HIGH', notification: { sound: 'default' } } } }),
      });
      if (r.ok) { inviate++; validi.push(token); continue; }
      const t = await r.text();
      if (!(r.status === 404 || /UNREGISTERED|registration-token-not-registered/.test(t))) validi.push(token);
    }
    if (validi.length !== tokens.length) await this.ctx.storage.put('tokens', validi);
    return { inviate, telefoni: validi.length, telegram: tg };
  }

  boards() {
    return this.ctx.getWebSockets('board').filter((ws) => ws.readyState === 1);
  }

  toApps(s) {
    for (const ws of this.ctx.getWebSockets('app')) { try { ws.send(s); } catch (e) { /* */ } }
  }

  async webSocketMessage(ws, msg) {
    const [role] = this.ctx.getTags(ws);
    if (role === 'board') {
      if (typeof msg !== 'string') {                 // foto JPEG inviata dalla scheda
        if (msg.byteLength > 1500000) return;
        const ts = Date.now();
        await this.ctx.storage.put({ img: msg, imgts: ts });
        this.toApps(JSON.stringify({ t: 'img', ts }));
        const att = await this.ctx.storage.get('tgfoto');
        if (att) {
          await this.ctx.storage.delete('tgfoto');
          if (ts - att.ts < 30000) await this.tgFoto(att);
        }
        return;
      }
      this.toApps(msg);
      if (msg.includes('notify') || msg.includes('"riepilogo"') || msg.includes('"veglia"')) {
        for (const riga of msg.split('\n')) {
          try {
            const m = JSON.parse(riga);
            if (m.t === 'notify') await this.notifica(String(m.title || 'ESP32 Lab').slice(0, 80), String(m.body || '').slice(0, 300), false, !!m.foto);
            else if (m.t === 'k' && m.k === 'riepilogo') { await this.ctx.storage.put('riepilogo', String(m.v).slice(0, 500)); await this.contatto(); }
            else if (m.t === 'k' && m.k === 'veglia') { await this.ctx.storage.put('veglia', Math.max(0, Number(m.v) || 0)); await this.contatto(); }
          } catch (e) { /* riga non JSON */ }
        }
      }
      return;
    }
    if (typeof msg !== 'string') return;
    const boards = this.boards();
    if (!boards.length) { ws.send('{"t":"net","board":false}'); return; }
    for (const b of boards) { try { b.send(msg); } catch (e) { /* */ } }
  }

  async webSocketClose(ws, code) {
    const [role] = this.ctx.getTags(ws);
    try { ws.close(code === 1005 ? 1000 : code, 'chiuso'); } catch (e) { /* */ }
    if (role === 'board' && !this.boards().length) this.toApps('{"t":"net","board":false}');
  }

  async webSocketError(ws) {
    await this.webSocketClose(ws, 1011);
  }
}
