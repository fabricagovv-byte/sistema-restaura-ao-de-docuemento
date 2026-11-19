const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1366, 1100], [390, 1400]]) { const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(String(e)));
    await p.goto('file://' + process.argv[2]); await p.waitForSelector('#lista article'); await p.waitForTimeout(500);
    const ordem = await p.$$eval('.wrap > section, .wrap > nav, .wrap > div, .wrap > h2', (xs) => xs.map((x) => (x.id || x.className || x.tagName) + (x.classList.contains('fechado') ? '(recolhido)' : '')));
    console.log(w, ordem.join(' > ')); console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
    await p.screenshot({ path: `topo-${w}.png` }); await p.close(); }
  console.log('erros', JSON.stringify(erros)); await b.close(); })();
