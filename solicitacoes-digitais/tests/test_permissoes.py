import pytest

from .conftest import entrar

NOVO = {"email": "novo@exemplo.gov.br", "nome": "Pessoa Nova", "perfil": "operador", "senha": "Senha-Forte-2026"}

# rota -> perfis que podem usá-la (REQ-001: autorização testada por perfil)
CASOS = [
    ("GET", "/api/v1/usuarios", None, {"administrador", "gestor"}),
    ("POST", "/api/v1/usuarios", NOVO, {"administrador"}),
    ("GET", "/api/v1/auditoria", None, {"administrador", "gestor"}),
    ("GET", "/api/v1/auth/eu", None, {"administrador", "gestor", "operador", "solicitante"}),
    ("GET", "/api/v1/painel/indicadores", None, {"gestor"}),
    ("GET", "/api/v1/painel/exportacao.csv", None, {"gestor"}),
]


@pytest.mark.parametrize("metodo,rota,corpo,permitidos", CASOS)
def test_cada_perfil_so_acessa_o_que_pode(perfis, metodo, rota, corpo, permitidos):
    c, _ = perfis
    for perfil in ("administrador", "gestor", "operador", "solicitante"):
        h = entrar(c, f"{perfil}@exemplo.gov.br")
        r = c.request(metodo, rota, json=corpo, headers=h)
        if perfil in permitidos:
            assert r.status_code in (200, 201, 409), (perfil, rota, r.status_code, r.text)
        else:
            assert r.status_code == 403, (perfil, rota, r.status_code)
        assert c.request(metodo, rota, json=corpo).status_code == 401  # sem token


def test_admin_cria_usuario_valida_senha_e_email_duplicado(perfis):
    c, _ = perfis
    h = entrar(c, "administrador@exemplo.gov.br")
    fraca = dict(NOVO, senha="fraca")
    assert c.post("/api/v1/usuarios", json=fraca, headers=h).status_code == 422
    r = c.post("/api/v1/usuarios", json=NOVO, headers=h)
    assert r.status_code == 201 and r.json()["perfil"] == "operador" and "senha" not in r.json()
    assert c.post("/api/v1/usuarios", json=dict(NOVO, email="NOVO@exemplo.gov.br"), headers=h).status_code == 409
    entrar(c, "novo@exemplo.gov.br")  # a senha cadastrada funciona


def test_admin_nao_se_desativa(perfis):
    c, ids = perfis
    h = entrar(c, "administrador@exemplo.gov.br")
    r = c.patch(f"/api/v1/usuarios/{ids['administrador']}", json={"ativo": False}, headers=h)
    assert r.status_code == 409
