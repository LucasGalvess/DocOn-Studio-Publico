// Voz da DocOn: uma voz única, igual em todos os computadores, gerada no servidor.
// Base (VOZ_PROVEDOR): "kokoro" (padrão, gratuita, roda no próprio servidor: scripts/voz.py da skill, voz pf_dora pt-BR),
// "azure" (voz neural pt-BR) ou "elevenlabs" (voz desenhada). Sempre com sotaque brasileiro nativo.
// Por cima, o tratamento "assistente de IA" da DocOn (brilho, chorus sutil, eco curto), feito com ffmpeg.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';

import os from 'node:os';
import {fileURLToPath} from 'node:url';
const PROV = (process.env.VOZ_PROVEDOR || 'kokoro').toLowerCase();       // kokoro | azure | elevenlabs
const VOZPY = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '.claude/skills/docon-cinema/scripts/voz.py');
const KOKORO = path.join(process.env.DOCON_MODELOS || path.join(os.homedir(), '.docon/models'), 'kokoro', 'kokoro-v1.0.onnx');
export const vozConfigurada = () => (PROV === 'kokoro' && fs.existsSync(KOKORO)) || (PROV === 'azure' && !!process.env.VOZ_AZURE_CHAVE) || (PROV === 'elevenlabs' && !!process.env.VOZ_ELEVEN_CHAVE && !!process.env.VOZ_ELEVEN_ID);
function kokoro(texto, perfil, saida) {
  return new Promise((ok, no) => { const p = spawn('python3', [VOZPY, '-', saida, '--perfil', perfil || 'assistente']); let err = '';
    p.stderr.on('data', (d) => err += d); p.on('close', (c) => c === 0 ? ok() : no(new Error('voz.py: ' + err.slice(-300)))); p.stdin.end(texto); });
}

// tratamento da voz (mude VOZ_EFEITO para "nenhum" se quiserem a voz seca)
export const CADEIAS = {
  docon: 'highpass=f=90,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2,equalizer=f=9500:t=h:w=3000:g=3.5,' +
         'chorus=0.7:0.9:24|37:0.16|0.11:0.30|0.25:1.4|2.1,aecho=0.85:0.7:32|61:0.13|0.07,loudnorm=I=-18:TP=-2:LRA=7',
  leve: 'highpass=f=90,equalizer=f=9500:t=h:w=3000:g=2.5,aecho=0.85:0.7:30:0.08,loudnorm=I=-18:TP=-2:LRA=7',
  nenhum: 'highpass=f=80,loudnorm=I=-18:TP=-2:LRA=7',
};
const esc = (s) => String(s).replace(/[<>&'"]/g, (c) => ({'<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;'}[c]));

async function azure(texto, o) {
  const voz = o.voz || process.env.VOZ_AZURE_NOME || 'pt-BR-FranciscaNeural';
  const ssml = `<speak version="1.0" xml:lang="pt-BR" xmlns="http://www.w3.org/2001/10/synthesis"><voice name="${esc(voz)}"><prosody rate="${o.ritmo || '-6%'}" pitch="${o.tom || '-3%'}">${esc(texto)}</prosody></voice></speak>`;
  const r = await fetch(`https://${process.env.VOZ_AZURE_REGIAO || 'brazilsouth'}.tts.speech.microsoft.com/cognitiveservices/v1`, {method: 'POST',
    headers: {'Ocp-Apim-Subscription-Key': process.env.VOZ_AZURE_CHAVE, 'Content-Type': 'application/ssml+xml', 'X-Microsoft-OutputFormat': 'riff-48khz-16bit-mono-pcm', 'User-Agent': 'docon-studio'}, body: ssml});
  if (!r.ok) throw new Error('Azure ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return {buf: Buffer.from(await r.arrayBuffer()), fmt: 'wav'};
}
async function eleven(texto, o) {
  const id = o.voz || process.env.VOZ_ELEVEN_ID;
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(id)}?output_format=mp3_44100_128`, {method: 'POST',
    headers: {'xi-api-key': process.env.VOZ_ELEVEN_CHAVE, 'Content-Type': 'application/json', Accept: 'audio/mpeg'},
    body: JSON.stringify({text: texto, model_id: process.env.VOZ_ELEVEN_MODELO || 'eleven_multilingual_v2', language_code: 'pt', voice_settings: {stability: 0.62, similarity_boost: 0.8, style: 0.15, use_speaker_boost: true}})});
  if (!r.ok) throw new Error('ElevenLabs ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return {buf: Buffer.from(await r.arrayBuffer()), fmt: 'mp3'};
}
export function tratar(buf, cadeia = 'docon') {
  return new Promise((ok, no) => {
    const f = CADEIAS[cadeia] || CADEIAS.docon;
    const p = spawn('ffmpeg', ['-v', 'error', '-i', 'pipe:0', '-af', f, '-ar', '48000', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '128k', '-f', 'mp3', 'pipe:1']);
    const out = []; let err = ''; p.stdout.on('data', (d) => out.push(d)); p.stderr.on('data', (d) => err += d);
    p.on('close', (c) => c === 0 ? ok(Buffer.concat(out)) : no(new Error('ffmpeg: ' + err.slice(0, 300)))); p.stdin.end(buf);
  });
}
// mp3 pronto (com cache em disco: a mesma frase não é cobrada duas vezes)
export async function falar(texto, dataDir, o = {}) {
  texto = String(texto || '').replace(/[*#_`]/g, '').trim().slice(0, 2500); if (!texto) throw new Error('texto vazio');
  const cadeia = o.efeito || process.env.VOZ_EFEITO || 'docon';
  const key = crypto.createHash('sha256').update(JSON.stringify([PROV, o.voz || '', cadeia, o.perfil || '', o.ritmo || '', o.tom || '', texto])).digest('hex').slice(0, 32);
  const dir = path.join(dataDir, 'voz'); fs.mkdirSync(dir, {recursive: true}); const f = path.join(dir, key + '.mp3');
  if (fs.existsSync(f)) return fs.readFileSync(f);
  if (PROV === 'kokoro') { await kokoro(texto, o.perfil, f); return fs.readFileSync(f); }   // o voz.py já aplica pronúncia e tratamento
  const src = PROV === 'elevenlabs' ? await eleven(texto, o) : await azure(texto, o);
  const mp3 = await tratar(src.buf, cadeia); fs.writeFileSync(f, mp3); return mp3;
}
