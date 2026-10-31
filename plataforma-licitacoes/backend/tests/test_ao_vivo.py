"""Testes contra as fontes reais. Rodam só com LIC_TESTES_AO_VIVO=1 (precisam de rede liberada).

    LIC_TESTES_AO_VIVO=1 pytest tests/test_ao_vivo.py -v
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("LIC_TESTES_AO_VIVO") != "1", reason="defina LIC_TESTES_AO_VIVO=1")


def test_pncp_propostas_abertas():
    from licitacoes.conectores.base import ClienteHttp
    from licitacoes.conectores.pncp import ConectorPncp, normalizar_contratacao

    c = ConectorPncp(ClienteHttp(intervalo_minimo_s=4))
    primeiro = next(iter(c.propostas_abertas(date.today() + timedelta(days=10), modalidade=6, uf="SP")))
    d = normalizar_contratacao(primeiro)
    assert d["uf"] == "SP" and d["link_pncp"].startswith("https://pncp.gov.br/app/editais/")
    arquivos = c.arquivos(d["cnpj_orgao"], d["ano"], d["sequencial"])
    assert isinstance(arquivos, list)


def test_comprasgov_dados_abertos():
    from licitacoes.conectores.outras import ConectorComprasGov, normalizar_comprasgov_14133

    c = ConectorComprasGov()
    hoje = date.today()
    registro = next(iter(c.contratacoes_14133(hoje - timedelta(days=3), hoje, 6)), None)
    assert registro is not None
    assert normalizar_comprasgov_14133(registro)["objeto"]


def test_querido_diario():
    from licitacoes.conectores.outras import ConectorQueridoDiario

    hoje = date.today()
    diarios = list(c for _, c in zip(range(5), ConectorQueridoDiario().buscar('"digitalização" licitação', hoje - timedelta(days=30), hoje)))
    assert diarios and diarios[0].get("url")


def test_ibge_municipios():
    from licitacoes.conectores.outras import ConectorIbge

    m = ConectorIbge().municipios()
    assert len(m) > 5500 and all(x["uf"] for x in m)
