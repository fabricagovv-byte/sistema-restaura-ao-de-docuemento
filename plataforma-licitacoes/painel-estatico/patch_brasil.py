"""Aba 'Brasil — todas abertas': todas as licitações com proposta aberta no país (arquivo brasil.json publicado junto),
com busca por palavra, UF, assunto, modalidade, portal, valor e prazo; cópia para WhatsApp e planilha."""
import sys

p = sys.argv[1]
t = open(p).read()


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (a[:80], t.count(a))
    t = t.replace(a, b)


rep('''<a href="#buscas-sec">Minhas buscas</a>''', '''<a href="#br-sec">Brasil (todas)</a><a href="#buscas-sec">Minhas buscas</a>''')
rep('''  <section class="panel" id="cal-sec" aria-labelledby="h-cal">''', '''  <section class="panel" id="br-sec" aria-labelledby="h-br">
    <h2 id="h-br">Brasil — todas as licitações abertas</h2>
    <p class="lede" id="br-lede">Todas as licitações com proposta aberta no país, de todos os assuntos, direto do PNCP (inclui o que os portais parceiros publicam lá).</p>
    <div class="chips" id="br-assuntos" role="group" aria-label="Assunto"></div>
    <details class="br-palavras" id="br-palavras-box" open><summary><b>Palavras-chave</b> <span id="br-pal-resumo">(toque para escolher; vale qualquer uma das marcadas)</span></summary>
      <div id="br-palavras"></div>
      <div class="br-pal-nova"><input id="br-pal-input" type="text" placeholder="Criar palavra-chave (ex.: fábrica de software)" aria-label="Nova palavra-chave"><button type="button" class="mais" id="br-pal-add">Adicionar</button><button type="button" class="mais" id="br-pal-limpar">Limpar marcadas</button></div>
    </details>
    <div class="pesq-filtros">
      <label for="br-sit">Situação<select id="br-sit"><option value="">Todas com edital</option><option value="abertas">Propostas já abertas</option><option value="avir">A vir (propostas ainda não começaram)</option><option value="previstas">Previstas no plano de compras (sem edital, TI)</option></select></label>
      <label for="br-q">Palavra no objeto, órgão ou cidade<input id="br-q" type="search" placeholder="ex.: digitalização, UST, merenda"></label>
      <label for="br-regiao">Região<select id="br-regiao"><option value="">Brasil todo</option><option value="N">Norte</option><option value="NE">Nordeste</option><option value="CO">Centro-Oeste</option><option value="SE">Sudeste</option><option value="S">Sul</option></select></label>
      <label for="br-perto">Perto de (cidade)<input id="br-perto" list="br-cidades" placeholder="ex.: Alvorada de Minas - MG" autocomplete="off"><datalist id="br-cidades"></datalist></label>
      <label for="br-raio">Raio<select id="br-raio"><option value="0">Sem limite</option><option value="50">até 50 km</option><option value="100">até 100 km</option><option value="150">até 150 km</option><option value="200">até 200 km</option><option value="300">até 300 km</option></select></label>
      <label for="br-uf">UF<select id="br-uf"><option value="">Todas</option></select></label>
      <label for="br-mod">Modalidade<select id="br-mod"><option value="">Todas</option></select></label>
      <label for="br-portal">Portal<select id="br-portal"><option value="">Todos</option></select></label>
      <label for="br-vmin">Valor mínimo<select id="br-vmin"><option value="0">Qualquer</option><option value="100000">R$ 100 mil</option><option value="1000000">R$ 1 milhão</option><option value="5000000">R$ 5 milhões</option><option value="10000000">R$ 10 milhões</option><option value="50000000">R$ 50 milhões</option></select></label>
      <label for="br-dias">Encerra em<select id="br-dias"><option value="0">Qualquer prazo</option><option value="3">até 3 dias</option><option value="7">até 7 dias</option><option value="15">até 15 dias</option><option value="30">até 30 dias</option></select></label>
      <label for="br-ord">Ordenar<select id="br-ord"><option value="prazo">Prazo mais próximo</option><option value="valor">Maior valor</option><option value="recente">Prazo mais distante</option><option value="perto">Mais perto da cidade</option></select></label>
    </div>
    <div class="acoes"><button type="button" class="mais" id="br-pregoes" aria-pressed="false">Só pregões</button><button type="button" class="abrir" id="br-copiar">Copiar os 40 primeiros para o WhatsApp</button>
      <button type="button" class="mais" id="br-csv">Baixar planilha com todas as filtradas (CSV)</button></div>
    <p class="conta" id="br-conta" aria-live="polite">Carregando a lista do Brasil…</p>
    <ol class="pesq-lista" id="br-lista"></ol>
    <button type="button" class="mais" id="br-mais" hidden>Mostrar mais</button>
  </section>
  <section class="panel" id="cal-sec" aria-labelledby="h-cal">''')

JS = r'''
(function brasil() {
  let BR = null, lim = 50, assunto = "", soPregao = false;
  const PALAVRAS = {
    "UST, PF e serviços de TI": ["UST", "unidade de serviço técnico", "ponto de função", "fábrica de software", "desenvolvimento de sistemas", "desenvolvimento de software", "sustentação", "manutenção de sistemas", "manutenção evolutiva", "horas técnicas", "alocação de profissionais", "outsourcing", "service desk", "suporte técnico", "help desk", "central de serviços", "testes de software", "business intelligence", "ciência de dados", "inteligência artificial", "banco de dados", "integração de sistemas", "transformação digital"],
    "Sistemas, nuvem e fixo mensal": ["sistema de gestão", "gestão pública", "ERP", "software", "licença de uso", "locação de sistema", "SaaS", "software como serviço", "plataforma", "nuvem", "data center", "hospedagem", "backup", "segurança da informação", "firewall", "LGPD", "internet", "link dedicado", "rede lógica", "cabeamento", "portal", "aplicativo", "site", "mensal"],
    "Gestão documental": ["digitalização", "indexação", "GED", "gestão documental", "gestão arquivística", "arquivo", "acervo", "microfilmagem", "guarda de documentos", "tratamento documental", "OCR", "escaneamento"],
    "Consultoria e educação": ["consultoria", "assessoria", "governança", "PDTI", "capacitação", "treinamento", "EAD", "ensino a distância", "curso"],
    "Obras e material de construção": ["obra", "pavimentação", "recapeamento", "calçamento", "reforma", "construção", "engenharia", "drenagem", "material de construção", "cimento", "areia", "brita", "tijolo", "bloquete", "material hidráulico", "material elétrico", "tinta", "telha", "madeira", "ferragens", "concreto", "asfalto"],
    "Gráfica e comunicação": ["material gráfico", "serviços gráficos", "gráfica", "impressos", "impressão", "banner", "placa", "adesivo", "comunicação visual", "plotagem", "agenda", "carimbo", "panfleto", "cartilha"],
    "Outros": ["veículo", "combustível", "pneu", "merenda", "gêneros alimentícios", "medicamento", "material hospitalar", "limpeza", "vigilância", "uniforme", "mobiliário", "equipamentos de informática", "computador", "notebook"],
  };
  const REGIAO = { N: "AC AM AP PA RO RR TO", NE: "AL BA CE MA PB PE PI RN SE", CO: "DF GO MS MT", SE: "ES MG RJ SP", S: "PR RS SC" };
  let marcadas = new Set(), extras = [];
  try { marcadas = new Set(JSON.parse(localStorage.getItem("br-pal") || "[]")); extras = JSON.parse(localStorage.getItem("br-pal-extra") || "[]"); } catch (e) {}
  function salvarPal() { try { localStorage.setItem("br-pal", JSON.stringify([...marcadas])); localStorage.setItem("br-pal-extra", JSON.stringify(extras)); } catch (e) {} }
  function desenharPal() {
    const grupos = { ...PALAVRAS, ...(extras.length ? { "Minhas palavras": extras } : {}) };
    $("br-palavras").innerHTML = Object.entries(grupos).map(([g, ws]) => `<h4>${esc(g)}</h4><div class="chips">` +
      ws.map((w) => `<button type="button" data-pal="${esc(w)}" aria-pressed="${marcadas.has(w)}">${esc(w)}</button>`).join("") + `</div>`).join("");
    $("br-pal-resumo").textContent = marcadas.size ? `${marcadas.size} marcada(s): ${[...marcadas].slice(0, 6).join(", ")}${marcadas.size > 6 ? "…" : ""}` : "(toque para escolher; vale qualquer uma das marcadas)";
  }
  const $ = (id) => document.getElementById(id);
  const semAc = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const link = (c) => { const m = /^(\d{14})-\d-(\d+)\/(\d{4})$/.exec(c); return m ? `https://pncp.gov.br/app/editais/${m[1]}/${m[3]}/${+m[2]}` : "https://pncp.gov.br/app/editais"; };
  const mi = (v) => v >= 1e9 ? `R$ ${(v / 1e9).toFixed(2).replace(".", ",")} bi` : v >= 1e6 ? `R$ ${(v / 1e6).toFixed(1).replace(".", ",")} mi` : v > 0 ? `R$ ${Math.round(v / 1e3)} mil` : "";
  const data = (s) => s ? `${s.slice(8, 10)}/${s.slice(5, 7)}${s.slice(0, 4) !== String(new Date().getFullYear()) ? "/" + s.slice(0, 4) : ""} ${s.slice(11, 16)}` : "";
  const SUS = 2e9;  // acima disso o valor costuma ser erro de digitação do órgão
  const vv = (r) => r[5] > 0 && r[5] < SUS ? r[5] : 0;
  const val = (r) => r[5] >= SUS ? `${mi(r[5])} ⚠️ conferir` : r[5] > 0 ? mi(r[5]) : (r[6] ? "sigiloso" : "valor não informado");
  function conta(t) { $("br-conta").textContent = t; }
  // distância em linha reta até a cidade escolhida (coordenadas IBGE já embutidas no app)
  const geoCidade = (txt) => { const m = /^(.*?)\s*[-–/]\s*([A-Za-z]{2})$/.exec((txt || "").trim()); if (!m) return null; return GEO_NOME.get(norm(m[1] + " " + m[2].toUpperCase()).trim()) || null; };
  const distCache = new Map();
  const distR = (r, alvo) => { if (!alvo) return null; const k = alvo[0] + "|" + r[2] + "|" + r[3];
    if (!distCache.has(k)) { const g = GEO_NOME.get(norm(r[2] + " " + r[3]).trim()); distCache.set(k, g ? km(alvo, g) : null); } return distCache.get(k); };
  async function carregar() {
    if (BR) return;
    try {
      const resp = await fetch("brasil.json", { cache: "no-store" });
      if (!resp.ok) throw new Error(resp.status);
      BR = await resp.json();
      if (BR.tab) { const T = BR.tab; BR.registros = BR.registros.map((r) => [r[0], T.o[r[1]], T.m[r[2]], r[3], T.mod[r[4]], r[5], r[6], r[7], r[8], T.p[r[9]], T.a[r[10]], r[11], r[12]]); }
      BR.busca = BR.registros.map((r) => semAc(`${r[8]} ${r[1]} ${r[2]} ${r[0]}`));
      preparar(); render();
    } catch (e) {
      conta("A lista completa do Brasil não veio junto com esta cópia do app. Abra pelo link do Claude para ver todas.");
    }
  }
  function preparar() {
    const R = BR.registros, cont = (i) => { const m = new Map(); R.forEach((r) => m.set(r[i], (m.get(r[i]) || 0) + 1)); return [...m].sort((a, b) => b[1] - a[1]); };
    const opc = (sel, lista, max) => { $(sel).insertAdjacentHTML("beforeend", lista.slice(0, max).map(([k, n]) => `<option value="${esc(k)}">${esc(k || "—")} (${fmt(n)})</option>`).join("")); };
    $("br-cidades").innerHTML = GEO.map((g) => `<option value="${esc(g[1])} - ${esc(g[2])}">`).join("");
    opc("br-uf", cont(3).sort((a, b) => a[0].localeCompare(b[0])), 30);
    opc("br-mod", cont(4), 20);
    opc("br-portal", cont(9), 40);
    const as = cont(10);
    $("br-assuntos").innerHTML = `<button type="button" aria-pressed="true" data-as="">Todos (${fmt(R.length)})</button>` + as.map(([k, n]) => `<button type="button" aria-pressed="false" data-as="${esc(k)}">${esc(k)} (${fmt(n)})</button>`).join("");
    const nAvir = R.filter((r) => r[12] > new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16)).length;
    $("br-sit").options[2].textContent = `A vir — propostas ainda não começaram (${fmt(nAvir)})`;
    $("br-sit").options[3].textContent = `Previstas no plano de compras, sem edital — TI (${fmt((BR.previstas || []).length)})`;
    $("br-lede").textContent = `${fmt(R.length)} licitações com prazo aberto no Brasil (${fmt(nAvir)} ainda vão abrir as propostas), de todos os assuntos (PNCP, verificado em ${BR.verificado_em.slice(8, 10)}/${BR.verificado_em.slice(5, 7)} às ${BR.verificado_em.slice(11, 16)}). Inclui o que os portais parceiros publicam no PNCP.`;
  }
  function filtrados() {
    const q = semAc($("br-q").value).split(/\s+/).filter(Boolean), uf = $("br-uf").value, mod = $("br-mod").value, portal = $("br-portal").value;
    const vmin = +$("br-vmin").value, dias = +$("br-dias").value, agora = Date.now(), sit = $("br-sit").value;
    const alvo = geoCidade($("br-perto").value), raio = +$("br-raio").value;
    const reg = $("br-regiao").value, ufsReg = reg ? new Set(REGIAO[reg].split(" ")) : null;
    const pals = [...marcadas].map((w) => { const s = semAc(w).trim(); return s.length <= 4 ? new RegExp("(^|[^a-z0-9])" + s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "([^a-z0-9]|$)") : s; });
    const agoraTxt = new Date(agora - 3 * 3600e3).toISOString().slice(0, 16);
    const out = [];
    BR.registros.forEach((r, i) => {
      if (sit === "abertas" && r[12] > agoraTxt) return; if (sit === "avir" && !(r[12] > agoraTxt)) return;
      if (soPregao && !/preg/i.test(r[4])) return;
      if (uf && r[3] !== uf) return; if (mod && r[4] !== mod) return; if (portal && r[9] !== portal) return;
      if (assunto && r[10] !== assunto) return; if (vmin && !(vv(r) >= vmin)) return;
      if (dias && (new Date(r[7]).getTime() - agora) > dias * 864e5) return;
      if (q.length && !q.every((w) => BR.busca[i].includes(w))) return;
      if (ufsReg && !ufsReg.has(r[3])) return;
      if (pals.length && !pals.some((w) => typeof w === "string" ? BR.busca[i].includes(w) : w.test(BR.busca[i]))) return;
      if (alvo && raio) { const d = distR(r, alvo); if (d == null || d > raio) return; }
      out.push(r);
    });
    const o = $("br-ord").value;
    if (o === "perto" && alvo) out.sort((a, b) => (distR(a, alvo) ?? 1e9) - (distR(b, alvo) ?? 1e9));
    else if (o === "valor") out.sort((a, b) => vv(b) - vv(a)); else if (o === "recente") out.sort((a, b) => b[7].localeCompare(a[7])); else out.sort((a, b) => a[7].localeCompare(b[7]));
    return out;
  }
  function item(r) {
    const alvo = geoCidade($("br-perto").value), d = distR(r, alvo);
    return `<li><div class="topo"><b>${esc(r[1])}</b><span>${esc(r[2])}/${esc(r[3])}</span>${d != null ? `<span class="dist">📍 ${Math.round(d)} km</span>` : ""}</div>
      <p>${esc(r[8])}</p>
      <div class="linha"><span><strong>${esc(val(r))}</strong></span>${r[12] && r[12] > new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16) ? `<span>🔜 Abre <strong>${esc(data(r[12]))}</strong></span>` : ""}<span>Até <strong>${esc(data(r[7]))}</strong></span><span>${esc(r[4])}</span><span>${esc(r[10])}</span>${r[9] ? `<span>${esc(r[9])}</span>` : ""}</div>
      <div class="links"><a href="${link(r[0])}" target="_blank" rel="noopener">Abrir no PNCP</a></div></li>`;
  }
  function renderPrevistas() {
    const P = (BR.previstas || []), q = semAc($("br-q").value), uf = $("br-uf").value;
    const r = P.filter((x) => (!uf || x.uf === uf) && (!q || semAc(`${x.orgao} ${x.unidade} ${x.nome}`).includes(q)));
    conta(`${fmt(r.length)} contratações previstas no plano anual (PCA) de órgãos que compram TI — ainda sem edital publicado. Data = quando o órgão quer contratar.`);
    $("br-lista").innerHTML = r.slice(0, lim).map((x) => `<li><div class="topo"><b>${esc(x.unidade || x.orgao)}</b><span>${esc(x.orgao)}</span></div>
      <p>${esc(x.nome)}</p><div class="linha"><span><strong>${esc(mi(x.valor) || "valor não informado")}</strong></span><span>Previsto para <strong>${esc(x.data)}</strong></span><span>PCA ${esc(x.ano)}</span></div>
      <div class="links">${x.publicado ? `<a href="${esc(x.publicado)}" target="_blank" rel="noopener">Publicação relacionada</a>` : ""}<a href="${esc(x.pca)}" target="_blank" rel="noopener">Plano oficial (PNCP)</a></div></li>`).join("");
    $("br-mais").hidden = r.length <= lim;
  }
  function render() {
    if (!BR) return;
    if ($("br-sit").value === "previstas") return renderPrevistas();
    const r = filtrados(), soma = r.reduce((s, x) => s + vv(x), 0);
    conta(`${fmt(r.length)} licitações · soma estimada ${mi(soma) || "R$ 0"}${r.length > lim ? ` · mostrando ${fmt(lim)}` : ""}`);
    $("br-lista").innerHTML = r.slice(0, lim).map(item).join("");
    $("br-mais").hidden = r.length <= lim;
  }
  function whats() {
    const r = filtrados().slice(0, 40);
    return `*📋 Licitações abertas — Brasil · ${new Date().toLocaleDateString("pt-BR").slice(0, 5)}*\nPNCP (inclui portais parceiros). ${fmt(filtrados().length)} no filtro; os ${r.length} primeiros:\n\n` +
      r.map((x, i) => `*${i + 1}. ${x[1]}* (${x[3]}) · ${x[8].slice(0, 90)}\n💰 *${val(x)}* · 📅 ${data(x[7])}\n🔗 ${link(x[0])}`).join("\n\n");
  }
  ["br-q"].forEach((id) => $(id).addEventListener("input", () => { lim = 50; render(); }));
  desenharPal();
  $("br-palavras").addEventListener("click", (e) => { const b = e.target.closest("[data-pal]"); if (!b) return; const w = b.dataset.pal;
    if (marcadas.has(w)) marcadas.delete(w); else marcadas.add(w); salvarPal(); desenharPal(); lim = 50; render(); });
  const addPal = () => { const w = $("br-pal-input").value.trim(); if (!w) return; if (!extras.includes(w)) extras.push(w); marcadas.add(w); $("br-pal-input").value = ""; salvarPal(); desenharPal(); lim = 50; render(); };
  $("br-pal-add").addEventListener("click", addPal);
  $("br-pal-input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addPal(); } });
  $("br-pal-limpar").addEventListener("click", () => { marcadas.clear(); salvarPal(); desenharPal(); lim = 50; render(); });
  $("br-regiao").addEventListener("change", () => { lim = 50; render(); });
  $("br-pregoes").addEventListener("click", (e) => { soPregao = !soPregao; e.currentTarget.setAttribute("aria-pressed", String(soPregao)); lim = 50; render(); });
  $("br-perto").addEventListener("change", () => { lim = 50; try { localStorage.setItem("br-perto", $("br-perto").value); } catch (e) {} render(); });
  try { const v = localStorage.getItem("br-perto"); if (v) $("br-perto").value = v; } catch (e) {}
  ["br-sit", "br-uf", "br-mod", "br-portal", "br-vmin", "br-dias", "br-ord"].forEach((id) => $(id).addEventListener("change", () => { lim = 50; render(); }));
  $("br-assuntos").addEventListener("click", (e) => { const b = e.target.closest("[data-as]"); if (!b) return; assunto = b.dataset.as; lim = 50;
    $("br-assuntos").querySelectorAll("[data-as]").forEach((c) => c.setAttribute("aria-pressed", String(c === b))); render(); });
  $("br-mais").addEventListener("click", () => { lim += 100; render(); });
  $("br-copiar").addEventListener("click", async () => { if (!BR) return; const t = whats();
    try { await navigator.clipboard.writeText(t); conta("Copiado. Cole no WhatsApp."); } catch (e) { conta("Não deu para copiar automaticamente neste navegador."); } });
  $("br-csv").addEventListener("click", () => { if (!BR) return;
    const q = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const linhas = [["orgao", "municipio", "uf", "modalidade", "valor", "sigiloso", "fim_propostas", "objeto", "portal", "assunto", "link_pncp"].join(";")]
      .concat(filtrados().map((r) => [r[1], r[2], r[3], r[4], r[5], r[6] ? "sim" : "", r[7], r[8], r[9], r[10], link(r[0])].map(q).join(";")));
    baixarArquivo("licitacoes-abertas-brasil.csv", "﻿" + linhas.join("\n")); });
  const io = "IntersectionObserver" in window ? new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { io.disconnect(); carregar(); } }, { rootMargin: "400px" }) : null;
  if (io) io.observe($("br-sec")); else carregar();
  document.querySelector('a[href="#br-sec"]')?.addEventListener("click", carregar);
})();
'''
rep('''  renderBuscas(); renderPesquisa();
})();''', '''  renderBuscas(); renderPesquisa();
})();''' + JS)
open(p, "w").write(t)
print("ok")
