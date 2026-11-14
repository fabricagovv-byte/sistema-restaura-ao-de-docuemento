// Seu foco (5 áreas) + esconder/mostrar painéis (lembra ao recarregar) + Fechar da prévia no computador
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 } }); const p = await ctx.newPage();
    p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + process.argv[2]); await p.waitForSelector('#foco-lista li');
    const areas = await p.$$eval('#foco-areas button', (bs) => bs.map((x) => x.innerText.replace(/\s+/g, ' ')));
    console.log(w, 'áreas:', areas.join(' | '));
    if (w === 1366 && process.argv[3]) {
      const dados = await p.evaluate(() => Object.fromEntries(AREAS.map(([k]) => [k, listaArea(k).map((x) => ({ id: x.id, nota: notaOportunidade(x).nota,
        o: x.o, uf: x.uf, m: x.m, v: x.v, enc: x.enc, obj: x.obj, vol: x.vol, cp: CATS[principal(x)], pncp: x.pncp || x.orig }))])));
      fs.writeFileSync(process.argv[3], JSON.stringify(dados, null, 1));
    }
    await p.click('#foco-areas [data-area="documental"]'); await p.waitForTimeout(200);
    console.log(' documental:', await p.textContent('#foco-conta'));
    await p.selectOption('#foco-ord', 'nota'); await p.waitForTimeout(200);
    await p.click('#foco-lista li[data-foco]'); await p.waitForTimeout(300);
    const fechar = await p.$('#previa [data-fechar-previa]');
    console.log(' prévia aberta:', await p.$eval('#previa', (e) => !e.hidden), '| botão Fechar visível:', fechar ? await fechar.isVisible() : false);
    if (fechar) { await fechar.click(); await p.waitForTimeout(200); console.log(' prévia fechada:', await p.$eval('#previa', (e) => e.hidden)); }
    await p.click('#foco-ver'); await p.waitForTimeout(300); console.log(' lista principal:', (await p.textContent('#conta')).replace(/\s+/g, ' ').slice(0, 70));
    // esconder
    const n = await p.$$eval('section.panel > .esconder', (xs) => xs.length);
    await p.click('#funil-sec > .esconder'); await p.waitForTimeout(100);
    const fechado = await p.$eval('#funil-sec', (e) => [e.classList.contains('fechado'), e.querySelector('#funil-etapas').offsetParent === null, e.querySelector('h2').offsetParent !== null]);
    console.log(' botões:', n, '| funil fechado/conteúdo oculto/título visível:', fechado.join('/'));
    await p.reload(); await p.waitForSelector('#foco-lista li');
    console.log(' depois de recarregar continua fechado:', await p.$eval('#funil-sec', (e) => e.classList.contains('fechado')));
    await p.click('#paineis-fechar'); await p.waitForTimeout(100);
    console.log(' todos fechados:', await p.$$eval('section.panel', (xs) => xs.every((x) => x.classList.contains('fechado'))),
      '| destaques mostra título:', await p.$eval('#destaques-sec .panel-nome', (e) => e.offsetParent !== null && e.textContent.slice(0, 30)));
    if (w === 390) await p.screenshot({ path: 'fechados-390.png', fullPage: false });
    await p.click('#paineis-abrir'); await p.waitForTimeout(100);
    console.log(' todos abertos:', await p.$$eval('section.panel', (xs) => xs.every((x) => !x.classList.contains('fechado'))));
    console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
    await ctx.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
