const { chromium } = require('playwright');
(async()=>{const [f,t,out]=process.argv.slice(2);
const b=await chromium.launch({args:['--allow-file-access-from-files','--disable-web-security']});
const p=await b.newPage({viewport:{width:1080,height:1920}});
p.on('pageerror',e=>console.error('ERR',e.message)); p.on('console',m=>{if(m.type()==='error')console.error(m.text())});
await p.goto('file://'+require('path').resolve(f)); await p.evaluate(async()=>{await document.fonts.ready; if(window.prepare) await window.prepare();});
for (const tt of t.split(',')) { await p.evaluate(async x=>{await window.renderFrame(x)}, parseFloat(tt)); await p.screenshot({path:out.replace('%t',tt),type:'jpeg',quality:90}); }
await b.close();})();
