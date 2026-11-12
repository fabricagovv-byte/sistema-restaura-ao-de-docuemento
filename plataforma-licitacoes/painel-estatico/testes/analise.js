const { chromium } = require('playwright');
const path = require('path');
const [html, pdf, libs] = process.argv.slice(2);
(async () => { const b = await chromium.launch(); const erros = [];
  for (const [w, h] of [[1280, 1000], [390, 844]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  await ctx.route(/cdnjs\.cloudflare\.com\/ajax\/libs\/(.+)$/, (r) => { const u = r.request().url();
    const m = { 'pdf.js/3.11.174/pdf.min.js': 'pdfjs-dist-3.11.174/build/pdf.min.js', 'pdf.js/3.11.174/pdf.worker.min.js': 'pdfjs-dist-3.11.174/build/pdf.worker.min.js',
      'mammoth/1.6.0/mammoth.browser.min.js': 'mammoth-1.6.0/mammoth.browser.min.js', 'jszip/3.10.1/jszip.min.js': 'jszip-3.10.1/dist/jszip.min.js' };
    const k = Object.keys(m).find((k) => u.endsWith(k)); return k ? r.fulfill({ path: path.join(libs, m[k]), contentType: 'application/javascript' }) : r.abort(); });
  await ctx.addInitScript(() => {
    window.__prompts = [];
    const fake = async (input, opts = {}) => { const txt = typeof input === 'string' ? input : input.map((t) => t.content).join('\n'); window.__prompts.push(txt);
      await new Promise((r) => setTimeout(r, 150));
      const resp = Array.isArray(input) ? 'Sim: **visita técnica facultativa** (edital.pdf, p. 1).' : '# Análise do edital\n## 1. Resumo executivo\n- Objeto: digitalização de **2.000.000 páginas** (edital.pdf, p. 1)\n## 5. Habilitação\n| Exigência | Fonte |\n|---|---|\n| PL mínimo 10% | edital.pdf, p. 1 |\n## 9. Viabilidade e recomendação\nParticipar com ressalvas.';
      opts.onText && opts.onText({ text: resp.slice(0, 20), delta: resp.slice(0, 20) }); opts.onText && opts.onText({ text: resp, delta: resp.slice(20) });
      return { text: resp, truncated: false, modelTierApplied: 'default' }; };
    fake.json = async (input) => { window.__prompts.push(input); return { itens: [{ grupo: 'Qualificação técnica', item: 'Atestado de digitalização', detalhe: 'mínimo 1.000.000 páginas', ref: 'edital.pdf, p. 1', prazo: 'com a proposta' },
      { grupo: 'Econômico-financeira', item: 'Balanço com índices > 1', detalhe: 'PL mínimo 10%', ref: 'edital.pdf, p. 1', prazo: '' }] }; };
    fake.limits = async () => ({ maxPromptBytes: 262144 });
    window.claude = { use: async (n) => n === 'sample' ? fake : null };
  });
  const p = await ctx.newPage(); p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
  await p.goto('file://' + html);
  await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  await p.click('.card [data-aba="analise"]');
  await p.waitForSelector('#an-gerar:not([disabled])');
  console.log(w, 'aba:', await p.textContent('#ficha-titulo'), '| botão:', await p.textContent('#an-gerar'));
  await p.setInputFiles('#an-arquivo', pdf);
  await p.waitForFunction(() => /Anexado/.test(document.getElementById('ficha-corpo').textContent), null, { timeout: 30000 });
  console.log(' anexado:', (await p.textContent('#ficha-corpo section')).replace(/\s+/g, ' ').slice(0, 140));
  await p.click('#an-gerar'); await p.waitForSelector('#an-texto h3');
  await p.waitForFunction(() => /Gerar análise de novo/.test(document.getElementById('an-gerar')?.textContent || ''));
  console.log(' análise:', (await p.textContent('#an-texto')).replace(/\s+/g, ' ').slice(0, 120), '| tabela:', await p.locator('#an-texto table').count());
  const pr = await p.evaluate(() => window.__prompts[0]);
  console.log(' prompt tem texto do edital:', /patrimonio liquido minimo/i.test(pr), '| tem modelo:', /Resumo executivo/.test(pr), '| tamanho', pr.length);
  await p.click('#an-check'); await p.waitForSelector('ul.check input');
  await p.click('ul.check input >> nth=0');
  console.log(' checklist:', (await p.textContent('#ficha-corpo')).match(/\d+ de \d+ providenciados/)[0]);
  await p.click('[data-sug="Tem visita técnica obrigatória?"]'); await p.waitForSelector('.qa .q');
  await p.waitForFunction(() => document.querySelectorAll('.qa').length >= 1 && !document.getElementById('an-resp-viva'));
  console.log(' resposta:', (await p.textContent('.qa .md')).trim());
  await p.screenshot({ path: `an-${w}.png`, fullPage: false });
  // recarregar: análise, checklist e pergunta continuam (armazenamento local neste teste)
  await p.reload(); await p.waitForFunction(() => !document.getElementById('cat-todas').textContent.includes('carregando'), null, { timeout: 30000 });
  await p.waitForSelector('#an-texto', { timeout: 30000 });  // o link (#p…-analise) reabre a aba sozinho
  console.log(' depois de recarregar: análise', await p.locator('#an-texto h3').count() > 0, '| marcados', (await p.textContent('#ficha-corpo')).match(/\d+ de \d+ providenciados/)[0], '| perguntas', await p.locator('.qa').count(), '| edital', /Anexado/.test(await p.textContent('#ficha-corpo')));
  console.log(' modelo:', await p.textContent('#modelo-estado'));
  console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
  await ctx.close(); }
  console.log('erros', erros); await b.close(); })();
