// DocOn Artes · renderiza páginas HTML (uma por arte/slide) em PNG no tamanho exato, com o Chromium do Playwright.
// uso: node render.mjs PLANO.json   →  PLANO = {"paginas": [{"html": "/abs/slide_01.html", "png": "/abs/slide_01.png", "w": 1080, "h": 1350}]}
import {createRequire} from 'module';
const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const fs = require('fs');
const plano = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const exe = ['/opt/pw-browsers/chromium'].find((p) => fs.existsSync(p));
const b = await chromium.launch(exe && !fs.statSync(exe).isDirectory() ? {executablePath: exe} : {});
for (const pg of plano.paginas) {
  const page = await b.newPage({viewport: {width: pg.w, height: pg.h}, deviceScaleFactor: 1});
  const erros = []; page.on('pageerror', (e) => erros.push(e.message)); page.on('requestfailed', (r) => erros.push('falhou: ' + r.url().slice(0, 120)));
  await page.goto('file://' + pg.html, {waitUntil: 'networkidle'});
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode().catch(() => {}))); });
  // texto que não coube: avisa (o texto encolhe sozinho até o mínimo; se ainda assim vazar, o plano precisa de menos palavras)
  const vaza = await page.evaluate(() => [...document.querySelectorAll('[data-fit]')].filter((e) => e.scrollHeight > e.clientHeight + parseFloat(getComputedStyle(e).fontSize) * 0.25 + 2 || e.scrollWidth > e.clientWidth + 2).map((e) => e.dataset.fit));
  await page.screenshot({path: pg.png, clip: {x: 0, y: 0, width: pg.w, height: pg.h}});
  if (erros.length || vaza.length) console.log(JSON.stringify({png: pg.png, erros, texto_vazando: vaza}));
  await page.close();
}
await b.close();
console.log('ok', plano.paginas.length);
