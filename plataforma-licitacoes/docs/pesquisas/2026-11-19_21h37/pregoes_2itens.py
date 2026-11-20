"""Pregões de TIC com até 2 itens, com foco em UST, PF e fixo mensal. Completa os itens que faltam direto no PNCP."""
import json, re, subprocess, sys, unicodedata, concurrent.futures as cf
from datetime import datetime
from licitacoes.taxonomia import tipo_volume

ENTRADA, SAIDA_JSON, SAIDA_TXT = sys.argv[1:4]
D = json.load(open(ENTRADA))
SEM = lambda s: unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()  # noqa: E731
lista = [e for e in D["lista"] if "Pregão" in (e.get("modalidade") or "")]


def itens(e):
    if "itens_raw" in e:
        return e
    try:
        r = subprocess.run(["pncp", "itens", e["orgao_cnpj"], str(e["ano"]), str(e["numero_sequencial"]), "-q", "--retries", "4"],
                           capture_output=True, text=True, timeout=240)
        its = json.loads(r.stdout) if r.stdout.strip() else []
    except Exception:  # noqa: BLE001
        its = None
    e["itens_raw"] = [{"n": i.get("numeroItem"), "d": " ".join((i.get("descricao") or "").split())[:200], "q": i.get("quantidade"),
                       "u": i.get("unidadeMedida"), "vu": i.get("valorUnitarioEstimado"), "vt": i.get("valorTotal"),
                       "ms": i.get("materialOuServicoNome")} for i in its] if its is not None else None
    return e


with cf.ThreadPoolExecutor(6) as ex:
    lista = list(ex.map(itens, lista))

MES_UN = re.compile(r"^\s*(mes|meses|mensal|mensalidade|men|mês)\b", re.I)
sel = []
for e in lista:
    its = e["itens_raw"]
    if its is None or not (1 <= len(its) <= 2):
        continue
    texto = SEM(f"{e.get('objeto')} " + " ".join(f"{i['d']} {i['u'] or ''}" for i in its))
    tags = []
    vol = dict(e.get("vol") or {})
    for i in its:
        k = tipo_volume(i["u"], i["d"], i["q"], i["vu"])
        if k in ("ust", "pf", "hora", "mes") and not str(i["ms"] or "").lower().startswith("m"):
            vol[k] = max(vol.get(k, 0), float(i["q"] or 0))
    if "ust" in vol or re.search(r"\bust\b|unidades? de servicos? tecnicos?", texto):
        tags.append("UST")
    if "pf" in vol or re.search(r"pontos? de funcao", texto):
        tags.append("PF")
    if "hora" in vol or re.search(r"\bhst\b|horas? tecnicas?|horas? de servico tecnico", texto):
        tags.append("HST")
    mensal = "mes" in vol or any(MES_UN.match(SEM(i["u"] or "")) for i in its) or re.search(r"valor (fixo )?mensal|mensalidade|por mes|locacao mensal|licenciamento mensal|assinatura mensal", texto)
    if mensal:
        tags.append("Fixo mensal")
    tags.append("TIC")
    e["tags"], e["vol2"] = tags, vol
    sel.append(e)

foco = lambda e: any(t in e["tags"] for t in ("UST", "PF", "HST", "Fixo mensal"))  # noqa: E731
sel.sort(key=lambda e: (not foco(e), -(0 if e.get("valor_suspeito") else (e.get("valor") or 0))))


def brl(v):
    return ("R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")) if v else "NÃO INFORMADO"


def dh(s):
    return datetime.fromisoformat(s).strftime("%d/%m/%Y — %H:%M") if s else "NÃO INFORMADO"


NOM = {"ust": "UST", "pf": "PF", "hora": "horas técnicas", "mes": "meses"}
out = [f"*PREGÕES DE TIC COM ATÉ 2 ITENS — foco UST, PF, HST e fixo mensal*", f"Fonte: PNCP, verificado em {D.get('verificado_em_txt', '')}. Só prazo de proposta aberto.", ""]
for i, e in enumerate(sel, 1):
    ed = [a["url"] for a in e.get("arquivos") or [] if (a.get("tipo") or "").lower().startswith("edital")][:1]
    tr = [a["url"] for a in e.get("arquivos") or [] if "refer" in (a.get("tipo") or "").lower()][:1]
    itx = "\n".join(f"   • Item {it['n']}: {it['d'][:120]} — {it['q']:,.0f} {it['u'] or ''}{(' × ' + brl(it['vu'])) if it['vu'] else ''}".replace(",", ".")
                    if isinstance(it["q"], (int, float)) else f"   • Item {it['n']}: {it['d'][:120]}" for it in e["itens_raw"])
    qt = "; ".join(f"{q:,.0f} {NOM[k]}".replace(",", ".") for k, q in e["vol2"].items() if k in NOM) or "ver itens"
    out += [f"🏛️ *{i:03d} — {e['orgao_nome']}*", f"📍 {e.get('municipio_nome') or ''}/{e.get('uf') or ''} · 📑 {e.get('modalidade')} nº {e.get('numero') or 'NÃO INFORMADO'}",
            f"🏷️ {' · '.join(e['tags'])}", f"💰 {brl(e.get('valor'))}" + (" ⚠️ conferir" if e.get("valor_suspeito") else ""),
            f"📦 {' '.join((e.get('objeto') or '').split())[:300]}", f"📊 {qt}", f"🧾 {len(e['itens_raw'])} item(ns):", itx,
            f"⏳ Propostas até {dh(e.get('encerramento'))}", f"🔗 {e['link_pncp']}",
            f"📥 Edital: {ed[0] if ed else 'NÃO LOCALIZADO no PNCP'}", f"📥 TR: {tr[0] if tr else 'NÃO LOCALIZADO em separado'}", ""]
open(SAIDA_TXT, "w").write("\n".join(out))
json.dump(sel, open(SAIDA_JSON, "w"), ensure_ascii=False, default=str)
print("pregões:", len(lista), "| itens lidos:", sum(e["itens_raw"] is not None for e in lista), "| com 1 ou 2 itens:", len(sel),
      "| com UST/PF/HST/fixo mensal:", sum(foco(e) for e in sel))
for t in ("UST", "PF", "HST", "Fixo mensal"):
    print(t, sum(t in e["tags"] for e in sel))
