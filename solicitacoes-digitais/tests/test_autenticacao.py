from datetime import datetime, timedelta, timezone

import jwt

from solicitacoes.config import config

from .conftest import SENHA, criar, entrar


def test_login_eu_e_logout(perfis):
    c, ids = perfis
    h = entrar(c, "operador@exemplo.gov.br")
    r = c.get("/api/v1/auth/eu", headers=h)
    assert r.status_code == 200 and r.json()["perfil"] == "operador" and "senha_hash" not in r.json()
    assert c.post("/api/v1/auth/logout", headers=h).status_code == 204
    assert c.get("/api/v1/auth/eu", headers=h).status_code == 401  # token revogado


def test_login_recusa_senha_errada_email_inexistente_e_inativo(app_cliente):
    c = app_cliente
    criar("inativo@exemplo.gov.br", "operador", ativo=False)
    criar("ativo@exemplo.gov.br", "operador")
    for email, senha in [("ativo@exemplo.gov.br", "errada"), ("ninguem@exemplo.gov.br", SENHA), ("inativo@exemplo.gov.br", SENHA)]:
        r = c.post("/api/v1/auth/login", json={"email": email, "senha": senha})
        assert r.status_code == 401 and r.json()["detail"] == "e-mail ou senha incorretos"  # mesma mensagem


def test_token_expirado_adulterado_ou_ausente(perfis):
    c, ids = perfis
    vencido = jwt.encode({"sub": str(ids["gestor"]), "jti": "x", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         config().segredo, algorithm="HS256")
    outro_segredo = jwt.encode({"sub": str(ids["gestor"]), "jti": "y", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                               "segredo-de-outra-pessoa-0000000000000000", algorithm="HS256")
    for h in ({"Authorization": f"Bearer {vencido}"}, {"Authorization": f"Bearer {outro_segredo}"}, {}):
        assert c.get("/api/v1/auth/eu", headers=h).status_code == 401


def test_usuario_desativado_perde_a_sessao(perfis):
    c, ids = perfis
    h_op = entrar(c, "operador@exemplo.gov.br")
    h_adm = entrar(c, "administrador@exemplo.gov.br")
    assert c.patch(f"/api/v1/usuarios/{ids['operador']}", json={"ativo": False}, headers=h_adm).status_code == 200
    assert c.get("/api/v1/auth/eu", headers=h_op).status_code == 401
