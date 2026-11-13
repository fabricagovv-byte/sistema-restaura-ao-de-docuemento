// Frontend do Sistema de Solicitações Digitais (OS-001, dia 5): login, recuperação de senha, perfis,
// lista e cadastro de solicitações, com estados de carregamento, vazio e erro.
// Regras de segurança: o DOM é montado só com textContent (nada de innerHTML), o token fica no
// sessionStorage (some ao fechar a aba) e toda chamada passa por api(), que trata 401/403/422 e falha de rede.

const TOKEN = "sd-token";
const STATUS = {
  recebida: "Recebida", em_triagem: "Em triagem", em_atendimento: "Em atendimento",
  aguardando_solicitante: "Aguardando o solicitante", concluida: "Concluída", indeferida: "Indeferida", cancelada: "Cancelada",
};
const FINAIS = new Set(["concluida", "indeferida", "cancelada"]);
const PRIORIDADES = { baixa: "Baixa", normal: "Normal", alta: "Alta", urgente: "Urgente" };
const PERFIS = { administrador: "Administrador", gestor: "Gestor", operador: "Operador", solicitante: "Solicitante" };
const CAMPOS = { titulo: "Título", descricao: "Descrição", categoria_id: "Categoria", prioridade: "Prioridade", email: "E-mail",
  senha: "Senha", nova_senha: "Nova senha", token: "Link" };

let eu = null;  // usuário logado ({id, nome, perfil, ...})

/* ------------------------------------------------------------------ DOM seguro */
function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "on") for (const [ev, fn] of Object.entries(v)) n.addEventListener(ev, fn);
    else if (k === "class") n.className = v;
    else if (k === "dados") for (const [dk, dv] of Object.entries(v)) n.dataset[dk] = dv;
    else n.setAttribute(k, v === true ? "" : String(v));
  }
  for (const f of filhos.flat()) if (f != null && f !== false) n.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return n;
}
const main = () => document.getElementById("conteudo");
function tela(titulo, ...conteudo) {
  const m = main();
  m.replaceChildren(el("h1", {}, titulo), ...conteudo.filter((c) => c != null && c !== false));
  m.removeAttribute("aria-busy");
  document.title = `${titulo} · Solicitações Digitais`;
  m.focus();
}
function carregando(texto = "Carregando…") { const m = main(); m.setAttribute("aria-busy", "true"); m.replaceChildren(el("p", { class: "carregando" }, texto)); }
function avisar(texto, tipo = "ok") {
  const a = document.getElementById("aviso");
  a.className = `aviso ${tipo}`; a.textContent = texto; a.hidden = !texto;
  a.setAttribute("role", tipo === "erro" ? "alert" : "status");
}
const dataHora = (s) => s ? new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

/* ------------------------------------------------------------------ API */
class ErroApi extends Error {
  constructor(status, mensagem, campos = {}) { super(mensagem); this.status = status; this.campos = campos; }
}
function traduzirValidacao(d) {
  const ctx = d.ctx || {};
  if (d.type === "missing") return "Obrigatório.";
  if (d.type === "string_too_short") return `Use pelo menos ${ctx.min_length} caracteres.`;
  if (d.type === "string_too_long") return `Use no máximo ${ctx.max_length} caracteres.`;
  if (d.type === "value_error") return String(d.msg || "").replace(/^Value error, /, "");
  if (d.type === "literal_error" || d.type === "enum") return "Escolha uma das opções.";
  if (d.type?.startsWith("int_")) return "Escolha uma opção válida.";
  return d.msg || "Valor inválido.";
}
export async function api(metodo, caminho, corpo) {
  const cab = { Accept: "application/json" };
  const token = sessionStorage.getItem(TOKEN);
  if (token) cab.Authorization = `Bearer ${token}`;
  const ehArquivo = typeof FormData !== "undefined" && corpo instanceof FormData;  // envio de anexo (multipart)
  if (corpo !== undefined && !ehArquivo) cab["Content-Type"] = "application/json";
  let r;
  try {
    r = await fetch(`/api/v1${caminho}`, { method: metodo, headers: cab, body: corpo === undefined ? undefined : ehArquivo ? corpo : JSON.stringify(corpo) });
  } catch {
    throw new ErroApi(0, "Sem conexão com o servidor. Verifique a internet e tente de novo.");
  }
  if (r.status === 204) return null;
  let dados = null;
  try { dados = await r.json(); } catch { /* resposta sem corpo JSON */ }
  if (r.ok) return dados;
  const det = dados && dados.detail;
  if (r.status === 401 && caminho !== "/auth/login") {
    sessionStorage.removeItem(TOKEN); eu = null;
    avisar("Sua sessão expirou ou foi encerrada. Entre de novo.", "erro");
    ir("#/entrar");
    throw new ErroApi(401, "Sessão expirada.");
  }
  if (r.status === 422 && Array.isArray(det)) {
    const campos = {};
    for (const d of det) { const c = (d.loc || []).slice(-1)[0]; if (c && !campos[c]) campos[c] = traduzirValidacao(d); }
    throw new ErroApi(422, "Confira os campos destacados.", campos);
  }
  const msg = typeof det === "string" ? det : r.status === 403 ? "Seu perfil não tem permissão para esta ação."
    : r.status >= 500 ? "O servidor teve um problema. Tente de novo em instantes." : "Não foi possível concluir.";
  throw new ErroApi(r.status, msg.charAt(0).toUpperCase() + msg.slice(1));
}

/* ------------------------------------------------------------------ formulários */
function campo(nome, rotulo, controle, ajuda) {
  controle.id = controle.id || `c-${nome}`; controle.name = nome;
  const erro = el("span", { class: "erro-campo", id: `e-${nome}`, hidden: true });
  const descr = [ajuda ? `a-${nome}` : null, `e-${nome}`].filter(Boolean).join(" ");
  controle.setAttribute("aria-describedby", descr);
  return el("label", { for: controle.id }, rotulo, ajuda ? el("span", { class: "ajuda", id: `a-${nome}` }, ajuda) : null, controle, erro);
}
function mostrarErros(form, campos) {
  form.querySelectorAll(".erro-campo").forEach((e) => { e.hidden = true; e.textContent = ""; });
  form.querySelectorAll("[aria-invalid]").forEach((c) => c.removeAttribute("aria-invalid"));
  let primeiro = null;
  for (const [nome, msg] of Object.entries(campos || {})) {
    const c = form.elements[nome]; const e = form.querySelector(`#e-${nome}`);
    if (c) { c.setAttribute("aria-invalid", "true"); primeiro = primeiro || c; }
    if (e) { e.hidden = false; e.textContent = msg; } else avisar(`${CAMPOS[nome] || nome}: ${msg}`, "erro");
  }
  if (primeiro) primeiro.focus();
}
async function enviar(form, botao, acao) {
  const original = botao.textContent;
  botao.disabled = true; botao.textContent = "Enviando…"; form.setAttribute("aria-busy", "true");
  avisar("");
  try { await acao(); }
  catch (e) {
    if (e.status === 401 && !form.closest("[data-tela=entrar]")) return;
    mostrarErros(form, e.campos);
    avisar(e.message, "erro");
  } finally { botao.disabled = false; botao.textContent = original; form.removeAttribute("aria-busy"); }
}

/* ------------------------------------------------------------------ telas: acesso */
function telaEntrar() {
  const email = el("input", { type: "email", autocomplete: "username", required: true });
  const senha = el("input", { type: "password", autocomplete: "current-password", required: true });
  const botao = el("button", { type: "submit" }, "Entrar");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    const faltam = {}; if (!email.value.trim()) faltam.email = "Informe o e-mail."; if (!senha.value) faltam.senha = "Informe a senha.";
    if (Object.keys(faltam).length) { mostrarErros(form, faltam); return; }
    enviar(form, botao, async () => {
      const r = await api("POST", "/auth/login", { email: email.value.trim(), senha: senha.value });
      sessionStorage.setItem(TOKEN, r.token); senha.value = "";
      await carregarEu(); avisar(""); ir(inicial());
    });
  } } }, campo("email", "E-mail", email), campo("senha", "Senha", senha), el("div", { class: "acoes" }, botao, el("a", { href: "#/recuperar" }, "Esqueci minha senha")));
  tela("Entrar", el("div", { class: "cartao estreito", dados: { tela: "entrar" } }, form));
}
function telaRecuperar() {
  const email = el("input", { type: "email", autocomplete: "email", required: true });
  const botao = el("button", { type: "submit" }, "Enviar link");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    if (!email.value.trim()) { mostrarErros(form, { email: "Informe o e-mail." }); return; }
    enviar(form, botao, async () => {
      const r = await api("POST", "/auth/recuperar", { email: email.value.trim() });
      avisar(r.mensagem, "ok"); ir("#/entrar");
    });
  } } }, campo("email", "E-mail da conta", email, "Enviaremos um link para criar uma nova senha, válido por 30 minutos."),
  el("div", { class: "acoes" }, botao, el("a", { href: "#/entrar" }, "Voltar")));
  tela("Recuperar acesso", el("div", { class: "cartao estreito", dados: { tela: "entrar" } }, form));
}
function telaRedefinir(token) {
  const nova = el("input", { type: "password", autocomplete: "new-password", required: true });
  const conf = el("input", { type: "password", autocomplete: "new-password", required: true });
  const botao = el("button", { type: "submit" }, "Salvar nova senha");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    if (nova.value !== conf.value) { mostrarErros(form, { confirmacao: "As duas senhas precisam ser iguais." }); return; }
    enviar(form, botao, async () => {
      await api("POST", "/auth/redefinir", { token, nova_senha: nova.value });
      history.replaceState(null, "", "/"); avisar("Senha alterada. Entre com a nova senha.", "ok"); ir("#/entrar");
    });
  } } }, campo("nova_senha", "Nova senha", nova, "Pelo menos 10 caracteres, com letras maiúsculas, minúsculas e números."), campo("confirmacao", "Repita a nova senha", conf), el("div", { class: "acoes" }, botao));
  tela("Criar nova senha", el("div", { class: "cartao estreito", dados: { tela: "entrar" } }, form));
}

/* ------------------------------------------------------------------ telas: solicitações */
const MENU = {
  solicitante: [["#/solicitacoes", "Minhas solicitações"], ["#/nova", "Nova solicitação"]],
  operador: [["#/solicitacoes", "Minha fila"], ["#/nova", "Nova solicitação"]],
  gestor: [["#/solicitacoes", "Solicitações"], ["#/nova", "Nova solicitação"], ["#/auditoria", "Auditoria"]],
  administrador: [["#/usuarios", "Usuários"], ["#/auditoria", "Auditoria"]],
};
const inicial = () => eu && eu.perfil === "administrador" ? "#/usuarios" : "#/solicitacoes";
function etiquetaStatus(s) {
  const cls = FINAIS.has(s.status) ? "final" : s.status === "aguardando_solicitante" ? "espera" : "";
  return el("span", { class: `etiqueta ${cls}` }, STATUS[s.status] || s.status);
}
const estadoLista = { status: "", q: "", atrasada: "", pagina: 1 };
async function telaLista() {
  const titulos = { solicitante: "Minhas solicitações", operador: "Minha fila", gestor: "Solicitações" };
  const status = el("select", {}, el("option", { value: "" }, "Todos"), ...Object.entries(STATUS).map(([k, n]) => el("option", { value: k, selected: k === estadoLista.status }, n)));
  const busca = el("input", { type: "search", value: estadoLista.q, placeholder: "título, descrição ou protocolo" });
  const prazo = el("select", {}, el("option", { value: "" }, "Todos"), el("option", { value: "true", selected: estadoLista.atrasada === "true" }, "Só atrasadas"),
    el("option", { value: "false", selected: estadoLista.atrasada === "false" }, "No prazo"));
  const resultado = el("div", { id: "resultado", "aria-live": "polite" });
  const buscar = el("button", { type: "submit" }, "Filtrar");
  const filtros = el("form", { class: "filtros", role: "search", on: { submit: (ev) => { ev.preventDefault();
    Object.assign(estadoLista, { status: status.value, q: busca.value.trim(), atrasada: prazo.value, pagina: 1 }); carregarLista(resultado); } } },
  campo("f-status", "Situação", status), campo("f-q", "Busca", busca), campo("f-prazo", "Prazo", prazo), el("div", {}, buscar));
  tela(titulos[eu.perfil] || "Solicitações", el("div", { class: "cartao" }, filtros, resultado));
  await carregarLista(resultado);
}
async function carregarLista(alvo) {
  alvo.setAttribute("aria-busy", "true"); alvo.replaceChildren(el("p", { class: "carregando" }, "Carregando solicitações…"));
  const p = new URLSearchParams({ pagina: estadoLista.pagina, por_pagina: 20 });
  if (estadoLista.status) p.set("status", estadoLista.status);
  if (estadoLista.q) p.set("q", estadoLista.q);
  if (estadoLista.atrasada) p.set("atrasada", estadoLista.atrasada);
  try {
    const r = await api("GET", `/solicitacoes?${p}`);
    alvo.removeAttribute("aria-busy");
    if (!r.itens.length) {
      alvo.replaceChildren(el("p", { class: "vazio" }, estadoLista.status || estadoLista.q || estadoLista.atrasada ? "Nenhuma solicitação com esses filtros."
        : "Nenhuma solicitação ainda.", " ", eu.perfil !== "administrador" ? el("a", { href: "#/nova" }, "Abrir uma solicitação") : null));
      return;
    }
    const linhas = r.itens.map((s) => el("tr", {},
      el("td", { "data-rotulo": "Protocolo" }, el("a", { href: `#/solicitacoes/${s.id}` }, s.protocolo)),
      el("td", { "data-rotulo": "Título" }, s.titulo),
      el("td", { "data-rotulo": "Categoria" }, s.categoria),
      el("td", { "data-rotulo": "Situação" }, etiquetaStatus(s)),
      el("td", { "data-rotulo": "Prioridade" }, PRIORIDADES[s.prioridade] || s.prioridade),
      el("td", { "data-rotulo": "Prazo" }, dataHora(s.prazo_em), s.atrasada ? el("span", { class: "etiqueta atrasada" }, " atrasada") : null),
      el("td", { "data-rotulo": "Responsável" }, s.responsavel ? s.responsavel.nome : "—")));
    const paginas = Math.max(1, Math.ceil(r.total / r.por_pagina));
    const mudar = (d) => { estadoLista.pagina += d; carregarLista(alvo); };
    alvo.replaceChildren(...[
      el("p", { class: "ajuda" }, `${r.total} ${r.total === 1 ? "solicitação" : "solicitações"}`),
      el("div", { class: "tabela" }, el("table", { class: "responsiva" },
        el("caption", { class: "pular" }, "Solicitações"),
        el("thead", {}, el("tr", {}, ...["Protocolo", "Título", "Categoria", "Situação", "Prioridade", "Prazo", "Responsável"].map((t) => el("th", { scope: "col" }, t)))),
        el("tbody", {}, linhas))),
      paginas > 1 ? el("div", { class: "paginacao" },
        el("button", { type: "button", class: "secundario", disabled: r.pagina <= 1, on: { click: () => mudar(-1) } }, "Anterior"),
        el("span", {}, `Página ${r.pagina} de ${paginas}`),
        el("button", { type: "button", class: "secundario", disabled: r.pagina >= paginas, on: { click: () => mudar(1) } }, "Próxima")) : null].filter(Boolean));
  } catch (e) {
    if (e.status === 401) return;
    alvo.removeAttribute("aria-busy");
    alvo.replaceChildren(el("p", { class: "erro", role: "alert" }, e.message, " "), el("button", { type: "button", class: "secundario", on: { click: () => carregarLista(alvo) } }, "Tentar de novo"));
  }
}
async function telaNova() {
  carregando("Carregando categorias…");
  let cats;
  try { cats = await api("GET", "/categorias"); }
  catch (e) { if (e.status !== 401) tela("Nova solicitação", el("p", { class: "erro", role: "alert" }, e.message)); return; }
  if (!cats.length) { tela("Nova solicitação", el("p", { class: "vazio" }, "Ainda não há categorias ativas. Peça ao administrador para cadastrar.")); return; }
  const titulo = el("input", { maxlength: 200, required: true });
  const descricao = el("textarea", { rows: 6, maxlength: 10000, required: true });
  const categoria = el("select", { required: true }, el("option", { value: "" }, "Escolha…"), ...cats.map((c) => el("option", { value: c.id }, `${c.nome} (prazo de ${c.prazo_dias} ${c.prazo_dias === 1 ? "dia" : "dias"})`)));
  const prioridade = el("select", {}, ...Object.entries(PRIORIDADES).map(([k, n]) => el("option", { value: k, selected: k === "normal" }, n)));
  const botao = el("button", { type: "submit" }, "Abrir solicitação");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    const erros = {};
    if (titulo.value.trim().length < 5) erros.titulo = "Use pelo menos 5 caracteres.";
    if (descricao.value.trim().length < 10) erros.descricao = "Descreva o pedido com pelo menos 10 caracteres.";
    if (!categoria.value) erros.categoria_id = "Escolha a categoria.";
    if (Object.keys(erros).length) { mostrarErros(form, erros); return; }
    enviar(form, botao, async () => {
      const s = await api("POST", "/solicitacoes", { titulo: titulo.value.trim(), descricao: descricao.value.trim(),
        categoria_id: Number(categoria.value), prioridade: prioridade.value });
      avisar(`Solicitação ${s.protocolo} aberta. Prazo de atendimento: ${dataHora(s.prazo_em)}.`, "ok");
      ir(`#/solicitacoes/${s.id}`);
    });
  } } }, campo("titulo", "Título", titulo, "Resuma o pedido em uma frase."), campo("descricao", "Descrição", descricao, "Explique o que precisa; não coloque senhas ou dados de cartão."),
  campo("categoria_id", "Categoria", categoria), campo("prioridade", "Prioridade", prioridade), el("div", { class: "acoes" }, botao, el("a", { href: "#/solicitacoes" }, "Cancelar")));
  tela("Nova solicitação", el("div", { class: "cartao" }, form));
}
const PODE_ANEXAR_TIPOS = ".pdf,.png,.jpg,.jpeg,.docx,application/pdf,image/png,image/jpeg";
const tamanho = (b) => b >= 1048576 ? `${(b / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
const EVENTOS = { criacao: "Abertura", transicao: "Mudança de situação", atribuicao: "Atribuição", edicao: "Edição", arquivamento: "Arquivamento",
  desarquivamento: "Desarquivamento", anexo: "Anexo" };
function blocoCarregando(titulo) {
  return el("section", { class: "cartao", "aria-busy": "true" }, el("h2", {}, titulo), el("p", { class: "carregando" }, "Carregando…"));
}
function preencherBloco(sec, ...conteudo) { sec.removeAttribute("aria-busy"); sec.replaceChildren(sec.firstChild, ...conteudo.filter((c) => c != null && c !== false)); }
function erroBloco(sec, e, recarregar) {
  if (e.status === 401) return;
  preencherBloco(sec, el("p", { class: "erro", role: "alert" }, e.message, " "),
    recarregar ? el("button", { type: "button", class: "secundario", on: { click: recarregar } }, "Tentar de novo") : null);
}
async function apiBaixar(metodo, caminho, nome) {
  const r = await fetch(`/api/v1${caminho}`, { method: metodo, headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN)}` } });
  if (!r.ok) { let d = null; try { d = (await r.json()).detail; } catch { /* sem corpo */ } throw new ErroApi(r.status, typeof d === "string" ? d : "Não foi possível baixar o arquivo."); }
  const url = URL.createObjectURL(await r.blob());
  const a = el("a", { href: url, download: nome }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
const recarregarDetalhe = (id, msg) => { if (msg) avisar(msg, "ok"); telaDetalhe(id); };

async function telaDetalhe(id) {
  carregando("Carregando a solicitação…");
  let s;
  try { s = await api("GET", `/solicitacoes/${id}`); }
  catch (e) { if (e.status !== 401) tela("Solicitação", el("p", { class: "erro", role: "alert" }, e.status === 404 ? "Solicitação não encontrada ou sem permissão para vê-la." : e.message), el("a", { href: "#/solicitacoes" }, "Voltar à lista")); return; }
  const linha = (rot, ...val) => [el("dt", {}, rot), el("dd", {}, ...val)];
  const finalizada = FINAIS.has(s.status);
  const blocos = [];
  // 1. tramitação
  if (s.acoes_possiveis.length && !s.arquivada) blocos.push(blocoTramitar(s));
  // 2. atribuição
  if (!finalizada && !s.arquivada && eu.perfil === "gestor") blocos.push(blocoAtribuirGestor(s));
  if (!finalizada && !s.arquivada && eu.perfil === "operador" && !s.responsavel && ["recebida", "em_triagem"].includes(s.status)) {
    const b = el("button", { type: "button", on: { click: async () => { b.disabled = true;
      try { await api("POST", `/solicitacoes/${s.id}/atribuir`, { responsavel_id: eu.id }); recarregarDetalhe(s.id, "Solicitação assumida por você."); }
      catch (e) { b.disabled = false; if (e.status !== 401) avisar(e.message, "erro"); } } } }, "Assumir para mim");
    blocos.push(el("section", { class: "cartao" }, el("h2", {}, "Atendimento"), el("p", { class: "ajuda" }, "Ninguém está atendendo esta solicitação."), b));
  }
  // 3. arquivamento (gestor)
  if (eu.perfil === "gestor" && (finalizada || s.arquivada)) blocos.push(blocoArquivar(s));
  const secAnexos = blocoCarregando("Anexos"), secHist = blocoCarregando("Histórico");
  const secAud = eu.perfil === "gestor" ? blocoCarregando("Auditoria desta solicitação") : null;
  tela(`Solicitação ${s.protocolo}`, el("div", { class: "cartao" }, el("dl", { class: "dados" },
    ...linha("Título", s.titulo), ...linha("Situação", etiquetaStatus(s), s.arquivada ? el("span", { class: "etiqueta" }, " arquivada") : ""),
    ...linha("Categoria", s.categoria), ...linha("Prioridade", PRIORIDADES[s.prioridade] || s.prioridade),
    ...linha("Prazo", dataHora(s.prazo_em), s.atrasada ? el("span", { class: "etiqueta atrasada" }, " atrasada") : ""),
    ...linha("Solicitante", s.solicitante.nome), ...linha("Responsável", s.responsavel ? s.responsavel.nome : "ainda não atribuído"),
    ...linha("Aberta em", dataHora(s.criado_em)), ...linha("Descrição", s.descricao))),
  ...blocos, secAnexos, secHist, secAud, el("a", { href: "#/solicitacoes" }, "Voltar à lista"));
  carregarAnexos(s, secAnexos); carregarHistorico(s, secHist); if (secAud) carregarAuditoria(secAud, { recurso: "solicitacao", recurso_id: String(s.id) }, true);
}

function blocoTramitar(s) {
  const comentario = el("textarea", { rows: 3, maxlength: 5000, placeholder: "Obrigatório para concluir, indeferir, pedir complemento, cancelar e reabrir." });
  const form = el("form", { novalidate: true, on: { submit: (ev) => ev.preventDefault() } }, campo("comentario", "Comentário ou resposta", comentario));
  const botoes = s.acoes_possiveis.map((para) => {
    const b = el("button", { type: "button", class: para === "indeferida" || para === "cancelada" ? "secundario" : "", dados: { para } }, `Mover para: ${STATUS[para] || para}`);
    b.addEventListener("click", () => enviar(form, b, async () => {
      await api("POST", `/solicitacoes/${s.id}/tramitar`, { para, comentario: comentario.value.trim() || null });
      recarregarDetalhe(s.id, `Situação alterada para "${STATUS[para] || para}".`);
    }));
    return b;
  });
  form.append(el("div", { class: "acoes" }, ...botoes));
  return el("section", { class: "cartao" }, el("h2", {}, "Tramitar"), form);
}
function blocoAtribuirGestor(s) {
  const sel = el("select", {}, el("option", { value: "" }, "Carregando pessoas…"));
  const botao = el("button", { type: "submit" }, s.responsavel ? "Trocar responsável" : "Atribuir");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    if (!sel.value) { mostrarErros(form, { responsavel_id: "Escolha quem vai atender." }); return; }
    enviar(form, botao, async () => {
      await api("POST", `/solicitacoes/${s.id}/atribuir`, { responsavel_id: Number(sel.value) });
      recarregarDetalhe(s.id, "Responsável definido.");
    });
  } } }, campo("responsavel_id", "Responsável", sel, "Só operadores e gestores ativos."), el("div", { class: "acoes" }, botao));
  api("GET", "/usuarios?ativo=true").then((us) => {
    const aptos = us.filter((u) => u.perfil === "operador" || u.perfil === "gestor");
    sel.replaceChildren(el("option", { value: "" }, "Escolha…"), ...aptos.map((u) => el("option", { value: u.id, selected: s.responsavel && s.responsavel.id === u.id }, `${u.nome} (${PERFIS[u.perfil]})`)));
  }).catch((e) => { if (e.status !== 401) sel.replaceChildren(el("option", { value: "" }, "Não foi possível carregar as pessoas")); });
  return el("section", { class: "cartao" }, el("h2", {}, "Atribuição"), form);
}
function blocoArquivar(s) {
  const comentario = el("input", { maxlength: 2000, placeholder: "opcional" });
  const botao = el("button", { type: "submit", class: "secundario" }, s.arquivada ? "Desarquivar" : "Arquivar");
  const form = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
    enviar(form, botao, async () => {
      await api("POST", `/solicitacoes/${s.id}/arquivamento`, { arquivar: !s.arquivada, comentario: comentario.value.trim() || null });
      recarregarDetalhe(s.id, s.arquivada ? "Solicitação desarquivada." : "Solicitação arquivada.");
    });
  } } }, campo("arq-comentario", "Comentário", comentario), el("div", { class: "acoes" }, botao));
  return el("section", { class: "cartao" }, el("h2", {}, "Arquivo"), el("p", { class: "ajuda" }, s.arquivada ? "Arquivada: não tramita até ser desarquivada." : "Finalizada: pode ser arquivada."), form);
}
function podeAnexar(s) {
  if (s.arquivada || FINAIS.has(s.status)) return false;
  if (eu.perfil === "solicitante") return s.solicitante.id === eu.id;
  if (eu.perfil === "operador") return !!s.responsavel && s.responsavel.id === eu.id;
  return eu.perfil === "gestor";
}
async function carregarAnexos(s, sec) {
  let lista;
  try { lista = await api("GET", `/solicitacoes/${s.id}/anexos`); }
  catch (e) { erroBloco(sec, e, () => carregarAnexos(s, sec)); return; }
  const itens = lista.map((a) => {
    const baixar = el("button", { type: "button", class: "secundario", on: { click: async () => {
      baixar.disabled = true; try { await apiBaixar("GET", `/solicitacoes/${s.id}/anexos/${a.id}`, a.nome); } catch (e) { avisar(e.message, "erro"); } finally { baixar.disabled = false; } } } }, "Baixar");
    const pode = podeAnexar(s) && (a.enviado_por === eu.id || eu.perfil === "gestor");
    const remover = pode ? el("button", { type: "button", class: "secundario", on: { click: async () => {
      if (!window.confirm(`Remover o anexo "${a.nome}"? Ele continua guardado para a auditoria.`)) return;
      remover.disabled = true;
      try { await api("DELETE", `/solicitacoes/${s.id}/anexos/${a.id}`); avisar("Anexo removido.", "ok"); carregarAnexos(s, sec); carregarHistorico(s, document.querySelector("[data-bloco=historico]")); }
      catch (e) { remover.disabled = false; if (e.status !== 401) avisar(e.message, "erro"); } } } }, "Remover") : null;
    return el("li", { class: "anexo" }, el("span", {}, el("b", {}, a.nome), ` · ${tamanho(a.tamanho)} · ${dataHora(a.em)}`), el("span", { class: "acoes" }, baixar, remover));
  });
  let envio = null;
  if (podeAnexar(s)) {
    const arq = el("input", { type: "file", accept: PODE_ANEXAR_TIPOS });
    const botao = el("button", { type: "submit" }, "Enviar anexo");
    envio = el("form", { novalidate: true, on: { submit: (ev) => { ev.preventDefault();
      if (!arq.files.length) { mostrarErros(envio, { arquivo: "Escolha um arquivo." }); return; }
      const dados = new FormData(); dados.append("arquivo", arq.files[0]);
      enviar(envio, botao, async () => { await api("POST", `/solicitacoes/${s.id}/anexos`, dados); avisar("Anexo enviado.", "ok"); carregarAnexos(s, sec);
        carregarHistorico(s, document.querySelector("[data-bloco=historico]")); });
    } } }, campo("arquivo", "Novo anexo", arq, "PDF, PNG, JPEG ou DOCX, até 10 MB."), el("div", { class: "acoes" }, botao));
  }
  preencherBloco(sec, itens.length ? el("ul", { class: "anexos" }, itens) : el("p", { class: "vazio" }, "Nenhum anexo."), envio);
}
async function carregarHistorico(s, sec) {
  if (!sec) return;
  sec.dataset.bloco = "historico";
  let h;
  try { h = await api("GET", `/solicitacoes/${s.id}/historico`); }
  catch (e) { erroBloco(sec, e, () => carregarHistorico(s, sec)); return; }
  preencherBloco(sec, el("ol", { class: "linha-tempo" }, h.map((x) => el("li", {},
    el("span", { class: "quando" }, dataHora(x.em)), " ",
    el("b", {}, EVENTOS[x.evento] || x.evento),
    x.de_status || x.para_status ? ` ${x.de_status ? (STATUS[x.de_status] || x.de_status) + " → " : ""}${STATUS[x.para_status] || x.para_status || ""}` : "",
    ` · ${x.ator.nome}`, x.comentario ? el("p", { class: "comentario" }, x.comentario) : null))));
}
const ACOES_AUD = { criar: "Criação", alterar: "Alteração", tramitar: "Tramitação", atribuir: "Atribuição", arquivar: "Arquivamento", desarquivar: "Desarquivamento",
  anexar: "Anexo enviado", remover_anexo: "Anexo removido", login: "Entrada", logout: "Saída", exportar: "Exportação", pedir_recuperacao: "Pedido de nova senha", redefinir_senha: "Nova senha" };
async function carregarAuditoria(sec, filtros, compacto = false) {
  const p = new URLSearchParams({ limite: compacto ? 50 : 200 });
  for (const [k, v] of Object.entries(filtros)) if (v) p.set(k, v);
  let evs;
  try { evs = await api("GET", `/auditoria?${p}`); }
  catch (e) { erroBloco(sec, e, () => carregarAuditoria(sec, filtros, compacto)); return; }
  if (!evs.length) { preencherBloco(sec, el("p", { class: "vazio" }, "Nenhum evento com esses filtros.")); return; }
  const json = (o) => o ? JSON.stringify(o, null, 1) : "";
  preencherBloco(sec, el("p", { class: "ajuda" }, `${evs.length} ${evs.length === 1 ? "evento" : "eventos"} (mais recentes primeiro). A auditoria não pode ser alterada.`),
    el("div", { class: "tabela" }, el("table", { class: "responsiva" },
      el("thead", {}, el("tr", {}, ...["Quando", "Ação", "Recurso", "Ator", "Resultado", "Antes → depois", "Correlação"].map((t) => el("th", { scope: "col" }, t)))),
      el("tbody", {}, evs.map((e) => el("tr", {},
        el("td", { "data-rotulo": "Quando" }, dataHora(e.em)), el("td", { "data-rotulo": "Ação" }, ACOES_AUD[e.acao] || e.acao),
        el("td", { "data-rotulo": "Recurso" }, `${e.recurso}${e.recurso_id ? " #" + e.recurso_id : ""}`), el("td", { "data-rotulo": "Ator" }, e.ator_id ? `usuário ${e.ator_id}` : "—"),
        el("td", { "data-rotulo": "Resultado" }, e.resultado),
        el("td", { "data-rotulo": "Antes → depois" }, e.antes || e.depois ? el("details", {}, el("summary", {}, "ver"), el("pre", {}, `${json(e.antes)}${e.antes && e.depois ? "\n→\n" : ""}${json(e.depois)}`)) : "—"),
        el("td", { "data-rotulo": "Correlação" }, el("code", {}, e.correlacao || "—"))))))));
}
async function telaAuditoria() {
  const recurso = el("select", {}, ...[["", "Todos"], ["solicitacao", "Solicitação"], ["usuario", "Usuário"], ["categoria", "Categoria"], ["sessao", "Sessão (entrada e saída)"], ["painel", "Painel e exportação"]]
    .map(([v, n]) => el("option", { value: v }, n)));
  const recursoId = el("input", { inputmode: "numeric", placeholder: "ex.: 12" });
  const correl = el("input", { placeholder: "X-Correlation-ID" });
  const sec = el("section", { class: "cartao", "aria-busy": "true" }, el("h2", {}, "Eventos"), el("p", { class: "carregando" }, "Carregando…"));
  const filtrar = () => { sec.setAttribute("aria-busy", "true"); carregarAuditoria(sec, { recurso: recurso.value, recurso_id: recursoId.value.trim(), correlacao: correl.value.trim() }); };
  const form = el("form", { class: "filtros", role: "search", on: { submit: (ev) => { ev.preventDefault(); filtrar(); } } },
    campo("a-recurso", "Recurso", recurso), campo("a-id", "Número do recurso", recursoId), campo("a-correl", "Correlação", correl), el("div", {}, el("button", { type: "submit" }, "Filtrar")));
  tela("Auditoria", el("div", { class: "cartao" }, form), sec);
  filtrar();
}
async function telaUsuarios() {
  carregando("Carregando usuários…");
  try {
    const us = await api("GET", "/usuarios");
    tela("Usuários", el("div", { class: "cartao tabela" }, el("table", { class: "responsiva" },
      el("thead", {}, el("tr", {}, ...["Nome", "E-mail", "Perfil", "Situação"].map((t) => el("th", { scope: "col" }, t)))),
      el("tbody", {}, us.map((u) => el("tr", {}, el("td", { "data-rotulo": "Nome" }, u.nome), el("td", { "data-rotulo": "E-mail" }, u.email),
        el("td", { "data-rotulo": "Perfil" }, PERFIS[u.perfil] || u.perfil), el("td", { "data-rotulo": "Situação" }, u.ativo ? "Ativo" : "Inativo")))))));
  } catch (e) { if (e.status !== 401) tela("Usuários", el("p", { class: "erro", role: "alert" }, e.message)); }
}

/* ------------------------------------------------------------------ sessão, menu e rotas */
async function carregarEu() {
  eu = await api("GET", "/auth/eu");
  document.getElementById("conta-nome").textContent = eu.nome;
  document.getElementById("conta-perfil").textContent = PERFIS[eu.perfil] || eu.perfil;
  document.getElementById("conta").hidden = false;
  const menu = document.getElementById("menu");
  menu.replaceChildren(...(MENU[eu.perfil] || []).map(([h, t]) => el("a", { href: h }, t)));
  menu.hidden = false;
}
function sairDaTela() {
  eu = null; Object.assign(estadoLista, { status: "", q: "", atrasada: "", pagina: 1 });  // filtros não passam para o próximo usuário
  document.getElementById("conta").hidden = true; document.getElementById("menu").hidden = true;
}
function ir(hash) { if (location.hash === hash) rota(); else location.hash = hash; }
const PROTEGIDAS = /^#\/(solicitacoes|nova|usuarios|auditoria)/;
async function rota() {
  if (location.pathname === "/redefinir-senha") { const t = new URLSearchParams(location.hash.slice(1)).get("token"); sairDaTela(); return telaRedefinir(t || ""); }
  const h = location.hash || "#/";
  if (!sessionStorage.getItem(TOKEN)) { sairDaTela(); if (h === "#/recuperar") return telaRecuperar(); return telaEntrar(); }
  if (!eu) { carregando(); try { await carregarEu(); } catch (e) { if (e.status !== 401) tela("Erro", el("p", { class: "erro", role: "alert" }, e.message)); return; } }
  if (!PROTEGIDAS.test(h)) return ir(inicial());
  document.querySelectorAll("#menu a").forEach((a) => { if (h.startsWith(a.getAttribute("href"))) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  const m = h.match(/^#\/solicitacoes\/(\d+)$/);
  if (m) return telaDetalhe(m[1]);
  if (h.startsWith("#/nova")) return eu.perfil === "administrador" ? tela("Nova solicitação", el("p", { class: "erro" }, "O administrador não abre solicitações.")) : telaNova();
  if (h.startsWith("#/usuarios")) return telaUsuarios();
  if (h.startsWith("#/auditoria")) return ["gestor", "administrador"].includes(eu.perfil) ? telaAuditoria() : tela("Auditoria", el("p", { class: "erro" }, "Seu perfil não vê a auditoria."));
  if (eu.perfil === "administrador") return ir("#/usuarios");
  return telaLista();
}
document.getElementById("sair").addEventListener("click", async () => {
  try { await api("POST", "/auth/logout"); } catch { /* a sessão já pode ter expirado */ }
  sessionStorage.removeItem(TOKEN); sairDaTela(); avisar("Você saiu do sistema.", "ok"); ir("#/entrar");
});
window.addEventListener("hashchange", rota);
rota();
