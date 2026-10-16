// Captura cuadros de una composicion HTML con funcion determinista window.renderFrame(t).
// Uso: node render_worker.js <index.html> <outdir> <fps> <from> <to> [quality]
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const [comp, outdir, fpsS, fromS, toS, qS] = process.argv.slice(2);
  const fps = parseFloat(fpsS), from = parseInt(fromS), to = parseInt(toS);
  const quality = parseInt(qS || '95');
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({
    args: ['--allow-file-access-from-files', '--disable-web-security', '--font-render-hinting=none',
           '--force-color-profile=srgb', '--disable-gpu-vsync', '--hide-scrollbars'],
  });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('console', m => { if (m.type() === 'error') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto('file://' + path.resolve(comp));
  await page.evaluate(async () => { await document.fonts.ready; if (window.prepare) await window.prepare(); });
  const t0 = Date.now();
  for (let i = from; i < to; i++) {
    const out = path.join(outdir, `f_${String(i).padStart(5, '0')}.jpg`);
    if (fs.existsSync(out)) continue;
    await page.evaluate(async (t) => { await window.renderFrame(t); }, i / fps);
    await page.screenshot({ path: out, type: 'jpeg', quality });
    if ((i - from) % 30 === 0) {
      const el = (Date.now() - t0) / 1000;
      process.stdout.write(`w${from}: ${i - from + 1}/${to - from} (${(el / (i - from + 1)).toFixed(2)} s/cuadro)\n`);
    }
  }
  await browser.close();
  process.stdout.write(`w${from}: listo\n`);
})().catch(e => { console.error(e); process.exit(1); });
