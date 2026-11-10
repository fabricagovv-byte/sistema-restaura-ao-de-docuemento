"""Migrações numeradas e idempotentes.

Cada versão roda uma única vez; rodar `aplicar()` de novo não altera nada. Novas versões entram no fim da lista.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection

from .banco import engine, sessao
from .modelos import (Anexo, Base, Categoria, EventoAuditoria, HistoricoSolicitacao, MensagemSaida, Solicitacao, TokenRecuperacao,
                      TokenRevogado, Usuario, VersaoEsquema)


def _v1(conn: Connection) -> None:
    """Esquema inicial: usuários, revogação de tokens, solicitações e auditoria."""
    for tabela in (Usuario.__table__, TokenRevogado.__table__, Solicitacao.__table__, EventoAuditoria.__table__):
        tabela.create(conn, checkfirst=True)


def _v2(conn: Connection) -> None:
    """Categorias com prazo de atendimento e histórico de tramitação."""
    for tabela in (Categoria.__table__, HistoricoSolicitacao.__table__):
        tabela.create(conn, checkfirst=True)


def _v3(conn: Connection) -> None:
    """Anexos, recuperação de conta, caixa de saída de mensagens e versão de sessão do usuário."""
    for tabela in (Anexo.__table__, TokenRecuperacao.__table__, MensagemSaida.__table__):
        tabela.create(conn, checkfirst=True)
    colunas = {c["name"] for c in inspect(conn).get_columns("usuario")}
    if "sessao_versao" not in colunas:  # bancos criados antes desta versão
        conn.execute(text("ALTER TABLE usuario ADD COLUMN sessao_versao INTEGER NOT NULL DEFAULT 0"))


MIGRACOES: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "esquema inicial: usuários, tokens revogados, solicitações e auditoria", _v1),
    (2, "categorias com prazo e histórico de tramitação", _v2),
    (3, "anexos, recuperação de conta, caixa de saída e versão de sessão", _v3),
]


def aplicar() -> list[int]:
    """Aplica as migrações pendentes e devolve as versões aplicadas nesta chamada."""
    eng = engine()
    with eng.begin() as conn:
        VersaoEsquema.__table__.create(conn, checkfirst=True)
    feitas: list[int] = []
    with sessao() as s:
        ja = set(s.scalars(select(VersaoEsquema.versao)))
    for versao, descricao, passo in MIGRACOES:
        if versao in ja:
            continue
        with eng.begin() as conn:
            passo(conn)
            conn.execute(VersaoEsquema.__table__.insert().values(versao=versao, descricao=descricao))
        feitas.append(versao)
    return feitas


def versao_atual() -> int:
    with sessao() as s:
        if not inspect(s.get_bind()).has_table("versao_esquema"):
            return 0
        return max(s.scalars(select(VersaoEsquema.versao)), default=0)


assert sorted(v for v, _, _ in MIGRACOES) == [v for v, _, _ in MIGRACOES], "migrações fora de ordem"
assert Base  # todas as tabelas declaradas estão em modelos.Base
