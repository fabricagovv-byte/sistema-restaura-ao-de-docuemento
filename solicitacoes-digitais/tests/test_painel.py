"""Painel gerencial e exportação CSV (REQ-004): permissão, conciliação com os registros, prazo, filtros e CSV seguro."""

import csv
import hashlib
import io
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from solicitacoes import rotas_painel
from solicitacoes.banco import sessao
from solicitacoes.modelos import EventoAuditoria, HistoricoSolicitacao, Solicitacao

from .apoio import cenario, nova, tramitar

IND = "/api/v1/painel/indicadores"
CSV = "/api/v1/painel/exportacao.csv"


def _ler_csv(r) -> list[dict]:
    assert r.status_code == 200, r.text
    assert r.content.startswith("﻿".encode())  # BOM para o Excel em português
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def _atender(c, h, ids, sid, final="concluida", operador="operador", triar=True):
    if triar:
        assert tramitar(c, h["gestor"], sid, "em_triagem").status_code == 200
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids[operador]}, headers=h["gestor"]).status_code == 200
    assert tramitar(c, h[operador], sid, "em_atendimento").status_code == 200
    if final:
        assert tramitar(c, h[operador], sid, final, "resposta ao cidadão").status_code == 200


def _ajustar(sid, **campos):
    with sessao() as s:
        sol = s.get(Solicitacao, sid)
        for k, v in campos.items():
            setattr(sol, k, v)


def _fim(sid, quando):
    """Desloca o momento da última transição registrada (simula atendimento em outra data)."""
    with sessao() as s:
        h = s.scalars(select(HistoricoSolicitacao).where(HistoricoSolicitacao.solicitacao_id == sid)
                      .order_by(HistoricoSolicitacao.id.desc())).first()
        h.em = quando


@pytest.fixture()
def carteira(app_cliente):
    """Nove solicitações em todos os estados, com duas categorias, duas prioridades e dois operadores."""
    c = app_cliente
    ids, h, cat = cenario(c)
    cat2 = c.post("/api/v1/categorias", json={"nome": "Alvará", "prazo_dias": 10}, headers=h["administrador"]).json()
    s = {}
    s["recebida"] = nova(c, h["solicitante"], cat)["id"]
    s["triagem"] = nova(c, h["solicitante"], cat2, prioridade="alta")["id"]
    tramitar(c, h["gestor"], s["triagem"], "em_triagem")
    s["atendimento"] = nova(c, h["solicitante2"], cat)["id"]
    _atender(c, h, ids, s["atendimento"], final=None)
    s["aguardando"] = nova(c, h["solicitante2"], cat2, prioridade="urgente")["id"]
    _atender(c, h, ids, s["aguardando"], final="aguardando_solicitante", operador="operador2")
    s["concluida"] = nova(c, h["solicitante"], cat)["id"]
    _atender(c, h, ids, s["concluida"])
    s["indeferida"] = nova(c, h["solicitante"], cat2)["id"]
    _atender(c, h, ids, s["indeferida"], final="indeferida", operador="operador2")
    s["cancelada"] = nova(c, h["solicitante2"], cat)["id"]
    tramitar(c, h["solicitante2"], s["cancelada"], "cancelada", "desisti")
    s["arquivada"] = nova(c, h["solicitante"], cat)["id"]
    _atender(c, h, ids, s["arquivada"])
    assert c.post(f"/api/v1/solicitacoes/{s['arquivada']}/arquivamento", json={}, headers=h["gestor"]).status_code == 200
    s["outra"] = nova(c, h["solicitante2"], cat)["id"]
    return c, ids, h, cat, cat2, s


def test_so_o_gestor_ve_e_exporta(carteira):
    c, ids, h, *_ = carteira
    for rota in (IND, CSV):
        assert c.get(rota, headers=h["gestor"]).status_code == 200
        for perfil in ("administrador", "operador", "solicitante"):
            assert c.get(rota, headers=h[perfil]).status_code == 403, (rota, perfil)
        assert c.get(rota).status_code == 401


def test_indicadores_conciliam_com_os_registros_e_com_o_csv(carteira):
    c, ids, h, cat, cat2, s = carteira
    ind = c.get(IND, headers=h["gestor"]).json()
    assert ind["total"] == 8 and ind["abertas"] == 5  # arquivada fica de fora por padrão
    assert ind["por_status"] == {"recebida": 2, "em_triagem": 1, "em_atendimento": 1, "aguardando_solicitante": 1,
                                 "concluida": 1, "indeferida": 1, "cancelada": 1}
    # cada contagem bate com a listagem da API e com a soma das outras dimensões
    for st, n in ind["por_status"].items():
        assert c.get("/api/v1/solicitacoes", params={"status": st}, headers=h["gestor"]).json()["total"] == n, st
    for dim in ("por_categoria", "por_responsavel"):
        assert sum(x["total"] for x in ind[dim]) == ind["total"], dim
    assert sum(ind["por_prioridade"].values()) == ind["total"]
    assert ind["por_prioridade"] == {"baixa": 0, "normal": 6, "alta": 1, "urgente": 1}
    assert {x["nome"]: (x["total"], x["abertas"]) for x in ind["por_categoria"]} == {"Segunda via de documento": (5, 3), "Alvará": (3, 2)}
    resp = {x["nome"]: (x["id"], x["total"], x["abertas"]) for x in ind["por_responsavel"]}
    assert resp == {"Sem responsável": (None, 4, 3), "Operador": (ids["operador"], 2, 1), "Operador2": (ids["operador2"], 2, 1)}
    assert ind["por_responsavel"][0]["id"] is None  # a fila sem dono aparece primeiro
    linhas = _ler_csv(c.get(CSV, headers=h["gestor"]))
    assert len(linhas) == ind["total"]
    assert {st: sum(1 for x in linhas if x["status"] == st) for st in ind["por_status"]} == ind["por_status"]
    # com os arquivados incluídos, o painel e o CSV continuam batendo
    ind_tudo = c.get(IND, params={"arquivadas": "incluir"}, headers=h["gestor"]).json()
    assert ind_tudo["total"] == 9 and len(_ler_csv(c.get(CSV, params={"arquivadas": "incluir"}, headers=h["gestor"]))) == 9
    so_arq = _ler_csv(c.get(CSV, params={"arquivadas": "somente"}, headers=h["gestor"]))
    assert [(x["arquivada"], x["status"]) for x in so_arq] == [("sim", "concluida")]


def test_indicadores_de_prazo_e_tempo_medio(carteira):
    c, ids, h, cat, cat2, s = carteira
    agora = datetime.now(timezone.utc)
    _ajustar(s["recebida"], prazo_em=agora - timedelta(days=1))           # aberta e atrasada
    _ajustar(s["atendimento"], prazo_em=agora + timedelta(hours=20))      # vence em 48h
    _ajustar(s["concluida"], criado_em=agora - timedelta(hours=10), prazo_em=agora + timedelta(days=4))
    _fim(s["concluida"], agora)                                           # concluída em 10 h, no prazo
    _ajustar(s["indeferida"], prazo_em=agora - timedelta(days=2))
    _fim(s["indeferida"], agora - timedelta(days=1))                      # indeferida um dia depois do prazo
    ind = c.get(IND, headers=h["gestor"]).json()
    p = ind["prazo"]
    assert p == {"abertas_no_prazo": 4, "abertas_atrasadas": 1, "vencem_em_48h": 1, "atendidas_no_prazo": 1,
                 "atendidas_com_atraso": 1, "canceladas": 1, "sem_prazo": 0, "percentual_atendidas_no_prazo": 50.0}
    assert p["abertas_no_prazo"] + p["abertas_atrasadas"] == ind["abertas"]
    assert ind["tempo_medio_conclusao_horas"] == pytest.approx(10, abs=0.05)
    assert {x["nome"]: x["atrasadas"] for x in ind["por_responsavel"]}["Sem responsável"] == 1
    situacao = {x["protocolo"][-6:].lstrip("0"): x["situacao_prazo"] for x in _ler_csv(c.get(CSV, headers=h["gestor"]))}
    assert situacao[str(s["recebida"])] == "atrasada" and situacao[str(s["atendimento"])] == "no_prazo"
    assert situacao[str(s["concluida"])] == "atendida_no_prazo" and situacao[str(s["indeferida"])] == "atendida_com_atraso"
    assert situacao[str(s["cancelada"])] == "cancelada"


def test_reaberta_e_concluida_de_novo_conta_uma_vez_pela_ultima_conclusao(carteira):
    c, ids, h, cat, cat2, s = carteira
    sid = s["concluida"]
    assert tramitar(c, h["gestor"], sid, "em_triagem", "faltou documento").status_code == 200
    _atender(c, h, ids, sid, operador="operador2", triar=False)  # a reabertura já devolve para a triagem
    agora = datetime.now(timezone.utc)
    _ajustar(sid, prazo_em=agora - timedelta(hours=1))
    with sessao() as db:  # a primeira conclusão foi antes do prazo, a segunda (atual) depois
        primeira = db.scalars(select(HistoricoSolicitacao).where(HistoricoSolicitacao.solicitacao_id == sid,
                                                                 HistoricoSolicitacao.para_status == "concluida")
                              .order_by(HistoricoSolicitacao.id)).first()
        primeira.em = agora - timedelta(days=1)
    ind = c.get(IND, headers=h["gestor"]).json()
    # a reaberta conta uma vez, pela conclusão atual (atrasada); a outra atendida no prazo é a indeferida da carteira
    assert ind["prazo"]["atendidas_com_atraso"] == 1 and ind["prazo"]["atendidas_no_prazo"] == 1
    linhas = [x for x in _ler_csv(c.get(CSV, headers=h["gestor"])) if x["protocolo"].endswith(f"{sid:06d}")]
    assert len(linhas) == 1 and linhas[0]["situacao_prazo"] == "atendida_com_atraso" and linhas[0]["responsavel"] == "Operador2"


def test_filtros_valem_igual_para_painel_e_csv(carteira):
    c, ids, h, cat, cat2, s = carteira
    casos = [({"categoria_id": cat2["id"]}, 3), ({"prioridade": "urgente"}, 1), ({"status": "recebida"}, 2),
             ({"responsavel_id": ids["operador2"]}, 2), ({"sem_responsavel": "true"}, 4),
             ({"categoria_id": cat["id"], "status": "concluida"}, 1)]
    for params, esperado in casos:
        ind = c.get(IND, params=params, headers=h["gestor"]).json()
        assert ind["total"] == esperado, params
        assert len(_ler_csv(c.get(CSV, params=params, headers=h["gestor"]))) == esperado, params
    assert c.get(IND, params={"categoria_id": cat2["id"]}, headers=h["gestor"]).json()["filtros"] == {"categoria_id": cat2["id"], "arquivadas": "excluir"}
    for invalido in ({"de": "2026-03-10", "ate": "2026-03-01"}, {"responsavel_id": ids["operador"], "sem_responsavel": "true"},
                     {"status": "pendente"}, {"prioridade": "maxima"}, {"de": "ontem"}, {"categoria_id": 0}, {"arquivadas": "todas"}):
        assert c.get(IND, params=invalido, headers=h["gestor"]).status_code == 422, invalido
        assert c.get(CSV, params=invalido, headers=h["gestor"]).status_code == 422, invalido


def test_periodo_usa_o_dia_de_brasilia(carteira):
    c, ids, h, cat, cat2, s = carteira
    # 01/03/2026 02:30 UTC é 28/02/2026 23:30 em Brasília
    _ajustar(s["recebida"], criado_em=datetime(2026, 3, 1, 2, 30, tzinfo=timezone.utc))
    _ajustar(s["outra"], criado_em=datetime(2026, 3, 1, 3, 0, tzinfo=timezone.utc))  # 01/03 00:00 em Brasília
    def total(**p):
        return c.get(IND, params=p, headers=h["gestor"]).json()["total"]
    assert total(de="2026-02-28", ate="2026-02-28") == 1
    assert total(de="2026-03-01", ate="2026-03-01") == 1
    assert total(de="2026-02-01", ate="2026-03-31") == 2
    linha = _ler_csv(c.get(CSV, params={"de": "2026-02-28", "ate": "2026-02-28"}, headers=h["gestor"]))[0]
    assert linha["criado_em"] == "28/02/2026 23:30"


def test_csv_formato_minimizacao_e_auditoria(carteira):
    c, ids, h, cat, cat2, s = carteira
    r = c.get(CSV, headers=h["gestor"], params={"status": "recebida"})
    assert r.headers["content-type"].startswith("text/csv") and "attachment; filename=\"solicitacoes-" in r.headers["content-disposition"]
    texto = r.content.decode("utf-8-sig")
    assert texto.splitlines()[0] == ";".join(rotas_painel.COLUNAS) and "\r\n" in texto
    assert "Preciso da segunda via" not in texto and "Solicitante" not in texto  # sem descrição nem nome do solicitante
    linhas = _ler_csv(r)
    assert {x["solicitante_id"] for x in linhas} == {str(ids["solicitante"]), str(ids["solicitante2"])}
    sha = hashlib.sha256(r.content).hexdigest()
    assert r.headers["X-Conteudo-SHA256"] == sha and r.headers["X-Total-Linhas"] == "2"
    with sessao() as db:
        ev = db.scalars(select(EventoAuditoria).where(EventoAuditoria.acao == "exportar")).one()
        assert ev.recurso == "painel" and ev.ator_id == ids["gestor"] and ev.correlacao == r.headers["X-Correlation-ID"]
        assert ev.depois == {"filtros": {"status": "recebida", "arquivadas": "excluir"}, "linhas": 2, "sha256": sha}
    # consultar indicadores não gera evento; só a exportação (saída de dados) é auditada
    c.get(IND, headers=h["gestor"])
    with sessao() as db:
        assert len(db.scalars(select(EventoAuditoria).where(EventoAuditoria.recurso == "painel")).all()) == 1


@pytest.mark.parametrize("titulo", ["=CMD|' /C calc'!A0", "+5551999999999", "-2+3+cmd", "@SUM(1+1)"])
def test_csv_neutraliza_formula_em_texto_do_usuario(carteira, titulo):
    c, ids, h, cat, cat2, s = carteira
    sid = nova(c, h["solicitante"], cat, titulo=titulo)["id"]
    linha = next(x for x in _ler_csv(c.get(CSV, headers=h["gestor"])) if x["protocolo"].endswith(f"{sid:06d}"))
    assert linha["titulo"] == "'" + titulo


def test_celula_segura_e_situacao_de_prazo():
    assert rotas_painel.celula_segura(None) == "" and rotas_painel.celula_segura(12) == "12"
    assert rotas_painel.celula_segura("linha 1\nlinha 2\r\nfim") == "linha 1 linha 2 fim"
    assert rotas_painel.celula_segura("\t=1") == "'\t=1" and rotas_painel.celula_segura("Texto = normal") == "Texto = normal"
    agora = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
    sp = rotas_painel.situacao_prazo
    assert sp("recebida", None, None, agora) == "sem_prazo"
    assert sp("concluida", agora, None, agora) == "atendida_com_atraso"  # sem registro de fim não se presume prazo cumprido
    assert sp("indeferida", agora, agora, agora) == "atendida_no_prazo"


def test_exportacao_respeita_o_limite(carteira, monkeypatch):
    c, ids, h, *_ = carteira
    monkeypatch.setattr(rotas_painel, "LIMITE_EXPORTACAO", 3)
    r = c.get(CSV, headers=h["gestor"])
    assert r.status_code == 422 and "restrinja" in r.json()["detail"]
    assert c.get(CSV, params={"status": "recebida"}, headers=h["gestor"]).status_code == 200


def test_painel_vazio(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    ind = c.get(IND, headers=h["gestor"]).json()
    assert ind["total"] == 0 and ind["por_categoria"] == [] and ind["por_responsavel"] == []
    assert ind["prazo"]["percentual_atendidas_no_prazo"] is None and ind["tempo_medio_conclusao_horas"] is None
    assert _ler_csv(c.get(CSV, headers=h["gestor"])) == []
