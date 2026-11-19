// uso: node render_t.cjs CENA SAIDA [t1,t2,...]   (sem lista: todos os quadros da cena a 30 fps)
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const [,,sc,out,lista]=process.argv;fs.mkdirSync(out,{recursive:true});const full=+sc===4;
const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const p=await b.newPage({viewport:{width:1080,height:full?1920:960}});const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto('http://127.0.0.1:8811/testes.html?s='+sc);await p.waitForFunction(()=>window.pronto,null,{timeout:180000}).catch(()=>errs.push('timeout'));
if(errs.length)console.log('ERROS',errs.join('\n'));const dur=await p.evaluate(()=>window.DUR);
const ts=lista?lista.split(',').map(Number):Array.from({length:Math.round(dur*30)},(_,i)=>i/30);
for(const [i,t] of ts.entries()){await p.evaluate(t=>window.renderAt(t),t);await p.screenshot({path:`${out}/${String(i).padStart(5,'0')}.png`});}
console.log('ok',sc,ts.length,errs.length);await b.close();})();
