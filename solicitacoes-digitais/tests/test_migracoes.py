from sqlalchemy import inspect

from solicitacoes.banco import engine
from solicitacoes.migracoes import MIGRACOES, aplicar, versao_atual


def test_migracoes_sao_idempotentes(app_cliente):
    # o cliente já aplicou na subida; rodar de novo não aplica nada nem quebra
    assert versao_atual() == MIGRACOES[-1][0]
    assert aplicar() == []
    assert aplicar() == []
    tabelas = set(inspect(engine()).get_table_names())
    assert {"usuario", "token_revogado", "solicitacao", "evento_auditoria", "versao_esquema"} <= tabelas


def test_saude_informa_versao_do_esquema(app_cliente):
    r = app_cliente.get("/api/v1/saude")
    assert r.status_code == 200 and r.json()["esquema"] == MIGRACOES[-1][0]
