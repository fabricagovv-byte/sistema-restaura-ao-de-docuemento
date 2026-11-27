"""Todas as licitações dos leads, uma mensagem de WhatsApp numerada por licitação, um arquivo por categoria.
Uso: python3 msg_todas.py todas.json saida_dir todos.json -- tema_dir1 tema_dir2 ...
todos.json = {categoria: [link PNCP em ordem de prioridade]} (escrito por leads_whatsapp.py)."""
import json, re, sys, os, unicodedata
from datetime import datetime, timedelta, timezone
a = sys.argv[1:]; sep = a.index("--")
todas, saida, lista, temas = a[0], a[1], a[2], a[sep + 1:]
agora = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
REG = {}
for r in json.load(open(todas))["registros"]:
    m = re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})", r[0])
    if m: REG[(m.group(1), m.group(3), m.group(2))] = r
UNID = {"ust": "UST", "ust_doc": "UST", "pf": "PF", "pf_doc": "PF", "hora": "horas", "pagina": "páginas", "caixa": "caixas", "metro_linear": "metros lineares", "registro": "registros"}
TEMA = {}
for t in temas:
    try: L = json.load(open(f"{t}/ultima.json"))["licitacoes"]
    except (OSError, ValueError, KeyError): continue
    for e in L:
        d = TEMA.setdefault(e["numero_controle_pncp"], {})
        for k in ("link_origem", "mensal", "meses", "plataforma"):
            if e.get(k) and not d.get(k): d[k] = e[k]
        vs, out = set(), []
        for k, q in (e.get("vol") or {}).items():
            u = UNID.get(k)
            if u and q and q >= 10 and u not in vs: vs.add(u); out.append(f"{q:,.0f}".replace(",", ".") + f" {u}")
        if out and not d.get("vol"): d["vol"] = " · ".join(out)
def mi(v):
    if not v: return "não divulgado"
    if v >= 2e9: return "a conferir no edital"
    return f"R$ {v/1e6:.2f} mi".replace(".", ",") if v >= 1e6 else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
SEM = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
ESF = {"M": "Municipal", "E": "Estadual", "F": "Federal", "D": "Distrital"}
def tit(s): return " ".join(w if w in ("de", "da", "do", "dos", "das", "e") else w.capitalize() for w in s.lower().split())
os.makedirs(saida, exist_ok=True)
import urllib.request
CACHE_F = saida + ".api.json"
try: API = json.load(open(CACHE_F))
except (OSError, ValueError): API = {}
def api(cnpj, ano, seq):
    return API.get(f"{cnpj}/{ano}/{seq}") or {}
CATS = json.load(open(lista))
from concurrent.futures import ThreadPoolExecutor
alvos = list(dict.fromkeys(re.search(r"editais/(\d{14})/(\d{4})/(\d+)", u).groups() for v in CATS.values() for u in v))
falta_api = [x for x in alvos if not API.get("/".join(x))]
def busca(x):
    k = "/".join(x)
    try:
        return k, json.load(urllib.request.urlopen(f"https://pncp.gov.br/api/consulta/v1/orgaos/{x[0]}/compras/{x[1]}/{x[2]}", timeout=40))
    except Exception:
        return k, {}
for rodada in range(2):
    with ThreadPoolExecutor(8) as ex:
        for k, d in ex.map(busca, [x for x in alvos if not API.get("/".join(x))]):
            if d: API[k] = d
json.dump(API, open(CACHE_F, "w"), ensure_ascii=False)
print(len(falta_api), "buscadas;", sum(1 for x in alvos if not API.get("/".join(x))), "sem resposta do PNCP")
indice, n = [], 0
for ci, (cat, links) in enumerate(CATS.items(), 1):
    msgs = []
    for url in links:
        lk = re.search(r"https://pncp\.gov\.br/app/editais/(\d{14})/(\d{4})/(\d+)", url)
        r = REG.get((lk.group(1), lk.group(2), lk.group(3)))
        if not r: continue
        c, org, mun, uf, mod, v, sig, fim, obj, portal, ass, esf, ini = r
        t = dict(TEMA.get(c, {})); n += 1; i = len(msgs) + 1
        d = api(lk.group(1), lk.group(2), lk.group(3))
        if d.get("objetoCompra"): obj = d["objetoCompra"]
        elif len(obj) >= 165: obj = obj.rstrip() + "… (resumo; texto completo no edital)"
        if d.get("linkSistemaOrigem") and not t.get("link_origem"): t["link_origem"] = d["linkSistemaOrigem"]
        if d.get("srp"): mod += " · Registro de preços"
        if d.get("dataEncerramentoProposta"): fim = d["dataEncerramentoProposta"]
        f = datetime.strptime(fim[:16], "%Y-%m-%dT%H:%M"); dias = (f.date() - agora.date()).days
        falta = "HOJE" if dias == 0 else "amanhã" if dias == 1 else f"faltam {dias} dias"
        L = [f"*📨 MENSAGEM {i}/{len(links)} · {cat}*", "", f"🏛️ *{tit(org)}*", f"📍 {mun}/{uf} · {ESF.get(esf, '')}".rstrip(" ·"), "",
             f"📝 *Objeto:* {(lambda o: o if len(o) <= 700 else o[:700].rsplit(' ', 1)[0] + '…')(' '.join(obj.split()))}", "",
             f"💰 *Valor estimado:* {'sigiloso' if sig else mi(v)}"]
        if t.get("mensal") and t["mensal"] >= 1000 and 1 <= (t.get("meses") or 12) <= 120:
            L.append(f"🗓️ *Mensal:* {mi(t['mensal'])}/mês" + (f" × {t['meses']} meses" if t.get("meses") else ""))
        if t.get("vol"): L.append(f"📦 *Volume no edital:* {t['vol']}")
        L += [f"⚖️ {mod}", f"🖥️ Portal: {portal or t.get('plataforma') or 'NÃO LOCALIZADO'}",
              f"📅 *Propostas até {SEM[f.weekday()]}, {f:%d/%m/%Y} às {f:%H:%M}* ({falta}){' ⚠️' if dias <= 2 else ''}"]
        if ini: L.append(f"🟢 Aberta desde {ini[8:10]}/{ini[5:7]}/{ini[:4]}")
        L += ["", f"🔗 Edital no PNCP: {lk.group(0)}"]
        if t.get("link_origem"): L.append(f"🌐 Disputa: {t['link_origem']}")
        L.append(f"Nº PNCP {c}")
        msgs.append("\n".join(L))
    if not msgs: continue
    base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", re.sub(r"\(.*", "", cat)).encode("ascii", "ignore").decode().lower()).strip("-")
    open(f"{saida}/{ci}-{base}.txt", "w").write(f"*{cat}* · {len(msgs)} mensagens (ordem de prioridade) · lista de {agora:%d/%m/%Y}\n\n════════════════\n\n" + "\n\n════════════════\n\n".join(msgs))
    indice.append(f"{ci}-{base}.txt: {len(msgs)}")
print(n, "mensagens"); print("\n".join(indice))
