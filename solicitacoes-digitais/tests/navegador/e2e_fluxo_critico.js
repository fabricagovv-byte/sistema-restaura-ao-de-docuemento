// Teste ponta a ponta do fluxo crítico no navegador (OS-001, D6-B / RNF-07).
// Uso: node tests/navegador/e2e_fluxo_critico.js <url-base> <pasta-temporaria>
// Roda contra um servidor local com dados fictícios (o pytest tests/test_e2e_navegador.py sobe tudo).
// Sai com código 1 na primeira verificação que falhar.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [URL, PASTA] = process.argv.slice(2);
const SENHA = 'Senha-Forte-2026';
let passo = 0;
const ok = (cond, msg) => { passo += 1; if (!cond) throw new Error(`passo ${passo} falhou: ${msg}`); console.log(`ok ${passo} - ${msg}`); };

(async () => {
  const b = await chromium.launch();
  const erros = [];
  const pdf = path.join(PASTA, 'comprovante.pdf');
  fs.writeFileSync(pdf, '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n');
  async function entrar(email) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => erros.push(e.message));
    p.on('dialog', (d) => d.accept());
    await p.goto(URL);
    await p.fill('#c-email', email); await p.fill('#c-senha', SENHA); await p.click('button[type=submit]');
    await p.waitForSelector('#conta:not([hidden])');
    return { ctx, p };
  }
  const titulo = (p) => p.textContent('main h1');
  const esperarDetalhe = (p) => p.waitForFunction(() => /^Solicitação \d+/.test(document.querySelector('main h1')?.textContent || '')
    && !document.querySelector('[aria-busy="true"]'));
  const situacao = async (p) => (await p.textContent('dl.dados dd:nth-of-type(2)')).trim();
  async function tramitar(p, para, comentario) {
    if (comentario !== undefined) await p.fill('#c-comentario', comentario);
    await p.click(`button[data-para="${para}"]`);
  }

  try {
    // 1. solicitante abre a solicitação e anexa um PDF
    let { ctx, p } = await entrar('cidada@exemplo.gov.br');
    await p.click('#menu a[href="#/nova"]'); await p.waitForSelector('#c-titulo');
    await p.fill('#c-titulo', 'Segunda via da certidão de casamento'); await p.fill('#c-descricao', 'O documento original foi danificado pela chuva.');
    await p.selectOption('#c-categoria_id', { label: 'Certidão (prazo de 10 dias)' });
    await p.click('form button[type=submit]'); await esperarDetalhe(p);
    const protocolo = (await titulo(p)).replace('Solicitação ', '');
    const id = (await p.evaluate(() => location.hash)).split('/').pop();
    ok(/^\d{10}$/.test(protocolo) && (await situacao(p)) === 'Recebida', `solicitante abriu a solicitação ${protocolo} (recebida)`);
    await p.setInputFiles('#c-arquivo', pdf); await p.click('text=Enviar anexo');
    await p.waitForSelector('ul.anexos li.anexo');
    ok((await p.textContent('ul.anexos')).includes('comprovante.pdf'), 'anexo enviado aparece na lista');
    await p.waitForFunction(() => /Anexo/.test(document.querySelector('[data-bloco=historico]')?.textContent || ''));
    ok(true, 'histórico registra o anexo');
    await ctx.close();

    // 2. gestor faz a triagem e atribui ao operador
    ({ ctx, p } = await entrar('gestor@exemplo.gov.br'));
    await p.goto(`${URL}#/solicitacoes/${id}`); await esperarDetalhe(p);
    await tramitar(p, 'em_triagem'); await esperarDetalhe(p);
    ok((await situacao(p)) === 'Em triagem', 'gestor moveu para Em triagem');
    await p.waitForSelector('#c-responsavel_id option[value]:not([value=""])', { state: 'attached' });
    await p.selectOption('#c-responsavel_id', { label: 'Otto Operador (Operador)' });
    await p.click('text=Atribuir'); await esperarDetalhe(p);
    ok((await p.textContent('dl.dados')).includes('Otto Operador'), 'gestor atribuiu ao operador');
    await ctx.close();

    // 3. operador atende e pede complemento; sem comentário a tela mostra o erro do servidor
    ({ ctx, p } = await entrar('operador@exemplo.gov.br'));
    await p.waitForSelector('#resultado tbody tr');
    ok((await p.textContent('#resultado')).includes(protocolo), 'solicitação aparece na fila do operador');
    await p.click(`text=${protocolo}`); await esperarDetalhe(p);
    await tramitar(p, 'em_atendimento'); await esperarDetalhe(p);
    ok((await situacao(p)) === 'Em atendimento', 'operador iniciou o atendimento');
    await tramitar(p, 'aguardando_solicitante', '');
    await p.waitForSelector('#aviso.erro');
    ok(/comentário|motivo/i.test(await p.textContent('#aviso')), 'pedir complemento sem comentário é recusado com mensagem');
    await tramitar(p, 'aguardando_solicitante', 'Envie a cópia do RG, por favor.'); await esperarDetalhe(p);
    ok((await situacao(p)) === 'Aguardando o solicitante', 'operador pediu complemento');
    await ctx.close();

    // 4. solicitante responde
    ({ ctx, p } = await entrar('cidada@exemplo.gov.br'));
    await p.goto(`${URL}#/solicitacoes/${id}`); await esperarDetalhe(p);
    await tramitar(p, 'em_atendimento', 'Cópia do RG enviada em anexo.'); await esperarDetalhe(p);
    ok((await situacao(p)) === 'Em atendimento', 'solicitante respondeu e a solicitação voltou ao atendimento');
    ok(!(await p.isVisible('button[data-para="concluida"]')), 'solicitante não vê a ação de concluir');
    await ctx.close();

    // 5. operador conclui
    ({ ctx, p } = await entrar('operador@exemplo.gov.br'));
    await p.goto(`${URL}#/solicitacoes/${id}`); await esperarDetalhe(p);
    await tramitar(p, 'concluida', 'Segunda via emitida e disponível para retirada.'); await esperarDetalhe(p);
    ok((await situacao(p)) === 'Concluída', 'operador concluiu');
    ok(!(await p.isVisible('#c-arquivo')), 'solicitação concluída não aceita novo anexo');
    await ctx.close();

    // 6. gestor arquiva, baixa o anexo e confere histórico e auditoria
    ({ ctx, p } = await entrar('gestor@exemplo.gov.br'));
    await p.goto(`${URL}#/solicitacoes/${id}`); await esperarDetalhe(p);
    const [download] = await Promise.all([p.waitForEvent('download'), p.click('ul.anexos button:has-text("Baixar")')]);
    const baixado = await download.path();
    ok(fs.readFileSync(baixado, 'latin1').startsWith('%PDF') && download.suggestedFilename() === 'comprovante.pdf', 'gestor baixou o anexo com o conteúdo original');
    await p.click('text=Arquivar'); await esperarDetalhe(p);
    ok((await p.textContent('dl.dados')).includes('arquivada'), 'gestor arquivou');
    const hist = await p.$$eval('[data-bloco=historico] li b', (bs) => bs.map((x) => x.textContent));
    ok(JSON.stringify(hist) === JSON.stringify(['Abertura', 'Anexo', 'Mudança de situação', 'Atribuição', 'Mudança de situação', 'Mudança de situação',
      'Mudança de situação', 'Mudança de situação', 'Arquivamento']), `histórico completo na ordem: ${hist.join(' > ')}`);
    await p.waitForSelector('section:has(h2:text("Auditoria desta solicitação")) tbody tr');
    const acoes = await p.$$eval('section:has(h2:text("Auditoria desta solicitação")) tbody tr td:nth-child(2)', (t) => t.map((x) => x.textContent));
    ok(['Criação', 'Anexo enviado', 'Tramitação', 'Atribuição', 'Arquivamento'].every((a) => acoes.includes(a)), `auditoria tem os eventos: ${[...new Set(acoes)].join(', ')}`);
    await p.click('#menu a[href="#/auditoria"]');
    await p.waitForFunction(() => document.querySelector('main h1')?.textContent === 'Auditoria' && document.querySelector('main section tbody tr'));
    ok((await titulo(p)) === 'Auditoria', 'tela de auditoria do gestor abre com eventos');
    await ctx.close();

    ok(erros.length === 0, `sem erro de JavaScript no navegador ${JSON.stringify(erros)}`);
    console.log(`fluxo crítico aprovado: ${passo} verificações`);
  } catch (e) {
    console.error(String(e && e.stack || e));
    process.exitCode = 1;
  } finally {
    await b.close();
  }
})();
