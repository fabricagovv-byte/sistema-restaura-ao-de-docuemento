from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from solicitacoes import banco, config as cfg_mod, seguranca
from solicitacoes.banco import sessao
from solicitacoes.modelos import Usuario

SENHA = "Senha-Forte-2026"


@pytest.fixture()
def app_cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("SD_AMBIENTE", "teste")
    pg = os.environ.get("SD_TESTE_PG")  # ex.: postgresql+psycopg://usuario:senha@localhost/sd_teste
    monkeypatch.setenv("SD_BANCO_URL", pg or f"sqlite:///{tmp_path / 'teste.db'}")
    if pg:  # banco limpo a cada teste
        from sqlalchemy import create_engine

        from solicitacoes.modelos import Base

        e = create_engine(pg)
        Base.metadata.drop_all(e)
        e.dispose()
    monkeypatch.setenv("SD_ANEXOS_DIR", str(tmp_path / "anexos"))
    monkeypatch.setenv("SD_ANEXO_MAX_MB", "1")
    monkeypatch.setenv("SD_PBKDF2_ITERACOES", "1000")  # rápido nos testes; produção usa 600 mil
    cfg_mod.config.cache_clear()
    banco.reiniciar()
    from solicitacoes.api import app

    with TestClient(app) as c:
        yield c
    banco.reiniciar()
    cfg_mod.config.cache_clear()


def criar(email: str, perfil: str, ativo: bool = True) -> int:
    with sessao() as s:
        u = Usuario(email=email, nome=email.split("@")[0].title(), perfil=perfil, senha_hash=seguranca.gerar_hash(SENHA), ativo=ativo)
        s.add(u)
        s.flush()
        return u.id


def entrar(c: TestClient, email: str, senha: str = SENHA) -> dict:
    r = c.post("/api/v1/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def perfis(app_cliente):
    ids = {p: criar(f"{p}@exemplo.gov.br", p) for p in ("administrador", "gestor", "operador", "solicitante")}
    return app_cliente, ids
