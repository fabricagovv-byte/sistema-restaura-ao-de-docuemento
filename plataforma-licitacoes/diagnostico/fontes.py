"""Diagnóstico das fontes: grava a resposta crua (status, cabeçalhos, início do corpo) de cada variante.

Uso: python fontes.py saida.json
"""
import json
import ssl
import sys
from datetime import date, timedelta

import httpx

H = date.today()
D = lambda n: (H - timedelta(days=n)).isoformat()  # noqa: E731
UA = {"User-Agent": "PlataformaLicitacoes/5.0 diagnostico", "Accept": "application/json"}

ctx_legado = ssl.create_default_context()
ctx_legado.set_ciphers("DEFAULT:@SECLEVEL=1")
ctx_legado.minimum_version = ssl.TLSVersion.TLSv1_2

TESTES = [
    ("comprasgov_14133_ultimos3d", "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
     {"pagina": 1, "tamanhoPagina": 10, "dataPublicacaoPncpInicial": D(3), "dataPublicacaoPncpFinal": D(0), "codigoModalidade": 6}),
    ("comprasgov_14133_mes", "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
     {"pagina": 1, "tamanhoPagina": 10, "dataPublicacaoPncpInicial": D(30), "dataPublicacaoPncpFinal": D(20), "codigoModalidade": 6}),
    ("comprasgov_legado", "https://dadosabertos.compras.gov.br/modulo-legado/1_consultarLicitacao",
     {"pagina": 1, "data_publicacao_inicial": D(30), "data_publicacao_final": D(25)}),
    ("comprasgov_api_docs", "https://dadosabertos.compras.gov.br/v3/api-docs", None),
    ("querido_diario_api", "https://api.queridodiario.ok.org.br/gazettes", {"querystring": "licitação", "size": 1}),
    ("querido_diario_site_api", "https://queridodiario.ok.org.br/api/gazettes", {"querystring": "licitação", "size": 1}),
    ("querido_diario_busca_real", "https://queridodiario.ok.org.br/api/gazettes",
     {"querystring": '"digitalização" licitação', "published_since": D(7), "published_until": D(0), "size": 2,
      "excerpt_size": 300, "number_of_excerpts": 2, "sort_by": "descending_date"}),
    ("pncp_arquivos", "https://pncp.gov.br/api/pncp/v1/orgaos/44531788000138/compras/2026/168/arquivos", None),
]


def chamar(url, params, verify):
    try:
        with httpx.Client(timeout=60, headers=UA, follow_redirects=True, verify=verify) as c:
            r = c.get(url, params=params)
        corpo = r.text
        if "api-docs" in url and r.status_code == 200:
            try:
                d = r.json()
                corpo = json.dumps({p: {m: [(x.get("name"), x.get("required"), (x.get("schema") or {}).get("format"))
                                            for x in (v.get("parameters") or [])] for m, v in ops.items()}
                                    for p, ops in d.get("paths", {}).items()
                                    if "contratac" in p or "legado/1_" in p or "pregao" in p.lower()}, ensure_ascii=False)
                return {"status": r.status_code, "url": str(r.url), "corpo": corpo[:40000]}
            except ValueError:
                pass
        return {"status": r.status_code, "url": str(r.url), "content_type": r.headers.get("content-type"),
                "corpo": corpo[:6000]}
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {e}"}


saida = {}
for nome, url, params in TESTES:
    saida[nome] = {"padrao": chamar(url, params, True)}
    if "erro" in saida[nome]["padrao"]:
        saida[nome]["tls_legado"] = chamar(url, params, ctx_legado)
json.dump(saida, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: {m: (v.get("status") or v.get("erro")) for m, v in x.items()} for k, x in saida.items()}, indent=1))
