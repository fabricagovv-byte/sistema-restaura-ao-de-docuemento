"""Conexão com o banco. PostgreSQL em produção; SQLite serve para testes e uso local."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import config


class Base(DeclarativeBase):
    pass


_engine = None
_Sessao = None


def engine():
    global _engine, _Sessao
    if _engine is None:
        url = config().database_url
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi_conn, _):  # pragma: no cover - detalhe do SQLite
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        _Sessao = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reiniciar_engine() -> None:
    """Usado nos testes, quando a URL do banco muda."""
    global _engine, _Sessao
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Sessao = None


def eh_postgres() -> bool:
    return engine().dialect.name == "postgresql"


def nova_sessao() -> Session:
    engine()
    return _Sessao()


@contextmanager
def sessao() -> Iterator[Session]:
    s = nova_sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def iniciar_banco() -> None:
    """Cria tabelas e, no PostgreSQL, os índices de busca (pg_trgm) e o pgvector se existir."""
    from . import modelos  # noqa: F401 - registra as tabelas

    eng = engine()
    if eng.dialect.name == "postgresql":
        with eng.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(eng)
    if eng.dialect.name == "postgresql":
        with eng.begin() as c:
            c.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_licitacao_texto_trgm "
                "ON licitacao USING gin (texto_busca gin_trgm_ops)"
            ))
            tem_vector = c.execute(text(
                "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
            )).first()
            if tem_vector:
                c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                c.execute(text(
                    "CREATE TABLE IF NOT EXISTS licitacao_embedding ("
                    " licitacao_id integer PRIMARY KEY REFERENCES licitacao(id) ON DELETE CASCADE,"
                    " modelo text NOT NULL, vetor vector(384) NOT NULL)"
                ))


def pgvector_disponivel(s: Session) -> bool:
    if not eh_postgres():
        return False
    return bool(s.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'licitacao_embedding'"
    )).first())
