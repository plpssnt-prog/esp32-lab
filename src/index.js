// ESP32 Lab - Worker: serve la PWA e fa da ponte su Internet tra la scheda e il telefono.
// Ogni scheda ha un codice (dev) e una chiave segreta (key); un Durable Object per scheda
// inoltra i messaggi JSON tra la scheda (role=board) e le app (role=app) via WebSocket.
import { DurableObject } from 'cloudflare:workers';

const HEX = /^[0-9a-f]{8,64}$/;

const json = (o, status = 200) => new Response(JSON.stringify(o), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
});

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

    if (url.pathname === '/api/stato') return json({ board: this.boards().length > 0, apps: this.ctx.getWebSockets('app').length });
    return json({ error: 'non trovato' }, 404);
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
