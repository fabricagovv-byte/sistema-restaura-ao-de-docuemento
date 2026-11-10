import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from solicitacoes.banco import sessao
from solicitacoes.modelos import MensagemSaida, TokenRecuperacao

from .conftest import SENHA, criar, entrar

NOVA = "Nova-Senha-Forte-2027"


def pedir(c, email):
    r = c.post("/api/v1/auth/recuperar", json={"email": email})
    assert r.status_code == 202
    return r.json()["mensagem"]


def token_enviado(email):
    with sessao() as s:
        m = s.scalars(select(MensagemSaida).where(MensagemSaida.para == email).order_by(MensagemSaida.id.desc())).first()
        return re.search(r"#token=([\w-]+)", m.corpo).group(1)


def test_fluxo_completo_troca_senha_e_encerra_sessoes(app_cliente):
    c = app_cliente
    criar("ana@exemplo.gov.br", "solicitante")
    sessao_antiga = entrar(c, "ana@exemplo.gov.br")
    pedir(c, "ANA@exemplo.gov.br")
    token = token_enviado("ana@exemplo.gov.br")
    with sessao() as s:  # só o hash fica no banco
        assert s.scalar(select(TokenRecuperacao.hash)) != token
    assert c.post("/api/v1/auth/redefinir", json={"token": token, "nova_senha": "fraca"}).status_code == 422
    assert c.post("/api/v1/auth/redefinir", json={"token": token, "nova_senha": NOVA}).status_code == 204
    assert c.get("/api/v1/auth/eu", headers=sessao_antiga).status_code == 401           # sessão anterior encerrada
    assert c.post("/api/v1/auth/login", json={"email": "ana@exemplo.gov.br", "senha": SENHA}).status_code == 401
    entrar(c, "ana@exemplo.gov.br", NOVA)
    assert c.post("/api/v1/auth/redefinir", json={"token": token, "nova_senha": NOVA}).status_code == 400  # uso único


def test_resposta_igual_para_email_inexistente_e_sem_mensagem(app_cliente):
    c = app_cliente
    criar("bia@exemplo.gov.br", "operador")
    assert pedir(c, "ninguem@exemplo.gov.br") == pedir(c, "bia@exemplo.gov.br")
    with sessao() as s:
        assert [m.para for m in s.scalars(select(MensagemSaida))] == ["bia@exemplo.gov.br"]


def test_token_expirado_e_limite_de_pedidos(app_cliente):
    c = app_cliente
    criar("caio@exemplo.gov.br", "gestor")
    pedir(c, "caio@exemplo.gov.br")
    token = token_enviado("caio@exemplo.gov.br")
    with sessao() as s:
        s.scalars(select(TokenRecuperacao)).first().expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert c.post("/api/v1/auth/redefinir", json={"token": token, "nova_senha": NOVA}).status_code == 400
    for _ in range(5):
        pedir(c, "caio@exemplo.gov.br")
    with sessao() as s:
        assert len(s.scalars(select(MensagemSaida)).all()) == 3  # no máximo 3 por hora


def test_novo_link_invalida_os_anteriores_depois_da_troca(app_cliente):
    c = app_cliente
    criar("davi@exemplo.gov.br", "solicitante")
    pedir(c, "davi@exemplo.gov.br")
    primeiro = token_enviado("davi@exemplo.gov.br")
    pedir(c, "davi@exemplo.gov.br")
    segundo = token_enviado("davi@exemplo.gov.br")
    assert c.post("/api/v1/auth/redefinir", json={"token": segundo, "nova_senha": NOVA}).status_code == 204
    assert c.post("/api/v1/auth/redefinir", json={"token": primeiro, "nova_senha": NOVA}).status_code == 400
