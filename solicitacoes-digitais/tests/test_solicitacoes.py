from datetime import datetime, timedelta, timezone

from solicitacoes.banco import sessao
from solicitacoes.modelos import Solicitacao

from .apoio import cenario, nova, tramitar


def test_cria_com_protocolo_prazo_e_historico(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    s = nova(c, h["solicitante"], cat)
    assert s["status"] == "recebida" and s["protocolo"] == f"{datetime.now(timezone.utc).year}{s['id']:06d}"
    assert s["solicitante"]["id"] == ids["solicitante"] and s["responsavel"] is None and s["categoria"] == cat["nome"]
    prazo = datetime.fromisoformat(s["prazo_em"])
    assert abs((prazo - datetime.fromisoformat(s["criado_em"])) - timedelta(days=5)) < timedelta(seconds=5)
    assert s["acoes_possiveis"] == ["cancelada"]
    hist = c.get(f"/api/v1/solicitacoes/{s['id']}/historico", headers=h["solicitante"]).json()
    assert [(x["evento"], x["para_status"]) for x in hist] == [("criacao", "recebida")]


def test_validacoes_de_cadastro(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    base = {"titulo": "Pedido válido", "descricao": "Descrição com tamanho suficiente.", "categoria_id": cat["id"]}
    for erro in ({"titulo": "abc"}, {"descricao": "curta"}, {"titulo": "     "}, {"categoria_id": 999}, {"prioridade": "maxima"}):
        assert c.post("/api/v1/solicitacoes", json={**base, **erro}, headers=h["solicitante"]).status_code == 422, erro
    assert c.post("/api/v1/solicitacoes", json=base, headers=h["administrador"]).status_code == 403
    assert c.post("/api/v1/solicitacoes", json=base).status_code == 401


def test_visibilidade_por_perfil(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    a = nova(c, h["solicitante"], cat, "Pedido do primeiro")
    b = nova(c, h["solicitante2"], cat, "Pedido do segundo")
    ver = lambda quem: {x["id"] for x in c.get("/api/v1/solicitacoes", headers=h[quem]).json()["itens"]}  # noqa: E731
    assert ver("solicitante") == {a["id"]} and ver("solicitante2") == {b["id"]}
    assert ver("gestor") == ver("operador") == {a["id"], b["id"]}  # fila sem responsável é de todos os operadores
    assert c.get(f"/api/v1/solicitacoes/{b['id']}", headers=h["solicitante"]).status_code == 404
    c.post(f"/api/v1/solicitacoes/{a['id']}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"])
    assert tramitar(c, h["operador"], a["id"], "em_triagem").status_code == 200
    assert ver("operador2") == {b["id"]}  # a já tem responsável
    assert c.get(f"/api/v1/solicitacoes/{a['id']}", headers=h["operador2"]).status_code == 404
    assert c.get("/api/v1/solicitacoes", headers=h["administrador"]).status_code == 403


def test_edicao_pelo_dono_so_enquanto_recebida(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    s = nova(c, h["solicitante"], cat)
    r = c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"titulo": "Título corrigido", "prioridade": "alta"}, headers=h["solicitante"])
    assert r.status_code == 200 and r.json()["titulo"] == "Título corrigido" and r.json()["prioridade"] == "alta"
    assert c.patch(f"/api/v1/solicitacoes/{s['id']}", json={}, headers=h["solicitante"]).status_code == 422
    assert c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"titulo": "Outro título"}, headers=h["solicitante2"]).status_code == 404
    tramitar(c, h["gestor"], s["id"], "em_triagem")
    assert c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"titulo": "Tarde demais"}, headers=h["solicitante"]).status_code == 409
    assert c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"titulo": "Ajuste do gestor"}, headers=h["gestor"]).status_code == 200


def test_filtros_busca_paginacao_e_atraso(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    feitos = [nova(c, h["solicitante"], cat, f"Pedido número {i}", prioridade="urgente" if i == 3 else "normal") for i in range(5)]
    r = c.get("/api/v1/solicitacoes", params={"por_pagina": 2, "pagina": 2}, headers=h["gestor"]).json()
    assert r["total"] == 5 and len(r["itens"]) == 2
    assert [x["titulo"] for x in c.get("/api/v1/solicitacoes", params={"prioridade": "urgente"}, headers=h["gestor"]).json()["itens"]] == ["Pedido número 3"]
    assert c.get("/api/v1/solicitacoes", params={"q": "PEDIDO número 4"}, headers=h["gestor"]).json()["total"] == 1
    assert c.get("/api/v1/solicitacoes", params={"q": feitos[2]["protocolo"]}, headers=h["gestor"]).json()["total"] == 1
    with sessao() as s:  # vence o prazo de uma
        s.get(Solicitacao, feitos[0]["id"]).prazo_em = datetime.now(timezone.utc) - timedelta(days=1)
    atras = c.get("/api/v1/solicitacoes", params={"atrasada": True}, headers=h["gestor"]).json()
    assert [x["id"] for x in atras["itens"]] == [feitos[0]["id"]] and atras["itens"][0]["atrasada"]
    assert c.get("/api/v1/solicitacoes", params={"atrasada": False}, headers=h["gestor"]).json()["total"] == 4


def test_nao_ha_exclusao(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    s = nova(c, h["solicitante"], cat)
    assert c.delete(f"/api/v1/solicitacoes/{s['id']}", headers=h["gestor"]).status_code == 405
