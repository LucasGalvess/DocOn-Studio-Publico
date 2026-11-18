const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const [,,out,dur,lista]=process.argv;fs.mkdirSync(out,{recursive:true});
const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const p=await b.newPage({viewport:{width:1080,height:1920}});const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto('http://127.0.0.1:8811/cena.html');await p.waitForFunction(()=>window.pronto,null,{timeout:180000}).catch(e=>errs.push('timeout'));
if(errs.length)console.log('ERROS',errs.join('\n'));
const ts=lista?lista.split(',').map(Number):Array.from({length:Math.round(+dur*30)},(_,i)=>i/30);const t0=Date.now();
for(const [i,t] of ts.entries()){await p.evaluate(t=>window.renderAt(t),t);await p.screenshot({path:`${out}/${String(i).padStart(5,'0')}.png`});if(i%100==0)console.log('q',i,((Date.now()-t0)/1000).toFixed(0)+'s')}
console.log('ok',ts.length,errs.length);await b.close();})();
