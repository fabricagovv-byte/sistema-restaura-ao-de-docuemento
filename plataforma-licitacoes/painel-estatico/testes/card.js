const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  await p.click('#cat-gv'); await p.selectOption('#ord', 'vol'); await p.fill('#q', 'ust|pf'); await p.waitForTimeout(100);
  await p.evaluate(() => document.getElementById('lista').scrollIntoView()); await p.screenshot({ path: 'card-cel.png' }); await b.close(); })();
