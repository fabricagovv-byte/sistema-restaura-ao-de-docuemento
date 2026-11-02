const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(500);
  const f = (sel) => p.evaluate((sel) => [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().right > 392 && ![...e.children].some(c => c.getBoundingClientRect().right > 392)).slice(0, 10).map(e => e.tagName + '#' + e.id + '.' + e.className + ' w' + Math.round(e.getBoundingClientRect().width) + ' ' + (e.textContent||'').slice(0,50)), sel);
  console.log(await f('body *'));
  await p.click('.abrir'); await p.waitForTimeout(300); console.log(await f('dialog *'));
  await b.close(); })();
