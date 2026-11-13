const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1366, 1000], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  const blocos = await p.$$eval('.dst-bloco', (bs) => bs.map((b) => b.querySelector('h3').textContent.replace(/\s+/g, ' ').trim() + ' | 1º: ' + (b.querySelector('.dst-item') ? b.querySelector('.dst-item').textContent.replace(/\s+/g, ' ').trim().slice(0, 110) : '-')));
  if (w > 1000) blocos.forEach((x) => console.log(' ', x));
  console.log(w, 'cartões em destaque na lista:', await p.locator('.card.destaque').count(), '| faixa:', await p.locator('.faixa-destaque').first().textContent().catch(() => '-'));
  await p.click('.dst-item >> nth=0'); console.log(' clique no destaque -> prévia:', (await p.textContent('#previa h3')).trim());
  await p.uncheck('#dst-so-pregao'); console.log(' sem "só pregões":', (await p.textContent('.dst-bloco h3')).replace(/\s+/g, ' '));
  const todos = p.locator('[data-dst-todos]').first(); if (await todos.count()) { await todos.click(); console.log(' ver todos ->', (await p.textContent('#conta')).trim().slice(0, 60), '| ordem:', await p.inputValue('#ord')); }
  if (w > 1000) await p.screenshot({ path: 'destaques.png' });
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); await p.close(); }
  console.log('erros', erros); await b.close(); })();
