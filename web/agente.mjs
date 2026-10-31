// Agente de edição na nuvem: Claude Managed Agents com o repositório docon-studio montado
// (a skill .claude/skills/docon-cinema é descoberta sozinha) e ferramentas para ler/gravar o Studio.
// Uma sessão por projeto; as respostas do agente aparecem na aba "Sessão" do Studio (canal/site/msgs).
import fs from 'node:fs';
import {dbGet, dbSet, dbUpdate, saveBlob, blobPath} from './server.mjs';
import {AGENT_TOOLS} from './agente-def.mjs';

const AGENT = process.env.DOCON_AGENTE_ID, ENV = process.env.DOCON_AMBIENTE_ID;
const REPO = process.env.DOCON_REPO || 'https://github.com/LucasGalvess/DocOn-Studio';
const GH = process.env.DOCON_GITHUB_TOKEN;
const CID = 'site';
export const agentConfigured = () => !!(AGENT && ENV && GH && (process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN));

const say = (de, texto, extra = {}) => dbSet(`canal/${CID}/msgs/m-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, {de, texto: String(texto).slice(0, 8000), t: Date.now(), ...extra});
const status = (s) => { if (dbGet('sessoes/ativa')) dbUpdate('sessoes/ativa', {status: s || ''}); };
export function ensureSessaoAtiva() {
  if (agentConfigured() && !dbGet('sessoes/ativa')) dbSet('sessoes/ativa', {conversa_id: CID, titulo: 'Agente de edição DocOn (nuvem)', desde: Date.now(), status: ''});
}

async function upFile(anthropic, blobId, name) {
  const metaP = blobPath(blobId) + '.json'; const meta = JSON.parse(fs.readFileSync(metaP, 'utf8'));
  if (meta.file_id) return meta.file_id;
  const {toFile} = await import('@anthropic-ai/sdk');
  const f = await anthropic.files.upload({file: await toFile(fs.createReadStream(blobPath(blobId)), name, {type: meta.type})});
  meta.file_id = f.id; fs.writeFileSync(metaP, JSON.stringify(meta)); return f.id;
}
async function sessionFor(anthropic, proj) {
  const key = 'sistema/agente-' + (proj || 'geral'); const s = dbGet(key);
  if (s?.id) { try { const r = await anthropic.beta.sessions.retrieve(s.id); if (r.status !== 'terminated') return s.id; } catch (e) {} }
  const resources = [{type: 'github_repository', url: REPO, authorization_token: GH, mount_path: '/workspace/docon-studio', checkout: {type: 'branch', name: 'main'}}];
  const p = proj && dbGet('projetos/' + proj);
  for (const a of p?.midias || []) if (a.asset_id) resources.push({type: 'file', file_id: await upFile(anthropic, a.asset_id, a.nome), mount_path: '/workspace/media/' + a.nome.replace(/[^\w.\-]/g, '_')});
  for (const a of p?.anexos || []) if (a.asset_id) resources.push({type: 'file', file_id: await upFile(anthropic, a.asset_id, a.nome), mount_path: '/workspace/media/anexos/' + a.id + '-' + a.nome.replace(/[^\w.\-]/g, '_')});
  const sess = await anthropic.beta.sessions.create({agent: AGENT, environment_id: ENV, title: 'DocOn · ' + (p?.titulo || proj || 'geral'), resources});
  dbSet(key, {id: sess.id, criado: Date.now()}); dbUpdate('sessoes/ativa', {sessao_url: `https://platform.claude.com/workspaces/default/sessions/${sess.id}`});
  return sess.id;
}
async function runTool(anthropic, sid, ev) {
  const i = ev.input || {};
  if (ev.name === 'studio_ler') return JSON.stringify(dbGet(String(i.caminho)) ?? null);
  if (ev.name === 'studio_listar') { const c = String(i.colecao); const out = []; for (const k of Object.keys(globalThis.__doconDB?.() || {})) if (k.startsWith(c + '/') && k.split('/').length === c.split('/').length + 1) out.push(k.split('/').pop()); return JSON.stringify(out); }
  if (ev.name === 'studio_gravar') { const c = String(i.caminho); if (/^(data\/users|sistema)\//.test(c)) return 'caminho protegido'; (i.modo === 'set' ? dbSet : dbUpdate)(c, i.dados || {}); return 'ok'; }
  if (ev.name === 'studio_status') { status(String(i.texto || '')); return 'ok'; }
  if (ev.name === 'studio_publicar') {
    let files = []; for (let k = 0; k < 4 && !files.length; k++) { const l = await anthropic.beta.files.list({scope_id: sid, betas: ['managed-agents-2026-04-01']}); files = l.data.filter((f) => f.filename === i.arquivo || f.filename.endsWith('/' + i.arquivo)); if (!files.length) await new Promise((r) => setTimeout(r, 1500)); }
    if (!files.length) return 'arquivo não encontrado em /mnt/session/outputs/ (grave lá e tente de novo)';
    const resp = await anthropic.beta.files.download(files[0].id); const buf = Buffer.from(await resp.arrayBuffer());
    const type = /\.jpe?g$/i.test(i.arquivo) ? 'image/jpeg' : /\.png$/i.test(i.arquivo) ? 'image/png' : 'video/mp4';
    const id = saveBlob(buf, type, i.arquivo, 'agente'); const p = dbGet('projetos/' + i.projeto);
    if (p) { const v = i.tipo === 'previa' ? {rotulo: i.rotulo, data: Date.now(), previa_id: id, obs: i.obs || ''} : {rotulo: i.rotulo, data: Date.now(), asset_id: id, obs: i.obs || ''}; dbUpdate('projetos/' + i.projeto, {versoes: [...(p.versoes || []), v]}); }
    if (i.aprovacao && dbGet('aprovacoes/' + i.aprovacao)) dbUpdate('aprovacoes/' + i.aprovacao, {depois_asset: id});
    return JSON.stringify({asset_id: id});
  }
  return 'ferramenta desconhecida';
}
const running = new Map();
async function pump(anthropic, sid) {
  if (running.has(sid)) return; running.set(sid, true);
  try {
    const stream = await anthropic.beta.sessions.events.stream(sid);
    for await (const ev of stream) {
      if (ev.type === 'agent.message') { const t = (ev.content || []).filter((b) => b.type === 'text').map((b) => b.text).join(''); if (t.trim()) say('claude', t); }
      else if (ev.type === 'agent.custom_tool_use') { let out; try { out = await runTool(anthropic, sid, ev); } catch (e) { out = 'erro: ' + (e.message || e); } await anthropic.beta.sessions.events.send(sid, {events: [{type: 'user.custom_tool_result', custom_tool_use_id: ev.id, content: [{type: 'text', text: String(out)}]}]}); }
      else if ((ev.type === 'agent.tool_use' || ev.type === 'agent.mcp_tool_use') && ev.evaluated_permission === 'ask') {
        // ninguém aprova chamadas em tempo real aqui: nega e avisa a equipe na aba Sessão
        await anthropic.beta.sessions.events.send(sid, {events: [{type: 'user.tool_confirmation', tool_use_id: ev.id, result: 'deny'}]}); say('sistema', 'O agente pediu permissão para uma ação de risco e ela foi negada automaticamente.');
      }
      else if (ev.type === 'session.status_idle') { if (ev.stop_reason?.type !== 'requires_action') { status(''); break; } }
      else if (ev.type === 'session.status_terminated') { status(''); break; }
    }
  } catch (e) { say('sistema', 'Conexão com o agente caiu: ' + (e.message || e)); status(''); }
  finally { running.delete(sid); }
}
export async function startAgentRun({texto, anthropic}) {
  if (!agentConfigured()) return {ok: false, erro: 'agente não configurado'};
  const proj = /projeto ([\w-]+)/.exec(texto)?.[1];
  const sid = await sessionFor(anthropic, proj && proj !== '-' ? proj : null);
  status('lendo o pedido');
  const go = pump(anthropic, sid);                               // abre o stream antes de mandar a mensagem
  await anthropic.beta.sessions.events.send(sid, {events: [{type: 'user.message', content: [{type: 'text', text: texto}]}]});
  go.catch(() => {});
  return {ok: true, threadId: sid};
}
