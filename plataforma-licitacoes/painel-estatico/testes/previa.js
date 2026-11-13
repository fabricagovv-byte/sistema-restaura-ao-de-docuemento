const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1366, 900], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  console.log(w, 'prévia escondida no início:', await p.isHidden('#previa'));
  await p.click('.card >> nth=1', { position: { x: 30, y: 8 } });
  console.log(' clique no cartão -> prévia:', (await p.textContent('#previa h3')).trim(), '|', (await p.textContent('#previa .contagem')).trim(), '| ficha aberta?', await p.evaluate(() => document.getElementById('ficha').open));
  console.log(' marcado:', await p.locator('.card[aria-current="true"]').count());
  if (w > 1000) { await p.focus('.card[aria-current="true"]'); await p.keyboard.press('ArrowDown'); console.log(' seta ↓ ->', (await p.textContent('#previa h3')).trim()); await p.screenshot({ path: 'previa-desk.png' }); }
  await p.click('#previa [data-abrir][data-aba="calc"]'); console.log(' botão Calculadora abre ficha:', await p.evaluate(() => document.getElementById('ficha').open), await p.textContent('#ficha-titulo'));
  await p.click('#fechar');
  if (w < 1000) { await p.screenshot({ path: 'previa-cel.png' }); await p.click('#previa [data-fechar-previa]'); console.log(' fechar no celular:', await p.isHidden('#previa')); }
  await p.click('#vistas [data-vista="agenda"]'); await p.waitForSelector('.agenda-dia');
  console.log(' agenda:', (await p.textContent('.agenda-dias')).replace(/\s+/g, ' ').slice(0, 150));
  console.log('  1º dia:', (await p.textContent('.agenda-dia h3')).replace(/\s+/g, ' '));
  await p.click('.agenda-item >> nth=0'); console.log('  clique na agenda -> prévia:', (await p.textContent('#previa h3')).trim());
  await p.click('.agenda-dias button >> nth=2'); console.log('  dia escolhido:', await p.locator('.agenda-dia').count(), 'bloco,', await p.locator('.agenda-item').count(), 'itens');
  if (w > 1000) await p.screenshot({ path: 'agenda-desk.png' });
  await p.click('#vistas [data-vista="lista"]'); console.log(' volta à lista:', await p.locator('.card').count(), 'cartões');
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); await p.close(); }
  console.log('erros', erros); await b.close(); })();
