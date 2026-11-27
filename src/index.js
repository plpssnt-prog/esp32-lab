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

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
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

    if (url.pathname === '/api/stato') return json({ board: this.boards().length > 0, apps: this.ctx.getWebSockets('app').length });
    return json({ error: 'non trovato' }, 404);
  }

  // invia una notifica a tutti i telefoni registrati per questa scheda (al massimo una ogni 15 s)
  async notifica(title, body, forza = false) {
    const sa = fcmSA(this.env);
    if (!sa) return { error: 'Notifiche non configurate sul server (manca FCM_SA)' };
    const now = Date.now();
    if (!forza && now - (this.ultimaNotifica || 0) < 15000) return { saltata: true };
    this.ultimaNotifica = now;
    const tokens = (await this.ctx.storage.get('tokens')) || [];
    if (!tokens.length) return { error: 'Nessun telefono registrato: premi «Attiva notifiche» nell’app' };
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
    return { inviate, telefoni: validi.length };
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
        return;
      }
      this.toApps(msg);
      if (msg.includes('notify')) {
        for (const riga of msg.split('\n')) {
          try {
            const m = JSON.parse(riga);
            if (m.t === 'notify') await this.notifica(String(m.title || 'ESP32 Lab').slice(0, 80), String(m.body || '').slice(0, 300));
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
