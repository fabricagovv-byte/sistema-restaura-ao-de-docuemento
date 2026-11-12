const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1280, 1000], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  for (const c of ['remun_fixo_mensal', 'remun_ust', 'remun_pf', 'digitalizacao', 'indexacao']) {
    await p.click('#cat-' + c); await p.waitForTimeout(100);
    const blocos = await p.locator('.card .itens-tipo:not(.vazio)').count();
    console.log(w, c, '|', (await p.textContent('#conta')).trim(), '| cards com itens do tipo:', blocos);
    if (blocos) console.log('   1º:', (await p.locator('.card .itens-tipo:not(.vazio) tbody tr').first().textContent()).replace(/\s+/g, ' ').slice(0, 130));
  }
  await p.click('#cat-remun_fixo_mensal'); await p.fill('#imin', '200 mil'); await p.waitForTimeout(150);
  console.log(' mensal itens > 200 mil:', (await p.textContent('#conta')).trim());
  await p.selectOption('#ord', 'itens'); await p.waitForTimeout(150);
  console.log(' maior valor nos itens:', (await p.locator('.card .itens-tipo p').first().textContent()).trim(), '|', (await p.locator('.card .obj').first().textContent()).slice(0, 70));
  await p.fill('#imin', ''); await p.fill('#vmin', '1,5 mi'); await p.waitForTimeout(150);
  console.log(' edital > 1,5 mi:', (await p.textContent('#conta')).trim(), '| menor valor mostrado ok:', await p.evaluate(() => [...document.querySelectorAll('.card .valor')].every((v) => !/R\$/.test(v.textContent) || parseFloat(v.textContent.replace(/[^\d,]/g, '').replace(',', '.')) >= 1.5e6)));
  await p.fill('#vmin', '300.000'); await p.waitForTimeout(100); const a = (await p.textContent('#conta')).trim();
  await p.fill('#vmin', '300 mil'); await p.waitForTimeout(100); console.log(' "300.000" = "300 mil":', a === (await p.textContent('#conta')).trim());
  await p.screenshot({ path: `itens-${w}.png` });
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); await p.close(); }
  console.log('erros', erros); await b.close(); })();
