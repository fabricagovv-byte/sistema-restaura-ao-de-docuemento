from .conftest import entrar


def test_alteracoes_geram_eventos_com_ator_correlacao_e_sem_senha(perfis):
    c, ids = perfis
    h = entrar(c, "administrador@exemplo.gov.br")
    novo = {"email": "auditado@exemplo.gov.br", "nome": "Auditado", "perfil": "solicitante", "senha": "Senha-Forte-2026"}
    r = c.post("/api/v1/usuarios", json=novo, headers={**h, "X-Correlation-ID": "teste-correlacao-123"})
    assert r.headers["X-Correlation-ID"] == "teste-correlacao-123"
    uid = r.json()["id"]
    c.patch(f"/api/v1/usuarios/{uid}", json={"perfil": "operador"}, headers=h)
    ev = c.get("/api/v1/auditoria", params={"recurso": "usuario", "recurso_id": str(uid)}, headers=h).json()
    assert [e["acao"] for e in ev] == ["alterar", "criar"]
    criar = ev[1]
    assert criar["ator_id"] == ids["administrador"] and criar["correlacao"] == "teste-correlacao-123"
    assert criar["depois"]["senha"] == "***" and "Senha-Forte" not in str(ev)
    assert ev[0]["antes"] == {"perfil": "solicitante"} and ev[0]["depois"] == {"perfil": "operador"}
    por_corr = c.get("/api/v1/auditoria", params={"correlacao": "teste-correlacao-123"}, headers=h).json()
    assert len(por_corr) == 1 and por_corr[0]["id"] == criar["id"]


def test_login_recusado_fica_auditado(perfis):
    c, _ = perfis
    c.post("/api/v1/auth/login", json={"email": "gestor@exemplo.gov.br", "senha": "errada"})
    h = entrar(c, "gestor@exemplo.gov.br")
    ev = c.get("/api/v1/auditoria", params={"recurso": "sessao"}, headers=h).json()
    assert {"recusado", "sucesso"} <= {e["resultado"] for e in ev}


def test_auditoria_nao_tem_rota_de_alteracao(perfis):
    c, _ = perfis
    h = entrar(c, "administrador@exemplo.gov.br")
    assert c.delete("/api/v1/auditoria", headers=h).status_code == 405
    assert c.put("/api/v1/auditoria", headers=h, json={}).status_code == 405


def test_correlacao_gerada_quando_ausente_e_saneada(app_cliente):
    r = app_cliente.get("/api/v1/saude")
    assert len(r.headers["X-Correlation-ID"]) == 32
    r = app_cliente.get("/api/v1/saude", headers={"X-Correlation-ID": "abc<script>"})
    assert r.headers["X-Correlation-ID"] == "abcscript"
