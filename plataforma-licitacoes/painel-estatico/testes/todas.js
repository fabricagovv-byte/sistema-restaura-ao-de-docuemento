const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = []; const f = process.argv[2];
  for (const [w, h, n] of [[1280, 1000, 't-desk'], [390, 844, 't-cel']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    p.on('pageerror', e => erros.push(e.message)); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
    const t0 = Date.now(); await p.goto('file://' + f);
    await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
    console.log(n, 'carregou tudo em', Date.now() - t0, 'ms;', await p.textContent('#cat-todas'), '|', await p.textContent('#cat-foco'), '|', await p.textContent('#cat-seg'));
    for (const c of ['ead', 'pesquisa', 'pd_inovacao']) console.log(' ', c, await p.locator('#cat-' + c).count() ? await p.textContent('#cat-' + c) : '-');
    await p.click('#cat-todas'); console.log(' todas:', await p.textContent('#conta'));
    const t1 = Date.now(); await p.fill('#q', 'ambulancia'); await p.waitForTimeout(50); console.log(' busca ambulancia:', await p.textContent('#conta'), Date.now() - t1, 'ms');
    await p.click('.abrir'); await p.waitForTimeout(300);
    console.log(' ficha', await p.textContent('#ficha-titulo'), '| links:', await p.locator('#ficha-corpo .acoes a').count(), '|', (await p.textContent('#ficha-corpo')).includes('carregados no painel só'));
    await p.screenshot({ path: `${n}.png` });
    await p.keyboard.press('Escape');
    await p.click('#cat-ead'); await p.fill('#q', ''); await p.waitForTimeout(100); console.log(' EAD:', await p.textContent('#conta'));
    await p.click('#cat-foco'); await p.fill('#q', 'xyzinexistente'); await p.waitForTimeout(100); console.log(' botão buscar todas:', await p.locator('#buscar-todas').count());
    console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
  }
  console.log('erros:', erros.filter(e => !e.includes('fonts.g')));
  await b.close();
})();
