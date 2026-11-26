"""Junta as listas da busca do dia (5 temas) ao brasil.json do app.

Uso: python3 montar_temas.py brasil.json pasta_documental pasta_ust pasta_mensal pasta_consultoria pasta_servicos
Cada pasta tem o ultima.json escrito por busca_diaria.py. O brasil.json ganha:
  temas:  {chave: {nome, verificado, itens: {controle: [nota, volume_txt, link_portal]}}}
  extras: registros (já decodificados) de licitações dos temas que não estavam na coleta geral.
Só entra o que o PNCP informou; nada é estimado.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

TEMAS = [
    ("documental", "📄 GED e digitalização"),
    ("ust", "⚙️ UST e Ponto de Função"),
    ("mensal", "💻 Fixo mensal de TI"),
    ("consultoria", "🧠 Consultoria em TI"),
    ("servicos", "🛠️ Serviços de TIC"),
]
UNID = {"ust": "UST", "ust_doc": "UST", "pf": "PF", "pf_doc": "PF", "hora": "horas", "pagina": "páginas",
        "caixa": "caixas", "registro": "registros", "metro_linear": "metros lineares"}


def num(q):
    return f"{q:,.0f}".replace(",", ".")


def volume(e):
    v, vistos = e.get("vol") or {}, set()
    out = []
    for k, q in v.items():
        u = UNID.get(k, k)
        if q and u not in vistos:
            vistos.add(u)
            out.append(f"{num(q)} {u}" + (" (edital)" if k.endswith("_doc") else ""))
    return " · ".join(out)


def esfera(e):
    n = (e.get("esfera_nome") or "").lower()
    return {"municipal": "M", "estadual": "E", "federal": "F", "distrital": "D"}.get(n, "N")


def main():
    arq, pastas = sys.argv[1], sys.argv[2:7]
    B = json.load(open(arq))
    conhecidos = {r[0] for r in B["registros"]}
    agora = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
    temas, extras, vistos = {}, [], set()
    for (chave, nome), pasta in zip(TEMAS, pastas):
        try:
            d = json.load(open(f"{pasta}/ultima.json"))
        except (OSError, ValueError):
            continue
        itens = {}
        for e in d.get("licitacoes", []):
            c, fim = e["numero_controle_pncp"], (e.get("encerramento") or "")[:16]
            if not fim or fim <= agora:
                continue
            itens[c] = [e.get("nota") or 0, volume(e), e.get("link_origem") or ""]
            if c not in conhecidos and c not in vistos:
                vistos.add(c)
                host = urlparse(e.get("link_origem") or "").hostname or ""
                extras.append([c, e.get("orgao_nome") or "", e.get("municipio_nome") or "", e.get("uf") or "",
                               e.get("modalidade") or "", e.get("valor") or 0, 1 if "sigilo" in (e.get("sigiloso") or "").lower() and "sem" not in (e.get("sigiloso") or "").lower() else 0,
                               fim, " ".join((e.get("objeto") or "").split())[:170], e.get("plataforma") or host,
                               "Gestão documental" if chave == "documental" else "Tecnologia (TI)", esfera(e), (e.get("abertura") or "")[:16]])
        temas[chave] = {"nome": nome, "verificado": d.get("verificado_em", "")[:16], "itens": itens}
        print(f"{chave}: {len(itens)} no prazo ({d.get('verificado_em', '')[:16]})")
    B["temas"], B["extras"] = temas, extras
    json.dump(B, open(arq, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(extras)} licitações dos temas acrescentadas à lista geral")


if __name__ == "__main__":
    main()
