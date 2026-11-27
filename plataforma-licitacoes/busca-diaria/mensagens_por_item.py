"""Uma mensagem de WhatsApp por licitação dos leads (leads-do-dia + saúde), com dados completos do PNCP.
Uso: python3 msg_item.py todas.json saida_dir leads1.txt [leads2.txt ...] -- tema_dir1 tema_dir2 ..."""
import json, re, sys, os
from datetime import datetime, timedelta, timezone
a = sys.argv[1:]; sep = a.index("--")
todas, saida, txts, temas = a[0], a[1], a[2:sep], a[sep + 1:]
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
    k = f"{cnpj}/{ano}/{seq}"
    if k not in API:
        try:
            API[k] = json.load(urllib.request.urlopen(f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}", timeout=30))
        except Exception:
            API[k] = {}
        json.dump(API, open(CACHE_F, "w"), ensure_ascii=False)
    return API[k]
todas_msgs, n = [], 0
for txt in txts:
    cat = None
    for bloco in open(txt).read().split("\n\n"):
        h = re.match(r"^\*([^\d*][^*]+)\*$", bloco.strip().split("\n")[0])
        if h and "LEADS DO DIA" not in h.group(1): cat = re.sub(r" · LICITAÇÕES ABERTAS.*", "", h.group(1))
        lk = re.search(r"https://pncp\.gov\.br/app/editais/(\d{14})/(\d{4})/(\d+)", bloco)
        if not lk or not cat: continue
        r = REG.get((lk.group(1), lk.group(2), lk.group(3)))
        if not r: continue
        c, org, mun, uf, mod, v, sig, fim, obj, portal, ass, esf, ini = r
        t = dict(TEMA.get(c, {})); n += 1
        d = api(lk.group(1), lk.group(2), lk.group(3))
        if d.get("objetoCompra"): obj = d["objetoCompra"]
        elif len(obj) >= 165: obj = obj.rstrip() + "… (resumo; texto completo no edital)"
        if d.get("linkSistemaOrigem") and not t.get("link_origem"): t["link_origem"] = d["linkSistemaOrigem"]
        if d.get("srp"): mod += " · Registro de preços"
        if d.get("dataEncerramentoProposta"): fim = d["dataEncerramentoProposta"]
        f = datetime.strptime(fim[:16], "%Y-%m-%dT%H:%M"); dias = (f.date() - agora.date()).days
        falta = "HOJE" if dias == 0 else "amanhã" if dias == 1 else f"faltam {dias} dias"
        L = [f"*{cat}*", "", f"🏛️ *{tit(org)}*", f"📍 {mun}/{uf} · {ESF.get(esf, '')}".rstrip(" ·"), "",
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
        m = "\n".join(L); todas_msgs.append(m)
        nome = re.sub(r"[^a-z0-9]+", "-", tit(org).lower())[:40].strip("-")
        open(f"{saida}/{n:02d}-{nome}.txt", "w").write(m)
open(f"{saida}/../mensagens-por-item.txt", "w").write("\n\n════════════════\n\n".join(todas_msgs))
print(n, "mensagens")
