// Prepara o site na primeira vez: gera os materiais base (sons, trilhas, imagens, vídeos) com a skill,
// guarda os arquivos no armazenamento do site e registra no banco com os mesmos ids do Studio ("base-…").
// Também cria os estilos padrão, se ainda não existirem.   node materiais.mjs
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
process.env.DOCON_NAO_ESCUTAR = '1';
const {dbGet, dbSet, saveBlob, flushDB} = await import('./server.mjs');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(process.env.DOCON_DATA || path.join(HERE, 'data'), 'materiais');
if (!fs.existsSync(path.join(OUT, 'catalogo.json'))) execFileSync('python3', [path.join(HERE, '..', '.claude/skills/docon-cinema/scripts/materiais_base.py'), OUT], {stdio: 'inherit'});
const cat = JSON.parse(fs.readFileSync(path.join(OUT, 'catalogo.json'), 'utf8')); let n = 0;
for (const c of cat) {
  if (dbGet('banco/' + c.id)) continue;
  const type = c.tipo === 'imagem' ? 'image/jpeg' : c.tipo === 'video' ? 'video/mp4' : 'audio/mp4';
  const id = saveBlob(fs.readFileSync(path.join(OUT, c.arquivo)), type, path.basename(c.arquivo), 'materiais');
  dbSet('banco/' + c.id, {tipo: c.tipo, nome: c.nome, tags: c.tags, asset_id: id, mime: type, duracao: c.duracao, base: true, origem: 'materiais_base.py', criado: Date.now()}); n++;
}
const est = JSON.parse(fs.readFileSync(path.join(HERE, 'seed', 'estilos.json'), 'utf8'));
for (const [k, v] of Object.entries(est)) if (!dbGet('estilos/' + k)) dbSet('estilos/' + k, v);
flushDB(); console.log(`${n} materiais novos registrados · estilos: ${Object.keys(est).join(', ')}`);
