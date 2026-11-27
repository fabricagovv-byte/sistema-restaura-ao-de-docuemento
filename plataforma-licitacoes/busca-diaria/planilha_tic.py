"""Mega planilha de TIC e sistemas prontos de ALTO VALOR: licitações abertas, calendário, itens com preços, portais.
Fontes: lista completa (todas.json) + volumes/notas das buscas dos temas (UST, serviços, mensal); detalhe e itens direto da API do PNCP.
Uso: python3 planilha_tic.py todas.json saida.xlsx tema_dir1 tema_dir2 ..."""
import calendar
import concurrent.futures as cf
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

todas, saida, temas = sys.argv[1], sys.argv[2], sys.argv[3:]
VMIN = 1_000_000
agora = datetime.now(timezone.utc) - timedelta(hours=3)
AG = agora.strftime("%Y-%m-%dT%H:%M")
norm = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()  # noqa: E731

CATS = [
    ("UST / Ponto de Função", r"\bust\b|\busts\b|unidades? de servicos? tecnicos?|pontos? de funcao|fabrica de software"),
    ("Desenvolvimento e sustentação", r"desenvolvimento (e (manutencao|sustentacao) )?(de |do |dos )?(novos? )?(software|sistemas?|aplicativos?|aplicacoes|solucoes? (tecnologica|digita)|portal|plataforma)|sustentacao de (sistemas|software|aplicacoes)|manutencao (evolutiva|corretiva|adaptativa)[^.;]{0,40}(software|sistemas? de informac|aplicac)|devops"),
    ("Sistema pronto (licença/locação/SaaS)", r"(locacao|licenciamento|licencas?|cessao (de direito )?de uso|direito de uso|subscric|assinatura|software como servico|\bsaas\b|\bpaas\b|\biaas\b|hospedagem|computacao em nuvem|servicos? de nuvem|nuvem publica|provimento)[^.;]{0,90}(software|sistemas?|solucao|plataforma|aplicativo|tecnologia|nuvem|informatica|\berp\b)|sistemas? (integrados? )?de gestao (publica|municipal|integrada|em saude|hospitalar|escolar|tributaria)|\berp\b|sistemas? informatizados? (de|para) gestao|solucao (tecnologica )?integrada de gestao"),
    ("Serviços de TIC (suporte, infra, dados, segurança)", r"service desk|help ?desk|central de servicos|suporte tecnico (de|em|a) (ti|informatica|usuarios|sistemas)|outsourcing de (ti|infraestrutura)|data ?center|seguranca da informacao|ciberseguranca|\bsoc\b|\bnoc\b|business intelligence|ciencia de dados|inteligencia artificial|banco de dados|infraestrutura de (ti|tecnologia)|servicos? (gerenciados|continuados|tecnicos especializados) (de|em) (ti|tecnologia)|tecnologia da informacao e comunicacao|\btic\b|servicos de tecnologia da informacao|rede (logica|corporativa)|link de (dados|internet)|conectividade|transformacao digital"),
]
CRX = [(n, re.compile(x)) for n, x in CATS]
FORA = re.compile(r"alarme|cftv|cameras?|camaras? de|gravador|motobomba|bombas?\b|automacao predial|climatiza|ar condicionado|elevador|gerador|incendio|estruturas? para|tendas?|palco|sonoriza|eventos|banheiro|impressao|reprografia|veicul|combustivel|merenda|aliment|obra|pavimenta|reforma|medicament|ambulancia|uniforme|radiolog|raio[ -]?x|mamogra|telefonia movel|aparelhos? celulares|aquisicao de (computador|notebook|microcomputador|equipamentos|tablets|impressora|monitores|switch)|fornecimento de (computador|notebook|equipamentos)|material de informatica|toner|cartucho|mobiliario|notebooks?|microcomputador|switch|transceiver|aquisicao de .{0,25}servidores|servidores? (de rede|rack|blade)|de servidores|headsets?|webcams?|energia eletrica|locacao de equipamentos|material de expediente|insumos|ativos de rede|seguranca eletronica|engenharia|wireless|pontos de acesso|equipamentos, acessorios")


def categoria(o):
    if FORA.search(o):
        return None
    for n, rx in CRX:
        if rx.search(o):
            return n
    return None


VOLT, NOTA = {}, {}
for td in temas:
    try:
        for e in json.load(open(f"{td}/ultima.json"))["licitacoes"]:
            c = e["numero_controle_pncp"]
            NOTA[c] = max(NOTA.get(c, 0), e.get("nota") or 0)
            VOLT.setdefault(c, {}).update({k: q for k, q in (e.get("vol") or {}).items() if q})
    except (OSError, ValueError, KeyError):
        pass

# ---------------------------------------------------------------- 1. quem entra
cands = {}
for r in json.load(open(todas))["registros"]:
    c, org, mun, uf, mod, v, sig, fim, obj = r[:9]
    ini = r[12] or ""
    if not fim or fim <= AG or fim[:4] > str(agora.year + 2) or (ini and ini < (agora - timedelta(days=150)).strftime("%Y-%m-%d")):
        continue
    cat = categoria(norm(obj))
    vt = VOLT.get(c, {})
    if not cat and any(vt.get(k) for k in ("ust", "ust_doc", "pf", "pf_doc")) and not FORA.search(norm(obj)):
        cat = "UST / Ponto de Função"
    if not cat or r[10] not in ("Tecnologia (TI)", "Gestão documental", "Educação e cultura", "Saúde", "Outros"):
        continue
    alto = (v or 0) >= VMIN and v < 2e9
    if alto or (not v and any(vt.get(k) for k in ("ust", "ust_doc", "pf", "pf_doc"))):
        cands[c] = {"lista": r, "cat": cat}
print(len(cands), "candidatas", file=sys.stderr)


def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "licitacoes-planilha"}), timeout=40) as f:
                return json.loads(f.read() or b"null")
        except Exception:  # noqa: BLE001
            continue
    return None


def partes(c):
    m = re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})", c)
    return m.group(1), m.group(3), m.group(2)


def detalhar(c):
    cnpj, ano, seq = partes(c)
    d = get(f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}") or {}
    itens = []
    for p in range(1, 6):
        x = get(f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens?pagina={p}&tamanhoPagina=500") or []
        itens += x
        if len(x) < 500:
            break
    return c, d, itens


import os
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
CACHE = saida + ".cache.json"
det = {}
if os.path.exists(CACHE):
    det = {c: tuple(v) for c, v in json.load(open(CACHE)).items()}
falta = [c for c in cands if c not in det]
with cf.ThreadPoolExecutor(8) as ex:
    det.update({c: (d, it) for c, d, it in ex.map(detalhar, falta)})
json.dump(det, open(CACHE, "w"), ensure_ascii=False)


def limpo(o):
    if isinstance(o, str):
        return ILLEGAL_CHARACTERS_RE.sub(" ", o)
    if isinstance(o, list):
        return [limpo(i) for i in o]
    if isinstance(o, tuple):
        return tuple(limpo(i) for i in o)
    if isinstance(o, dict):
        return {k: limpo(v) for k, v in o.items()}
    return o


det = limpo(det)

# ---------------------------------------------------------------- 2. linhas
UNID = {"ust": "UST", "ust_doc": "UST", "pf": "PF", "pf_doc": "PF", "pagina": "páginas", "caixa": "caixas", "metro_linear": "metros lineares", "registro": "registros", "hora": "horas"}
L = []
for c, x in cands.items():
    d, itens = det[c]
    t, r = x.get("tema") or {}, x.get("lista")
    sit = d.get("situacaoCompraNome") or t.get("situacao") or ""
    fim = (d.get("dataEncerramentoProposta") or t.get("encerramento") or (r[7] if r else "") or "")[:16]
    if not fim or fim <= AG or (sit and not sit.startswith("Divulgada")):
        continue
    obj = " ".join((d.get("objetoCompra") or t.get("objeto") or (r[8] if r else "")).split())
    if FORA.search(norm(obj)):
        continue
    uo = d.get("unidadeOrgao") or {}
    org = (d.get("orgaoEntidade") or {}).get("razaoSocial") or t.get("orgao_nome") or (r[1] if r else "")
    v = d.get("valorTotalEstimado")
    v = v if v is not None else (t.get("valor") if t else (r[5] if r else None))
    vs, vl = set(), []
    for k, q in VOLT.get(c, {}).items():
        if q and q >= 10 and k in UNID and UNID[k] not in vs:
            vs.add(UNID[k])
            vl.append(f"{q:,.0f}".replace(",", ".") + " " + UNID[k] + (" (edital)" if k.endswith("_doc") else ""))
    vol = " · ".join(vl)
    cnpj, ano, seq = partes(c)
    L.append({
        "c": c, "org": org, "unid": uo.get("nomeUnidade") or t.get("unidade_nome") or "", "mun": uo.get("municipioNome") or t.get("municipio_nome") or (r[2] if r else ""),
        "uf": uo.get("ufSigla") or t.get("uf") or (r[3] if r else ""), "mod": d.get("modalidadeNome") or t.get("modalidade") or (r[4] if r else ""),
        "disp": d.get("modoDisputaNome") or "", "num": d.get("numeroCompra") or t.get("numero") or "", "proc": d.get("processo") or t.get("processo") or "",
        "srp": "Sim" if (d.get("srp") if d else t.get("srp")) else "Não", "ini": (d.get("dataAberturaProposta") or t.get("abertura") or (r[12] if r else "") or "")[:16],
        "fim": fim, "obj": obj, "v": v or 0, "sig": not v and any(i.get("orcamentoSigiloso") for i in itens),
        "portal": d.get("usuarioNome") or (r[9] if r else "") or "", "lo": d.get("linkSistemaOrigem") or t.get("link_origem") or "",
        "lp": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}", "vol": vol, "nota": NOTA.get(c, ""), "itens": itens, "cat": x["cat"],
        "esf": {"M": "Municipal", "E": "Estadual", "F": "Federal", "D": "Distrital"}.get((d.get("orgaoEntidade") or {}).get("esferaId") or "", ""),
    })
vistos, U = set(), []
for x in sorted(L, key=lambda x: x["fim"]):
    k = (x["org"], round(x["v"])) if x["v"] else (x["org"], norm(x["obj"])[:50])
    if k not in vistos:
        vistos.add(k)
        U.append(x)
L = U
print(len(L), "abertas", file=sys.stderr)


def dias(x):
    return (datetime.fromisoformat(x["fim"]) - agora.replace(tzinfo=None)).total_seconds() / 86400


def status(x):
    if x["ini"] and x["ini"] > AG:
        return "A VIR", "avir"
    d = dias(x)
    return ("URGENTE", "urg") if d <= 2 else ("ESTA SEMANA", "sem") if d <= 7 else ("NO PRAZO", "ok")


# ---------------------------------------------------------------- 3. estilo
COR = {"urg": ("FDE2E1", "B42318"), "sem": ("FEF0C7", "B54708"), "ok": ("DCFAE6", "067647"), "avir": ("DBEAFE", "1D4ED8")}
TINTA, AZUL, CINZA, BRANCO = "0F2A3D", "1E5A7A", "F2F5F7", "FFFFFF"
fill = lambda h: PatternFill("solid", start_color=h, end_color=h)  # noqa: E731
fino = Side(style="thin", color="D5DDE3")
borda = Border(left=fino, right=fino, top=fino, bottom=fino)
H = Font(name="Calibri", bold=True, color=BRANCO, size=11)
wb = Workbook()


def cabecalho(ws, cols, linha):
    for i, (nome, larg) in enumerate(cols, 1):
        cel = ws.cell(row=linha, column=i, value=nome)
        cel.font, cel.fill, cel.border = H, fill(AZUL), borda
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = larg
    ws.row_dimensions[linha].height = 32


def titulo(ws, txt, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    a, b = ws.cell(row=1, column=1, value=txt), ws.cell(row=2, column=1, value=sub)
    a.font, a.fill = Font(name="Calibri", bold=True, size=16, color=BRANCO), fill(TINTA)
    b.font, b.fill = Font(name="Calibri", italic=True, size=10, color="44546A"), fill(CINZA)
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 30, 20
    for cel in (a, b):
        cel.alignment = Alignment(vertical="center", indent=1)


BRL = '"R$" #,##0.00'
DTH = "dd/mm/yyyy hh:mm"
fonte = f"Fonte: PNCP (inclui portais parceiros que publicam lá) · gerado em {agora:%d/%m/%Y %H:%M} · só licitações com proposta aberta · valores estimados pelo órgão"
soma = sum(x["v"] for x in L if x["v"] < 2e9)

# ---------------------------------------------------------------- aba Licitações
ws = wb.active
ws.title = "Licitações"
cols = [("Status", 13), ("Categoria", 22), ("Encerra propostas", 17), ("Dias", 7), ("Abertura propostas", 17), ("Órgão", 34), ("Unidade", 24), ("Cidade", 18), ("UF", 5),
        ("Esfera", 10), ("Modalidade", 18), ("Disputa", 12), ("Nº", 9), ("Processo", 18), ("SRP", 6), ("Objeto", 70), ("Valor estimado", 17),
        ("Nº itens", 8), ("Volume lido no edital", 24), ("Nota", 6), ("Portal da disputa", 26), ("Link do portal", 22), ("Link PNCP", 22), ("Nº controle PNCP", 28)]
titulo(ws, "💻 TIC e sistemas prontos · alto valor (a partir de R$ 1 mi) · licitações abertas", fonte, len(cols))
cabecalho(ws, cols, 4)
for i, x in enumerate(L, 5):
    st, k = status(x)
    vals = [st, x["cat"], datetime.fromisoformat(x["fim"]), round(dias(x), 1), datetime.fromisoformat(x["ini"]) if x["ini"] else None, x["org"], x["unid"], x["mun"], x["uf"],
            x["esf"], x["mod"], x["disp"], x["num"], x["proc"], x["srp"], x["obj"], (x["v"] if x["v"] else ("sigiloso" if x["sig"] else "não informado")),
            len(x["itens"]), x["vol"], x["nota"], x["portal"], x["lo"] or "—", x["lp"], x["c"]]
    for j, v in enumerate(vals, 1):
        cel = ws.cell(row=i, column=j, value=v)
        cel.border = borda
        cel.alignment = Alignment(vertical="top", wrap_text=j in (2, 6, 7, 16, 19, 21))
    ws.cell(row=i, column=1).fill, ws.cell(row=i, column=1).font = fill(COR[k][0]), Font(bold=True, color=COR[k][1])
    ws.cell(row=i, column=3).number_format = DTH
    ws.cell(row=i, column=5).number_format = DTH
    ws.cell(row=i, column=17).number_format = BRL
    ws.cell(row=i, column=17).font = Font(bold=True)
    ws.cell(row=i, column=2).font = Font(bold=True, color=AZUL)
    for j, u in ((22, x["lo"]), (23, x["lp"])):
        if u:
            ws.cell(row=i, column=j).hyperlink = u
            ws.cell(row=i, column=j).value = "abrir portal ↗" if j == 22 else "abrir no PNCP ↗"
            ws.cell(row=i, column=j).font = Font(color="1D4ED8", underline="single")
    if i % 2:
        for j in range(2, len(cols) + 1):
            if j not in (22, 23):
                ws.cell(row=i, column=j).fill = fill("F8FAFB")
    ws.row_dimensions[i].height = 48
n = len(L) + 4
ws.cell(row=n + 1, column=16, value="TOTAL (soma dos valores divulgados)").font = Font(bold=True)
t = ws.cell(row=n + 1, column=17, value=f"=SUM(Q5:Q{n})")
t.number_format, t.font = BRL, Font(bold=True, color=BRANCO)
t.fill = fill(TINTA)
ws.freeze_panes = "G5"
ws.auto_filter.ref = f"A4:{get_column_letter(len(cols))}{n}"

# ---------------------------------------------------------------- aba Itens e preços
wi = wb.create_sheet("Itens e preços")
ci = [("Encerra", 12), ("Órgão", 30), ("UF", 5), ("Item", 6), ("Descrição do item", 60), ("Tipo", 9), ("Quantidade", 13), ("Unidade", 12),
      ("Valor unitário", 15), ("Valor total do item", 17), ("Critério", 14), ("Situação do item", 14), ("Link PNCP", 18)]
titulo(wi, "💰 Itens e preços de cada licitação", "Itens publicados pelo órgão no PNCP (quantidade, unidade, valor unitário e total estimados). Sigiloso = o órgão não divulgou o preço.", len(ci))
cabecalho(wi, ci, 4)
row, banda = 5, False
for x in L:
    banda = not banda
    for it in sorted(x["itens"], key=lambda i: i.get("numeroItem") or 0):
        sig = it.get("orcamentoSigiloso")
        vals = [datetime.fromisoformat(x["fim"]), x["org"], x["uf"], it.get("numeroItem"), " ".join((it.get("descricao") or "").split()),
                it.get("materialOuServicoNome") or "", it.get("quantidade"), it.get("unidadeMedida") or "",
                "sigiloso" if sig else it.get("valorUnitarioEstimado"), "sigiloso" if sig else it.get("valorTotal"),
                it.get("criterioJulgamentoNome") or "", it.get("situacaoCompraItemNome") or "", "abrir ↗"]
        for j, v in enumerate(vals, 1):
            cel = wi.cell(row=row, column=j, value=v)
            cel.border = borda
            cel.alignment = Alignment(vertical="top", wrap_text=j in (2, 5))
            if banda:
                cel.fill = fill("EEF4F8")
        wi.cell(row=row, column=1).number_format = "dd/mm/yyyy"
        wi.cell(row=row, column=7).number_format = "#,##0.##"
        for j in (9, 10):
            wi.cell(row=row, column=j).number_format = BRL
        wi.cell(row=row, column=10).font = Font(bold=True)
        wi.cell(row=row, column=13).hyperlink = x["lp"]
        wi.cell(row=row, column=13).font = Font(color="1D4ED8", underline="single")
        row += 1
wi.freeze_panes = "E5"
wi.auto_filter.ref = f"A4:{get_column_letter(len(ci))}{row - 1}"

# ---------------------------------------------------------------- aba Calendário
wc = wb.create_sheet("Calendário", 0)
por_dia = defaultdict(list)
for x in L:
    por_dia[x["fim"][:10]].append(x)
meses = sorted({x["fim"][:7] for x in L})[:4]
titulo(wc, "🗓️ Calendário de encerramento das propostas", "Cada dia mostra as licitações que fecham nele: hora · órgão/UF · valor. Cor do dia = a mais urgente dele.", 7)
NOMES = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
MES = ["", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
for j in range(1, 8):
    wc.column_dimensions[get_column_letter(j)].width = 30
r0 = 4
ordem = ["urg", "sem", "ok", "avir"]
for m in meses:
    a, mm = int(m[:4]), int(m[5:7])
    wc.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=7)
    c = wc.cell(row=r0, column=1, value=f"{MES[mm]} {a}")
    c.font, c.fill, c.alignment = Font(bold=True, size=14, color=BRANCO), fill(AZUL), Alignment(horizontal="center", vertical="center")
    wc.row_dimensions[r0].height = 26
    for j, n_ in enumerate(NOMES, 1):
        h = wc.cell(row=r0 + 1, column=j, value=n_)
        h.font, h.fill, h.alignment, h.border = Font(bold=True, color=TINTA), fill("D9E4EC"), Alignment(horizontal="center"), borda
    for s, semana in enumerate(calendar.Calendar(0).monthdayscalendar(a, mm)):
        rr = r0 + 2 + s
        maior = 1
        for j, dia in enumerate(semana, 1):
            cel = wc.cell(row=rr, column=j)
            cel.border = borda
            cel.alignment = Alignment(vertical="top", wrap_text=True)
            if not dia:
                cel.fill = fill("F4F6F8")
                continue
            chave = f"{a:04d}-{mm:02d}-{dia:02d}"
            xs = sorted(por_dia.get(chave, []), key=lambda x: x["fim"])
            linhas = [f"{dia:02d}" + ("  · HOJE" if chave == AG[:10] else "")]
            for x in xs:
                v = f"R$ {x['v']/1e6:.1f} mi".replace(".", ",") if x["v"] >= 1e6 else f"R$ {x['v']/1e3:.0f} mil" if x["v"] else "sigiloso"
                linhas.append(f"{x['fim'][11:16]} · {x['org'][:26].title()}/{x['uf']} · {v}")
            cel.value = "\n".join(linhas)
            if xs:
                k = min((status(x)[1] for x in xs), key=ordem.index)
                cel.fill, cel.font = fill(COR[k][0]), Font(color=COR[k][1], bold=False, size=9)
                cel.hyperlink = xs[0]["lp"] if len(xs) == 1 else None
            elif chave < AG[:10]:
                cel.fill, cel.font = fill("F4F6F8"), Font(color="98A2B3", size=9)
            else:
                cel.font = Font(color="44546A", size=9)
            maior = max(maior, len(linhas))
        wc.row_dimensions[rr].height = max(42, 13 * maior + 6)
    r0 += 2 + len(calendar.Calendar(0).monthdayscalendar(a, mm)) + 1
# agenda em lista logo abaixo
wc.cell(row=r0, column=1, value="AGENDA EM LISTA").font = Font(bold=True, size=12, color=TINTA)
r0 += 1
SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
for j, n_ in enumerate(["Data", "Hora", "Órgão", "Cidade/UF", "Valor", "Status", "Link PNCP"], 1):
    h = wc.cell(row=r0, column=j, value=n_)
    h.font, h.fill, h.border = H, fill(AZUL), borda
for x in L:
    r0 += 1
    st, k = status(x)
    dfim = datetime.fromisoformat(x["fim"])
    vals = [f"{SEMANA[dfim.weekday()]} {dfim:%d/%m/%Y}", x["fim"][11:16], x["org"], f"{x['mun']}/{x['uf']}", x["v"] or ("sigiloso" if x["sig"] else "não informado"), st, "abrir ↗"]
    for j, v in enumerate(vals, 1):
        cel = wc.cell(row=r0, column=j, value=v)
        cel.border = borda
        cel.alignment = Alignment(wrap_text=j == 3, vertical="top")
    wc.cell(row=r0, column=5).number_format = BRL
    wc.cell(row=r0, column=6).fill, wc.cell(row=r0, column=6).font = fill(COR[k][0]), Font(bold=True, color=COR[k][1])
    wc.cell(row=r0, column=7).hyperlink, wc.cell(row=r0, column=7).font = x["lp"], Font(color="1D4ED8", underline="single")

# ---------------------------------------------------------------- aba Portais
wp = wb.create_sheet("Portais")
titulo(wp, "🌐 Onde é a disputa (portal)", "Portal = sistema onde o órgão publica e recebe as propostas. É preciso estar cadastrado nele para disputar.", 4)
cabecalho(wp, [("Portal da disputa", 46), ("Licitações", 12), ("Soma estimada", 20), ("Exemplo de link", 60)], 4)
grp = defaultdict(list)
for x in L:
    grp[x["portal"] or "não informado"].append(x)
for i, (p, xs) in enumerate(sorted(grp.items(), key=lambda kv: -len(kv[1])), 5):
    ex = next((x["lo"] for x in xs if x["lo"]), xs[0]["lp"])
    vals = [p, len(xs), sum(x["v"] for x in xs if x["v"] < 2e9), ex]
    for j, v in enumerate(vals, 1):
        cel = wp.cell(row=i, column=j, value=v)
        cel.border = borda
    wp.cell(row=i, column=3).number_format = BRL
    wp.cell(row=i, column=4).hyperlink, wp.cell(row=i, column=4).font = ex, Font(color="1D4ED8", underline="single")

# ---------------------------------------------------------------- aba Resumo (primeira)
wr = wb.create_sheet("Resumo", 0)
titulo(wr, "📊 TIC e sistemas prontos de alto valor · painel", fonte + " · alto valor = R$ 1 mi ou mais (ou sigiloso com UST/PF no edital)", 6)
for j, w in enumerate([44, 24, 4, 30, 14, 20], 1):
    wr.column_dimensions[get_column_letter(j)].width = w
cont = Counter(status(x)[1] for x in L)
kpis = [("Licitações abertas", len(L), None), ("Soma estimada (divulgada)", soma, BRL), ("Itens publicados", sum(len(x["itens"]) for x in L), None),
        ("Urgentes (até 2 dias)", cont["urg"], None), ("Fecham em até 7 dias", cont["sem"], None), ("Com prazo maior", cont["ok"], None), ("A vir (ainda não abriu)", cont["avir"], None),
        ("Com valor sigiloso", sum(1 for x in L if x["sig"]), None)]
for i, (nome, v, fmt) in enumerate(kpis, 4):
    a, b = wr.cell(row=i, column=1, value=nome), wr.cell(row=i, column=2, value=v)
    a.font, b.font = Font(bold=True, color=TINTA), Font(bold=True, size=13, color=AZUL)
    a.border = b.border = borda
    if fmt:
        b.number_format = fmt
k_cor = {7: "urg", 8: "sem", 9: "ok", 10: "avir"}
rc = 4 + len(kpis) + 1
for j, n_ in enumerate(["Categoria", "Qtd · soma"], 1):
    h = wr.cell(row=rc, column=j, value=n_)
    h.font, h.fill, h.border = H, fill(AZUL), borda
for i, (cat, n_) in enumerate(Counter(x["cat"] for x in L).most_common(), rc + 1):
    s_ = sum(x["v"] for x in L if x["cat"] == cat and x["v"] < 2e9)
    a, b = wr.cell(row=i, column=1, value=cat), wr.cell(row=i, column=2, value=f"{n_} · R$ {s_/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", "."))
    a.border = b.border = borda
    a.font = Font(bold=True, color=AZUL)
for rr, k in k_cor.items():
    wr.cell(row=rr, column=1).fill = fill(COR[k][0])
cabecalho_r = [("Por estado (UF)", 30), ("Licitações", 14), ("Soma estimada", 18)]
for j, (n_, _) in enumerate(cabecalho_r, 4):
    h = wr.cell(row=3, column=j, value=n_)
    h.font, h.fill, h.border = H, fill(AZUL), borda
for i, (uf, n_) in enumerate(Counter(x["uf"] for x in L).most_common(), 4):
    vals = [uf, n_, sum(x["v"] for x in L if x["uf"] == uf and x["v"] < 2e9)]
    for j, v in enumerate(vals, 4):
        c = wr.cell(row=i, column=j, value=v)
        c.border = borda
    wr.cell(row=i, column=6).number_format = BRL
# top 10 por valor
r0 = max(4 + len(kpis) + 2 + len(CATS) + 2, 4 + len(Counter(x["uf"] for x in L)) + 2)
wr.cell(row=r0, column=1, value="🏆 15 MAIORES POR VALOR").font = Font(bold=True, size=12, color=TINTA)
for j, n_ in enumerate(["Órgão", "Valor", "", "Objeto", "Encerra", "Link"], 1):
    if n_:
        h = wr.cell(row=r0 + 1, column=j, value=n_)
        h.font, h.fill, h.border = H, fill(AZUL), borda
for i, x in enumerate(sorted([x for x in L if x["v"] < 2e9], key=lambda x: -x["v"])[:15], r0 + 2):
    vals = {1: f"{x['org']} ({x['uf']})", 2: x["v"] or ("sigiloso" if x["sig"] else "—"), 4: x["obj"][:140], 5: datetime.fromisoformat(x["fim"]), 6: "abrir ↗"}
    for j, v in vals.items():
        c = wr.cell(row=i, column=j, value=v)
        c.border = borda
        c.alignment = Alignment(wrap_text=j in (1, 4), vertical="top")
    wr.cell(row=i, column=2).number_format, wr.cell(row=i, column=5).number_format = BRL, "dd/mm hh:mm"
    st, k = status(x)
    wr.cell(row=i, column=5).fill = fill(COR[k][0])
    wr.cell(row=i, column=6).hyperlink, wr.cell(row=i, column=6).font = x["lp"], Font(color="1D4ED8", underline="single")
    wr.row_dimensions[i].height = 44
# legenda
r0 = r0 + 18
wr.cell(row=r0, column=1, value="LEGENDA DE CORES").font = Font(bold=True, color=TINTA)
for i, (k, txt) in enumerate([("urg", "URGENTE · encerra em até 2 dias"), ("sem", "ESTA SEMANA · 3 a 7 dias"), ("ok", "NO PRAZO · mais de 7 dias"), ("avir", "A VIR · propostas ainda não abriram")], r0 + 1):
    c = wr.cell(row=i, column=1, value=txt)
    c.fill, c.font, c.border = fill(COR[k][0]), Font(bold=True, color=COR[k][1]), borda
wr.cell(row=r0 + 6, column=1, value="Abas: Calendário · Licitações (tabela completa com filtros) · Itens e preços · Portais").font = Font(italic=True, color="44546A")
wb.active = 0
wb.save(saida)
print(f"ok: {len(L)} licitações, {sum(len(x['itens']) for x in L)} itens, soma R$ {soma:,.0f}", file=sys.stderr)
