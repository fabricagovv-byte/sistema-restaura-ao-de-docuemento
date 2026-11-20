// Aba Pesquisa nacional (PNCP): contagens, faixas, filtros, cópia WhatsApp, CSV, celular sem rolagem lateral
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, acceptDownloads: true, permissions: ['clipboard-read', 'clipboard-write'] });
    const p = await ctx.newPage(); p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + process.argv[2]); await p.waitForSelector('#pesq-lista li');
    if (w === 1366) console.log((await p.textContent('#pesq-lede')).slice(0, 260));
    const faixas = await p.$$eval('#pesq-faixas button', (bs) => bs.map((x) => x.innerText.replace(/\s+/g, ' ')));
    console.log(w, 'faixas:', faixas.join(' | '));
    console.log(' todas:', await p.textContent('#pesq-conta'));
    await p.click('#pesq-faixas [data-pf="10mi"]'); console.log(' acima de 10 mi:', await p.textContent('#pesq-conta'));
    await p.click('#pesq-faixas [data-pf="ust"]'); console.log(' com UST:', await p.textContent('#pesq-conta'));
    await p.click('#pesq-faixas [data-pf="todas"]');
    await p.fill('#pesq-q', 'sustentação'); await p.waitForTimeout(150); console.log(' busca "sustentação":', await p.textContent('#pesq-conta'));
    await p.fill('#pesq-q', ''); await p.selectOption('#pesq-ord', 'valor'); await p.waitForTimeout(150);
    console.log(' 1º por valor:', (await p.textContent('#pesq-lista li .topo b')));
    await p.click('#pesq-lista [data-pw="0"]'); await p.waitForTimeout(200);
    const t = await p.inputValue('#pesq-texto');
    console.log(' cópia WhatsApp:', t.split('\n').slice(0, 3).join(' / '), '| linhas', t.split('\n').length, '|', await p.textContent('#pesq-conta'));
    const [d] = await Promise.all([p.waitForEvent('download'), p.click('#pesq-csv')]);
    console.log(' CSV:', d.suggestedFilename());
    await p.click('#pesq-mais').catch(() => {}); console.log(' itens na lista:', await p.locator('#pesq-lista > li').count());
    console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
    if (w === 390) await (await p.$('#pesq-sec')).screenshot({ path: 'pesquisa-390.png' });
    await ctx.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
