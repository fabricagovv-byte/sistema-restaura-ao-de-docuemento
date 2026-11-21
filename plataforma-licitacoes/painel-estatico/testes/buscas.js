// Aba Minhas buscas: cartões com contagem, "Ver lista" aplica a busca na aba Pesquisa PNCP, "Copiar" gera texto, "Ver todas" limpa
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
    const p = await ctx.newPage(); p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.goto('file://' + process.argv[2]); await p.waitForSelector('#buscas-lista li');
    const cards = await p.$$eval('#buscas-lista li', (xs) => xs.map((x) => `${x.querySelector('b').textContent}: ${x.querySelector('.num').textContent}`));
    if (w === 1366) console.log(cards.join('\n'));
    await p.click('#buscas-lista [data-busca="ead"]:not([data-acao])'); await p.waitForTimeout(300);
    console.log(w, 'EAD na lista:', (await p.textContent('#pesq-conta')), '|', (await p.textContent('#pesq-busca')).trim().slice(0, 60));
    await p.click('#buscas-lista [data-busca="mensal"]:not([data-acao])'); await p.waitForTimeout(300);
    console.log(' mensal 1º:', (await p.textContent('#pesq-lista li .linha')).replace(/\s+/g, ' ').slice(0, 120));
    await p.click('#buscas-lista [data-busca="dev"][data-acao="copiar"]'); await p.waitForTimeout(200);
    console.log(' copiar dev:', (await p.inputValue('#pesq-texto')).split('\n')[0]);
    await p.click('#pesq-busca-limpar'); await p.waitForTimeout(200); console.log(' ver todas:', await p.textContent('#pesq-conta'));
    console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
    await ctx.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
