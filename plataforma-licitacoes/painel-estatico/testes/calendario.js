const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1366, 1000], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  console.log(w, 'meses:', (await p.textContent('#cal-meses')).replace(/\s+/g, ' ').slice(0, 160));
  console.log(' este mês:', (await p.textContent('#cal-lista .conta')).trim());
  console.log(' 1º:', (await p.locator('.cal-item').first().textContent()).replace(/\s+/g, ' ').slice(0, 230));
  await p.click('#cal-meses [data-mes] >> nth=1'); console.log(' mês que vem:', (await p.textContent('#cal-lista .conta')).trim());
  await p.click('#cal-meses [data-mes] >> nth=0');
  const dia = p.locator('.cal-dia.tem').first(); const n = await dia.getAttribute('data-dia'); await dia.click();
  console.log(' dia', n, '->', (await p.textContent('#cal-lista .conta')).trim().slice(0, 80));
  await p.fill('#cal-min', '75'); console.log(' nota ≥75:', (await p.textContent('#cal-lista .conta')).trim().slice(0, 80));
  await p.fill('#cal-min', '55');
  await p.click('.cal-item >> nth=0'); console.log(' clique -> prévia:', (await p.textContent('#previa h3')).trim(), '| marcas na prévia:', await p.locator('#previa .marca-item').count());
  await p.setInputFiles('#marc-arquivo', process.argv[3]); console.log(' planilha:', await p.textContent('#marc-estado'));
  await p.click('#marc-salvar'); await p.waitForTimeout(200); console.log(' salvo:', await p.textContent('#marc-estado'), '| chip:', (await p.textContent('#cat-marc')).trim());
  await p.click('#cat-marc'); await p.waitForTimeout(150); console.log(' filtro meus marcadores:', (await p.textContent('#conta')).trim().slice(0, 60), '| etiqueta:', await p.locator('.card .marca-item.minha').first().textContent().catch(() => '-'));
  await p.click('#cat-gv'); await p.waitForTimeout(150); await p.click('.card [data-abrir] >> nth=0'); await p.waitForSelector('#ficha-corpo table');
  console.log(' ficha: marcas nos itens:', await p.locator('#ficha-corpo .marca-item').count(), '|', (await p.locator('#ficha-corpo .marca-item').allTextContents()).slice(0, 6).join(', '));
  await p.click('#fechar');
  await p.click('#cat-premiadas'); await p.waitForTimeout(150); console.log(' chip premiadas:', (await p.textContent('#conta')).trim().slice(0, 60));
  if (w > 1000) await p.locator('#cal-sec').screenshot({ path: 'calendario.png' });
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); await p.close(); }
  console.log('erros', erros); await b.close(); })();
