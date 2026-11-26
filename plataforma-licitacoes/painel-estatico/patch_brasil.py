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
    <div class="br-temas-box"><p class="br-temas-tit"><b>Busca do dia por tema</b> <span id="br-temas-info">— as melhores de cada tema, com nota e volume (UST, PF, páginas) lidos no edital</span></p>
      <div class="chips br-temas" id="br-temas" role="group" aria-label="Busca do dia por tema"></div></div>
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
      <label for="br-rec">Mais recentes<select id="br-rec"><option value="90">Abriu nos últimos 90 dias</option><option value="30">Abriu nos últimos 30 dias</option><option value="7">Abriu nos últimos 7 dias</option><option value="2">Novas (últimos 2 dias)</option><option value="0">Qualquer data (inclui antigas)</option></select></label>
      <label for="br-dias">Encerra em<select id="br-dias"><option value="0">Qualquer prazo</option><option value="3">até 3 dias</option><option value="7">até 7 dias</option><option value="15">até 15 dias</option><option value="30">até 30 dias</option></select></label>
      <label for="br-ord">Ordenar<select id="br-ord"><option value="novas">Mais novas primeiro</option><option value="prazo">Encerra primeiro</option><option value="nota">Melhores do tema (nota)</option><option value="valor">Maior valor</option><option value="recente">Prazo mais distante</option><option value="perto">Mais perto da cidade</option></select></label>
    </div>
    <div class="acoes"><button type="button" class="mais" id="br-pregoes" aria-pressed="false">Só pregões</button><button type="button" class="abrir" id="br-copiar">Copiar os 40 primeiros para o WhatsApp</button>
      <button type="button" class="mais" id="br-csv">Baixar planilha com todas as filtradas (CSV)</button></div>
    <p class="conta" id="br-conta" aria-live="polite">Carregando a lista do Brasil…</p>
    <div class="br-corpo">
      <div class="br-coluna"><ol class="br-lista" id="br-lista"></ol>
        <button type="button" class="mais" id="br-mais" hidden>Mostrar mais</button></div>
      <aside class="br-previa" id="br-previa" aria-live="polite" aria-label="Prévia da licitação"><p class="br-previa-vazia">Passe o mouse (ou toque) numa licitação para ver a prévia aqui.</p></aside>
    </div>
  </section>
  <section class="panel" id="cal-sec" aria-labelledby="h-cal">''')

JS = r'''
(function brasil() {
  let antigas = 0;
  let BR = null, lim = 50, assunto = "", soPregao = false, tema = "", TEM = null;
  const temaDe = (c) => { if (!BR || !BR.temas) return null; if (tema) return BR.temas[tema]?.itens[c] || null; for (const k in BR.temas) { const x = BR.temas[k].itens[c]; if (x) return x; } return null; };
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
      if (BR.extras && BR.extras.length) BR.registros = BR.registros.concat(BR.extras);
      // datas digitadas erradas pelo órgão (ex.: ano 9202, abertura depois do fim): abertura vira desconhecida; fim absurdo marca a licitação como suspeita
      const anoMax = String(new Date().getFullYear() + 2);
      BR.registros.forEach((r) => { if (r[12] && (r[12] > r[7] || r[12].slice(0, 4) > anoMax || r[12].slice(0, 4) < "2015")) r[12] = ""; r.dataRuim = r[7].slice(0, 4) > anoMax; });
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
    const hj = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
    const TM = BR.temas || {}, ag = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16), noPrazo = (k) => { const fim = new Map(R.map((r) => [r[0], r[7]])); return Object.keys(TM[k].itens).filter((c) => (fim.get(c) || "") > ag).length; };
    $("br-temas").innerHTML = Object.keys(TM).length ? `<button type="button" aria-pressed="true" data-tema="">Todas</button>` + Object.entries(TM).map(([k, x]) => `<button type="button" aria-pressed="false" data-tema="${esc(k)}" title="Busca verificada em ${esc(data(x.verificado))}">${esc(x.nome)} <b>${fmt(noPrazo(k))}</b> <small class="${x.verificado.slice(0, 10) < hj ? "velha" : ""}">${x.verificado.slice(0, 10) < hj ? "de " + esc(data(x.verificado).slice(0, 5)) : "hoje " + esc(x.verificado.slice(11, 16))}</small></button>`).join("") : '<span class="br-temas-tit">Busca do dia ainda não disponível nesta cópia.</span>';
    const as = cont(10);
    $("br-assuntos").innerHTML = `<button type="button" aria-pressed="true" data-as="">Todos (${fmt(R.length)})</button>` + as.map(([k, n]) => `<button type="button" aria-pressed="false" data-as="${esc(k)}">${esc(k)} (${fmt(n)})</button>`).join("");
    const nAvir = R.filter((r) => r[12] > new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16)).length;
    $("br-sit").options[2].textContent = `A vir — propostas ainda não começaram (${fmt(nAvir)})`;
    $("br-sit").options[3].textContent = `Previstas no plano de compras, sem edital — TI (${fmt((BR.previstas || []).filter((x) => !x.data || `${x.data.slice(6, 10)}-${x.data.slice(3, 5)}-${x.data.slice(0, 2)}` >= hj).length)})`;
    $("br-lede").textContent = `${fmt(R.length)} licitações com prazo aberto no Brasil (${fmt(nAvir)} ainda vão abrir as propostas), de todos os assuntos (PNCP, verificado em ${BR.verificado_em.slice(8, 10)}/${BR.verificado_em.slice(5, 7)} às ${BR.verificado_em.slice(11, 16)}). Inclui o que os portais parceiros publicam no PNCP.`;
  }
  function filtrados() {
    const q = semAc($("br-q").value).split(/\s+/).filter(Boolean), uf = $("br-uf").value, mod = $("br-mod").value, portal = $("br-portal").value;
    const vmin = +$("br-vmin").value, dias = +$("br-dias").value, agora = Date.now(), sit = $("br-sit").value;
    const alvo = geoCidade($("br-perto").value), raio = +$("br-raio").value;
    const reg = $("br-regiao").value, ufsReg = reg ? new Set(REGIAO[reg].split(" ")) : null;
    const pals = [...marcadas].map((w) => { const s = semAc(w).trim(); return s.length <= 4 ? new RegExp("(^|[^a-z0-9])" + s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "([^a-z0-9]|$)") : s; });
    const agoraTxt = new Date(agora - 3 * 3600e3).toISOString().slice(0, 16);
    const rec = +$("br-rec").value, desde = rec ? new Date(agora - 3 * 3600e3 - rec * 864e5).toISOString().slice(0, 10) : "";
    const out = []; antigas = 0;
    BR.registros.forEach((r, i) => {
      if (r[7] <= agoraTxt) return;  // venceu depois da coleta: some sozinho
      if (desde && ((r[12] && r[12] < desde) || r.dataRuim)) { antigas++; return; }
      if (sit === "abertas" && r[12] > agoraTxt) return; if (sit === "avir" && !(r[12] > agoraTxt)) return;
      if (soPregao && !/preg/i.test(r[4])) return;
      if (uf && r[3] !== uf) return; if (mod && r[4] !== mod) return; if (portal && r[9] !== portal) return;
      if (tema && !TEM[r[0]]) return;
      if (assunto && r[10] !== assunto) return; if (vmin && !(vv(r) >= vmin)) return;
      if (dias && (new Date(r[7]).getTime() - agora) > dias * 864e5) return;
      if (q.length && !q.every((w) => BR.busca[i].includes(w))) return;
      if (ufsReg && !ufsReg.has(r[3])) return;
      if (pals.length && !pals.some((w) => typeof w === "string" ? BR.busca[i].includes(w) : w.test(BR.busca[i]))) return;
      if (alvo && raio) { const d = distR(r, alvo); if (d == null || d > raio) return; }
      out.push(r);
    });
    const o = $("br-ord").value;
    if (o === "nota") out.sort((a, b) => ((temaDe(b[0]) || [0])[0] - (temaDe(a[0]) || [0])[0]) || vv(b) - vv(a));
    else if (o === "perto" && alvo) out.sort((a, b) => (distR(a, alvo) ?? 1e9) - (distR(b, alvo) ?? 1e9));
    else if (o === "valor") out.sort((a, b) => vv(b) - vv(a)); else if (o === "recente") out.sort((a, b) => b[7].localeCompare(a[7])); else if (o === "prazo") out.sort((a, b) => a[7].localeCompare(b[7]));
    else { const k = (x) => x[12] && x[12] <= agoraTxt ? x[12] : ""; out.sort((a, b) => k(b).localeCompare(k(a)) || a[7].localeCompare(b[7])); }
    return out;
  }
  const agoraTxt = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16);
  let LISTA = [];
  const MES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];
  function prazo(r) {
    const hoje = agoraTxt().slice(0, 10), fimD = r[7].slice(0, 10), h = r[7].slice(11, 16);
    if (r[12] && r[12] > agoraTxt()) return ["avir", `🔜 Abre ${data(r[12]).slice(0, 5)} às ${r[12].slice(11, 16)}`];
    const dias = Math.round((new Date(fimD + "T12:00") - new Date(hoje + "T12:00")) / 864e5);
    if (dias <= 0) { const min = Math.round((new Date(r[7]) - (Date.now() - 3 * 3600e3 + new Date().getTimezoneOffset() * 6e4)) / 6e4);
      return ["hoje", min < 120 && min > 0 ? `⏳ Encerra HOJE às ${h} (faltam ${min} min)` : `⏳ Encerra HOJE às ${h}`]; }
    if (dias === 1) return ["perto", `⏳ Encerra AMANHÃ às ${h}`];
    if (dias <= 3) return ["perto", `Faltam ${dias} dias`];
    return ["", `Faltam ${dias} dias`];
  }
  function item(r, i) {
    const alvo = geoCidade($("br-perto").value), d = distR(r, alvo), [cl, pz] = prazo(r), tm = temaDe(r[0]);
    const avir = cl === "avir", ref = avir ? r[12] : r[7];
    return `<li class="br-ficha ${cl}" tabindex="0" data-i="${i}"><div class="br-data" aria-label="${avir ? "Abre" : "Encerra"} ${esc(data(ref))}"><small>${avir ? "ABRE" : "ENCERRA"}</small><b>${ref.slice(8, 10)}</b><span>${MES[+ref.slice(5, 7) - 1]}${ref.slice(0, 4) !== agoraTxt().slice(0, 4) ? " " + ref.slice(0, 4) : ""}</span><em>${ref.slice(11, 16)}</em></div>
      <div class="br-meio"><div class="br-cab"><span class="br-prazo ${cl}">${esc(pz)}</span><span class="br-tag assunto">${esc(r[10])}</span><span class="br-tag">${esc(r[4])}</span>${tm ? `<span class="br-nota" title="Nota da busca do dia (0 a 100)">★ ${tm[0]}</span>` : ""}</div>
      <h4>${esc(r[1])}</h4><p class="br-obj">${esc(r[8])}</p>${tm && tm[1] ? `<p class="br-vol">📦 ${esc(tm[1])}</p>` : ""}
      <div class="br-pe"><span>📍 ${esc(r[2])}/${esc(r[3])}${d != null ? ` · ${Math.round(d)} km` : ""}</span>${r[12] && !avir ? `<span>Aberta desde ${esc(data(r[12]).slice(0, 5))}</span>` : ""}<a href="${link(r[0])}" target="_blank" rel="noopener">Ver no PNCP ↗</a></div></div>
      <div class="br-dir"><span class="br-valor">${esc(val(r))}</span></div></li>`;
  }
  function previa(r) {
    const alvo = geoCidade($("br-perto").value), d = distR(r, alvo), ini = r[12] ? new Date(r[12]) : null, fim = new Date(r[7]);
    const tm = temaDe(r[0]), temasDela = BR.temas ? Object.values(BR.temas).filter((x) => x.itens[r[0]]).map((x) => x.nome) : [];
    const pct = ini ? Math.max(0, Math.min(100, (Date.now() - ini) / Math.max(1, fim - ini) * 100)) : 0, [, pz] = prazo(r);
    return `<div class="br-prev"><p class="eyebrow">${esc(r[10])} · ${esc(r[4])}</p><h3>${esc(r[1])}</h3>
      <div class="grande">${esc(val(r))}</div>
      <div class="br-linha-tempo"><span>Abre ${esc(ini ? data(r[12]) : "—")}</span><span class="barra"><i style="width:${pct.toFixed(0)}%"></i></span><span style="text-align:right">Fecha ${esc(data(r[7]))}</span></div>
      <p><strong>${esc(pz)}</strong>${tm ? ` · <span class="br-nota">★ nota ${tm[0]}</span>` : ""}</p>
      ${tm && tm[1] ? `<p class="br-vol grande-vol">📦 Volume: <strong>${esc(tm[1])}</strong></p>` : ""}
      ${temasDela.length ? `<p class="br-temas-dela">${temasDela.map((n) => `<span class="br-tag assunto">${esc(n)}</span>`).join(" ")}</p>` : ""}
      <p>${esc(r[8])}${r[8].length >= 168 ? "…" : ""}</p>
      <dl class="br-campos"><dt>Local</dt><dd>${esc(r[2])}/${esc(r[3])}${d != null ? ` · ${Math.round(d)} km de ${esc($("br-perto").value)}` : ""}</dd>
        <dt>Portal</dt><dd>${esc(r[9] || "não informado")}</dd><dt>Esfera</dt><dd>${esc({ M: "Municipal", E: "Estadual", F: "Federal", D: "Distrital" }[r[11]] || "—")}</dd>
        <dt>Nº PNCP</dt><dd>${esc(r[0])}</dd></dl>
      <div class="br-acoes"><a class="prim" href="${link(r[0])}" target="_blank" rel="noopener">Abrir edital no PNCP ↗</a>${tm && tm[2] ? `<a href="${esc(tm[2])}" target="_blank" rel="noopener">Portal da disputa ↗</a>` : ""}<button type="button" data-copiar="1">Copiar p/ WhatsApp</button></div></div>`;
  }
  let fixada = null;
  function mostrarPrevia(i, fixar) {
    const r = LISTA[+i]; if (!r) return;
    if (fixar) fixada = +i;
    $("br-previa").innerHTML = previa(r);
    $("br-lista").querySelectorAll(".br-ficha").forEach((li) => li.classList.toggle("ativa", +li.dataset.i === +i));
  }
  function renderPrevistas() {
    const hj = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10), iso = (d) => d ? `${d.slice(6, 10)}-${d.slice(3, 5)}-${d.slice(0, 2)}` : "9999";
    const P = (BR.previstas || []).filter((x) => iso(x.data) >= hj), q = semAc($("br-q").value), uf = $("br-uf").value;
    const r = P.filter((x) => (!uf || x.uf === uf) && (!q || semAc(`${x.orgao} ${x.unidade} ${x.nome}`).includes(q)));
    conta(`${fmt(r.length)} contratações previstas no plano anual (PCA) de órgãos que compram TI — ainda sem edital publicado. Data = quando o órgão quer contratar.`);
    $("br-previa").innerHTML = '<p class="br-previa-vazia">Previstas no plano de compras ainda não têm edital; use o link do plano oficial.</p>';
    $("br-lista").innerHTML = r.slice(0, lim).map((x) => `<li class="br-ficha"><div class="topo"><b>${esc(x.unidade || x.orgao)}</b><span>${esc(x.orgao)}</span></div>
      <p>${esc(x.nome)}</p><div class="linha"><span><strong>${esc(mi(x.valor) || "valor não informado")}</strong></span><span>Previsto para <strong>${esc(x.data)}</strong></span><span>PCA ${esc(x.ano)}</span></div>
      <div class="links">${x.publicado ? `<a href="${esc(x.publicado)}" target="_blank" rel="noopener">Publicação relacionada</a>` : ""}<a href="${esc(x.pca)}" target="_blank" rel="noopener">Plano oficial (PNCP)</a></div></li>`).join("");
    $("br-mais").hidden = r.length <= lim;
  }
  function render() {
    if (!BR) return;
    if ($("br-sit").value === "previstas") return renderPrevistas();
    const r = filtrados(), soma = r.reduce((s, x) => s + vv(x), 0);
    conta(`${fmt(r.length)} licitações · soma estimada ${mi(soma) || "R$ 0"}${r.length > lim ? ` · mostrando ${fmt(lim)}` : ""}${antigas ? ` · ${fmt(antigas)} antigas escondidas (abertas há mais tempo; mude em “Mais recentes”)` : ""}`);
    LISTA = r; fixada = null;
    $("br-lista").innerHTML = r.slice(0, lim).map((x, i) => item(x, i)).join("");
    if (r.length) mostrarPrevia(0); else $("br-previa").innerHTML = '<p class="br-previa-vazia">Nenhuma licitação com esses filtros.</p>';
    $("br-mais").hidden = r.length <= lim;
  }
  function whats() {
    const r = filtrados().slice(0, 40);
    return `*📋 Licitações abertas — Brasil · ${new Date().toLocaleDateString("pt-BR").slice(0, 5)}*\nPNCP (inclui portais parceiros). ${fmt(filtrados().length)} no filtro; os ${r.length} primeiros:\n\n` +
      r.map((x, i) => { const tm = temaDe(x[0]); return `*${i + 1}. ${x[1]}* (${x[3]}) · ${x[8].slice(0, 90)}\n💰 *${val(x)}* · 📅 ${data(x[7])}${tm && tm[1] ? `\n📦 ${tm[1]}` : ""}\n🔗 ${link(x[0])}`; }).join("\n\n");
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
  ["br-rec", "br-sit", "br-uf", "br-mod", "br-portal", "br-vmin", "br-dias", "br-ord"].forEach((id) => $(id).addEventListener("change", () => { lim = 50; render(); }));
  $("br-assuntos").addEventListener("click", (e) => { const b = e.target.closest("[data-as]"); if (!b) return; assunto = b.dataset.as; lim = 50;
    $("br-assuntos").querySelectorAll("[data-as]").forEach((c) => c.setAttribute("aria-pressed", String(c === b))); render(); });
  $("br-temas").addEventListener("click", (e) => { const b = e.target.closest("[data-tema]"); if (!b) return; tema = b.dataset.tema; TEM = tema ? BR.temas[tema].itens : null; lim = 50;
    $("br-temas").querySelectorAll("[data-tema]").forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
    $("br-ord").value = tema ? "nota" : "novas";
    $("br-temas-info").textContent = tema ? `— ${BR.temas[tema].nome}: busca verificada em ${data(BR.temas[tema].verificado)}, ordenada pela nota` : "— as melhores de cada tema, com nota e volume (UST, PF, páginas) lidos no edital";
    render(); });
  $("br-mais").addEventListener("click", () => { lim += 100; render(); });
  // prévia: passar o mouse/focar mostra ao lado; tocar (celular) abre dentro da ficha; clicar fixa
  $("br-lista").addEventListener("mouseover", (e) => { const li = e.target.closest(".br-ficha"); if (li && fixada == null) mostrarPrevia(li.dataset.i); });
  $("br-lista").addEventListener("focusin", (e) => { const li = e.target.closest(".br-ficha"); if (li) mostrarPrevia(li.dataset.i); });
  $("br-lista").addEventListener("click", (e) => {
    if (e.target.closest("a")) return; const li = e.target.closest(".br-ficha"); if (!li) return;
    if (e.target.closest("[data-copiar]")) return;
    if (!LISTA[+li.dataset.i] || li.dataset.i === undefined) return;
    mostrarPrevia(li.dataset.i, true);
    const dentro = li.querySelector(".br-prev");
    if (dentro) dentro.remove(); else li.insertAdjacentHTML("beforeend", previa(LISTA[+li.dataset.i]));
  });
  $("br-lista").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.classList.contains("br-ficha")) e.target.click(); });
  document.getElementById("br-sec").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-copiar]"); if (!b) return; e.stopPropagation();
    const li = b.closest(".br-ficha"), r = li ? LISTA[+li.dataset.i] : LISTA[fixada ?? 0]; if (!r) return;
    const t = `*${r[1]}* (${r[3]}) · ${r[8].slice(0, 120)}\n💰 *${val(r)}* · 📅 ${data(r[7])}\n🔗 ${link(r[0])}`;
    try { await navigator.clipboard.writeText(t); b.textContent = "Copiado ✓"; } catch (err) { b.textContent = "Não deu para copiar aqui"; }
  });
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
