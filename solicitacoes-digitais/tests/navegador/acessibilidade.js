// Verificação automática de acessibilidade e responsividade (OS-001, D7-A / RNF-09).
// Uso: node tests/navegador/acessibilidade.js <url-base> <pasta-temporaria>
// Em cada tela, por perfil, em 1280 px e 390 px: axe-core (WCAG 2 A e AA) sem violação grave ou crítica
// e página sem rolagem lateral. Sai com código 1 se algo falhar e lista o problema.
const { chromium } = require('playwright');
const path = require('path');

const [URL] = process.argv.slice(2);
const AXE = path.join(__dirname, 'node_modules', 'axe-core', 'axe.min.js');
const SENHA = 'Senha-Forte-2026';
const falhas = [];
let telas = 0;

async function pronta(p) {
  await p.waitForFunction(() => document.querySelector('main h1') && !document.querySelector('[aria-busy="true"]'), null, { timeout: 30000 });
}
async function verificar(p, nome, largura) {
  await pronta(p);
  await p.addScriptTag({ path: AXE });
  const r = await p.evaluate(async () => {
    const res = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
    return res.violations.map((v) => ({ id: v.id, impacto: v.impact, ajuda: v.help, alvos: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }));
  });
  const graves = r.filter((v) => v.impacto === 'serious' || v.impacto === 'critical');
  const transborda = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  telas += 1;
  const leves = r.length - graves.length;
  console.log(`${graves.length || transborda ? 'FALHA' : 'ok'} ${largura}px ${nome}: ${graves.length} graves/críticas, ${leves} moderadas/leves${transborda ? ', ROLAGEM LATERAL' : ''}`);
  graves.forEach((v) => { console.log(`   - ${v.id} (${v.impacto}): ${v.ajuda} → ${v.alvos.join(' | ')}`); falhas.push(`${largura}px ${nome}: ${v.id}`); });
  if (transborda) falhas.push(`${largura}px ${nome}: rolagem lateral`);
}
async function entrar(ctx, email) {
  const p = await ctx.newPage();
  await p.goto(URL); await p.fill('#c-email', email); await p.fill('#c-senha', SENHA); await p.click('button[type=submit]');
  await p.waitForSelector('#conta:not([hidden])');
  return p;
}

(async () => {
  const b = await chromium.launch();
  try {
    // dados: uma solicitação aberta pela solicitante, triada e atribuída pelo gestor (para as telas terem conteúdo)
    const prep = await b.newContext();
    const ps = await entrar(prep, 'cidada@exemplo.gov.br');
    const id = await ps.evaluate(async () => {
      const t = sessionStorage.getItem('sd-token'); const h = { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' };
      const cats = await (await fetch('/api/v1/categorias', { headers: h })).json();
      const s = await (await fetch('/api/v1/solicitacoes', { method: 'POST', headers: h, body: JSON.stringify({ titulo: 'Segunda via da certidão', descricao: 'Documento danificado pela chuva.', categoria_id: cats[0].id }) })).json();
      return s.id;
    });
    await prep.close();

    for (const largura of [1280, 390]) {
      // bypassCSP só aqui, para injetar o axe-core; as páginas continuam servidas com a CSP (conferida em test_web.py)
      const ctx = await b.newContext({ viewport: { width: largura, height: 900 }, bypassCSP: true });
      const p0 = await ctx.newPage();
      await p0.goto(URL); await verificar(p0, 'entrar', largura);
      await p0.goto(URL + '#/recuperar'); await verificar(p0, 'recuperar acesso', largura);
      await p0.close();
      let p = await entrar(ctx, 'cidada@exemplo.gov.br');
      await verificar(p, 'solicitante: minhas solicitações', largura);
      await p.goto(URL + '#/nova'); await p.waitForSelector('#c-titulo'); await verificar(p, 'solicitante: nova solicitação', largura);
      await p.click('form button[type=submit]'); await p.waitForSelector('#e-titulo:not([hidden])'); await verificar(p, 'solicitante: formulário com erros', largura);
      await p.goto(URL + `#/solicitacoes/${id}`); await verificar(p, 'solicitante: detalhe', largura);
      await p.click('#sair'); await p.waitForSelector('#c-email'); await p.close();
      p = await entrar(ctx, 'gestor@exemplo.gov.br');
      await verificar(p, 'gestor: solicitações', largura);
      await p.goto(URL + `#/solicitacoes/${id}`); await verificar(p, 'gestor: detalhe com tramitar, atribuir, anexos, histórico e auditoria', largura);
      await p.goto(URL + '#/painel'); await p.waitForSelector('#painel-resultado .kpis'); await verificar(p, 'gestor: painel gerencial', largura);
      await p.goto(URL + '#/auditoria'); await verificar(p, 'gestor: auditoria', largura);
      await p.click('#sair'); await p.waitForSelector('#c-email'); await p.close();
      p = await entrar(ctx, 'admin@exemplo.gov.br');
      await verificar(p, 'administrador: usuários', largura);
      await ctx.close();
    }
    if (falhas.length) { console.log(`acessibilidade reprovada em ${falhas.length} ponto(s) de ${telas} telas`); process.exitCode = 1; }
    else console.log(`acessibilidade aprovada: ${telas} telas sem violação grave ou crítica e sem rolagem lateral`);
  } catch (e) {
    console.error(String(e && e.stack || e)); process.exitCode = 1;
  } finally { await b.close(); }
})();
