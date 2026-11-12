// Verificação no navegador do frontend do dia 5 (login, perfis, lista, cadastro, erros e carregamento).
// Uso: subir o servidor com dados fictícios em http://localhost:8765 e rodar  node tests/navegador/verificacao-dia05.js <pasta-das-telas>
const { chromium } = require('playwright');
const URL = 'http://localhost:8765/';
(async () => {
  const b = await chromium.launch(); const erros = []; const log = (...a) => console.log(...a);
  for (const [w, h] of [[1280, 900], [390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } }); const p = await ctx.newPage();
    p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && !/401|403|422/.test(m.text()) && erros.push(m.text()));
    const titulo = () => p.textContent('main h1');
    await p.goto(URL); await p.waitForSelector('main h1');
    log(`[${w}] tela inicial sem sessão:`, await titulo());
    // validação no navegador e erro do servidor
    await p.click('button[type=submit]'); log(' login vazio:', await p.textContent('#e-email'), '|', await p.textContent('#e-senha'));
    await p.fill('#c-email', 'cidada@exemplo.gov.br'); await p.fill('#c-senha', 'senha-errada'); await p.click('button[type=submit]');
    await p.waitForSelector('#aviso.erro'); log(' senha errada:', await p.textContent('#aviso'));
    // solicitante
    await p.fill('#c-senha', 'Senha-Forte-2026'); await p.click('button[type=submit]');
    await p.waitForFunction(() => document.querySelector('main h1')?.textContent === 'Minhas solicitações');
    await p.waitForSelector('#resultado:not([aria-busy])');
    log(' solicitante entrou:', await titulo(), '| perfil:', await p.textContent('#conta-perfil'), '| menu:', (await p.textContent('#menu')).trim(), '| lista:', (await p.textContent('#resultado')).trim());
    await p.click('#menu a[href="#/nova"]'); await p.waitForSelector('#c-titulo');
    await p.click('form button[type=submit]'); log(' cadastro vazio:', await p.textContent('#e-titulo'), '|', await p.textContent('#e-categoria_id'));
    await p.fill('#c-titulo', 'Segunda via da carteira'); await p.fill('#c-descricao', 'Perdi o documento original em uma mudança.');
    await p.selectOption('#c-categoria_id', { index: 1 }); await p.selectOption('#c-prioridade', 'alta');
    await p.click('form button[type=submit]'); await p.waitForFunction(() => /^Solicitação \d+/.test(document.querySelector('main h1')?.textContent || ''));
    log(' criada:', await titulo(), '|', await p.textContent('#aviso'));
    log(' detalhe:', (await p.textContent('dl.dados')).replace(/\s+/g, ' ').slice(0, 120), '|', await p.textContent('main p.ajuda'));
    await p.click('#menu a[href="#/solicitacoes"]'); await p.waitForSelector('#resultado tbody tr');
    log(' lista:', await p.locator('#resultado tbody tr').count(), 'linha(s);', (await p.textContent('#resultado tbody tr')).replace(/\s+/g, ' ').slice(0, 110));
    await p.fill('#c-f-q', 'inexistente'); await p.click('form.filtros button'); await p.waitForSelector('#resultado .vazio');
    log(' filtro sem resultado:', await p.textContent('#resultado .vazio'));
    // sessão revogada no servidor: a tela volta para o login com aviso
    await p.evaluate(() => sessionStorage.setItem('sd-token', 'token-invalido'));
    await p.click('form.filtros button'); await p.waitForFunction(() => document.querySelector('main h1')?.textContent === 'Entrar');
    log(' token inválido:', await titulo(), '|', await p.textContent('#aviso'));
    // falha de rede: carregamento e mensagem de erro com "tentar de novo"
    await p.fill('#c-email', 'gestor@exemplo.gov.br'); await p.fill('#c-senha', 'Senha-Forte-2026'); await p.click('button[type=submit]');
    await p.waitForSelector('#resultado tbody tr');
    log(' gestor:', await titulo(), '| vê', await p.locator('#resultado tbody tr').count(), 'solicitação(ões) | menu:', (await p.textContent('#menu')).trim());
    await ctx.route('**/api/v1/solicitacoes?**', (r) => r.abort());
    await p.click('form.filtros button'); await p.waitForSelector('#resultado .erro');
    log(' sem rede:', await p.textContent('#resultado .erro'), '| botão:', await p.textContent('#resultado button'));
    await ctx.unroute('**/api/v1/solicitacoes?**');
    await ctx.route('**/api/v1/solicitacoes?**', async (r) => { await new Promise((ok) => setTimeout(ok, 700)); r.continue(); });
    await p.click('#resultado button'); log(' carregando:', await p.getAttribute('#resultado', 'aria-busy'), '|', await p.textContent('#resultado'));
    await p.waitForSelector('#resultado tbody tr'); await ctx.unroute('**/api/v1/solicitacoes?**');
    await p.click('#sair'); await p.waitForFunction(() => document.querySelector('main h1')?.textContent === 'Entrar');
    log(' sair:', await p.textContent('#aviso'), '| token:', await p.evaluate(() => sessionStorage.getItem('sd-token')));
    // administrador: usuários; não abre solicitação
    await p.fill('#c-email', 'admin@exemplo.gov.br'); await p.fill('#c-senha', 'Senha-Forte-2026'); await p.click('button[type=submit]');
    await p.waitForSelector('main table'); log(' admin:', await titulo(), '|', await p.locator('main tbody tr').count(), 'usuários | menu:', (await p.textContent('#menu')).trim());
    await p.goto(URL + '#/nova'); await p.waitForSelector('main .erro'); log(' admin em #/nova:', await p.textContent('main .erro'));
    await p.click('#sair'); await p.waitForFunction(() => document.querySelector('main h1')?.textContent === 'Entrar');
    // recuperação de senha e página do link
    await p.click('a[href="#/recuperar"]'); await p.fill('#c-email', 'cidada@exemplo.gov.br'); await p.click('button[type=submit]');
    await p.waitForSelector('#aviso.ok'); log(' recuperar:', await p.textContent('#aviso'));
    await p.goto(URL + 'redefinir-senha#token=' + 'x'.repeat(40)); await p.waitForSelector('#c-nova_senha');
    await p.fill('#c-nova_senha', 'Nova-Senha-2026'); await p.fill('#c-confirmacao', 'Outra-Senha-2026'); await p.click('button[type=submit]');
    log(' senhas diferentes:', await p.textContent('#e-confirmacao'));
    await p.fill('#c-confirmacao', 'Nova-Senha-2026'); await p.click('button[type=submit]'); await p.waitForSelector('#aviso.erro');
    log(' link inválido:', await p.textContent('#aviso'));
    // operador: fila
    await p.goto(URL); await p.waitForSelector('#c-email'); await p.fill('#c-email', 'operador@exemplo.gov.br'); await p.fill('#c-senha', 'Senha-Forte-2026'); await p.click('button[type=submit]');
    await p.waitForSelector('#resultado tbody tr, #resultado .vazio'); log(' operador:', await titulo(), '|', (await p.textContent('#resultado')).replace(/\s+/g, ' ').slice(0, 80));
    await p.screenshot({ path: `${process.argv[2]}/tela-${w}.png`, fullPage: true });
    log(' largura da página:', await p.evaluate(() => document.documentElement.scrollWidth), '| CSP bloqueou algo:', erros.some((e) => /Content Security Policy/.test(e)));
    await ctx.close();
  }
  // as falhas provocadas de propósito (rede cortada e link de senha inválido) aparecem como erro de recurso no console
  const inesperados = erros.filter((e) => !/net::ERR_FAILED|status of 400/.test(e));
  log('erros provocados no teste:', erros.length - inesperados.length, '| erros inesperados no navegador:', JSON.stringify(inesperados)); await b.close();
})();
