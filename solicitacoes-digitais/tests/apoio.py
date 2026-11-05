"""Cenário padrão para os testes de solicitações."""

from __future__ import annotations

from .conftest import criar, entrar


def cenario(c):
    ids = {p: criar(f"{p}@exemplo.gov.br", p) for p in ("administrador", "gestor", "operador", "solicitante")}
    ids["operador2"] = criar("operador2@exemplo.gov.br", "operador")
    ids["solicitante2"] = criar("solicitante2@exemplo.gov.br", "solicitante")
    h = {k: entrar(c, f"{k}@exemplo.gov.br") for k in ids}
    cat = c.post("/api/v1/categorias", json={"nome": "Segunda via de documento", "prazo_dias": 5}, headers=h["administrador"]).json()
    return ids, h, cat


def nova(c, h, cat, titulo="Pedido de segunda via", **extra):
    corpo = {"titulo": titulo, "descricao": "Preciso da segunda via do documento perdido.", "categoria_id": cat["id"], **extra}
    r = c.post("/api/v1/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def tramitar(c, h, sid, para, comentario=None):
    return c.post(f"/api/v1/solicitacoes/{sid}/tramitar", json={"para": para, "comentario": comentario}, headers=h)
