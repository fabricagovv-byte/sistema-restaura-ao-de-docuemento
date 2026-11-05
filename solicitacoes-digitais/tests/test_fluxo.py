import pytest

from solicitacoes import fluxo

from .apoio import cenario, nova, tramitar


def ciclo_completo(c, ids, h, cat):
    s = nova(c, h["solicitante"], cat)
    sid = s["id"]
    assert tramitar(c, h["operador"], sid, "em_triagem").status_code == 200
    r = tramitar(c, h["operador"], sid, "em_atendimento")
    assert r.status_code == 409 and "responsável" in r.json()["detail"]
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["operador"]).status_code == 200
    assert tramitar(c, h["operador"], sid, "em_atendimento").status_code == 200
    assert tramitar(c, h["operador"], sid, "aguardando_solicitante").status_code == 422  # sem comentário
    assert tramitar(c, h["operador"], sid, "aguardando_solicitante", "Envie o número do documento").status_code == 200
    assert tramitar(c, h["solicitante"], sid, "em_atendimento", "Número 12345").status_code == 200
    r = tramitar(c, h["operador"], sid, "concluida", "Segunda via emitida")
    assert r.status_code == 200 and r.json()["status"] == "concluida" and r.json()["acoes_possiveis"] == []
    return sid


def test_fluxo_completo_com_historico_e_auditoria(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = ciclo_completo(c, ids, h, cat)
    hist = c.get(f"/api/v1/solicitacoes/{sid}/historico", headers=h["solicitante"]).json()
    passos = [(x["evento"], x["de_status"], x["para_status"]) for x in hist]
    assert passos == [("criacao", None, "recebida"), ("transicao", "recebida", "em_triagem"), ("atribuicao", None, None),
                      ("transicao", "em_triagem", "em_atendimento"), ("transicao", "em_atendimento", "aguardando_solicitante"),
                      ("transicao", "aguardando_solicitante", "em_atendimento"), ("transicao", "em_atendimento", "concluida")]
    assert hist[-1]["comentario"] == "Segunda via emitida" and hist[-1]["ator"]["id"] == ids["operador"]
    ev = c.get("/api/v1/auditoria", params={"recurso": "solicitacao", "recurso_id": str(sid)}, headers=h["gestor"]).json()
    assert [e["acao"] for e in reversed(ev)] == ["criar", "tramitar", "atribuir", "tramitar", "tramitar", "tramitar", "tramitar"]


def test_transicoes_invalidas_sao_bloqueadas_com_motivo(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    r = tramitar(c, h["gestor"], sid, "concluida", "pulando etapas")
    assert r.status_code == 409 and "a partir de recebida: cancelada, em_triagem" in r.json()["detail"]
    assert tramitar(c, h["solicitante"], sid, "em_triagem").status_code == 403
    assert tramitar(c, h["gestor"], sid, "status_inventado").status_code == 422
    assert tramitar(c, h["solicitante2"], sid, "cancelada", "não é minha").status_code == 404


def test_somente_responsavel_atende_e_operador_so_assume_para_si(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    tramitar(c, h["gestor"], sid, "em_triagem")
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador2"]}, headers=h["operador"]).status_code == 403
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["solicitante"]}, headers=h["gestor"]).status_code == 422
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador2"]}, headers=h["gestor"]).status_code == 200
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["operador"]).status_code == 404  # já não vê
    assert tramitar(c, h["operador2"], sid, "em_atendimento").status_code == 200
    assert tramitar(c, h["gestor"], sid, "concluida", "gestor pode concluir").status_code == 200


def test_cancelamento_pelo_solicitante_e_reabertura_pelo_gestor(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    assert tramitar(c, h["solicitante"], sid, "cancelada").status_code == 422
    assert tramitar(c, h["solicitante"], sid, "cancelada", "Resolvi de outra forma").status_code == 200
    assert tramitar(c, h["gestor"], sid, "em_triagem", "reabrir").status_code == 409  # cancelada não reabre
    sid2 = ciclo_completo(c, ids, h, cat)
    assert tramitar(c, h["operador"], sid2, "em_triagem", "quero reabrir").status_code == 403
    r = tramitar(c, h["gestor"], sid2, "em_triagem", "Documento saiu com erro")
    assert r.status_code == 200 and r.json()["responsavel"] is None  # volta para a fila


def test_arquivamento_so_de_finalizadas_e_bloqueia_tramitacao(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    arq = lambda quem, v=True: c.post(f"/api/v1/solicitacoes/{sid}/arquivamento", json={"arquivar": v}, headers=h[quem])  # noqa: E731
    assert arq("gestor").status_code == 409
    tramitar(c, h["gestor"], sid, "em_triagem")
    tramitar(c, h["gestor"], sid, "indeferida", "Fora do escopo do órgão")
    assert arq("operador").status_code == 403
    assert arq("gestor").status_code == 200 and arq("gestor").status_code == 409
    assert c.get("/api/v1/solicitacoes", headers=h["gestor"]).json()["total"] == 0
    assert c.get("/api/v1/solicitacoes", params={"arquivada": True}, headers=h["gestor"]).json()["total"] == 1
    assert tramitar(c, h["gestor"], sid, "em_triagem", "reabrir").status_code == 409
    assert arq("gestor", False).status_code == 200
    assert tramitar(c, h["gestor"], sid, "em_triagem", "Reaberta após recurso").status_code == 200


@pytest.mark.parametrize("de,para", sorted(fluxo.TRANSICOES))
def test_toda_transicao_declarada_tem_perfil_e_estados_validos(de, para):
    t = fluxo.TRANSICOES[(de, para)]
    assert de in fluxo.ESTADOS and para in fluxo.ESTADOS and t.perfis
    assert de not in fluxo.FINAIS or para == "em_triagem"  # de estado final só se sai por reabertura
