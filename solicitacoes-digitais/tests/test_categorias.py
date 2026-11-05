from .apoio import cenario


def test_admin_gere_categorias_e_os_outros_so_veem(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    assert cat["prazo_dias"] == 5 and cat["ativa"]
    assert c.post("/api/v1/categorias", json={"nome": "segunda VIA de documento", "prazo_dias": 3}, headers=h["administrador"]).status_code == 409
    assert c.post("/api/v1/categorias", json={"nome": "Outra", "prazo_dias": 0}, headers=h["administrador"]).status_code == 422
    assert c.post("/api/v1/categorias", json={"nome": "Outra", "prazo_dias": 3}, headers=h["gestor"]).status_code == 403
    assert [x["nome"] for x in c.get("/api/v1/categorias", headers=h["solicitante"]).json()] == ["Segunda via de documento"]
    r = c.patch(f"/api/v1/categorias/{cat['id']}", json={"ativa": False}, headers=h["administrador"])
    assert r.status_code == 200 and not r.json()["ativa"]
    assert c.get("/api/v1/categorias", headers=h["solicitante"]).json() == []
    assert len(c.get("/api/v1/categorias", params={"todas": True}, headers=h["administrador"]).json()) == 1
