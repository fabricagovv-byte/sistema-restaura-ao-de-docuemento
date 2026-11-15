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
    """Banco na versão 2 (sem usuario.sessao_versao) sobe para a 5 sem perder dados."""
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
        assert aplicar() == [3, 4, 5] and aplicar() == []
        cols = {c["name"] for c in inspect(engine()).get_columns("usuario")}
        assert "sessao_versao" in cols and {"anexo", "token_recuperacao", "mensagem_saida"} <= set(inspect(engine()).get_table_names())
        with engine().connect() as conn:
            assert conn.execute(text("SELECT email, sessao_versao FROM usuario")).one() == ("antigo@exemplo.gov.br", 0)
    finally:
        banco.reiniciar()
        cfg_mod.config.cache_clear()


def test_v5_atualiza_caixa_de_saida_antiga_sem_perder_mensagens(tmp_path, monkeypatch):
    """Caixa de saída da versão 4 (sem status/tentativas) sobe para a 5: enviada continua enviada, o resto fica pendente."""
    from sqlalchemy import create_engine, text

    from solicitacoes import banco, config as cfg_mod

    url = f"sqlite:///{tmp_path / 'v4.db'}"
    monkeypatch.setenv("SD_BANCO_URL", url)
    cfg_mod.config.cache_clear()
    banco.reiniciar()
    try:
        e = create_engine(url)
        with e.begin() as conn:
            conn.execute(text("CREATE TABLE versao_esquema (versao INTEGER PRIMARY KEY, descricao VARCHAR(200), aplicada_em DATETIME)"))
            conn.execute(text("CREATE TABLE mensagem_saida (id INTEGER PRIMARY KEY, para VARCHAR(254), assunto VARCHAR(200), corpo TEXT,"
                              " criado_em DATETIME, enviado_em DATETIME)"))
            conn.execute(text("INSERT INTO mensagem_saida (para, assunto, corpo, enviado_em) VALUES"
                              " ('a@exemplo.gov.br', 'já foi', 'x', '2026-11-10 10:00:00'), ('b@exemplo.gov.br', 'falta', 'y', NULL)"))
            conn.execute(text("INSERT INTO versao_esquema (versao, descricao) VALUES (1, 'v1'), (2, 'v2'), (3, 'v3'), (4, 'v4')"))
        e.dispose()
        assert aplicar() == [5] and aplicar() == []
        cols = {c["name"] for c in inspect(engine()).get_columns("mensagem_saida")}
        assert {"tipo", "status", "tentativas", "ultimo_erro", "proxima_tentativa_em", "solicitacao_id"} <= cols
        with engine().connect() as conn:
            linhas = conn.execute(text("SELECT assunto, status, tentativas, tipo FROM mensagem_saida ORDER BY id")).all()
        assert [tuple(x) for x in linhas] == [("já foi", "enviada", 0, "geral"), ("falta", "pendente", 0, "geral")]
    finally:
        banco.reiniciar()
        cfg_mod.config.cache_clear()
