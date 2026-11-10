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


def test_v3_atualiza_banco_criado_antes_da_coluna_de_sessao(tmp_path, monkeypatch):
    """Banco na versão 2 (sem usuario.sessao_versao) sobe para a 3 sem perder dados."""
    from sqlalchemy import create_engine, text

    from solicitacoes import banco, config as cfg_mod

    url = f"sqlite:///{tmp_path / 'antigo.db'}"
    e = create_engine(url)
    with e.begin() as conn:
        conn.execute(text("CREATE TABLE versao_esquema (versao INTEGER PRIMARY KEY, descricao VARCHAR(200), aplicada_em DATETIME)"))
        conn.execute(text("CREATE TABLE usuario (id INTEGER PRIMARY KEY, email VARCHAR(254) UNIQUE, nome VARCHAR(160), perfil VARCHAR(20),"
                          " senha_hash VARCHAR(200), ativo BOOLEAN, criado_em DATETIME, atualizado_em DATETIME)"))
        conn.execute(text("INSERT INTO usuario (email, nome, perfil, senha_hash, ativo) VALUES ('antigo@exemplo.gov.br', 'Antigo', 'gestor', 'x', 1)"))
        conn.execute(text("INSERT INTO versao_esquema (versao, descricao) VALUES (1, 'v1'), (2, 'v2')"))
    e.dispose()
    monkeypatch.setenv("SD_BANCO_URL", url)
    cfg_mod.config.cache_clear()
    banco.reiniciar()
    try:
        assert aplicar() == [3] and aplicar() == []
        cols = {c["name"] for c in inspect(engine()).get_columns("usuario")}
        assert "sessao_versao" in cols and {"anexo", "token_recuperacao", "mensagem_saida"} <= set(inspect(engine()).get_table_names())
        with engine().connect() as conn:
            assert conn.execute(text("SELECT email, sessao_versao FROM usuario")).one() == ("antigo@exemplo.gov.br", 0)
    finally:
        banco.reiniciar()
        cfg_mod.config.cache_clear()
