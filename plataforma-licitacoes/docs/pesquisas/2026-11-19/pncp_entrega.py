"""Etapa 3: filtro final, deduplicação, nota 0-100 (critérios do roteiro) e entrega em WhatsApp, planilha e JSON."""
import json, re, sys
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

ENTRADA, PASTA = sys.argv[1:3]
D = json.load(open(ENTRADA))
VERIF = D["verificado_em"]
AGORA = datetime.fromisoformat(VERIF)
TI_FORTE = re.compile(r"tecnologia da informa|\btic\b|\bti\b|software|sistemas? (de informa|informatiz|integrad|de gest)|desenvolvimento de sistemas|"
                      r"\bust\b|ponto de funcao|horas? tecnicas?|digitaliza|gestao documental|nuvem|cloud|banco de dados|ciberseg|seguranca da informa|"
                      r"data ?center|service desk|plataforma|licen[cs]a|subscri", re.I)
FORA = re.compile(r"autope[cç]|oficina|ve[ií]culo|pavimenta|climatiza|\bobras?\b|engenharia (el[eé]trica|civil)|credenciamento .{0,60}(sa[uú]de|m[eé]dic|"
                  r"cl[ií]nic|exames|home care|organiza[cç][oõ]es civis)|materiais de (limpeza|constru)|curativo|g[eê]neros|implementos|telemarketing|"
                  r"cogest[aã]o|telemedicina|apoio administrativo|som, il|estruturas, como som|regulariza[cç][aã]o fundi|geotecn", re.I)
SEM = lambda s: re.sub(r"[̀-ͯ]", "", __import__("unicodedata").normalize("NFD", s or "")).lower()  # noqa: E731

lista = []
for e in D["abertos"]:
    obj = f"{e.get('objeto') or e.get('description') or ''}"
    if FORA.search(obj) or FORA.search(SEM(obj)):
        continue
    if not e["cats"] and not TI_FORTE.search(SEM(obj)):
        continue
    lista.append(e)
# republicações: mesmo órgão, mesmo valor e mesmo começo de objeto -> fica a de controle mais recente
vistos = {}
for e in sorted(lista, key=lambda x: x["numero_controle_pncp"]):
    k = (e["orgao_cnpj"], round(e.get("valor") or 0), SEM(e.get("objeto") or "")[:70])
    vistos[k] = e
dups = len(lista) - len(vistos)
lista = list(vistos.values())

PESO_AREA = [({"desenvolvimento", "fabrica_software", "sustentacao", "manutencao_software"}, 25, "Desenvolvimento/sustentação"),
             ({"digitalizacao", "indexacao", "ged", "ocr", "triagem", "guarda", "higienizacao", "restauracao"}, 23, "Gestão documental"),
             ({"sistemas_gestao", "dados", "ia", "integracao", "ti_mensal"}, 18, "Sistemas, dados e IA"),
             ({"suporte", "consultoria_ti", "cloud", "seguranca", "infra_ti", "servidores", "ead"}, 13, "Infraestrutura, nuvem, segurança e suporte")]


def volumes(e):
    v = {}
    for fonte in ("vol_objeto", "vol_documentos", "vol_itens"):
        for k, q in (e.get(fonte) or {}).items():
            if k in ("ust", "pf", "hora", "pagina", "mes") and q:
                v[k] = max(v.get(k, 0), q)
    return v


def nota(e):
    val = e.get("valor") or 0
    suspeito = val > 1e9
    pts_valor = 0 if suspeito else 25 if val >= 5e7 else 21 if val >= 1e7 else 16 if val >= 5e6 else 9 if val >= 1e6 else 4
    cats = set(e["cats"])
    area, pts_tec = "Outros de TIC", 10
    for conj, p, nome in PESO_AREA:
        if cats & conj:
            area, pts_tec = nome, p
            break
    vol = volumes(e)
    mensal = "ti_mensal" in cats or "mes" in vol or re.search(r"continu|mensal", SEM(e.get("objeto") or ""))
    pts_prev = 20 if (vol.keys() & {"ust", "pf", "hora"}) else 16 if mensal else 10
    pts_viab = 12 if e.get("arquivos") else 8
    dias = (datetime.fromisoformat(e["encerramento"]) - AGORA).total_seconds() / 86400
    pts_prazo = 15 if dias >= 10 else 11 if dias >= 5 else 6 if dias >= 2 else 2
    return pts_valor + pts_tec + pts_prev + pts_viab + pts_prazo, area, vol, bool(mensal), dias, suspeito


for e in lista:
    e["nota"], e["area"], e["vol"], e["mensal"], e["dias"], e["valor_suspeito"] = nota(e)
lista.sort(key=lambda e: (-e["nota"], -(e.get("valor") or 0)))


def brl(v):
    if not v:
        return "NÃO INFORMADO (sigiloso ou não publicado)"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def data_hora(s):
    d = datetime.fromisoformat(s)
    return d.strftime("%d/%m/%Y — %H:%M")


NOMES_VOL = {"ust": "UST", "pf": "PF", "hora": "horas técnicas (HST)", "pagina": "páginas", "mes": "meses"}


def docs(e):
    ed = [a for a in e.get("arquivos") or [] if (a.get("tipo") or "").lower().startswith("edital")]
    tr = [a for a in e.get("arquivos") or [] if "refer" in (a.get("tipo") or "").lower() or "termo de refer" in SEM(a.get("titulo") or "")]
    return ed, tr


def bloco(i, e):
    ed, tr = docs(e)
    vol = e["vol"]
    qt = "; ".join(f"{q:,.0f} {NOMES_VOL[k]}".replace(",", ".") for k, q in vol.items() if k != "mes") or "NÃO LOCALIZADO nos itens/objeto"
    prior = "Alta" if e["nota"] >= 70 else "Média" if e["nota"] >= 55 else "Baixa"
    linhas = [
        f"🏛️ LICITAÇÃO {i:03d} — {e['orgao_nome']}",
        f"📍 Local: {e.get('municipio_nome') or ''}/{e.get('uf') or ''}",
        f"📑 {e.get('modalidade') or ''}: nº {e.get('numero') or 'NÃO INFORMADO'} · Processo {e.get('processo') or 'NÃO INFORMADO'}",
        f"🆔 PNCP: {e['numero_controle_pncp']}",
        f"💰 Valor global estimado: {brl(e.get('valor'))}" + (" ⚠️ valor publicado parece erro de digitação — conferir" if e["valor_suspeito"] else ""),
        "💵 Valor mensal: NÃO INFORMADO no PNCP",
        f"📦 Objeto: {' '.join((e.get('objeto') or '').split())[:400]}",
        f"📊 Quantidade: {qt}",
        f"📅 Abertura das propostas: {data_hora(e['abertura']) if e.get('abertura') else 'NÃO INFORMADO'}",
        f"⏳ Prazo final das propostas: {data_hora(e['encerramento'])} ({int(e['dias'])} dias)",
        f"🖥️ Disputa: {e.get('plataforma') or 'NÃO INFORMADO'} · {e.get('disputa') or ''}{' · Registro de preços' if e.get('srp') else ''}",
        "👨‍💻 Profissionais / 📋 Atestados / ⚙️ Tecnologias: NÃO LOCALIZADO nesta rodada (exige leitura do edital e do TR)",
        f"🔗 PNCP: {e['link_pncp']}",
    ]
    if e.get("link_origem"):
        linhas.append(f"🔗 Portal da disputa: {e['link_origem']}")
    linhas.append("📥 Edital: " + (" | ".join(a["url"] for a in ed[:2]) if ed else "NÃO LOCALIZADO como arquivo no PNCP"))
    linhas.append("📥 TR: " + (" | ".join(a["url"] for a in tr[:2]) if tr else "NÃO LOCALIZADO como arquivo separado (pode estar dentro do edital ou do ZIP)"))
    linhas.append(f"⭐ Prioridade: {prior} (nota {e['nota']}/100 — {e['area']})")
    linhas.append(f"✅ Situação: confirmada no PNCP em {AGORA.strftime('%d/%m/%Y %H:%M')} (Brasília): {e.get('situacao')}")
    return "\n".join(linhas)


faixa = lambda e: (e.get("valor") or 0)  # noqa: E731
acima10 = [e for e in lista if faixa(e) >= 1e7]
de5a10 = [e for e in lista if 5e6 <= faixa(e) < 1e7]
abaixo = [e for e in lista if faixa(e) < 5e6]
com_ust = [e for e in lista if "ust" in e["vol"] or "remun_ust" in e.get("termos", [])]
txt = [f"*PAINEL NACIONAL DIGITALGOV — pesquisa ao vivo no PNCP*", f"Verificado em {AGORA.strftime('%d/%m/%Y %H:%M')} (Brasília). Só licitações com prazo de proposta ainda aberto.", ""]
for titulo, grupo in (("🔥 ACIMA DE R$ 10 MILHÕES", acima10), ("💼 DE R$ 5 A 10 MILHÕES", de5a10)):
    txt.append(f"*{titulo}* ({len(grupo)})\n")
    for i, e in enumerate(sorted(grupo, key=lambda x: -x["nota"]), 1):
        txt.append(bloco(i, e) + "\n")
open(f"{PASTA}/licitacoes-whatsapp.txt", "w").write("\n".join(txt))

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
limpo = lambda v: ILLEGAL_CHARACTERS_RE.sub(" ", v) if isinstance(v, str) else v  # noqa: E731
wb = Workbook()
ws = wb.active
ws.title = "Oportunidades"
cab = ["Nota", "Prioridade", "Área", "Órgão", "Município", "UF", "Modalidade", "Número", "Processo", "Controle PNCP", "Valor estimado (R$)",
       "Valor suspeito", "UST", "PF", "Horas técnicas", "Páginas", "Abertura", "Prazo final", "Dias restantes", "Registro de preços",
       "Plataforma", "Objeto", "Link PNCP", "Portal da disputa", "Edital", "TR", "Palavras-chave que acharam", "Verificado em"]
ws.append(cab)
for e in lista:
    ed, tr = docs(e)
    ws.append([limpo(x) for x in [e["nota"], "Alta" if e["nota"] >= 70 else "Média" if e["nota"] >= 55 else "Baixa", e["area"], e["orgao_nome"],
               e.get("municipio_nome"), e.get("uf"), e.get("modalidade"), e.get("numero"), e.get("processo"), e["numero_controle_pncp"],
               e.get("valor"), "sim" if e["valor_suspeito"] else "", e["vol"].get("ust"), e["vol"].get("pf"), e["vol"].get("hora"),
               e["vol"].get("pagina"), (e.get("abertura") or "").replace("T", " ")[:16], e["encerramento"].replace("T", " ")[:16],
               int(e["dias"]), "sim" if e.get("srp") else "não", e.get("plataforma"), " ".join((e.get("objeto") or "").split())[:1000],
               e["link_pncp"], e.get("link_origem"), ed[0]["url"] if ed else "NÃO LOCALIZADO", tr[0]["url"] if tr else "NÃO LOCALIZADO",
               ", ".join(e["termos"][:8]), AGORA.strftime("%d/%m/%Y %H:%M")]])
for c in ws[1]:
    c.font = Font(bold=True)
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
for col, larg in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [6, 9, 22, 40, 18, 5, 18, 10, 22, 30, 16, 8, 9, 8, 10, 10, 16, 16, 8, 8, 18, 70, 45, 45, 45, 45]):
    ws.column_dimensions[col].width = larg
for row in ws.iter_rows(min_row=2, min_col=11, max_col=11):
    for c in row:
        c.number_format = '#,##0.00'
wb.save(f"{PASTA}/licitacoes-ti-abertas.xlsx")

soma = sum(e.get("valor") or 0 for e in lista if not e["valor_suspeito"])
res = {"examinados": D["examinados"], "triados_objeto": D["triados"], "abertos_confirmados": len(lista), "duplicados_removidos": dups,
       "acima_10mi": len(acima10), "de_5_a_10mi": len(de5a10), "abaixo_5mi": len(abaixo),
       "mensais_ou_continuados": sum(e["mensal"] for e in lista), "com_ust": sum(1 for e in lista if "ust" in e["vol"]),
       "com_pf": sum(1 for e in lista if "pf" in e["vol"]), "com_hst": sum(1 for e in lista if "hora" in e["vol"]),
       "valor_agregado_sem_suspeitos": soma, "por_area": {}, "com_edital": sum(1 for e in lista if docs(e)[0]),
       "com_tr": sum(1 for e in lista if docs(e)[1]), "suspeitos": [(e["orgao_nome"], e.get("valor")) for e in lista if e["valor_suspeito"]]}
for e in lista:
    res["por_area"][e["area"]] = res["por_area"].get(e["area"], 0) + 1
json.dump({"resumo": res, "lista": lista}, open(f"{PASTA}/licitacoes-ti-abertas.json", "w"), ensure_ascii=False, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
