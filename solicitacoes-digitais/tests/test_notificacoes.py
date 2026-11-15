"""Notificações por e-mail (REQ-006, D8-B), testadas ponta a ponta contra um servidor SMTP de homologação local."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from solicitacoes import config as cfg_mod, notificacoes
from solicitacoes.banco import sessao
from solicitacoes.modelos import EventoAuditoria, MensagemSaida

from .apoio import cenario, nova, tramitar
from .smtp_local import ServidorSmtp, porta_livre


def usar_smtp(monkeypatch, porta, usuario="", senha="", seguranca="nenhuma"):
    monkeypatch.setenv("SD_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SD_SMTP_PORTA", str(porta))
    monkeypatch.setenv("SD_SMTP_SEGURANCA", seguranca)
    monkeypatch.setenv("SD_SMTP_USUARIO", usuario)
    monkeypatch.setenv("SD_SMTP_SENHA", senha)
    monkeypatch.setenv("SD_SMTP_REMETENTE", "nao-responda@prefeitura.exemplo.gov.br")
    monkeypatch.setenv("SD_SMTP_TIMEOUT", "5")
    cfg_mod.config.cache_clear()


def enviar(agora=None):
    with sessao() as s:
        return notificacoes.enviar_pendentes(s, agora=agora)


def caixa():
    with sessao() as s:
        return [(m.para, m.tipo, m.status, m.tentativas) for m in s.scalars(select(MensagemSaida).order_by(MensagemSaida.id))]


def test_tramitacao_avisa_o_solicitante_por_email_de_verdade(app_cliente, monkeypatch):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    assert tramitar(c, h["gestor"], sol["id"], "em_triagem").status_code == 200
    assert caixa() == [("solicitante@exemplo.gov.br", "tramitacao", "pendente", 0)]
    with ServidorSmtp() as srv:
        usar_smtp(monkeypatch, srv.porta)
        assert enviar() == {"configurado": True, "enviadas": 1, "reagendadas": 0, "falharam": 0, "na_fila": 0}
    assert caixa() == [("solicitante@exemplo.gov.br", "tramitacao", "enviada", 1)]
    (rec,) = srv.recebidas
    m = rec.mensagem
    assert rec.destinatarios == ["solicitante@exemplo.gov.br"] and rec.remetente == "nao-responda@prefeitura.exemplo.gov.br"
    assert m["Subject"] == f"Solicitação {sol['protocolo']}: em triagem" and m["Message-ID"] and m["Date"]
    corpo = m.get_content()
    assert sol["protocolo"] in corpo and "\"recebida\" para \"em triagem\"" in corpo and f"/#/solicitacoes/{sol['id']}" in corpo
    with sessao() as s:
        ev = s.scalars(select(EventoAuditoria).where(EventoAuditoria.acao == "enviar_email")).one()
        assert ev.depois == {"tipo": "tramitacao", "status": "enviada", "tentativas": 1} and "corpo" not in json.dumps(ev.depois)
    # já enviada não sai de novo
    with ServidorSmtp() as srv2:
        usar_smtp(monkeypatch, srv2.porta)
        assert enviar()["enviadas"] == 0 and srv2.recebidas == []


def test_quem_age_nao_recebe_aviso_da_propria_acao_e_pedido_de_informacao_explica(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    assert tramitar(c, h["solicitante"], sol["id"], "cancelada", "não preciso mais").status_code == 200
    assert caixa() == []  # o próprio solicitante cancelou
    sol2 = nova(c, h["solicitante"], cat, titulo="Outro pedido")
    tramitar(c, h["gestor"], sol2["id"], "em_triagem")
    c.post(f"/api/v1/solicitacoes/{sol2['id']}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"])
    tramitar(c, h["operador"], sol2["id"], "em_atendimento")
    assert tramitar(c, h["operador"], sol2["id"], "aguardando_solicitante", "Envie a cópia do RG").status_code == 200
    with sessao() as s:
        ultima = s.scalars(select(MensagemSaida).where(MensagemSaida.tipo == "tramitacao").order_by(MensagemSaida.id.desc())).first()
        assert "Envie a cópia do RG" in ultima.corpo and "Precisamos de uma informação sua" in ultima.corpo
        assert ultima.solicitacao_id == sol2["id"]


def test_atribuicao_avisa_o_responsavel_mas_nao_quem_assume_para_si(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    tramitar(c, h["gestor"], sol["id"], "em_triagem")
    assert c.post(f"/api/v1/solicitacoes/{sol['id']}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"]).status_code == 200
    sol2 = nova(c, h["solicitante"], cat, titulo="Mais um pedido")
    tramitar(c, h["gestor"], sol2["id"], "em_triagem")
    assert c.post(f"/api/v1/solicitacoes/{sol2['id']}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["operador"]).status_code == 200
    atrib = [x for x in caixa() if x[1] == "atribuicao"]
    assert atrib == [("operador@exemplo.gov.br", "atribuicao", "pendente", 0)]


def test_recuperacao_de_senha_chega_por_email_e_o_link_some_da_caixa_depois(app_cliente, monkeypatch):
    c = app_cliente
    cenario(c)
    assert c.post("/api/v1/auth/recuperar", json={"email": "operador@exemplo.gov.br"}).status_code == 202
    with ServidorSmtp() as srv:
        usar_smtp(monkeypatch, srv.porta)
        assert enviar()["enviadas"] == 1
    corpo = srv.recebidas[0].mensagem.get_content()
    token = corpo.split("#token=")[1].split()[0]
    assert c.post("/api/v1/auth/redefinir", json={"token": token, "nova_senha": "Outra-Senha-2026"}).status_code == 204
    with sessao() as s:
        m = s.scalars(select(MensagemSaida)).one()
        assert m.status == "enviada" and m.corpo == notificacoes.CORPO_APAGADO and token not in m.corpo


def test_sem_smtp_configurado_nada_sai_e_a_fila_espera(app_cliente, monkeypatch):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    tramitar(c, h["gestor"], sol["id"], "em_triagem")
    monkeypatch.delenv("SD_SMTP_HOST", raising=False)
    cfg_mod.config.cache_clear()
    assert enviar() == {"configurado": False, "enviadas": 0, "reagendadas": 0, "falharam": 0, "na_fila": 1}
    assert caixa()[0][2:] == ("pendente", 0)


def test_servidor_fora_do_ar_reagenda_com_espera_crescente_e_desiste_na_quinta(app_cliente, monkeypatch):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    tramitar(c, h["gestor"], sol["id"], "em_triagem")
    usar_smtp(monkeypatch, porta_livre())
    t0 = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    r = enviar(t0)
    assert r["reagendadas"] == 1 and r["erro_conexao"]
    with sessao() as s:
        m = s.scalars(select(MensagemSaida)).one()
        assert m.status == "pendente" and m.tentativas == 1 and m.ultimo_erro
        assert notificacoes._utc(m.proxima_tentativa_em) == t0 + timedelta(minutes=1)
    assert enviar(t0 + timedelta(seconds=30))["reagendadas"] == 0  # ainda não é hora
    t = t0
    for espera in notificacoes.ESPERAS[:-1]:
        t = t + timedelta(hours=2)
        enviar(t)
    assert caixa()[0][2:] == ("pendente", 4)
    assert enviar(t + timedelta(hours=2))["falharam"] == 1
    assert caixa()[0][2:] == ("falhou", 5)


def test_recusa_definitiva_e_temporaria_por_destinatario_no_mesmo_lote(app_cliente, monkeypatch):
    c = app_cliente
    cenario(c)
    with sessao() as s:
        for para in ("existe@exemplo.gov.br", "inexistente@exemplo.gov.br", "cheia@exemplo.gov.br", "outro@exemplo.gov.br"):
            notificacoes.enfileirar(s, para=para, assunto="Aviso", corpo="Texto de teste")
    with ServidorSmtp(recusar={"inexistente@exemplo.gov.br"}, temporario={"cheia@exemplo.gov.br"}) as srv:
        usar_smtp(monkeypatch, srv.porta)
        r = enviar()
    assert (r["enviadas"], r["falharam"], r["reagendadas"]) == (2, 1, 1)
    assert sorted(d for x in srv.recebidas for d in x.destinatarios) == ["existe@exemplo.gov.br", "outro@exemplo.gov.br"]
    estado = {p: (st, n) for p, _, st, n in caixa()}
    assert estado["inexistente@exemplo.gov.br"] == ("falhou", 1) and estado["cheia@exemplo.gov.br"] == ("pendente", 1)
    with sessao() as s:
        m = s.scalars(select(MensagemSaida).where(MensagemSaida.para == "inexistente@exemplo.gov.br")).one()
        assert "550" in m.ultimo_erro


def test_autenticacao_no_servidor_de_email(app_cliente, monkeypatch):
    c = app_cliente
    cenario(c)
    with sessao() as s:
        notificacoes.enfileirar(s, para="alguem@exemplo.gov.br", assunto="Aviso", corpo="Texto")
    with ServidorSmtp(usuario="sd", senha="certa") as srv:
        usar_smtp(monkeypatch, srv.porta, usuario="sd", senha="errada")
        r = enviar()
        assert r["reagendadas"] == 1 and r["falharam"] == 0 and "535" in r["erro_conexao"]  # senha errada não condena a mensagem
        usar_smtp(monkeypatch, srv.porta, usuario="sd", senha="certa")
        assert enviar(datetime.now(timezone.utc) + timedelta(minutes=2))["enviadas"] == 1
    assert len(srv.recebidas) == 1


def test_administrador_acompanha_e_dispara_a_caixa_sem_ver_o_corpo(app_cliente, monkeypatch):
    c = app_cliente
    ids, h, cat = cenario(c)
    sol = nova(c, h["solicitante"], cat)
    tramitar(c, h["gestor"], sol["id"], "em_triagem")
    c.post("/api/v1/auth/recuperar", json={"email": "gestor@exemplo.gov.br"})
    r = c.get("/api/v1/mensagens", headers=h["administrador"])
    assert r.status_code == 200
    d = r.json()
    assert d["smtp_configurado"] is False and d["por_status"] == {"pendente": 2, "enviada": 0, "falhou": 0}
    assert {m["tipo"] for m in d["mensagens"]} == {"tramitacao", "recuperacao_senha"}
    assert all("corpo" not in m for m in d["mensagens"]) and "token" not in r.text
    for perfil in ("gestor", "operador", "solicitante"):
        assert c.get("/api/v1/mensagens", headers=h[perfil]).status_code == 403
        assert c.post("/api/v1/mensagens/enviar", headers=h[perfil]).status_code == 403
    with ServidorSmtp() as srv:
        usar_smtp(monkeypatch, srv.porta)
        r = c.post("/api/v1/mensagens/enviar", headers=h["administrador"])
    assert r.status_code == 200 and r.json()["enviadas"] == 2 and len(srv.recebidas) == 2
    assert c.get("/api/v1/mensagens?situacao=enviada", headers=h["administrador"]).json()["por_status"]["enviada"] == 2
    with sessao() as s:
        assert s.scalars(select(EventoAuditoria).where(EventoAuditoria.acao == "disparar_envio")).one().ator_id == ids["administrador"]


def test_linha_de_comando_envia_a_caixa(app_cliente, monkeypatch, capsys):
    from solicitacoes.__main__ import main

    c = app_cliente
    cenario(c)
    with sessao() as s:
        notificacoes.enfileirar(s, para="alguem@exemplo.gov.br", assunto="Aviso", corpo="Texto")
    with ServidorSmtp() as srv:
        usar_smtp(monkeypatch, srv.porta)
        assert main(["enviar-mensagens"]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["enviadas"] == 1 and len(srv.recebidas) == 1
    usar_smtp(monkeypatch, porta_livre())
    with sessao() as s:
        notificacoes.enfileirar(s, para="outro@exemplo.gov.br", assunto="Aviso", corpo="Texto")
    assert main(["enviar-mensagens"]) == 1  # servidor fora do ar: código de saída diferente de zero para o monitoramento


@pytest.mark.parametrize("ambiente,vars_,erro", [
    ("teste", {"SD_SMTP_SEGURANCA": "tls-qualquer"}, "SD_SMTP_SEGURANCA"),
    ("producao", {"SD_SEGREDO": "s" * 40, "SD_BANCO_URL": "postgresql+psycopg://a:b@banco/sd", "SD_SMTP_HOST": "smtp.exemplo.gov.br",
                  "SD_SMTP_SEGURANCA": "nenhuma"}, "starttls ou ssl"),
    ("producao", {"SD_SEGREDO": "s" * 40, "SD_BANCO_URL": "sqlite:///x.db"}, "PostgreSQL"),
])
def test_configuracao_de_email_e_de_producao_validada(monkeypatch, ambiente, vars_, erro):
    monkeypatch.setenv("SD_AMBIENTE", ambiente)
    for k, v in vars_.items():
        monkeypatch.setenv(k, v)
    cfg_mod.config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match=erro):
            cfg_mod.config()
    finally:
        cfg_mod.config.cache_clear()


def test_porta_padrao_conforme_a_seguranca(monkeypatch):
    monkeypatch.setenv("SD_AMBIENTE", "teste")
    monkeypatch.delenv("SD_SMTP_PORTA", raising=False)
    for seg, porta in (("ssl", 465), ("starttls", 587)):
        monkeypatch.setenv("SD_SMTP_SEGURANCA", seg)
        cfg_mod.config.cache_clear()
        assert cfg_mod.config().smtp_porta == porta
    cfg_mod.config.cache_clear()


def test_servico_continuo_sobrevive_a_banco_fora_do_ar(app_cliente, monkeypatch, capsys):
    """Achado da homologação em contêineres: o banco reiniciou e o serviço de envio caiu com OperationalError."""
    from sqlalchemy.exc import OperationalError

    from solicitacoes.__main__ import main

    chamadas = []

    def falha_depois_funciona(s, limite):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise OperationalError("SELECT 1", {}, Exception("connection refused\nmais detalhes"))
        return {"configurado": False, "enviadas": 0, "reagendadas": 0, "falharam": 0, "na_fila": 0}

    monkeypatch.setattr(notificacoes, "enviar_pendentes", falha_depois_funciona)
    assert main(["enviar-mensagens", "--continuo", "--intervalo", "0", "--voltas", "2"]) == 0
    linhas = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    assert "OperationalError" in linhas[0]["erro"] and "\n" not in linhas[0]["erro"] and linhas[1]["configurado"] is False
