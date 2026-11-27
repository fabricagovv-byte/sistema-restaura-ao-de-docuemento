"""Mega planilha de digitalização / gestão documental: licitações abertas, calendário, itens com preços, portais.
Fontes: busca do dia (tema documental) + lista completa de hoje (todas.json), detalhe e itens direto da API do PNCP.
Uso: python3 planilha_doc.py todas.json doc_dir saida.xlsx"""
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

todas, doc_dir, saida = sys.argv[1:4]
agora = datetime.now(timezone.utc) - timedelta(hours=3)
AG = agora.strftime("%Y-%m-%dT%H:%M")
norm = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()  # noqa: E731

DOC = re.compile(r"digitaliza|indexa|gestao documental|gestao arquivistica|\bged\b|\becm\b|microfilm|guarda (externa )?de (documentos|acervo|arquivos?)|tratamento (documental|arquivistico|de acervo)|organizacao de (acervo|arquivo|documentos)|escaneamento|higienizacao de documentos|custodia de documentos|arquivo (fisico|morto|permanente|intermediario)|acervo (documental|arquivistico)|gestao eletronica de (documentos|processos)|desmaterializa|transformacao digital[^.;]{0,60}document|gerenciamento eletronico de documentos")
FORA = re.compile(r"radiolog|raio[ -]?x|mamogra|imagens? (medica|radiolog)|tv digital|certificado digital|digitalizador de imagens? (medic|radio)|placa de video|\bcr\b.{0,20}(radiolog|imagem)|sistema de digitalizacao (de imagens|radiogr)|impressao|reprografia|reproducao de documentos|copias?\b|suprimentos|aquisicao|fornecimento de (desktop|scanners?|materiais|\d)|scanners? de mesa|prateleiras|material(is)? de expediente|equipamentos (de informatica|hospitalares)|locacao de equipamentos|inventario fisico|avaliacao patrimonial|audiovisual|captacao de recursos|processos judiciais")

# ---------------------------------------------------------------- 1. quem entra
cands = {}
try:
    for e in json.load(open(f"{doc_dir}/ultima.json"))["licitacoes"]:
        cands[e["numero_controle_pncp"]] = {"tema": e}
except (OSError, ValueError, KeyError):
    pass
for r in json.load(open(todas))["registros"]:
    c, org, mun, uf, mod, v, sig, fim, obj = r[:9]
    if fim and fim > AG and fim[:4] <= str(agora.year + 2) and DOC.search(norm(obj)) and not FORA.search(norm(obj)):
        cands.setdefault(c, {})["lista"] = r
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


with cf.ThreadPoolExecutor(8) as ex:
    det = {c: (d, it) for c, d, it in ex.map(detalhar, list(cands))}

# ---------------------------------------------------------------- 2. linhas
UNID = {"pagina": "páginas", "caixa": "caixas", "metro_linear": "metros lineares", "registro": "registros", "hora": "horas"}
L = []
for c, x in cands.items():
    d, itens = det[c]
    t, r = x.get("tema") or {}, x.get("lista")
    sit = d.get("situacaoCompraNome") or t.get("situacao") or ""
    fim = (d.get("dataEncerramentoProposta") or t.get("encerramento") or (r[7] if r else "") or "")[:16]
    if not fim or fim <= AG or (sit and not sit.startswith("Divulgada")):
        continue
    obj = " ".join((d.get("objetoCompra") or t.get("objeto") or (r[8] if r else "")).split())
    if (not DOC.search(norm(obj)) and not t) or FORA.search(norm(obj)):
        continue
    uo = d.get("unidadeOrgao") or {}
    org = (d.get("orgaoEntidade") or {}).get("razaoSocial") or t.get("orgao_nome") or (r[1] if r else "")
    v = d.get("valorTotalEstimado")
    v = v if v is not None else (t.get("valor") if t else (r[5] if r else None))
    vol = " · ".join(f"{q:,.0f}".replace(",", ".") + " " + UNID.get(k, k) for k, q in (t.get("vol") or {}).items() if q and q >= 10 and k in UNID)
    cnpj, ano, seq = partes(c)
    L.append({
        "c": c, "org": org, "unid": uo.get("nomeUnidade") or t.get("unidade_nome") or "", "mun": uo.get("municipioNome") or t.get("municipio_nome") or (r[2] if r else ""),
        "uf": uo.get("ufSigla") or t.get("uf") or (r[3] if r else ""), "mod": d.get("modalidadeNome") or t.get("modalidade") or (r[4] if r else ""),
        "disp": d.get("modoDisputaNome") or "", "num": d.get("numeroCompra") or t.get("numero") or "", "proc": d.get("processo") or t.get("processo") or "",
        "srp": "Sim" if (d.get("srp") if d else t.get("srp")) else "Não", "ini": (d.get("dataAberturaProposta") or t.get("abertura") or (r[12] if r else "") or "")[:16],
        "fim": fim, "obj": obj, "v": v or 0, "sig": not v and any(i.get("orcamentoSigiloso") for i in itens),
        "portal": d.get("usuarioNome") or (r[9] if r else "") or "", "lo": d.get("linkSistemaOrigem") or t.get("link_origem") or "",
        "lp": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}", "vol": vol, "nota": t.get("nota") or "", "itens": itens,
        "esf": {"M": "Municipal", "E": "Estadual", "F": "Federal", "D": "Distrital"}.get((d.get("orgaoEntidade") or {}).get("esferaId") or "", ""),
    })
vistos, U = set(), []
for x in sorted(L, key=lambda x: x["fim"]):
    k = (x["org"], round(x["v"] or 0), norm(x["obj"])[:50])
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
cols = [("Status", 13), ("Encerra propostas", 17), ("Dias", 7), ("Abertura propostas", 17), ("Órgão", 34), ("Unidade", 24), ("Cidade", 18), ("UF", 5),
        ("Esfera", 10), ("Modalidade", 18), ("Disputa", 12), ("Nº", 9), ("Processo", 18), ("SRP", 6), ("Objeto", 70), ("Valor estimado", 17),
        ("Nº itens", 8), ("Volume lido no edital", 24), ("Nota", 6), ("Portal da disputa", 26), ("Link do portal", 22), ("Link PNCP", 22), ("Nº controle PNCP", 28)]
titulo(ws, "📄 Digitalização e gestão documental · licitações abertas", fonte, len(cols))
cabecalho(ws, cols, 4)
for i, x in enumerate(L, 5):
    st, k = status(x)
    vals = [st, datetime.fromisoformat(x["fim"]), round(dias(x), 1), datetime.fromisoformat(x["ini"]) if x["ini"] else None, x["org"], x["unid"], x["mun"], x["uf"],
            x["esf"], x["mod"], x["disp"], x["num"], x["proc"], x["srp"], x["obj"], (x["v"] if x["v"] else ("sigiloso" if x["sig"] else "não informado")),
            len(x["itens"]), x["vol"], x["nota"], x["portal"], x["lo"] or "—", x["lp"], x["c"]]
    for j, v in enumerate(vals, 1):
        cel = ws.cell(row=i, column=j, value=v)
        cel.border = borda
        cel.alignment = Alignment(vertical="top", wrap_text=j in (5, 6, 15, 18, 20))
    ws.cell(row=i, column=1).fill, ws.cell(row=i, column=1).font = fill(COR[k][0]), Font(bold=True, color=COR[k][1])
    ws.cell(row=i, column=2).number_format = DTH
    ws.cell(row=i, column=4).number_format = DTH
    ws.cell(row=i, column=16).number_format = BRL
    ws.cell(row=i, column=16).font = Font(bold=True)
    for j, u in ((21, x["lo"]), (22, x["lp"])):
        if u:
            ws.cell(row=i, column=j).hyperlink = u
            ws.cell(row=i, column=j).value = "abrir portal ↗" if j == 21 else "abrir no PNCP ↗"
            ws.cell(row=i, column=j).font = Font(color="1D4ED8", underline="single")
    if i % 2:
        for j in range(2, len(cols) + 1):
            if j not in (21, 22):
                ws.cell(row=i, column=j).fill = fill("F8FAFB")
    ws.row_dimensions[i].height = 48
n = len(L) + 4
ws.cell(row=n + 1, column=15, value="TOTAL (soma dos valores divulgados)").font = Font(bold=True)
t = ws.cell(row=n + 1, column=16, value=f"=SUM(P5:P{n})")
t.number_format, t.font = BRL, Font(bold=True, color=BRANCO)
t.fill = fill(TINTA)
ws.freeze_panes = "F5"
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
titulo(wr, "📊 Digitalização · painel da semana", fonte, 6)
for j, w in enumerate([30, 18, 4, 30, 14, 18], 1):
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
r0 = max(14, 4 + len(Counter(x["uf"] for x in L)) + 2)
wr.cell(row=r0, column=1, value="🏆 10 MAIORES POR VALOR").font = Font(bold=True, size=12, color=TINTA)
for j, n_ in enumerate(["Órgão", "Valor", "", "Objeto", "Encerra", "Link"], 1):
    if n_:
        h = wr.cell(row=r0 + 1, column=j, value=n_)
        h.font, h.fill, h.border = H, fill(AZUL), borda
for i, x in enumerate(sorted([x for x in L if x["v"] < 2e9], key=lambda x: -x["v"])[:10], r0 + 2):
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
r0 = r0 + 13
wr.cell(row=r0, column=1, value="LEGENDA DE CORES").font = Font(bold=True, color=TINTA)
for i, (k, txt) in enumerate([("urg", "URGENTE · encerra em até 2 dias"), ("sem", "ESTA SEMANA · 3 a 7 dias"), ("ok", "NO PRAZO · mais de 7 dias"), ("avir", "A VIR · propostas ainda não abriram")], r0 + 1):
    c = wr.cell(row=i, column=1, value=txt)
    c.fill, c.font, c.border = fill(COR[k][0]), Font(bold=True, color=COR[k][1]), borda
wr.cell(row=r0 + 6, column=1, value="Abas: Calendário · Licitações (tabela completa com filtros) · Itens e preços · Portais").font = Font(italic=True, color="44546A")
wb.active = 0
wb.save(saida)
print(f"ok: {len(L)} licitações, {sum(len(x['itens']) for x in L)} itens, soma R$ {soma:,.0f}", file=sys.stderr)
