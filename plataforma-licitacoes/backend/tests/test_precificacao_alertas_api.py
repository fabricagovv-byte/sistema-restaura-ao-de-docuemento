from __future__ import annotations

import io
from datetime import timedelta

import openpyxl
import pytest
from fastapi.testclient import TestClient

from licitacoes import alertas, catalogo, coleta, precificacao
from licitacoes.auth import criar_usuario
from licitacoes.modelos import Alerta, HistoricoAlteracao, Monitoramento, agora

from .test_coleta_busca import _registro


def test_precificacao_formula():
    p = precificacao.ParametrosProposta.de_dict({
        "linhas": [{"descricao": "Digitalização", "unidade": "pagina", "quantidade": 1_000_000, "custo_unitario": 0.12},
                   {"descricao": "Analista", "unidade": "profissional", "quantidade": 12, "custo_unitario": 9000}],
        "tributos_pct": 14.25, "despesas_adm_pct": 8, "margem_pct": 12, "prazo_meses": 12, "valor_estimado_edital": 400_000,
    })
    r = precificacao.calcular(p)
    custo = 120_000 + 108_000
    ct = custo * 1.08
    preco = ct / (1 - 0.1425 - 0.12)
    assert r["custo_direto"] == pytest.approx(custo) and r["preco_total"] == pytest.approx(preco, abs=0.01)
    assert r["margem"] == pytest.approx(preco * 0.12, abs=0.02)
    assert r["preco_mensal"] == pytest.approx(preco / 12, abs=0.01)
    assert r["referencia_edital"]["natureza"].startswith("oficial")
    assert "Não é o valor oficial" in r["aviso"]
    sim = {x["desconto_pct"]: x for x in r["simulacoes"]}
    assert sim[0]["margem_pct"] == pytest.approx(12, abs=0.01)
    assert sim[20]["prejuizo"] is True


def test_precificacao_planilha_editavel_e_pdf():
    r = precificacao.calcular(precificacao.ParametrosProposta.de_dict({
        "linhas": [{"descricao": "Indexação", "unidade": "pagina", "quantidade": 5000, "custo_unitario": 0.3}],
        "tributos_pct": 10, "margem_pct": 10}))
    wb = openpyxl.load_workbook(io.BytesIO(precificacao.gerar_xlsx(r, "Teste")))
    ws = wb["Proposta"]
    assert ws["E4"].value == "=(1+B5)/(1-B4-B6)" and ws["H10"].value == "=F10*$E$4"
    assert precificacao.gerar_pdf(r, "Teste").startswith(b"%PDF")


def test_precificacao_valida_percentuais():
    with pytest.raises(ValueError):
        precificacao.calcular(precificacao.ParametrosProposta.de_dict({
            "linhas": [{"descricao": "x", "unidade": "fixo", "quantidade": 1, "custo_unitario": 1}],
            "tributos_pct": 60, "margem_pct": 40}))


def test_alertas_sem_duplicar(banco):
    s = banco
    f = catalogo.fonte(s, "pncp")
    m = Monitoramento(nome="Digitalização", termos=["digitalização"], canais={"painel": True, "email": "a@b.com"})
    s.add(m)
    s.commit()
    _, lic = coleta.gravar(s, _registro(valor_estimado=6_000_000.0, data_encerramento=agora() + timedelta(hours=30)), f)
    s.commit()
    desde = agora() - timedelta(hours=1)
    r1 = alertas.avaliar(s, desde=desde)
    tipos = {a.tipo for a in s.query(Alerta)}
    assert tipos == {"novo", "alto_valor", "prazo_proximo"}
    assert r1["entregas"].get("email:nao_configurado") == 3   # nunca finge que enviou
    r2 = alertas.avaliar(s, desde=desde)
    assert r2["alertas_novos"] == 0 and r2["repetidos_ignorados"] == 3
    coleta.gravar(s, _registro(valor_estimado=6_000_000.0, situacao="Suspensa",
                               data_encerramento=lic.data_encerramento), f)
    s.commit()
    r3 = alertas.avaliar(s, desde=desde)
    assert {a.tipo for a in s.query(Alerta)} >= {"suspensa"}
    assert s.query(HistoricoAlteracao).filter_by(evento="situacao").count() == 1
    assert r3["alertas_novos"] >= 1


@pytest.fixture()
def api(banco):
    from licitacoes.api import app

    criar_usuario(banco, "admin@x.com", "Admin", "senha-forte", "admin")
    coleta.gravar(banco, _registro(), catalogo.fonte(banco, "pncp"))
    banco.commit()
    with TestClient(app) as c:
        tok = c.post("/auth/login", json={"email": "admin@x.com", "senha": "senha-forte"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


def test_api_ponta_a_ponta(api):
    r = api.get("/licitacoes", params={"q": "digitalização", "valor_min": 1_000_000})
    assert r.status_code == 200 and r.json()["total"] == 1
    lid = r.json()["itens"][0]["id"]
    d = api.get(f"/licitacoes/{lid}").json()
    assert d["link_pncp"].startswith("https://pncp.gov.br") and d["checklist_documentos"]
    assert api.get(f"/licitacoes/{lid}/zip").status_code == 409  # sem documentos ainda
    p = api.post(f"/licitacoes/{lid}/propostas", json={"linhas": [
        {"descricao": "Página digitalizada", "unidade": "pagina", "quantidade": 1000, "custo_unitario": 0.2}],
        "tributos_pct": 10, "margem_pct": 10}).json()
    assert api.get(f"/propostas/{p['id']}/xlsx").status_code == 200
    assert api.get(f"/propostas/{p['id']}/pdf").content.startswith(b"%PDF")
    assert api.post(f"/licitacoes/{lid}/favorito").json() == {"favorito": True}
    painel = api.get("/painel").json()
    assert painel["abertos"] == 1 and painel["favoritos"][0]["id"] == lid
    q = api.get("/qualidade").json()
    assert q["portais_cadastrados"] >= 10 and "metodo" in q["cobertura"]
    assert api.post("/monitoramentos", json={"nome": "Docs", "termos": ["indexação"]}).status_code == 200


def test_api_exige_login(banco):
    from licitacoes.api import app

    with TestClient(app) as c:
        assert c.get("/licitacoes").status_code == 401
        assert c.post("/auth/login", json={"email": "x@x.com", "senha": "errada"}).status_code == 401


def test_producao_recusa_configuracao_insegura(monkeypatch):
    from licitacoes.config import Configuracao

    dev = Configuracao(_env_file=None)
    assert dev.conferir_producao() == []
    ruim = Configuracao(_env_file=None, ambiente="producao")
    erros = " ".join(ruim.conferir_producao())
    assert "LIC_JWT_SEGREDO" in erros and "LIC_CORS_ORIGENS" in erros and "LIC_DATABASE_URL" in erros
    boa = Configuracao(_env_file=None, ambiente="producao", jwt_segredo="x" * 40, cors_origens="https://licitacoes.exemplo.com.br",
                       database_url="postgresql+psycopg://u:s@postgres/licitacoes")
    assert boa.conferir_producao() == [] and boa.origens == ["https://licitacoes.exemplo.com.br"]
