const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage(); p.on('pageerror', e => erros.push(e.message)); p.on('console', m => m.type() === 'error' && erros.push(m.text()));
  const url = 'file://' + process.argv[2];
  await p.goto(url);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  console.log('crm estado:', (await p.textContent('#crm-estado')).slice(0, 120));
  // edital com itens UST
  await p.click('#cat-remun_ust');
  await p.click('.card button[data-aba="preco"]'); await p.waitForTimeout(300);
  console.log('aba preco:', await p.textContent('#ficha-titulo'), '| linhas', await p.locator('#pr-linhas tr').count(), '| pesquisa', await p.locator('#pr-linhas .ref button').count(), '| hash', await p.evaluate(() => location.hash));
  await p.fill('#pr-bdi', '25'); await p.fill('#pr-imp', '14,25');
  const inp = p.locator('#pr-linhas input[data-campo="custo"]').first(); await inp.fill('100');
  console.log('totais:', (await p.textContent('#pr-totais')).replace(/\s+/g, ' ').slice(0, 200));
  const amostra = p.locator('#pr-linhas .ref button').first(); if (await amostra.count()) { await amostra.click(); console.log('amostras visíveis:', await p.locator('.amostras:not([hidden]) li').count()); }
  await p.click('#pr-salvar'); await p.waitForTimeout(200); console.log('salvar:', await p.textContent('#pr-estado'));
  await p.screenshot({ path: 'preco-cel.png' });
  await p.click('#abas [data-aba="crm"]'); await p.waitForTimeout(200);
  await p.selectOption('#crm-status', 'participar'); await p.fill('#crm-passo', 'Pedir esclarecimento sobre a UST'); await p.fill('#crm-data', '2026-11-05');
  await p.click('#crm-salvar'); await p.waitForTimeout(200);
  await p.fill('#crm-nota', 'Liguei para o pregoeiro.'); await p.click('#crm-add'); await p.waitForTimeout(300);
  console.log('notas:', await p.locator('.notas li').count(), '|', await p.textContent('#crm-estado-ficha'));
  await p.screenshot({ path: 'crmficha-cel.png' });
  await p.keyboard.press('Escape');
  // recarregar e conferir persistência
  await p.goto(url); await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  console.log('depois de recarregar:', (await p.textContent('#crm-estado')).slice(0, 140), '| linhas CRM', await p.locator('#crm-lista tr').count(), '| chip', await p.textContent('#cat-meucrm'));
  await p.click('#crm-lista tr'); await p.waitForTimeout(300);
  console.log('abre do CRM:', await p.textContent('#ficha-titulo'), await p.inputValue('#crm-passo'));
  await p.click('#abas [data-aba="preco"]'); await p.waitForTimeout(200);
  console.log('preço persistiu:', await p.inputValue('#pr-bdi'), await p.locator('#pr-linhas input[data-campo="custo"]').first().inputValue());
  // edital sem itens: valor global
  await p.keyboard.press('Escape'); await p.click('#cat-todas'); await p.fill('#q', 'ambulancia'); await p.waitForTimeout(100);
  await p.click('.card button[data-aba="preco"]'); await p.waitForTimeout(200);
  console.log('sem itens:', await p.locator('#pr-linhas tr').count(), (await p.textContent('#pr-linhas td:nth-child(2)')).slice(0, 60));
  console.log('largura', await p.evaluate(() => document.documentElement.scrollWidth), 'dialog', await p.evaluate(() => document.getElementById('ficha').scrollWidth));
  console.log('erros', erros); await b.close(); })();
