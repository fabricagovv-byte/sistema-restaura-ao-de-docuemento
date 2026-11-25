"""Junta as buscas do dia em mensagens separadas para WhatsApp (uma por tema), no formato compacto do radar.

Uso: PYTHONPATH=plataforma-licitacoes/backend python resumo_whatsapp.py SAIDA_DIR tema=arquivo.json [tema=arquivo.json ...]
Temas: ust, mensal, servicos, consultoria, documental. Só entra o que ainda está com prazo de proposta aberto agora.
"""
import json, os, re, sys
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA, PARES = sys.argv[1], [a.split("=", 1) for a in sys.argv[2:]]
src = open(os.path.join(AQUI, "busca_diaria.py")).read()
ns = {}
sys_argv, sys.argv = sys.argv, ["x", "/nao-usado", "servicos"]
exec(src.split("# ------------------------------------------------------------------ 1.")[0], ns)
exec(src[src.index("def brl(v):"):src.index("def arq(e, rx):")], ns)
exec(src[src.index("def valor_txt(e):"):src.index("def bloco(i, e):")], ns)
exec(src[src.index("def nome_curto(e):"):src.index("def radar(lista):")], ns)
sys.argv = sys_argv
AGORA = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
norm, eh_tema = ns["norm"], ns["eh_tema"]

TITULOS = {"ust": "🧮 UST e PF · serviços de TI (sem software pronto)", "mensal": "📢 FIXO MENSAL de TI",
           "servicos": "🛠️ SERVIÇOS DE TIC sem produto pronto", "consultoria": "🧠 CONSULTORIA em tecnologia",
           "documental": "📂 DIGITALIZAÇÃO, INDEXAÇÃO e GESTÃO DOCUMENTAL"}
LIMITE = {"ust": 30, "mensal": 25, "servicos": 6, "consultoria": 15, "documental": 25}
if os.environ.get("PREVIA"):  # prévia curta: só os melhores de cada tema
    LIMITE = {k: (3 if k == "servicos" else 10) for k in LIMITE}
ROT = {"ust": "UST", "ust_doc": "UST", "ust_texto": "UST", "pf": "PF", "pf_doc": "PF", "hora": "horas", "pagina": "páginas",
       "pagina_texto": "páginas", "registro": "registros", "metro_linear": "m lineares", "caixa": "caixas"}


def aberto(e):
    return e.get("encerramento") and datetime.fromisoformat(e["encerramento"]) > AGORA


def vol_txt(e, tema):
    v = e.get("vol") or {}
    partes = [f"{ns['num'](q)} {ROT.get(k, k)}" for k, q in v.items() if k in ROT and q]
    if tema in ("ust", "servicos", "mensal") and e.get("mensal"):
        partes.append(f"{ns['brl'](e['mensal'])[:-3]}/mês" + (f" × {e['meses']}" if e.get("meses") and e["meses"] != 12 else ""))
    if not partes and e.get("ust_doc"):
        partes.append("UST no edital")
    return " · ".join(dict.fromkeys(partes))


LIXO = re.compile(r"^(-\s*|\"|constitui objeto d[oa] presente \w+\s*|o objeto d[aeo] presente \w+ (e|é) a\s*|pregao eletronico [\d/]+ -\s*|"
                  r"registro de pre[cç]os?\s*(para|visando)?\s*(a|à)?\s*(futura e eventual\s*)?|contrata[cç][aã]o\s*(de|da|do)?\s*|"
                  r"empresa\s*(\(s\))?\s*especializada\s*(\(s\))?\s*(para|na|em|no)?\s*(a|o)?\s*|"
                  r"presta[cç][aã]o\s*(continuada|de|dos)?\s*(de|dos)?\s*|pessoa jur[ií]dica\s*(especializada)?\s*(para|na|em)?\s*)", re.I)


def enxuga(obj):
    s = obj
    for _ in range(6):
        s2 = LIXO.sub("", s).strip(" ,;:-")
        if s2 == s:
            break
        s = s2
    s = s[:1].upper() + s[1:].lower() if s.isupper() else s[:1].upper() + s[1:]
    return (s[:72].rsplit(" ", 1)[0] + "…") if len(s) > 72 else s


def linha(i, e, tema):
    enc = datetime.fromisoformat(e["encerramento"])
    data = enc.strftime("%d/%m %H:%M" if enc.year == AGORA.year else "%d/%m/%Y %H:%M")
    if enc - AGORA < timedelta(days=2):
        data += " ⚠️"
    obj = re.sub(r"^\[[^\]]*\]\s*-?\s*", "", " ".join((e.get("objeto") or "").split()))
    assunto = ns["assunto"](e) if tema == "mensal" else enxuga(obj)
    v = vol_txt(e, tema)
    valor = ns["mi"](e["valor"]) if e.get("valor") else ns["valor_txt"](e).lower()
    return "\n".join([f"*{i}. {ns['nome_curto'](e)}* ({e.get('uf')}) · {assunto}",
                      f"💰 *{valor}*" + (f" · 📦 *{v}*" if v else "") + f" · 📅 {data}", f"🔗 {e['link_pncp']}"])


def filtra(tema, L):
    L = [e for e in L if aberto(e)]
    if tema in ("ust", "servicos"):  # serviço, sem software pronto
        ns["TEMA"] = "servicos"
        L = [e for e in L if eh_tema(e.get("objeto") or "")]
    if tema == "ust":
        L = [e for e in L if any((e.get("vol") or {}).get(k) for k in ("ust", "ust_doc", "pf", "pf_doc", "ust_texto"))
             or e.get("ust_doc") or ns["UST_RX"].search(norm(e.get("objeto")))]
        L.sort(key=lambda e: -(e.get("valor") or 0))
    elif tema == "consultoria":
        ns["TEMA"] = "consultoria"
        L = [e for e in L if eh_tema(e.get("objeto") or "")]
        L.sort(key=lambda e: -(e.get("valor") or 0))
    elif tema == "mensal":
        L.sort(key=lambda e: -(e.get("mensal") or 0))
    elif tema == "documental":
        L.sort(key=lambda e: (-(e.get("nota") or 0), -(e.get("valor") or 0)))
    return L


os.makedirs(SAIDA, exist_ok=True)
tudo = [f"*📋 BUSCA DO DIA · {AGORA.strftime('%d/%m/%Y')}*", "Fonte: PNCP (inclui o que os portais parceiros publicam lá). Só prazo de proposta aberto. ⚠️ = encerra em até 2 dias.", ""]
for tema, arq_json in PARES:
    d = json.load(open(arq_json))
    L = filtra(tema, d["licitacoes"])
    soma = sum(e.get("valor") or 0 for e in L if (e.get("valor") or 0) < 1e9)
    cab = [f"*{TITULOS[tema]} · {AGORA.strftime('%d/%m')}*", f"{len(L)} abertas · soma estimada {ns['mi'](soma)} · verificado {d['verificado_em'][8:10]}/{d['verificado_em'][5:7]} {d['verificado_em'][11:16]}", ""]
    corpo = []
    if tema == "servicos":
        usados = set()
        for titulo, rx in ns["GRUPOS_SERV"][:-1]:
            g = [e for e in L if e["numero_controle_pncp"] not in usados and re.search(rx, norm(e.get("objeto"))[:300])]
            g.sort(key=lambda e: (-(e.get("nota") or 0), -(e.get("valor") or 0)))
            usados |= {e["numero_controle_pncp"] for e in g}
            if g:
                corpo += [f"*{titulo}* ({len(g)})"] + [linha(i, e, tema) for i, e in enumerate(g[:LIMITE[tema]], 1)] + [""]
    else:
        corpo = [linha(i, e, tema) + "\n" for i, e in enumerate(L[:LIMITE[tema]], 1)]
        if len(L) > LIMITE[tema]:
            corpo.append(f"(+ {len(L) - LIMITE[tema]} na lista completa)")
    msg = "\n".join(cab + corpo).strip() + "\n"
    open(os.path.join(SAIDA, f"whatsapp-{tema}.txt"), "w").write(msg)
    tudo += [msg, "────────────", ""]
    print(tema, len(L), "abertas ->", len(msg), "caracteres")
open(os.path.join(SAIDA, "whatsapp-busca-do-dia.txt"), "w").write("\n".join(tudo))
