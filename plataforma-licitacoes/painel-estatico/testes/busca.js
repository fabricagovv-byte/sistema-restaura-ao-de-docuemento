const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1280, 1000], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', e => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  const chips = await p.evaluate(() => [...document.querySelectorAll('#cats button')].slice(0, 7).map(b => b.textContent.trim()));
  console.log(w, chips);
  await p.click('#cat-gv'); console.log(' grande volume:', await p.textContent('#conta'));
  await p.selectOption('#ord', 'vol'); console.log(' 1º:', (await p.textContent('.card .obj')).slice(0, 70), '|', await p.evaluate(() => [...document.querySelectorAll('.card')][0].querySelector('.vol')?.textContent));
  await p.click('#cat-todas');
  for (const q of ['ust', 'ust|pf', '"gestão documental"', 'digitalização -impressora', 'sistema folha pagamento', 'ead']) {
    await p.fill('#q', q); await p.waitForTimeout(80); console.log(' busca', JSON.stringify(q), '→', (await p.textContent('#conta')).split('·')[0].trim());
  }
  await p.fill('#q', ''); await p.selectOption('#tipo', 'todos'); console.log(' todos os tipos:', (await p.textContent('#conta')).split('·')[0], '| chip todas', await p.textContent('#cat-todas'));
  await p.selectOption('#tipo', 'material'); console.log(' só material:', (await p.textContent('#conta')).split('·')[0]);
  await p.selectOption('#tipo', 'servico');
  const baixar = await p.evaluate(() => [...document.querySelectorAll('.card a.baixar')].slice(0, 2).map(a => a.textContent + ' ' + a.href));
  console.log(' baixar:', baixar);
  await p.click('#cat-gv'); await p.click('.abrir'); await p.waitForTimeout(200);
  console.log(' ficha baixar:', await p.locator('#ficha-corpo a.baixar').count(), '| vol:', await p.locator('#ficha-corpo .vol').count(), '| largura', await p.evaluate(() => document.documentElement.scrollWidth));
  if (w < 500) await p.screenshot({ path: 'b-cel.png' });
  }
  console.log('erros', erros); await b.close(); })();
