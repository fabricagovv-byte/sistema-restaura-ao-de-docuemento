// Categorias organizadas: grupos, categoria principal em destaque, filtro por principal e por grupo
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + process.argv[2]); await p.waitForSelector('#cats .gcat');
    const grupos = await p.$$eval('#cats .gchip', (bs) => bs.map((x) => x.innerText.replace(/\s+/g, ' ')));
    console.log(w, 'grupos:', grupos.join(' | '));
    // todos os filtros por tipo (serviço + material) para conferir as contagens
    await p.selectOption('#tipo', 'todos').catch(() => {});
    const conta = async () => (await p.textContent('#conta')).replace(/\s+/g, ' ');
    await p.click('#cat-g-software'); await p.waitForTimeout(200);
    console.log(' software:', await conta());
    const pills = await p.$$eval('#lista article .pill.p-acc', (xs) => xs.slice(0, 5).map((x) => x.textContent));
    console.log(' principais na lista:', pills.join(', '));
    const sub = await p.$('#cat-sistemas_gestao');
    if (sub) { await sub.click(); await p.waitForTimeout(200); console.log(' sistemas_gestao (principal):', await conta());
      await p.check('#cat-cit'); await p.waitForTimeout(200); console.log(' + só citados:', await conta()); await p.uncheck('#cat-cit'); }
    await p.click('#cat-g-equipamentos'); await p.waitForTimeout(200); console.log(' equipamentos:', await conta());
    await p.click('#cat-remun_ust'); await p.waitForTimeout(200); console.log(' UST:', await conta());
    // ficha mostra a principal e o grupo
    await p.click('#cat-g-software'); await p.waitForTimeout(200);
    const abrir = await p.$('#lista article button.abrir[data-abrir]');
    if (abrir) { await abrir.click(); await p.waitForTimeout(300);
      const dl = await p.$$eval('dialog[open] dt', (xs) => xs.map((x) => x.textContent + ': ' + x.nextElementSibling.textContent.replace(/\s+/g, ' ').slice(0, 80)).filter((t) => /principal|cita/i.test(t)));
      console.log(' ficha:', dl.join(' || ')); await p.keyboard.press('Escape'); }
    const larg = await p.evaluate(() => document.documentElement.scrollWidth); console.log(' largura', larg);
    if (w === 390) await p.screenshot({ path: process.argv[3] || 'grupos-390.png', clip: { x: 0, y: await p.$eval('#cats', (e) => e.getBoundingClientRect().top + scrollY), width: 390, height: 900 } });
    await p.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
