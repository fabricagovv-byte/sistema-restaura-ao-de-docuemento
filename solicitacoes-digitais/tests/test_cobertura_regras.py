"""Regras que a medição de cobertura do dia 3 mostrou sem teste."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from solicitacoes import banco, config as cfg_mod, fluxo, seguranca
from solicitacoes.banco import sessao
from solicitacoes.modelos import Categoria, Solicitacao, Usuario

from .apoio import cenario, nova, tramitar
from .conftest import entrar
from .test_anexos import PDF, enviar


def test_producao_exige_segredo_forte(monkeypatch):
    monkeypatch.setenv("SD_AMBIENTE", "producao")
    monkeypatch.delenv("SD_SEGREDO", raising=False)
    cfg_mod.config.cache_clear()
    with pytest.raises(RuntimeError, match="SD_SEGREDO"):
        cfg_mod.config()
    monkeypatch.setenv("SD_SEGREDO", "s" * 40)
    cfg_mod.config.cache_clear()
    c = cfg_mod.config()
    assert c.producao and c.segredo == "s" * 40
    cfg_mod.config.cache_clear()


def test_hash_com_algoritmo_desconhecido_nao_confere():
    assert not seguranca.conferir_senha("x", "md5$1$YQ==$YQ==")


def test_regras_de_fluxo_isoladas():
    dono, outro, op, op2, ger, adm = (Usuario(id=i, perfil=p) for i, p in
                                       [(1, "solicitante"), (2, "solicitante"), (3, "operador"), (4, "operador"), (5, "gestor"), (6, "administrador")])
    s = Solicitacao(status="aguardando_solicitante", solicitante_id=1, responsavel_id=3, arquivada=False)
    with pytest.raises(fluxo.TransicaoInvalida) as e:
        fluxo.validar(s, "inexistente", ger, "x")
    assert e.value.codigo == 422
    with pytest.raises(fluxo.TransicaoInvalida) as e:
        fluxo.validar(s, "em_atendimento", outro, "resposta")
    assert e.value.codigo == 403 and "próprio solicitante" in str(e.value)
    with pytest.raises(fluxo.TransicaoInvalida) as e:
        fluxo.validar(s, "em_atendimento", op2, "resposta")
    assert e.value.codigo == 403 and "responsável" in str(e.value)
    assert fluxo.validar(s, "em_atendimento", dono, "resposta")
    assert not fluxo.pode_ver(s, adm) and fluxo.pode_ver(s, op) and not fluxo.pode_ver(s, op2)
    assert not fluxo.pode_editar(s, adm) and not fluxo.pode_editar(s, dono)  # dono só edita enquanto recebida
    s.status = "concluida"
    assert not fluxo.pode_editar(s, ger)


def test_filtros_de_usuarios_e_de_solicitacoes(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    so_operadores = c.get("/api/v1/usuarios", params={"perfil": "operador"}, headers=h["gestor"]).json()
    assert {u["id"] for u in so_operadores} == {ids["operador"], ids["operador2"]}
    c.patch(f"/api/v1/usuarios/{ids['operador2']}", json={"ativo": False}, headers=h["administrador"])
    inativos = c.get("/api/v1/usuarios", params={"ativo": False}, headers=h["administrador"]).json()
    assert [u["id"] for u in inativos] == [ids["operador2"]]
    assert c.patch("/api/v1/usuarios/9999", json={"nome": "Ninguém"}, headers=h["administrador"]).status_code == 404
    outra = c.post("/api/v1/categorias", json={"nome": "Certidões", "prazo_dias": 10}, headers=h["administrador"]).json()
    a = nova(c, h["solicitante"], cat, "Pedido da categoria A")
    b = nova(c, h["solicitante"], outra, "Pedido da categoria B")
    c.post(f"/api/v1/solicitacoes/{b['id']}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"])
    por_cat = c.get("/api/v1/solicitacoes", params={"categoria_id": outra["id"]}, headers=h["gestor"]).json()["itens"]
    por_resp = c.get("/api/v1/solicitacoes", params={"responsavel_id": ids["operador"]}, headers=h["gestor"]).json()["itens"]
    por_status = c.get("/api/v1/solicitacoes", params={"status": "recebida"}, headers=h["gestor"]).json()["total"]
    assert [x["id"] for x in por_cat] == [b["id"]] and [x["id"] for x in por_resp] == [b["id"]] and por_status == 2
    assert a["id"] != b["id"]


def test_troca_de_categoria_recalcula_prazo_e_recusa_inativa(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    longa = c.post("/api/v1/categorias", json={"nome": "Análise técnica", "prazo_dias": 30}, headers=h["administrador"]).json()
    s = nova(c, h["solicitante"], cat)
    r = c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"categoria_id": longa["id"]}, headers=h["solicitante"])
    assert r.status_code == 200 and r.json()["categoria"] == "Análise técnica"
    dif = datetime.fromisoformat(r.json()["prazo_em"]) - datetime.fromisoformat(s["criado_em"])
    assert abs(dif - timedelta(days=30)) < timedelta(seconds=5)
    c.patch(f"/api/v1/categorias/{cat['id']}", json={"ativa": False}, headers=h["administrador"])
    assert c.patch(f"/api/v1/solicitacoes/{s['id']}", json={"categoria_id": cat["id"]}, headers=h["solicitante"]).status_code == 422
    assert c.patch("/api/v1/categorias/9999", json={"ativa": True}, headers=h["administrador"]).status_code == 404


def test_atribuicao_em_finalizada_e_por_perfil_sem_poder(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["solicitante"]).status_code == 403
    tramitar(c, h["gestor"], sid, "em_triagem")
    tramitar(c, h["gestor"], sid, "indeferida", "Fora do escopo")
    assert c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"]).status_code == 409


def test_limite_de_anexos_por_solicitacao(app_cliente, monkeypatch):
    c = app_cliente
    ids, h, cat = cenario(c)
    monkeypatch.setenv("SD_ANEXOS_POR_SOLICITACAO", "2")
    cfg_mod.config.cache_clear()
    sid = nova(c, h["solicitante"], cat)["id"]
    assert enviar(c, h["solicitante"], sid, "zip.pdf", b"PK\x03\x04 corrompido").status_code == 415
    assert enviar(c, h["solicitante"], sid, "a.pdf", PDF).status_code == 201
    assert enviar(c, h["solicitante"], sid, "b.pdf", PDF).status_code == 201
    r = enviar(c, h["solicitante"], sid, "c.pdf", PDF)
    assert r.status_code == 409 and "limite de 2" in r.json()["detail"]


def test_sessao_desfaz_em_erro(app_cliente):
    with pytest.raises(RuntimeError):
        with sessao() as s:
            s.add(Categoria(nome="temporária", prazo_dias=1))
            s.flush()
            raise RuntimeError("falha no meio")
    with sessao() as s:
        assert s.execute(text("SELECT count(*) FROM categoria WHERE nome = 'temporária'")).scalar() == 0


def test_linha_de_comando_migrar_e_criar_admin(tmp_path, monkeypatch, capsys):
    from solicitacoes.__main__ import main

    monkeypatch.setenv("SD_BANCO_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("SD_AMBIENTE", "teste")
    monkeypatch.setenv("SD_PBKDF2_ITERACOES", "1000")
    cfg_mod.config.cache_clear()
    banco.reiniciar()
    try:
        assert main(["migrar"]) == 0 and "versão: 3" in capsys.readouterr().out
        assert main(["migrar"]) == 0 and "nenhuma" in capsys.readouterr().out
        monkeypatch.setattr("getpass.getpass", lambda prompt="": "fraca")
        assert main(["criar-admin", "chefe@exemplo.gov.br", "Chefe"]) == 2
        monkeypatch.setattr("getpass.getpass", lambda prompt="": "Senha-Forte-2026")
        assert main(["criar-admin", "chefe@exemplo.gov.br", "Chefe"]) == 0
        assert main(["criar-admin", "CHEFE@exemplo.gov.br", "Chefe"]) == 2  # duplicado
        with sessao() as s:
            u = s.query(Usuario).one()
            assert u.perfil == "administrador" and seguranca.conferir_senha("Senha-Forte-2026", u.senha_hash)
    finally:
        banco.reiniciar()
        cfg_mod.config.cache_clear()
