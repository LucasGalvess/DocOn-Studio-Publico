// DocOn Studio · site próprio. Serve a mesma página do Studio (../studio/index.html) com um "shim" que troca
// as capacidades do claude.ai por este servidor: banco em tempo real, arquivos, login da equipe, o Claude Opus 5.5
// (diretor, com nível de raciocínio) e o agente de edição na nuvem (Claude Managed Agents) que renderiza com a skill.
//
// node server.mjs   ·   variáveis em .env.exemplo
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import Anthropic from '@anthropic-ai/sdk';
import {startAgentRun, agentConfigured, ensureSessaoAtiva} from './agente.mjs';
import {falar, vozConfigurada} from './voz.mjs';
import {transcrever, ditadoConfigurado} from './ditado.mjs';
import * as F from './fontes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DATA = path.resolve(process.env.DOCON_DATA || path.join(HERE, 'data'));
const PORT = +(process.env.PORT || 8787);
const SECRET = process.env.DOCON_SEGREDO || crypto.randomBytes(32).toString('hex');
const MODEL = process.env.DOCON_MODELO || 'claude-opus-5-5';
fs.mkdirSync(path.join(DATA, 'blobs'), {recursive: true});

/* ---------------- equipe e sessões (cookie assinado) ---------------- */
// DOCON_EQUIPE="Lucas:senha1,Ana:senha2"  (no primeiro acesso a pessoa entra com nome e senha)
const TEAM = Object.fromEntries((process.env.DOCON_EQUIPE || '').split(',').map((x) => x.trim()).filter(Boolean).map((x) => { const i = x.indexOf(':'); return [x.slice(0, i).trim(), x.slice(i + 1)]; }));
const uidOf = (name) => 'u_' + crypto.createHash('sha256').update('docon:' + name.toLowerCase()).digest('base64url').slice(0, 22);
const sign = (v) => v + '.' + crypto.createHmac('sha256', SECRET).update(v).digest('base64url');
const unsign = (s) => { if (!s) return null; const i = s.lastIndexOf('.'); const v = s.slice(0, i); return s === sign(v) ? v : null; };
function userOf(req) {
  const c = Object.fromEntries((req.headers.cookie || '').split(';').map((x) => x.trim().split('=')).filter((x) => x[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
  const name = unsign(c.docon); return name && TEAM[name] !== undefined ? {id: uidOf(name), name} : null;
}

/* ---------------- banco: documentos JSON com caminho estilo Firestore, persistido em disco ---------------- */
const DBF = path.join(DATA, 'db.json');
let DB = fs.existsSync(DBF) ? JSON.parse(fs.readFileSync(DBF, 'utf8')) : {};
let dirty = null;
globalThis.__doconDB = () => DB;
export function flushDB() { clearTimeout(dirty); fs.writeFileSync(DBF + '.tmp', JSON.stringify(DB)); fs.renameSync(DBF + '.tmp', DBF); }
const persist = () => { clearTimeout(dirty); dirty = setTimeout(flushDB, 300); };
const parentOf = (p) => p.split('/').slice(0, -1).join('/');
const validPath = (p, kind) => typeof p === 'string' && /^[A-Za-z0-9_\-.~:@+]+(\/[A-Za-z0-9_\-.~:@+]+)*$/.test(p) && (p.split('/').length % 2 === (kind === 'doc' ? 0 : 1));
const watchers = new Set();          // {res, kind, path, sid}: todas as inscrições de uma aba passam por UMA conexão SSE (o navegador limita 6 por site)
const conns = new Map();             // conn -> {res, user}
function emit(docPath) {
  for (const w of watchers) if ((w.kind === 'doc' && w.path === docPath) || (w.kind === 'col' && w.path === parentOf(docPath))) sendSnap(w);
}
function colDocs(col) { const out = []; for (const k in DB) if (parentOf(k) === col) out.push({id: k.split('/').pop(), data: DB[k]}); return out; }
function sendSnap(w) {
  const payload = w.kind === 'doc' ? {exists: w.path in DB, id: w.path.split('/').pop(), data: DB[w.path] ?? null} : {docs: colDocs(w.path)};
  w.res.write(`data: ${JSON.stringify(w.sid ? {sid: w.sid, ...payload} : payload)}\n\n`);
}
function merge(a, b) { const o = {...(a || {})}; for (const [k, v] of Object.entries(b || {})) o[k] = v && typeof v === 'object' && !Array.isArray(v) && o[k] && typeof o[k] === 'object' && !Array.isArray(o[k]) ? merge(o[k], v) : v; return o; }
export function dbGet(p) { return DB[p]; }
export function dbSet(p, v) { DB[p] = v; persist(); emit(p); }
export function dbUpdate(p, v) { DB[p] = merge(DB[p], v); persist(); emit(p); }
// quem não é da equipe (cliente no link de aprovação) só lê e muda a própria aprovação, e só nestes campos
const APROV_FIELDS = new Set(['status', 'pedido', 'atualizado', 'eventos']);
function canWrite(user, p, body) {
  if (user) { const m = p.match(/^data\/users\/([^/]+)/); return !m || m[1] === user.id; }
  if (/^aprovacoes\/[^/]+$/.test(p) && DB[p] && body && Object.keys(body).every((k) => APROV_FIELDS.has(k)) && ['aprovado', 'alteracao'].includes(body.status) && DB[p].status === 'aguardando') return true;
  return false;
}
const canRead = (user, p) => user ? !(/^data\/users\/([^/]+)/.test(p) && !p.startsWith('data/users/' + user.id)) : /^aprovacoes\/[^/]+$/.test(p);

/* ---------------- arquivos (equivalente ao /_blob/ do claude.ai), com Range para o vídeo andar na timeline ---------------- */
const metaF = (id) => path.join(DATA, 'blobs', id + '.json');
export function saveBlob(buf, type, name, owner) {
  const id = crypto.randomBytes(16).toString('hex'); fs.writeFileSync(path.join(DATA, 'blobs', id), buf);
  fs.writeFileSync(metaF(id), JSON.stringify({type, name, owner, size: buf.length, criado: Date.now()})); return id;
}
export const blobPath = (id) => path.join(DATA, 'blobs', id);
function serveBlob(req, res, id) {
  if (!/^[0-9a-f]{32}$/.test(id) || !fs.existsSync(metaF(id))) return send(res, 404, 'não encontrado');
  const m = JSON.parse(fs.readFileSync(metaF(id), 'utf8')); const f = blobPath(id); const size = fs.statSync(f).size;
  const r = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '');
  if (r) { const a = r[1] ? +r[1] : size - +r[2]; const b = r[1] && r[2] ? +r[2] : size - 1;
    res.writeHead(206, {'Content-Type': m.type, 'Content-Range': `bytes ${a}-${b}/${size}`, 'Accept-Ranges': 'bytes', 'Content-Length': b - a + 1, 'Cache-Control': 'private, max-age=31536000'}); fs.createReadStream(f, {start: a, end: b}).pipe(res); return; }
  res.writeHead(200, {'Content-Type': m.type, 'Content-Length': size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=31536000'}); fs.createReadStream(f).pipe(res);
}

/* ---------------- Claude (diretor): streaming, ferramentas executadas na página ---------------- */
const anthropic = process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN ? new Anthropic() : null;
const EFFORTS = new Set(['low', 'medium', 'high', 'xhigh', 'max']);
async function claudeStream(req, res, body) {
  if (!anthropic) return send(res, 503, JSON.stringify({code: 'not_granted', message: 'ANTHROPIC_API_KEY não configurada no servidor'}));
  res.writeHead(200, {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive'});
  const out = (ev, d) => res.write(`event: ${ev}\ndata: ${JSON.stringify(d)}\n\n`);
  const effort = EFFORTS.has(body.effort) ? body.effort : 'medium';
  const tools = (body.tools || []).slice(0, 32).map((t) => ({name: String(t.name), description: String(t.description || ''), input_schema: t.input_schema || {type: 'object'}, eager_input_streaming: true}));
  const ctl = new AbortController(); req.on('close', () => ctl.abort());
  try {
    const stream = anthropic.beta.messages.stream({
      model: MODEL, max_tokens: 64000, thinking: {type: 'adaptive'}, output_config: {effort},
      betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default',          // recusa de classificador vai para o modelo de reserva recomendado
      system: body.system || undefined, messages: body.messages, ...(tools.length ? {tools} : {}),
    }, {signal: ctl.signal});
    stream.on('text', (d) => out('text', {d}));
    const msg = await stream.finalMessage();
    out('done', {stop_reason: msg.stop_reason, content: msg.content, usage: msg.usage});
  } catch (e) {
    const code = e?.status === 429 ? 'rate_limited' : e?.name === 'AbortError' || ctl.signal.aborted ? 'cancelled' : e instanceof Anthropic.APIError ? 'api_error' : 'tool_input_invalid';
    out('error', {code, message: String(e?.message || e).slice(0, 400)});
  }
  res.end();
}

/* ---------------- HTTP ---------------- */
function send(res, code, body, type = 'application/json') { res.writeHead(code, {'Content-Type': type}); res.end(body); }
const readBody = (req, max = 2e6) => new Promise((ok, no) => { const ch = []; let n = 0; req.on('data', (c) => { n += c.length; if (n > max) { no(new Error('grande demais')); req.destroy(); } else ch.push(c); }); req.on('end', () => ok(Buffer.concat(ch))); req.on('error', no); });
const json = async (req) => JSON.parse((await readBody(req)).toString('utf8') || '{}');
function page(extra) {
  const html = fs.readFileSync(path.join(ROOT, 'studio', 'index.html'), 'utf8');
  return html.replace('<script>', `<script>window.DOCON_SITE = 1;${extra || ''}</script><script src="/shim.js"></script><script>`);
}
const LOGIN = (msg = '') => `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DocOn Studio</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#141110;color:#EFE8DF;font:15px system-ui,sans-serif}form{display:grid;gap:12px;width:min(340px,92vw)}input,button{font:inherit;padding:11px 12px;border-radius:9px;border:1px solid #342D29;background:#1C1816;color:inherit}button{background:#D9A08F;color:#2A1714;font-weight:700;border:0}h1{font-size:22px;margin:0 0 6px}p{color:#E58873;margin:0}</style>
<form method="post" action="/entrar"><h1>DocOn Studio</h1><input name="nome" placeholder="Seu nome" autocomplete="username" required><input name="senha" type="password" placeholder="Senha da equipe" autocomplete="current-password" required><button>Entrar</button><p>${msg}</p></form>`;

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x'); const user = userOf(req); const p = u.pathname;
  try {
    if (p === '/entrar' && req.method === 'POST') {
      const f = new URLSearchParams((await readBody(req)).toString()); const nome = (f.get('nome') || '').trim();
      const key = Object.keys(TEAM).find((k) => k.toLowerCase() === nome.toLowerCase());
      if (!key || !crypto.timingSafeEqual(Buffer.from(sign(TEAM[key])), Buffer.from(sign(f.get('senha') || '')))) return send(res, 401, LOGIN('Nome ou senha não conferem.'), 'text/html; charset=utf-8');
      res.writeHead(302, {'Set-Cookie': `docon=${encodeURIComponent(sign(key))}; HttpOnly; Path=/; SameSite=Lax; Max-Age=2592000${process.env.DOCON_HTTPS ? '; Secure' : ''}`, Location: '/'}); return res.end();
    }
    if (p === '/sair') { res.writeHead(302, {'Set-Cookie': 'docon=; Path=/; Max-Age=0', Location: '/'}); return res.end(); }
    if (p === '/shim.js') return send(res, 200, fs.readFileSync(path.join(HERE, 'shim.js')), 'text/javascript; charset=utf-8');
    if (p.startsWith('/aprovar/') || p.startsWith('/ver/')) {        // página do cliente: só o vídeo (+ Aprovar / Pedir alteração no link de aprovação)
      const tk = (p.split('/')[2] || '').replace(/[^A-Za-z0-9_-]/g, ''); const html = fs.readFileSync(path.join(ROOT, 'studio', 'aprovacao.html'), 'utf8');
      return send(res, 200, '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' + html.replace('<script>', `<script>window.DOCON_APROV = ${JSON.stringify({token: tk, ver: p.startsWith('/ver/')})};</script><script>`), 'text/html; charset=utf-8');
    }
    if (p.startsWith('/_blob/')) { const id = p.split('/')[2]; return serveBlob(req, res, id); }   // ids aleatórios de 128 bits: o link de aprovação precisa ver o vídeo
    if (p === '/api/db/stream') {
      const conn = crypto.randomBytes(9).toString('base64url'); res.writeHead(200, {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive'});
      conns.set(conn, {res, user}); res.write(`event: hello\ndata: ${JSON.stringify({conn})}\n\n`); const ka = setInterval(() => res.write(': ka\n\n'), 25000);
      req.on('close', () => { clearInterval(ka); conns.delete(conn); for (const w of watchers) if (w.conn === conn) watchers.delete(w); }); return;
    }
    if (p === '/api/db/sub' || p === '/api/db/unsub') {
      const b = await json(req); const c = conns.get(b.conn); if (!c) return send(res, 404, '{"code":"unavailable"}');
      if (p === '/api/db/unsub') { for (const w of watchers) if (w.conn === b.conn && w.sid === b.sid) watchers.delete(w); return send(res, 200, '{"ok":true}'); }
      if (!validPath(b.path, b.kind) || !canRead(user, b.path)) return send(res, 403, '{"code":"forbidden"}');
      const w = {res: c.res, conn: b.conn, sid: String(b.sid), kind: b.kind, path: b.path}; watchers.add(w); sendSnap(w); return send(res, 200, '{"ok":true}');
    }
    if (p === '/api/db/doc' || p === '/api/db/col' || p === '/api/db/watch') {
      const dp = u.searchParams.get('path') || ''; const kind = p === '/api/db/col' ? 'col' : (u.searchParams.get('kind') || 'doc');
      if (!validPath(dp, kind)) return send(res, 400, '{"code":"invalid_argument"}');
      if (!canRead(user, dp)) return send(res, 403, '{"code":"forbidden"}');
      if (p === '/api/db/watch') { res.writeHead(200, {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive'}); const w = {res, kind, path: dp}; watchers.add(w); sendSnap(w); const ka = setInterval(() => res.write(': ka\n\n'), 25000); req.on('close', () => { watchers.delete(w); clearInterval(ka); }); return; }
      if (kind === 'col') return send(res, 200, JSON.stringify({docs: colDocs(dp)}));
      if (req.method === 'GET') return send(res, 200, JSON.stringify({exists: dp in DB, data: DB[dp] ?? null}));
      const body = req.method === 'DELETE' ? null : await json(req);
      if (!canWrite(user, dp, body)) return send(res, 403, '{"code":"invalid_argument"}');
      if (req.method === 'PUT') dbSet(dp, body); else if (req.method === 'PATCH') { if (!(dp in DB)) return send(res, 404, '{"code":"not_found"}'); dbUpdate(dp, body); } else if (req.method === 'DELETE') { delete DB[dp]; persist(); emit(dp); }
      return send(res, 200, '{"ok":true}');
    }
    if (p === '/api/me') return send(res, 200, JSON.stringify(user ? {id: user.id, name: user.name, avatarUrl: ''} : {id: null, name: ''}));
    if (p === '/api/profiles') { const ids = (u.searchParams.get('ids') || '').split(','); const out = {}; for (const n of Object.keys(TEAM)) if (ids.includes(uidOf(n))) out[uidOf(n)] = {name: n}; return send(res, 200, JSON.stringify(out)); }
    if (!user) { if (p === '/' || p === '/index.html') return send(res, 200, LOGIN(), 'text/html; charset=utf-8'); return send(res, 401, '{"code":"session_expired"}'); }
    // ------- daqui para baixo, só a equipe
    if (p === '/' || p === '/index.html') return send(res, 200, page(), 'text/html; charset=utf-8');
    /* ------- fontes online, geração com IA e referências ------- */
    if (p === '/api/fontes') return send(res, 200, JSON.stringify({fontes: F.fontesAtivas()}));
    if (p === '/api/fontes/buscar') { const r = await F.buscar(u.searchParams.get('fonte'), (u.searchParams.get('q') || '').slice(0, 120), u.searchParams.get('tipo') || 'imagem'); return send(res, 200, JSON.stringify({itens: r})); }
    if (p === '/api/fontes/previa') {                 // prévia vinda das fontes (só hosts conhecidos)
      const src = u.searchParams.get('u') || ''; if (!F.hostOk(src)) return send(res, 400, '{"code":"host"}');
      const r = await fetch(src, {headers: req.headers.range ? {Range: req.headers.range} : {}}); res.writeHead(r.status, {'Content-Type': r.headers.get('content-type') || 'application/octet-stream', ...(r.headers.get('content-range') ? {'Content-Range': r.headers.get('content-range')} : {}), ...(r.headers.get('content-length') ? {'Content-Length': r.headers.get('content-length')} : {}), 'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=3600'});
      const rd = r.body.getReader(); for (;;) { const {value, done} = await rd.read(); if (done) break; res.write(value); } return res.end();
    }
    const guardarNoBanco = async (buf, type, meta) => {
      const asset = saveBlob(buf, type, meta.nome, user.id); const id = 'b-' + crypto.randomBytes(5).toString('hex');
      const tipo = /^audio|mpeg/.test(type) ? (meta.duracao && meta.duracao > 20 ? 'trilha' : 'efeito') : /^video/.test(type) ? 'video' : 'imagem';
      dbSet('banco/' + id, {tipo, nome: meta.nome, tags: meta.tags || '', asset_id: asset, mime: type, tamanho: buf.length, duracao: meta.duracao || null, fonte: meta.fonte, autor: meta.autor || '', licenca: meta.licenca || '', pagina: meta.pagina || '', origem: meta.origem || 'online', prompt: meta.prompt || '', autor_conta: user.id, criado: Date.now()});
      return {id, asset_id: asset, tipo};
    };
    if (p === '/api/fontes/importar' && req.method === 'POST') {
      const it = (await json(req)).item || {}; const src = await F.urlDoArquivo(it); if (!F.hostOk(src)) return send(res, 400, '{"code":"host"}');
      const r = await fetch(src); if (!r.ok) return send(res, 502, '{"code":"download"}'); const buf = Buffer.from(await r.arrayBuffer()); if (buf.length > 300 * 1024 * 1024) return send(res, 413, '{"code":"too_large"}');
      return send(res, 200, JSON.stringify(await guardarNoBanco(buf, r.headers.get('content-type') || (it.tipo === 'video' ? 'video/mp4' : it.tipo === 'som' ? 'audio/mpeg' : 'image/jpeg'), {nome: (it.titulo || it.fonte).slice(0, 80), tags: it.fonte, fonte: it.fonte, autor: it.autor, licenca: it.licenca, pagina: it.pagina, duracao: it.duracao})));
    }
    if (p === '/api/ia/gerar' && req.method === 'POST') { const b = await json(req); const r = b.tipo === 'video' ? await F.gerarVideo(String(b.prompt || ''), b.imagem) : await F.gerarImagem(String(b.prompt || ''), b); return send(res, 200, JSON.stringify(r)); }
    if (p === '/api/ia/status') {                     // pronta: a imagem/vídeo fica como rascunho (asset), ainda fora do banco
      const st = await F.statusGeracao(u.searchParams.get('t'), u.searchParams.get('tipo'));
      if (!/complet|done|succe/.test(st.status) || !st.urls.length) return send(res, 200, JSON.stringify({status: st.status || 'processando'}));
      const out = []; for (const g of st.urls.slice(0, 4)) { const r = await fetch(g); const buf = Buffer.from(await r.arrayBuffer()); out.push(saveBlob(buf, r.headers.get('content-type') || 'image/jpeg', 'gerado-ia', user.id)); }
      return send(res, 200, JSON.stringify({status: 'pronto', assets: out}));
    }
    if (p === '/api/ia/aprovar' && req.method === 'POST') {   // aprovado: entra no banco com o prompt que gerou
      const b = await json(req); if (!/^[0-9a-f]{32}$/.test(b.asset_id || '') || !fs.existsSync(metaF(b.asset_id))) return send(res, 404, '{"code":"not_found"}');
      const m = JSON.parse(fs.readFileSync(metaF(b.asset_id), 'utf8')); const id = 'b-' + crypto.randomBytes(5).toString('hex');
      dbSet('banco/' + id, {tipo: /^video/.test(m.type) ? 'video' : 'imagem', nome: String(b.nome || 'Gerado com IA').slice(0, 80), tags: 'ia, magnific', asset_id: b.asset_id, mime: m.type, tamanho: m.size, fonte: 'magnific-ia', licenca: 'Gerado com IA na sua conta Magnific', origem: 'ia', prompt: String(b.prompt || '').slice(0, 1000), autor_conta: user.id, criado: Date.now()});
      return send(res, 200, JSON.stringify({id}));
    }
    if (p === '/api/referencia') return send(res, 200, JSON.stringify(await F.referencia(u.searchParams.get('url') || '')));
    if (p === '/api/assets' && req.method === 'GET') {          // lista com tamanhos (para medir o espaço e liberar ao excluir)
      const assets = fs.readdirSync(path.join(DATA, 'blobs')).filter((f) => f.endsWith('.json')).map((f) => { const id = f.slice(0, -5); const m = JSON.parse(fs.readFileSync(metaF(id), 'utf8')); return {id, url: '/_blob/' + id, contentType: m.type, sizeBytes: m.size, createdAt: new Date(m.criado || 0).toISOString()}; });
      return send(res, 200, JSON.stringify({assets, usage: {files: assets.length, bytes: assets.reduce((n, a) => n + a.sizeBytes, 0), maxFiles: 1e6, maxBytes: +(process.env.DOCON_LIMITE_BYTES || 50 * 1024 ** 3)}}));
    }
    if (p === '/api/assets' && req.method === 'POST') { const buf = await readBody(req, 1024 * 1024 * 1024); const id = saveBlob(buf, req.headers['content-type'] || 'application/octet-stream', decodeURIComponent(req.headers['x-filename'] || ''), user.id); return send(res, 200, JSON.stringify({id, url: '/_blob/' + id, contentType: req.headers['content-type']})); }
    if (p.startsWith('/api/assets/') && req.method === 'DELETE') { const id = p.split('/')[3]; if (/^[0-9a-f]{32}$/.test(id) && fs.existsSync(metaF(id))) { fs.rmSync(blobPath(id)); fs.rmSync(metaF(id)); return send(res, 200, '{"deleted":true}'); } return send(res, 200, '{"deleted":false}'); }
    if (p === '/api/claude' && req.method === 'POST') return claudeStream(req, res, await json(req));
    if (p === '/api/voz' && req.method === 'GET') return send(res, 200, JSON.stringify({configurada: vozConfigurada()}));
    if (p === '/api/voz' && req.method === 'POST') { if (!vozConfigurada()) return send(res, 503, '{"code":"unavailable"}'); const b = await json(req); const mp3 = await falar(b.texto, DATA, {perfil: DB['config/voz']?.perfil}); res.writeHead(200, {'Content-Type': 'audio/mpeg', 'Content-Length': mp3.length, 'Cache-Control': 'private, max-age=86400'}); return res.end(mp3); }
    if (p === '/api/ditado' && req.method === 'GET') return send(res, 200, JSON.stringify({configurado: ditadoConfigurado()}));
    if (p === '/api/ditado' && req.method === 'POST') { if (!ditadoConfigurado()) return send(res, 503, '{"code":"unavailable"}'); const buf = await readBody(req, 25 * 1024 * 1024); const texto = await transcrever(buf, req.headers['content-type'] || ''); return send(res, 200, JSON.stringify({texto})); }
    if (p === '/api/agente' && req.method === 'GET') return send(res, 200, JSON.stringify({configurado: agentConfigured()}));
    if (p === '/api/agente' && req.method === 'POST') { const b = await json(req); return send(res, 200, JSON.stringify(await startAgentRun({texto: String(b.text || ''), user, anthropic}))); }
    send(res, 404, 'não encontrado', 'text/plain; charset=utf-8');
  } catch (e) { console.error(e); if (!res.headersSent) send(res, 500, JSON.stringify({code: 'internal', message: String(e.message || e)})); else res.end(); }
});
if (!process.env.DOCON_NAO_ESCUTAR) server.listen(PORT, () => ensureSessaoAtiva() || console.log(`DocOn Studio em http://localhost:${PORT} · modelo ${MODEL} · ${anthropic ? 'Claude ligado' : 'SEM chave da API (diretor desligado)'} · agente ${agentConfigured() ? 'configurado' : 'não configurado'} · voz ${vozConfigurada() ? 'DocOn (servidor)' : 'do navegador'} · equipe: ${Object.keys(TEAM).join(', ') || '(defina DOCON_EQUIPE)'}`));
