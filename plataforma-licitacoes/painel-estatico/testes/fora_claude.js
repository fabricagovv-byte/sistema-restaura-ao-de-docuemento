// Painel fora do Claude (site próprio): sem window.claude, carrega, baixa .ics e CSV pelo navegador; grava os arquivos do site
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [html, saida] = process.argv.slice(2);
  const b = await chromium.launch(); const erros = [];
  const ctx = await b.newContext({ acceptDownloads: true, viewport: { width: 1366, height: 900 } });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
  await p.goto('file://' + html); await p.waitForSelector('#cal-lista');
  console.log('window.claude ausente:', await p.evaluate(() => !window.claude));
  for (const [id, nome] of [['cal-ics', 'calendario-licitacoes-premiadas.ics'], ['cal-csv', 'calendario-licitacoes-premiadas.csv'], ['crm-exportar', null]]) {
    const vis = await p.isVisible('#' + id);
    if (!nome) { console.log(id, 'visível:', vis); continue; }
    const [d] = await Promise.all([p.waitForEvent('download'), p.click('#' + id)]);
    const destino = `${saida}/${d.suggestedFilename()}`; await d.saveAs(destino);
    const t = fs.readFileSync(destino, 'utf8');
    console.log(id, 'visível:', vis, '| arquivo:', d.suggestedFilename(), fs.statSync(destino).size, 'bytes',
      id === 'cal-ics' ? `| eventos: ${(t.match(/BEGIN:VEVENT/g) || []).length} | URL: ${(t.match(/^URL:/gm) || []).length} | alarmes: ${(t.match(/BEGIN:VALARM/g) || []).length}` : `| linhas: ${t.split('\r\n').length - 1}`);
  }
  // calendário do foco (todas as notas) para assinatura por link
  const foco = await p.evaluate(() => { const ag = new Date();
    const l = itens.filter((x) => x.det && x.enc && new Date(x.enc) >= ag && AREAS.some(([k]) => naArea(x, k))).map((x) => [x, notaOportunidade(x)])
      .sort((a, c) => (a[0].enc < c[0].enc ? -1 : 1));
    return [l.length, gerarIcs(l)]; });
  fs.writeFileSync(`${saida}/calendario-foco.ics`, foco[1]);
  console.log('calendario-foco.ics eventos:', foco[0]);
  // análise com IA: fora do Claude deve avisar, não quebrar
  await p.click('#lista button.abrir[data-aba="analise"]').catch(() => {}); await p.waitForTimeout(400);
  console.log('aba Análise abre sem erro:', await p.evaluate(() => !!document.querySelector('dialog[open]')));
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
