const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const [w, h, n] of [[1280, 1000, 'p-desk'], [400, 900, 'p-cel']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    p.on('pageerror', e => erros.push(e.message)); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + process.argv[2]); await p.waitForTimeout(800);
    if (n === 'p-desk') { await p.click('#cat-fabrica_software'); await p.waitForTimeout(300); console.log(await p.textContent('#conta')); await p.click('#cat-todas'); }
    await p.screenshot({ path: `${n}.png` });
    console.log(n, 'largura do conteúdo', await p.evaluate(() => document.documentElement.scrollWidth));
  }
  console.log('erros:', erros.filter(e => !e.includes('fonts.g')));
  await b.close();
})();
