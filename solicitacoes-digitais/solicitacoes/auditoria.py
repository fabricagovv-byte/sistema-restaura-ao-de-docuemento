"""Eventos de auditoria (só inclusão)."""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.orm import Session

from .modelos import EventoAuditoria

correlacao_atual: ContextVar[str | None] = ContextVar("correlacao_atual", default=None)

CAMPOS_SENSIVEIS = {"senha", "senha_hash", "token"}


def _limpo(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {k: ("***" if k in CAMPOS_SENSIVEIS else v) for k, v in d.items()}


def registrar(s: Session, *, acao: str, recurso: str, recurso_id: object = None, ator_id: int | None = None,
              antes: dict | None = None, depois: dict | None = None, resultado: str = "sucesso") -> EventoAuditoria:
    ev = EventoAuditoria(acao=acao, recurso=recurso, recurso_id=None if recurso_id is None else str(recurso_id),
                         ator_id=ator_id, antes=_limpo(antes), depois=_limpo(depois), resultado=resultado,
                         correlacao=correlacao_atual.get())
    s.add(ev)
    s.flush()
    return ev
