"""Conectores com respostas HTTP simuladas (o conteúdo é de respostas reais do PNCP)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from licitacoes.conectores.base import AcessoNegado, ClienteHttp, LimiteDeAcesso
from licitacoes.conectores.outras import ESPELHOS, ConectorEspelhos, normalizar_diario
from licitacoes.conectores.pncp import ConectorPncp, normalizar_arquivo, normalizar_contratacao


def cliente(rotas, esperas=None):
    chamadas = []

    def handler(req: httpx.Request):
        chamadas.append(req)
        for cond, resp in rotas:
            if cond(req):
                r = resp(req) if callable(resp) else resp
                if isinstance(r, list):
                    return r.pop(0) if len(r) > 1 else r[0]
                return r
        return httpx.Response(404)

    dormidas = esperas if esperas is not None else []
    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(handler)),
                       dormir=dormidas.append)
    return http, chamadas, dormidas


def test_paginacao_e_datas(pncp_pagina):
    ultima = dict(pncp_pagina, paginasRestantes=0, numeroPagina=2)
    http, chamadas, _ = cliente([
        (lambda r: r.url.params.get("pagina") == "1", httpx.Response(200, json=pncp_pagina)),
        (lambda r: r.url.params.get("pagina") == "2", httpx.Response(200, json=ultima)),
    ])
    c = ConectorPncp(http)
    itens = list(c.propostas_abertas(date(2026, 12, 31), modalidade=6, uf="MG"))
    assert len(itens) == 20
    p = chamadas[0].url.params
    assert p["dataFinal"] == "20261231"          # AAAAMMDD: ISO dá 422 no PNCP
    assert p["codigoModalidadeContratacao"] == "6" and p["uf"] == "MG"
    assert 10 <= int(p["tamanhoPagina"]) <= 50


def test_204_e_sem_registros():
    http, _, _ = cliente([(lambda r: True, httpx.Response(204))])
    assert list(ConectorPncp(http).por_publicacao(date(2026, 1, 1), date(2026, 1, 1), 2)) == []


def test_429_espera_e_tenta_de_novo(pncp_pagina):
    final = dict(pncp_pagina, paginasRestantes=0)
    respostas = [httpx.Response(429, text="<html>Too Many</html>"), httpx.Response(200, json=final)]
    http, _, dormidas = cliente([(lambda r: True, respostas)])
    itens = list(ConectorPncp(http).propostas_abertas(date(2026, 12, 31)))
    assert len(itens) == 10
    assert dormidas[0] == 30  # primeiro degrau de espera


def test_429_persistente_vira_erro():
    http, _, _ = cliente([(lambda r: True, httpx.Response(429))])
    http.esperas_429_s = [1, 1]
    with pytest.raises(LimiteDeAcesso):
        list(ConectorPncp(http).propostas_abertas(date(2026, 12, 31)))


def test_410_edital_excluido_vira_none():
    http, _, _ = cliente([(lambda r: True, httpx.Response(410, text="A contratação informada foi excluída"))])
    assert ConectorPncp(http).contratacao("06015041000138", 2026, 62) is None


def test_403_nao_e_contornado():
    http, _, _ = cliente([(lambda r: True, httpx.Response(403))])
    with pytest.raises(AcessoNegado):
        http.get_json("https://exemplo.gov.br/x")


def test_normalizar_contratacao_real(pncp_pagina):
    d = normalizar_contratacao(pncp_pagina["data"][0])
    assert d["chave"] == "pncp:18278051000145-1-000133/2026"
    assert d["uf"] == "MG" and d["municipio"] == "Paracatu" and d["codigo_ibge"] == "3147006"
    assert d["link_pncp"] == "https://pncp.gov.br/app/editais/18278051000145/2026/133"
    assert d["modalidade_id"] == 6
    assert d["data_encerramento"].year == 2026


def test_normalizar_arquivo_monta_url():
    d = normalizar_arquivo({"sequencialDocumento": 3, "titulo": "Termo de Referência", "tipoDocumentoNome": "Termo de Referência"},
                           "44531788000138", 2026, 168)
    assert d["url"].endswith("/orgaos/44531788000138/compras/2026/168/arquivos/3")


def test_espelho_csv_real():
    conteudo = (__import__("pathlib").Path(__file__).parent / "fixtures" / "espelho_radar_amostra.csv").read_bytes()
    esp = next(e for e in ESPELHOS if e["formato"] == "csv_radar")
    regs = list(ConectorEspelhos(http=ClienteHttp(intervalo_minimo_s=0)).registros(esp, conteudo))
    assert len(regs) == 40
    assert all(r["chave"].startswith("pncp:") and r["link_pncp"].startswith("https://pncp.gov.br/app/editais/") for r in regs)


def test_diario_vira_aviso_com_link_original():
    avisos = normalizar_diario({"territory_id": "3550308", "territory_name": "São Paulo", "state_code": "SP",
                                "date": "2026-10-30", "url": "https://diario.exemplo/2026-10-30.pdf",
                                "excerpts": ["AVISO DE LICITAÇÃO — digitalização de acervo", "outro trecho"]}, "x")
    assert len(avisos) == 2 and avisos[0]["link_origem"].endswith(".pdf") and avisos[0]["codigo_ibge"] == "3550308"


def test_pncp_integracao_usa_caminho_alternativo_quando_o_principal_cai():
    import httpx

    from licitacoes.conectores.base import ClienteHttp
    from licitacoes.conectores.pncp import INTEGRACAO_ALT, ConectorPncp

    chamadas = []

    def responder(req):
        chamadas.append(str(req.url))
        if "/api/pncp/v1/" in str(req.url):
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, json=[{"numeroItem": 1, "descricao": "Digitalização", "unidadeMedida": "UST"}])

    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(responder)), dormir=lambda x: None)
    c = ConectorPncp(http)
    assert c.itens("00394502000144", 2026, 14826)[0]["descricao"] == "Digitalização"
    assert c.bases_integracao[0] == INTEGRACAO_ALT
    n = len(chamadas)
    c.arquivos("00394502000144", 2026, 14826)
    assert len(chamadas) == n + 1 and "/pncp-api/v1/" in chamadas[-1]  # vai direto no que respondeu
