const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1366, 900], [390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', (e) => erros.push(e.message));
  await p.goto('file://' + process.argv[2]);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  const conta = async () => (await p.textContent('#conta')).trim().split('·')[0].trim();
  await p.click('#cat-tecnologia'); console.log(w, 'tecnologia:', await conta());
  await p.click('#avancada summary');
  await p.selectOption('#adv-mod', 'pregao'); console.log(' só pregão:', await conta(), '| todos pregão?', await p.evaluate(() => [...document.querySelectorAll('.card .meta')].every((m) => /Preg/i.test(m.textContent))));
  await p.fill('#adv-vmax', '5 mi'); console.log(' até 5 mi:', await conta());
  await p.fill('#adv-ader', '60'); console.log(' aderência ≥ 60:', await conta(), '|', await p.textContent('#adv-conta'));
  await p.fill('#adv-orgao', 'prefeitura'); console.log(' órgão "prefeitura":', await conta());
  await p.fill('#adv-orgao', ''); await p.fill('#adv-excluir', 'impressora, veiculo'); console.log(' excluindo impressora/veículo:', await conta());
  await p.check('#adv-itens'); console.log(' só com itens:', await conta());
  const hoje = new Date(); const d = new Date(hoje.getTime() + 7 * 864e5).toISOString().slice(0, 10);
  await p.fill('#adv-ate', d); console.log(' encerra até', d + ':', await conta());
  await p.click('#adv-limpar'); console.log(' limpar:', await conta(), '|', JSON.stringify(await p.textContent('#adv-conta')));
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth)); if (w > 1000) await p.screenshot({ path: 'avancada.png' }); await p.close(); }
  console.log('erros', erros); await b.close(); })();
