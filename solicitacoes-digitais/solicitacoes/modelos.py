"""Modelos persistentes."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(160))
    perfil: Mapped[str] = mapped_column(String(20), index=True)  # administrador, gestor, operador, solicitante
    senha_hash: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class TokenRevogado(Base):
    __tablename__ = "token_revogado"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Solicitacao(Base):
    __tablename__ = "solicitacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    protocolo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="recebida")
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=True)
    prazo_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arquivada: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitante_id])
    responsavel: Mapped[Usuario | None] = relationship(foreign_keys=[responsavel_id])


class EventoAuditoria(Base):
    """Só inclusão: a API não altera nem exclui eventos."""

    __tablename__ = "evento_auditoria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    ator_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    recurso: Mapped[str] = mapped_column(String(60), index=True)
    recurso_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    correlacao: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    antes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    depois: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resultado: Mapped[str] = mapped_column(String(20), default="sucesso")


class VersaoEsquema(Base):
    __tablename__ = "versao_esquema"
    versao: Mapped[int] = mapped_column(primary_key=True)
    descricao: Mapped[str] = mapped_column(String(200))
    aplicada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
