"""Cada teste roda num banco novo. Por padrão SQLite; com LIC_TESTE_PG=<url> roda no PostgreSQL."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _sem_esperas_longas(monkeypatch):
    """Nos testes, falha simulada do PNCP não espera as rodadas extras de 30/60/120 s."""
    monkeypatch.setenv("LIC_PNCP_ESPERAS_PAGINA", "")
    from licitacoes import config

    config.config.cache_clear()
    yield
    config.config.cache_clear()


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    url = os.environ.get("LIC_TESTE_PG") or f"sqlite:///{tmp_path / 'teste.db'}"
    monkeypatch.setenv("LIC_DATABASE_URL", url)
    monkeypatch.setenv("LIC_ARMAZENAMENTO_DIR", str(tmp_path / "arquivos"))
    monkeypatch.setenv("LIC_AUTH_OBRIGATORIA", "true")
    monkeypatch.setenv("LIC_PNCP_INTERVALO_S", "0")
    from licitacoes import armazenamento, config, db

    config.config.cache_clear()
    db.reiniciar_engine()
    armazenamento.reiniciar()
    if url.startswith("postgresql"):
        from sqlalchemy import text

        with db.engine().begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    db.iniciar_banco()
    s = db.nova_sessao()
    from licitacoes import catalogo

    catalogo.registrar_fontes(s)
    s.commit()
    yield s
    s.close()
    db.reiniciar_engine()
    config.config.cache_clear()


@pytest.fixture()
def pncp_pagina():
    return json.loads((FIXTURES / "pncp_proposta_mg_p1.json").read_text(encoding="utf-8"))


@pytest.fixture()
def edital_lins():
    return json.loads((FIXTURES / "edital_lins_083_2026.json").read_text(encoding="utf-8"))
