"""Contrato da API versionado (REQ-006, RNF-05): salvo = gerado, prefixo /api/v1, segurança declarada e detecção de quebra."""

import copy
import json

from solicitacoes import __version__, contrato
from solicitacoes.api import ROTAS_PUBLICAS


def test_contrato_salvo_e_o_gerado_pelo_codigo():
    salvo, gerado = contrato.salvo(), contrato.gerar()
    assert contrato.texto(salvo) == contrato.texto(gerado), "API mudou: rode `python -m solicitacoes contrato` e revise o diff"
    assert salvo["info"]["version"] == __version__


def test_todas_as_rotas_sao_versionadas_e_protegidas():
    c = contrato.gerar()
    ops = contrato.operacoes(c)
    assert len(ops) >= 27
    for (metodo, rota), op in ops.items():
        assert rota.startswith("/api/v1/"), rota
        protegida = op.get("security") == [{"HTTPBearer": []}]
        assert protegida == (rota not in ROTAS_PUBLICAS), (metodo, rota)
        assert op.get("tags"), (metodo, rota)  # agrupada na documentação
    assert len({op["operationId"] for op in ops.values()}) == len(ops)
    assert c["components"]["securitySchemes"]["HTTPBearer"] == {"type": "http", "scheme": "bearer"}


def test_painel_documentado_no_contrato():
    c = contrato.gerar()
    ind = c["paths"]["/api/v1/painel/indicadores"]["get"]
    nomes = {p["name"] for p in ind["parameters"]}
    assert {"de", "ate", "status", "categoria_id", "responsavel_id", "sem_responsavel", "prioridade", "arquivadas"} <= nomes
    assert not any(p.get("required") for p in ind["parameters"])
    exp = c["paths"]["/api/v1/painel/exportacao.csv"]["get"]
    assert "text/csv" in exp["responses"]["200"]["content"]
    esquema = c["components"]["schemas"]["Indicadores"]
    assert {"total", "por_status", "por_categoria", "por_responsavel", "prazo"} <= set(esquema["required"])


def test_documentacao_publicada_na_versao(app_cliente):
    c = app_cliente
    r = c.get("/api/v1/openapi.json")
    assert r.status_code == 200 and r.json()["info"]["version"] == __version__
    assert contrato.texto(r.json()) == contrato.texto(contrato.salvo())
    assert c.get("/api/v1/docs").status_code == 200
    assert c.get("/openapi.json").status_code == 404 and c.get("/docs").status_code == 404
    assert c.get("/api/v1/saude").json()["versao"] == __version__


def test_detecta_mudancas_incompativeis():
    base = contrato.salvo()
    assert contrato.quebras(base, copy.deepcopy(base)) == []
    sem_rota = copy.deepcopy(base)
    del sem_rota["paths"]["/api/v1/painel/indicadores"]
    assert contrato.quebras(base, sem_rota) == ["rota removida: GET /api/v1/painel/indicadores"]
    obrig = copy.deepcopy(base)
    for p in obrig["paths"]["/api/v1/solicitacoes"]["get"]["parameters"]:
        if p["name"] == "q":
            p["required"] = True
    assert contrato.quebras(base, obrig) == ["parâmetro passou a ser obrigatório: GET /api/v1/solicitacoes q"]
    sem_campo = copy.deepcopy(base)
    del sem_campo["components"]["schemas"]["SolicitacaoSaida"]["properties"]["protocolo"]
    erros = contrato.quebras(base, sem_campo)
    assert "campo removido da resposta: GET /api/v1/solicitacoes/{sid} protocolo" in erros
    assert "campo removido da resposta: POST /api/v1/solicitacoes protocolo" in erros
    # acrescentar rota ou campo opcional é compatível
    nova = copy.deepcopy(base)
    nova["paths"]["/api/v1/nova"] = {"get": {"responses": {}}}
    assert contrato.quebras(base, nova) == []


def test_linha_de_comando_grava_e_verifica(tmp_path, capsys):
    destino = tmp_path / "api" / "openapi-v1.json"
    assert contrato.main(verificar=True, caminho=destino) == 1 and "ausente" in capsys.readouterr().out
    assert contrato.main(caminho=destino) == 0 and "operações" in capsys.readouterr().out
    assert contrato.main(verificar=True, caminho=destino) == 0 and "em dia" in capsys.readouterr().out
    antigo = json.loads(destino.read_text())
    antigo["paths"]["/api/v1/rota-antiga"] = {"get": {"responses": {}}}
    destino.write_text(json.dumps(antigo))
    assert contrato.main(verificar=True, caminho=destino) == 1
    saida = capsys.readouterr().out
    assert "INCOMPATÍVEL: rota removida: GET /api/v1/rota-antiga" in saida and "desatualizado" in saida
    assert contrato.main(verificar=True) == 0  # o contrato do repositório está em dia


def test_subcomando_contrato_da_linha_de_comando(capsys):
    from solicitacoes.__main__ import main

    assert main(["contrato", "--verificar"]) == 0 and "contrato em dia" in capsys.readouterr().out
