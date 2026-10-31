// Cria (uma vez) o ambiente e o agente de edição no Claude Managed Agents e imprime os ids para o .env.
// Rodar de novo atualiza o agente (nova versão) em vez de criar outro, se DOCON_AGENTE_ID já estiver definido.
//   node agente-setup.mjs
import Anthropic from '@anthropic-ai/sdk';
import {AGENT_SYSTEM, AGENT_TOOLS} from './agente-def.mjs';

const client = new Anthropic();
const MODEL = process.env.DOCON_MODELO || 'claude-opus-5-5';
// hosts que o setup da skill usa para baixar modelos e fontes (o resto da internet fica fechado)
const HOSTS = ['github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com', 'raw.githubusercontent.com', 'storage.googleapis.com',
  'fonts.googleapis.com', 'fonts.gstatic.com', 'registry.npmjs.org',
  // mídia online (scripts/buscar_midia.py)
  'api.magnific.com', 'api.freepik.com', 'api.pexels.com', 'images.pexels.com', 'videos.pexels.com', 'pixabay.com', 'cdn.pixabay.com', 'freesound.org', 'cdn.freesound.org', 'api.openverse.org'];

let env = process.env.DOCON_AMBIENTE_ID;
if (!env) {
  const e = await client.beta.environments.create({name: 'docon-studio-render', description: 'Render DocOn Cinema (ffmpeg, Python, modelos ONNX)',
    config: {type: 'cloud', networking: {type: 'limited', allow_package_managers: true, allowed_hosts: HOSTS}}});
  env = e.id;
}
const def = {
  name: 'DocOn Editor', model: {id: MODEL, effort: process.env.DOCON_AGENTE_ESFORCO || 'high'}, system: AGENT_SYSTEM,
  tools: [{type: 'agent_toolset_20260401', default_config: {enabled: true, permission_policy: {type: 'auto'}},
    configs: [{name: 'web_fetch', enabled: false}, {name: 'web_search', enabled: false}]}, ...AGENT_TOOLS],
};
let agent;
if (process.env.DOCON_AGENTE_ID) agent = await client.beta.agents.update(process.env.DOCON_AGENTE_ID, def);
else agent = await client.beta.agents.create(def);
console.log(`DOCON_AMBIENTE_ID=${env}\nDOCON_AGENTE_ID=${agent.id}   # versão ${agent.version}`);
