// Ditado no site: o navegador grava a fala (quando não tem reconhecimento de voz próprio, como Firefox, Safari ou o app
// do Claude) e o servidor transcreve com o modelo da skill (scripts/ditado.py, Parakeet pt-BR, gratuito e local).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const PY = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '.claude/skills/docon-cinema/scripts/ditado.py');
const MOD = path.join(process.env.DOCON_MODELOS || path.join(os.homedir(), '.docon/models'), 'parakeet');
export const ditadoConfigurado = () => fs.existsSync(path.join(MOD, 'encoder.int8.onnx'));
export function transcrever(buf, tipo = '') {
  const ext = /webm/.test(tipo) ? '.webm' : /ogg/.test(tipo) ? '.ogg' : /mp4|aac|m4a/.test(tipo) ? '.m4a' : /wav/.test(tipo) ? '.wav' : '.bin';
  const f = path.join(os.tmpdir(), 'dit-' + crypto.randomBytes(8).toString('hex') + ext); fs.writeFileSync(f, buf);
  return new Promise((ok, no) => { const p = spawn('python3', [PY, f, MOD]); let out = '', err = '';
    const to = setTimeout(() => p.kill('SIGKILL'), 120000);
    p.stdout.on('data', (d) => out += d); p.stderr.on('data', (d) => err += d);
    p.on('close', (c) => { clearTimeout(to); fs.rmSync(f, {force: true}); c === 0 ? ok(out.trim()) : no(new Error('ditado.py: ' + err.slice(-300))); }); });
}
