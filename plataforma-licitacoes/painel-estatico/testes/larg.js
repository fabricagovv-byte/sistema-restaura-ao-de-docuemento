const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(500);
  console.log(await p.evaluate(() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > 392 && !e.closest('dialog')).slice(0, 8).map(e => e.tagName + '#' + e.id + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))));
  await p.click('.abrir'); await p.waitForTimeout(300);
  console.log(await p.evaluate(() => [...document.querySelectorAll('dialog *')].filter(e => e.getBoundingClientRect().right > 392 && !e.closest('.tabela')).slice(0, 8).map(e => e.tagName + '#' + e.id + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))));
  await b.close(); })();
