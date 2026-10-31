// DocOn Studio · shim do site próprio: implementa window.claude.use(...) com o servidor (server.mjs),
// para a MESMA página do Studio rodar no claude.ai (artifact) e aqui, sem duas versões do código.
(() => {
  const api = async (url, opt = {}) => { const r = await fetch(url, {credentials: 'same-origin', ...opt}); const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) {} if (!r.ok) throw Object.assign(new Error(j?.message || t), {code: j?.code || (r.status === 401 ? 'session_expired' : r.status === 403 ? 'invalid_argument' : 'unavailable')}); return j; };
  const clone = (x) => x == null ? x : JSON.parse(JSON.stringify(x));

  /* ---------- banco: doc / collection / onSnapshot (SSE) ---------- */
  function docSnap(id, d) { return {id, exists: !!d.exists, data: () => clone(d.data)}; }
  // uma única conexão SSE por aba; cada onSnapshot vira uma inscrição nela
  let es = null, conn = null, ready = null; const subs = new Map(); let nsid = 0;
  function stream() {
    if (ready) return ready;
    ready = new Promise((ok) => {
      es = new EventSource('/api/db/stream');
      es.addEventListener('hello', async (e) => { conn = JSON.parse(e.data).conn; ok(); for (const [sid, s] of subs) sub(sid, s); });
      es.onmessage = (e) => { const d = JSON.parse(e.data); const s = subs.get(d.sid); if (s) s.onData(d); };
      es.onerror = () => { if (es.readyState === 2) { ready = null; setTimeout(stream, 2000); } };
    });
    return ready;
  }
  const sub = (sid, s) => fetch('/api/db/sub', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({conn, sid, kind: s.kind, path: s.path}), credentials: 'same-origin'}).then((r) => { if (!r.ok && s.onErr) s.onErr({code: 'forbidden'}); }).catch(() => {});
  function watch(kind, path, onData, onErr) {
    const sid = 's' + (++nsid); const s = {kind, path, onData, onErr}; subs.set(sid, s);
    stream().then(() => sub(sid, s));
    return () => { subs.delete(sid); if (conn) fetch('/api/db/unsub', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({conn, sid}), credentials: 'same-origin'}).catch(() => {}); };
  }
  function doc(path) {
    const id = path.split('/').pop(); const q = encodeURIComponent(path);
    return {
      id, path,
      get: async () => docSnap(id, await api(`/api/db/doc?path=${q}`)),
      set: (v) => api(`/api/db/doc?path=${q}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(v)}),
      update: (v) => api(`/api/db/doc?path=${q}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(v)}),
      delete: () => api(`/api/db/doc?path=${q}`, {method: 'DELETE'}),
      onSnapshot: (cb, err) => watch('doc', path, (d) => cb(docSnap(id, d)), err),
    };
  }
  function collection(path, q = {}) {
    const shape = (docs) => { let ds = docs.map((d) => ({id: d.id, data: d.data})); if (q.order) { const [f, dir] = q.order; ds.sort((a, b) => ((a.data?.[f] ?? 0) > (b.data?.[f] ?? 0) ? 1 : -1) * (dir === 'desc' ? -1 : 1)); } if (q.limit) ds = ds.slice(0, q.limit); return ds; };
    return {
      orderBy: (f, dir = 'asc') => collection(path, {...q, order: [f, dir]}), limit: (n) => collection(path, {...q, limit: n}), doc: (id) => doc(path + '/' + id),
      get: async () => { const r = await api(`/api/db/col?path=${encodeURIComponent(path)}`); const ds = shape(r.docs); return {docs: ds.map((d) => docSnap(d.id, {exists: true, data: d.data})), size: ds.length, empty: !ds.length}; },
      onSnapshot: (cb, err) => { let prev = new Map(); return watch('col', path, (r) => {
        const ds = shape(r.docs); const now = new Map(ds.map((d) => [d.id, JSON.stringify(d.data)])); const changes = [];
        for (const d of ds) { if (!prev.has(d.id)) changes.push({type: 'added', doc: docSnap(d.id, {exists: true, data: d.data})}); else if (prev.get(d.id) !== now.get(d.id)) changes.push({type: 'modified', doc: docSnap(d.id, {exists: true, data: d.data})}); }
        for (const id of prev.keys()) if (!now.has(id)) changes.push({type: 'removed', doc: docSnap(id, {exists: false, data: null})});
        prev = now; cb({docs: ds.map((d) => docSnap(d.id, {exists: true, data: d.data})), size: ds.length, docChanges: () => changes});
      }, err); },
    };
  }

  /* ---------- Claude: o laço de ferramentas roda aqui (as ferramentas mexem na timeline da página) ---------- */
  const tierEffort = {quick: 'low', default: 'medium'};
  async function claudeTurn(body, onText, signal) {
    const r = await fetch('/api/claude', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal, credentials: 'same-origin'});
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw Object.assign(new Error(j.message || 'falha'), {code: j.code || 'unavailable'}); }
    const rd = r.body.getReader(); const dec = new TextDecoder(); let buf = '', done = null;
    for (;;) {
      const {value, done: end} = await rd.read(); if (end) break; buf += dec.decode(value, {stream: true});
      let i; while ((i = buf.indexOf('\n\n')) >= 0) { const raw = buf.slice(0, i); buf = buf.slice(i + 2); const ev = /event: (\w+)/.exec(raw)?.[1]; const d = /data: (.*)/s.exec(raw)?.[1]; if (!ev || !d) continue; const j = JSON.parse(d);
        if (ev === 'text') onText(j.d); else if (ev === 'done') done = j; else if (ev === 'error') throw Object.assign(new Error(j.message), {code: j.code}); }
    }
    if (!done) throw Object.assign(new Error('resposta incompleta'), {code: 'unavailable'}); return done;
  }
  function validInput(schema, input) { if (!input || typeof input !== 'object') return false; for (const k of schema?.required || []) if (!(k in input)) return false; return true; }
  async function sample(turns, opts = {}) {
    const tools = opts.tools || []; const messages = turns.map((t) => ({role: t.role, content: t.content})); let text = '', all = '';
    const imgs = opts.images ? [...(opts.images instanceof Blob ? [opts.images] : opts.images)] : [];
    if (imgs.length) {      // imagens vão junto do último pedido da pessoa, como no claude.ai
      const blocks = []; for (const b of imgs) { const buf = new Uint8Array(await b.arrayBuffer()); let bin = ''; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
        blocks.push({type: 'image', source: {type: 'base64', media_type: b.type || 'image/jpeg', data: btoa(bin)}}); }
      const li = messages.map((m) => m.role).lastIndexOf('user'); if (li >= 0) messages[li] = {role: 'user', content: [...blocks, {type: 'text', text: String(messages[li].content)}]};
    }
    const effort = opts.effort || window.DOCON_EFFORT || tierEffort[opts.modelTier] || 'medium';
    for (let step = 0; step < 12; step++) {
      text = '';
      const r = await claudeTurn({messages, effort, system: opts.system, tools: tools.map((t) => ({name: t.name, description: t.description, input_schema: t.inputSchema}))}, (d) => { text += d; opts.onText && opts.onText({text: all + text}); }, opts.signal)
        .catch((e) => { throw Object.assign(e, {text: all + text}); });
      all += text;
      if (r.stop_reason === 'refusal') throw Object.assign(new Error('recusado'), {code: 'refused', text: all});
      const uses = (r.content || []).filter((b) => b.type === 'tool_use');
      if (r.stop_reason !== 'tool_use' || !uses.length) return {text: all};
      if (r.stop_reason === 'max_tokens') throw Object.assign(new Error('cortado'), {code: 'unavailable', text: all});
      messages.push({role: 'assistant', content: r.content});
      const results = [];
      for (const u of uses) {
        const t = tools.find((x) => x.name === u.name); let content, is_error = false;
        try { if (!t) throw new Error('ferramenta desconhecida'); if (!validInput(t.inputSchema, u.input)) throw new Error('INVALID_JSON: entrada incompleta, envie de novo'); content = JSON.stringify(await t.execute(u.input) ?? 'ok'); }
        catch (e) { content = String(e.message || e); is_error = true; }
        results.push({type: 'tool_result', tool_use_id: u.id, content, ...(is_error ? {is_error} : {})});
      }
      messages.push({role: 'user', content: results}); if (all && !all.endsWith('\n')) all += '\n';
    }
    return {text: all};
  }
  sample.json = async (prompt, opts = {}) => { const {text} = await sample([{role: 'user', content: prompt + '\n\nResponda apenas com JSON válido, sem texto em volta.'}], opts); const m = text.match(/[\[{][\s\S]*[\]}]/); return JSON.parse(m ? m[0] : text); };
  sample.limits = async () => ({tools: true, images: {maxCount: 8, maxInputBytes: 5 * 1024 * 1024, mediaTypes: ['image/jpeg', 'image/png', 'image/webp', 'image/gif']}});

  /* ---------- arquivos, identidade, downloads, sessão com o agente ---------- */
  const assets = {
    upload: async (file, o = {}) => { const r = await api('/api/assets', {method: 'POST', headers: {'Content-Type': o.type || file.type || 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name || 'arquivo')}, body: file}); return r; },
    delete: (id) => api('/api/assets/' + id, {method: 'DELETE'}),
    list: () => api('/api/assets'),
  };
  const user = { me: () => api('/api/me'), profiles: (ids) => api('/api/profiles?ids=' + encodeURIComponent(ids.join(','))) };
  const downloads = { save: async ({filename, data}) => { const b = data instanceof Blob ? data : new Blob([data]); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000); } };
  // a aba "Sessão" do Studio fala com o agente de edição na nuvem (Claude Managed Agents + skill docon-cinema)
  const comments = {
    canSendToClaude: async () => { try { return (await api('/api/agente')).configurado ? 'available' : 'no_session'; } catch (e) { return 'off'; } },
    anchorFor: async () => ({}),
    sendToClaude: async ({text}) => { const r = await api('/api/agente', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})}); return {threadId: r.threadId || 'agente'}; },
  };
  const caps = {db: {doc, collection}, sample, assets, user, downloads, comments};
  window.claude = {use: async (name) => caps[name] || null};
  // voz única da DocOn gerada no servidor (quando configurada): igual em todos os computadores
  const vozCache = new Map();
  api('/api/ditado').then((j) => { if (j && j.configurado) window.DOCON_DITADO = async (blob) => (await api('/api/ditado', {method: 'POST', headers: {'Content-Type': blob.type || 'audio/webm'}, body: blob})).texto || ''; }).catch(() => {});
  api('/api/voz').then((j) => { if (j && j.configurada) window.DOCON_TTS = async (texto) => {
    if (vozCache.has(texto)) return vozCache.get(texto);
    const r = await fetch('/api/voz', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({texto}), credentials: 'same-origin'});
    if (!r.ok) throw new Error('voz'); const u = URL.createObjectURL(await r.blob()); vozCache.set(texto, u); return u; }; }).catch(() => {});
})();
