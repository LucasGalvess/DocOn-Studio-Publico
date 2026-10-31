// Gera as amostras para a equipe escolher a voz da DocOn (salvas em data/voz-amostras/).
//   VOZ_PROVEDOR=azure VOZ_AZURE_CHAVE=... node voz-amostras.mjs
//   VOZ_PROVEDOR=elevenlabs VOZ_ELEVEN_CHAVE=... node voz-amostras.mjs   (desenha vozes novas pela descrição)
// Depois de escolher, coloque VOZ_AZURE_NOME (ou VOZ_ELEVEN_ID) nas variáveis do site.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {tratar} from './voz.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(process.env.DOCON_DATA || path.join(HERE, 'data'), 'voz-amostras'); fs.mkdirSync(OUT, {recursive: true});
const TEXTO = 'Agora entra o painel de vidro com a ficha do paciente. Cada item aparece no momento exato da fala, para o público acompanhar sem esforço.';
// descrição genérica do estilo "assistente de IA": nenhuma referência a pessoa ou personagem real
const DESCRICAO = 'Voz feminina adulta, por volta de 30 anos, falante nativa de português do Brasil com sotaque paulistano neutro. Timbre médio-grave, limpo e sem soprosidade. ' +
  'Fala calma, segura e acolhedora, articulação precisa, pausas bem marcadas, tom de assistente de inteligência artificial elegante e confiável. Gravação de estúdio, sem ruído.';
const PROV = (process.env.VOZ_PROVEDOR || '').toLowerCase();
const salvar = async (nome, buf) => { fs.writeFileSync(path.join(OUT, nome + '_seca.' + (PROV === 'azure' ? 'wav' : 'mp3')), buf); for (const c of ['docon', 'leve']) fs.writeFileSync(path.join(OUT, `${nome}_${c}.mp3`), await tratar(buf, c)); console.log('ok', nome); };

if (PROV === 'azure') {
  const {VOZ_AZURE_CHAVE: K, VOZ_AZURE_REGIAO: R = 'brazilsouth'} = process.env;
  for (const v of (process.env.VOZ_AZURE_CANDIDATAS || 'pt-BR-FranciscaNeural,pt-BR-ThalitaNeural,pt-BR-GiovannaNeural').split(',')) {
    const ssml = `<speak version="1.0" xml:lang="pt-BR" xmlns="http://www.w3.org/2001/10/synthesis"><voice name="${v}"><prosody rate="-6%" pitch="-3%">${TEXTO}</prosody></voice></speak>`;
    const r = await fetch(`https://${R}.tts.speech.microsoft.com/cognitiveservices/v1`, {method: 'POST', headers: {'Ocp-Apim-Subscription-Key': K, 'Content-Type': 'application/ssml+xml', 'X-Microsoft-OutputFormat': 'riff-48khz-16bit-mono-pcm', 'User-Agent': 'docon-studio'}, body: ssml});
    if (!r.ok) { console.log('falhou', v, r.status, (await r.text()).slice(0, 200)); continue; }
    await salvar(v, Buffer.from(await r.arrayBuffer()));
  }
} else if (PROV === 'elevenlabs') {
  // Voice Design: a ElevenLabs cria prévias de vozes novas a partir da descrição; cada uma vem com generated_voice_id
  const r = await fetch('https://api.elevenlabs.io/v1/text-to-voice/create-previews', {method: 'POST', headers: {'xi-api-key': process.env.VOZ_ELEVEN_CHAVE, 'Content-Type': 'application/json'},
    body: JSON.stringify({voice_description: DESCRICAO, text: TEXTO})});
  if (!r.ok) { console.log('falhou', r.status, (await r.text()).slice(0, 300)); process.exit(1); }
  const j = await r.json();
  for (const [i, p] of (j.previews || []).entries()) await salvar(`eleven_${i + 1}_${p.generated_voice_id}`, Buffer.from(p.audio_base_64, 'base64'));
  console.log('Para fixar a escolhida, salve a prévia como voz na ElevenLabs (Voice Design › Save) e use o voice_id em VOZ_ELEVEN_ID.');
} else console.log('Defina VOZ_PROVEDOR=azure ou elevenlabs e a chave correspondente.');
console.log('Amostras em', OUT);
