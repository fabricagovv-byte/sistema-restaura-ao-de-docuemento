"""Monta brasil.json para a aba 'Brasil' do app: todas as abertas (todas_abertas.py) + previstas no PCA (previstas_links.json).
Uso: python montar_brasil.py todas_abertas.json previstas_links.json brasil.json
"""
import json, re, sys
from datetime import date

todas, prev, saida = sys.argv[1:4]
B = json.load(open(todas))


def dt(s):
    try:
        d, m, a = s.split("/")
        return date(int(a), int(m), int(d))
    except Exception:  # noqa: BLE001
        return None


hoje = date.fromisoformat(B["verificado_em"][:10])
P = []
for c in json.load(open(prev)):
    d = dt(c.get("data") or "")
    if not d or d < hoje:
        continue
    nome = c.get("nome") or "; ".join(x for x in c.get("desc") or [] if re.search(r"[a-z]", x, re.I))[:160]
    P.append({"orgao": c["orgao"].title(), "unidade": (c.get("unidade") or "").strip(), "nome": " ".join(nome.split())[:220],
              "valor": round(c.get("valor") or 0), "data": c["data"], "ano": c.get("ano_pca"), "pca": c.get("pca_link"),
              "publicado": (c.get("publicado") or {}).get("link")})
P.sort(key=lambda x: (dt(x["data"]), -x["valor"]))
B["previstas"] = P
# compacta: textos repetidos (órgão, município, modalidade, portal, assunto) viram índices de tabela; objeto até 170 caracteres
tab = {k: [] for k in ("o", "m", "mod", "p", "a")}
idx = {k: {} for k in tab}


def ix(k, v):
    if v not in idx[k]:
        idx[k][v] = len(tab[k])
        tab[k].append(v)
    return idx[k][v]


B["registros"] = [[r[0], ix("o", r[1]), ix("m", r[2]), r[3], ix("mod", r[4]), r[5], r[6], r[7], r[8][:170], ix("p", r[9]), ix("a", r[10]), r[11], r[12]]
                  for r in B["registros"]]
B["tab"] = tab
json.dump(B, open(saida, "w"), ensure_ascii=False, separators=(",", ":"))
print(B["total"], "abertas,", B.get("a_vir"), "a vir,", len(P), "previstas ->", saida)
