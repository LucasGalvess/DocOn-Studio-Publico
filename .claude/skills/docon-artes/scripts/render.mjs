// DocOn Artes · monta as páginas com o motor (arte_engine.js, o mesmo da aba Artes do Studio) e tira o PNG de cada uma.
// uso: node render.mjs TRABALHO.json
//   TRABALHO = {"plano": {...}, "estilo": {...}, "ident": {...}, "saida": "/abs/dir", "fontes_css": "@font-face…",
//               "ft": "\"DocTitulo\",sans-serif", "fx": "\"DocTexto\",sans-serif", "logo": "logo.png", "arquivos": {"/orig/foto.jpg": "img_1.jpg"}}
// Saída: arte_NN.html e arte_NN.png em `saida`; uma linha JSON por página com problema (erros, texto_vazando).
import {createRequire} from 'module';
const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path');
const E = require('./arte_engine.js');
const T = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const n = E.nSlides(T.plano); const pngs = [];
const exe = ['/opt/pw-browsers/chromium'].find((p) => fs.existsSync(p));
const b = await chromium.launch(exe && !fs.statSync(exe).isDirectory() ? {executablePath: exe} : {});
for (let i = 0; i < n; i++) {
  const pg = E.pagina(T.plano, i, {estilo: T.estilo, ident: T.ident, url: (s) => (T.arquivos || {})[s] || s, logo: T.logo || '', ft: T.ft, fx: T.fx});
  const nome = `arte_${String(i + 1).padStart(2, '0')}`;
  const doc = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>${T.fontes_css || ''}\nhtml,body{margin:0;width:${pg.w}px;height:${pg.h}px;overflow:hidden}${pg.css}</style></head><body>${pg.html}</body></html>`;
  const hp = path.join(T.saida, nome + '.html'), png = path.join(T.saida, nome + '.png'); fs.writeFileSync(hp, doc);
  const page = await b.newPage({viewport: {width: pg.w, height: pg.h}, deviceScaleFactor: 1});
  const erros = []; page.on('pageerror', (e) => erros.push(e.message)); page.on('requestfailed', (r) => erros.push('falhou: ' + r.url().slice(0, 120)));
  await page.goto('file://' + hp, {waitUntil: 'networkidle'});
  await page.addScriptTag({path: path.join(path.dirname(new URL(import.meta.url).pathname), 'arte_engine.js')});
  const vaza = await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode().catch(() => {}))); return ArteEngine.ajustar(document); });
  await page.screenshot({path: png, clip: {x: 0, y: 0, width: pg.w, height: pg.h}});
  if (erros.length || vaza.length) console.log(JSON.stringify({png, erros, texto_vazando: vaza}));
  pngs.push({png, w: pg.w, h: pg.h}); await page.close();
}
await b.close();
console.log('ok', n);
