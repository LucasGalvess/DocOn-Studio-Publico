// DocOn 3D · renderiza uma cena de cena.html quadro a quadro (PNG com transparência, 720x1280; o pipeline amplia para 1080x1920).
// uso: node render3d.cjs CENA DUR_DESENHO SAIDA [t1,t2,... | ""] [DUR_REAL]   (DUR_REAL ajusta o ritmo da cena ao tempo do bloco)
// Precisa da pasta servida em http://127.0.0.1:${PORTA:-8799}/ com cena.html, malha.json, three/ e fonts/ (anim3d.sh prepara).
const {chromium} = require('playwright'); const fs = require('fs');
const [sc, dur, out, lista, real] = process.argv.slice(2); const K = real ? +dur / +real : 1; fs.mkdirSync(out, {recursive: true});
(async () => {
  const b = await chromium.launch({args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']});
  const p = await b.newPage({viewport: {width: 720, height: 1280}}); const erros = [];
  p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
  await p.goto(`http://127.0.0.1:${process.env.PORTA || 8799}/cena.html?s=${sc}&dur=${dur}`); await p.waitForFunction(() => window.pronto, null, {timeout: 60000}).catch(() => {});
  if (erros.length) { console.log('ERROS', erros.join('\n')); }
  const ts = lista ? lista.split(',').map(Number) : Array.from({length: Math.ceil((real ? +real : +dur) * 30) + 2}, (_, i) => i / 30 * K);
  for (const [i, t] of ts.entries()) { await p.evaluate((t) => window.renderAt(t), t);
    await p.screenshot({path: `${out}/${lista ? 't' + t : String(i).padStart(5, '0')}.png`, omitBackground: true}); }
  console.log('ok', sc, ts.length, erros.length ? 'com erros' : ''); await b.close();
})();
