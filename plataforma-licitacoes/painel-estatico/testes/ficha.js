const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = []; const f = process.argv[2];
  for (const [w, h, n] of [[1280, 1000, 'f-desk'], [390, 844, 'f-cel']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    p.on('pageerror', e => erros.push(e.message)); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + f); await p.waitForTimeout(600);
    console.log(n, await p.textContent('#conta'), 'largura', await p.evaluate(() => document.documentElement.scrollWidth));
    await p.click('#cat-todas');
    await p.selectOption('#plat', 'BLL Compras'); await p.waitForTimeout(200); console.log(' BLL:', await p.textContent('#conta'));
    await p.selectOption('#plat', ''); await p.fill('#q', 'praia grande'); await p.waitForTimeout(200);
    await p.click('.abrir'); await p.waitForTimeout(300);
    console.log(' aberto', await p.evaluate(() => document.getElementById('ficha').open), location = await p.evaluate(() => location.hash));
    console.log(' itens', await p.locator('#ficha-corpo table tbody tr').count(), 'docs', await p.locator('.docs li').count(),
      'largura dialog', await p.evaluate(() => document.getElementById('ficha').scrollWidth));
    await p.screenshot({ path: `${n}.png` });
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);
    console.log(' fechado', !(await p.evaluate(() => document.getElementById('ficha').open)), await p.evaluate(() => location.hash));
    await p.goto('file://' + f + '#p25531'); await p.waitForTimeout(500);
    console.log(' deep link', await p.evaluate(() => document.getElementById('ficha').open), (await p.textContent('#ficha-titulo')));
    if (n === 'f-desk') { await p.keyboard.press('Escape'); await p.evaluate(() => document.getElementById('avisos').scrollIntoView()); await p.screenshot({ path: 'f-avisos.png' }); console.log(' avisos', await p.locator('.aviso').count(), 'portais', await p.locator('#portais tr').count()); }
  }
  console.log('erros:', erros.filter(e => !e.includes('fonts.g')));
  await b.close();
})();
