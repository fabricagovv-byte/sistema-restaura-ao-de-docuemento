// Aba Brasil (todas abertas): carrega brasil.json, filtra por assunto/UF/valor/palavra, mostra mais, sem rolagem lateral
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 } });
    const p = await ctx.newPage(); p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.goto(process.argv[2]);
    await p.keyboard.press('Escape');
    await p.evaluate(() => document.getElementById('br-sec').scrollIntoView());
    await p.waitForSelector('#br-lista li', { timeout: 60000 });
    console.log(w, 'inicial:', await p.textContent('#br-conta'));
    if (w === 1366) console.log(' lede:', (await p.textContent('#br-lede')).slice(0, 160));
    await p.click('#br-assuntos [data-as="Tecnologia (TI)"]'); await p.waitForTimeout(300);
    console.log(' TI:', await p.textContent('#br-conta'));
    await p.selectOption('#br-uf', 'MG'); await p.waitForTimeout(300);
    console.log(' TI+MG:', await p.textContent('#br-conta'));
    await p.selectOption('#br-uf', ''); await p.click('#br-assuntos [data-as=""]');
    await p.fill('#br-q', 'digitalização'); await p.waitForTimeout(400);
    console.log(' "digitalização":', await p.textContent('#br-conta'), '|', (await p.textContent('#br-lista li h4')).replace(/\s+/g, ' ').slice(0, 80));
    await p.fill('#br-q', ''); await p.selectOption('#br-vmin', '10000000'); await p.selectOption('#br-ord', 'valor'); await p.waitForTimeout(400);
    console.log(' ≥10 mi por valor:', await p.textContent('#br-conta'), '|', (await p.textContent('#br-lista li .br-pe')).replace(/\s+/g, ' ').slice(0, 90));
    await p.selectOption('#br-vmin', '0'); await p.selectOption('#br-ord', 'prazo'); await p.waitForTimeout(300);
    const antes = await p.$$eval('#br-lista li', (x) => x.length); await p.click('#br-mais'); const depois = await p.$$eval('#br-lista li', (x) => x.length);
    console.log(' mostrar mais:', antes, '->', depois, '| largura', await p.evaluate(() => document.documentElement.scrollWidth));
    await p.fill('#br-perto', 'Alvorada de Minas - MG'); await p.dispatchEvent('#br-perto', 'change'); await p.selectOption('#br-raio', '150'); await p.selectOption('#br-ord', 'perto'); await p.waitForTimeout(500);
    console.log(' 150 km de Alvorada:', await p.textContent('#br-conta'), '|', (await p.textContent('#br-lista li h4')).replace(/\s+/g, ' ').slice(0, 90));
    await p.click('#br-assuntos [data-as="Obras e engenharia"]'); await p.waitForTimeout(300); console.log('  obras:', await p.textContent('#br-conta'));
    await p.click('#br-assuntos [data-as=""]'); await p.selectOption('#br-raio', '0'); await p.fill('#br-perto', ''); await p.dispatchEvent('#br-perto', 'change'); await p.selectOption('#br-ord', 'prazo');
    await p.click('#br-palavras [data-pal="UST"]'); await p.click('#br-palavras [data-pal="digitalização"]'); await p.waitForTimeout(400);
    console.log(' palavras UST+digitalização:', await p.textContent('#br-conta'), '|', await p.textContent('#br-pal-resumo'));
    await p.selectOption('#br-regiao', 'SE'); await p.waitForTimeout(300); console.log('  + Sudeste:', await p.textContent('#br-conta'));
    await p.fill('#br-pal-input', 'fábrica de software'); await p.press('#br-pal-input', 'Enter'); await p.waitForTimeout(300); console.log('  + criada:', await p.textContent('#br-conta'));
    await p.click('#br-pal-limpar'); await p.selectOption('#br-regiao', ''); await p.waitForTimeout(300);
    if (w === 1366) { await p.hover('#br-lista .br-ficha:nth-child(3)'); await p.waitForTimeout(200); console.log(' prévia (hover 3ª):', (await p.textContent('#br-previa')).replace(/\s+/g, ' ').slice(0, 140)); }
    else { await p.click('#br-lista .br-ficha:nth-child(2) h4'); await p.waitForTimeout(200); console.log(' prévia (toque):', (await p.textContent('#br-lista .br-ficha:nth-child(2) .br-prev')).replace(/\s+/g, ' ').slice(0, 120)); }
    console.log(' temas:', (await p.textContent('#br-temas')).replace(/\s+/g, ' '));
    for (const tm of ['documental', 'ust', 'mensal', 'consultoria', 'servicos']) { await p.click(`#br-temas [data-tema="${tm}"]`); await p.waitForTimeout(300);
      console.log('  tema', tm, await p.textContent('#br-conta'), '|', (await p.textContent('#br-lista li .br-cab')).replace(/\s+/g, ' ').slice(0, 70), '|', ((await p.$('#br-lista li .br-vol')) ? await p.textContent('#br-lista li .br-vol') : '-')); }
    if (w === 1366) { await p.hover('#br-lista .br-ficha:nth-child(1)'); console.log('  prévia tema:', (await p.textContent('#br-previa')).replace(/\s+/g, ' ').slice(0, 260)); await (await p.$('#br-sec')).screenshot({ path: 'telas/temas-1366.png' }); }
    await p.click('#br-temas [data-tema=""]'); await p.waitForTimeout(300);
    await p.click('#br-pregoes'); await p.waitForTimeout(300); console.log(' só pregões:', await p.textContent('#br-conta'));
    await p.selectOption('#br-sit', 'avir'); await p.waitForTimeout(300);
    console.log(' a vir:', await p.textContent('#br-conta'), '|', (await p.textContent('#br-lista li .br-pe')).replace(/\s+/g, ' ').slice(0, 110));
    await p.selectOption('#br-sit', 'previstas'); await p.waitForTimeout(300);
    console.log(' previstas:', (await p.textContent('#br-conta')).slice(0, 60), '|', (await p.textContent('#br-lista li')).replace(/\s+/g, ' ').slice(0, 120));
    await p.selectOption('#br-sit', ''); await p.click('#br-pregoes');
    console.log(' opções situação:', await p.$$eval('#br-sit option', (o) => o.map((x) => x.textContent).join(' | ')));
    if (w === 390) { await (await p.$('#br-sec')).screenshot({ path: process.argv[3] || 'brasil-390.png' }); }
    await ctx.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
