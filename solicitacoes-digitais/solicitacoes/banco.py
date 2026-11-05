"""Conexão com o banco (PostgreSQL em produção, SQLite em testes)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import config

_engine: Engine | None = None
_fabrica: sessionmaker | None = None


def engine() -> Engine:
    global _engine, _fabrica
    if _engine is None:
        url = config().banco_url
        args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=args, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi, _):  # chaves estrangeiras também no SQLite
                dbapi.execute("PRAGMA foreign_keys=ON")
        _fabrica = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def reiniciar() -> None:
    """Descarta a conexão (usado nos testes ao trocar de banco)."""
    global _engine, _fabrica
    if _engine is not None:
        _engine.dispose()
    _engine = _fabrica = None


def nova_sessao() -> Session:
    engine()
    assert _fabrica is not None
    return _fabrica()


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
