const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1280, 1000], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  const res = () => p.textContent('#calc-corpo .calc-res').then((t) => t.replace(/\s+/g, ' ').trim());
  const preenche = async (k, v) => { await p.fill(`#calc-corpo [data-k="${k}"]`, v); };
  const modo = async (m) => { await p.click(`#calc-corpo [data-modo="${m}"]`); };
  // preço: custo 100.000, DI 10%, impostos 16,33%, lucro 8% -> 100000*1,1/(1-0,2433) = 145.367,72
  await modo('preco'); await preenche('custo', '100 mil'); console.log(w, 'preço:', await res());
  // UST: hora 95, 1 h, fator 1,2, 5.000 UST -> custo 114; preço 114*1,1/0,7567 = 165,72; total 828.598...
  await modo('ust'); await preenche('hora', '95'); await preenche('fator', '1,2'); await preenche('qtd', '5.000'); await preenche('ref_ust', '200'); console.log(' ust:', await res());
  // página: 2 mi páginas, 3000/dia, 120 dias -> 6 operadores; 5,45 meses; mão 6*4500*5,4545=147.272,73; custo/pág 0,0736
  await modo('pagina'); await preenche('paginas', '2 mi'); console.log(' página:', await res());
  await modo('mensal'); await preenche('custoMes', '50 mil'); await preenche('meses', '24'); await preenche('reaj', '5'); console.log(' mensal:', await res());
  await modo('lance'); await preenche('estimado', '1 mi'); await preenche('desc', '30'); await preenche('custoTotal', '600 mil'); console.log(' lance:', await res());
  await modo('simples'); await preenche('expr', '2.000.000 * 0,42 / 12 + 15%'); console.log(' conta:', await res());
  await preenche('expr', '(10 + 5) x 2 - 3'); console.log(' conta2:', await res());
  await preenche('expr', '10 / (2 -'); console.log(' conta inválida:', await res());
  // aba na ficha, preenchida pelo edital
  await p.click('#cat-remun_ust'); await p.click('.card [data-abrir]');
  await p.click('#abas [data-aba="calc"]'); await p.waitForSelector('#calc-ficha .calc');
  console.log(' ficha:', await p.textContent('#ficha-titulo'), '| modo:', await p.getAttribute('#calc-ficha [aria-pressed="true"]', 'data-modo'),
    '| qtd:', await p.inputValue('#calc-ficha [data-k="qtd"]').catch(() => '-'), '| ref:', await p.inputValue('#calc-ficha [data-k="ref_ust"]').catch(() => '-'));
  await p.screenshot({ path: `calc-${w}.png` });
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); await p.close(); }
  console.log('erros', erros); await b.close(); })();
