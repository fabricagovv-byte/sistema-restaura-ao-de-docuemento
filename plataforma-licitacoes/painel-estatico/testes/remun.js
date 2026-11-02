const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 390, height: 844 } }); const erros = [];
  p.on('pageerror', e => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  const ids = await p.evaluate(() => [...document.querySelectorAll('#cats button')].slice(0, 8).map(b => b.textContent.trim()));
  console.log(ids);
  for (const c of ['remun_fixo_mensal', 'remun_ust', 'remun_pf']) { await p.click('#cat-' + c); console.log(c, await p.textContent('#conta')); }
  await p.click('.abrir'); await p.waitForTimeout(200); console.log('ficha', (await p.textContent('#ficha-corpo')).includes('Ponto de Função'));
  console.log('largura', await p.evaluate(() => document.documentElement.scrollWidth), 'erros', erros); await b.close(); })();
