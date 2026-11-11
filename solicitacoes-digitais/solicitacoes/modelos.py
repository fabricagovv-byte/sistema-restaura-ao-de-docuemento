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
    # sobe ao redefinir a senha: invalida todas as sessões abertas antes
    sessao_versao: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
    prazo_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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


class Categoria(Base):
    __tablename__ = "categoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    prazo_dias: Mapped[int] = mapped_column(Integer)  # prazo de atendimento em dias corridos
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class HistoricoSolicitacao(Base):
    """Cada passo da tramitação; só inclusão."""

    __tablename__ = "historico_solicitacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacao.id", ondelete="CASCADE"), index=True)
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    ator_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    evento: Mapped[str] = mapped_column(String(30))  # criacao, transicao, atribuicao, edicao, arquivamento
    de_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    para_status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)


class Anexo(Base):
    __tablename__ = "anexo"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacao.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(100))
    tamanho: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    caminho: Mapped[str] = mapped_column(String(300))
    enviado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    removido: Mapped[bool] = mapped_column(Boolean, default=False)


class TokenRecuperacao(Base):
    """Guarda só o hash do token enviado por e-mail."""

    __tablename__ = "token_recuperacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MensagemSaida(Base):
    """Caixa de saída: mensagens a enviar (e-mail). O envio por SMTP é a integração do dia 8."""

    __tablename__ = "mensagem_saida"
    id: Mapped[int] = mapped_column(primary_key=True)
    para: Mapped[str] = mapped_column(String(254), index=True)
    assunto: Mapped[str] = mapped_column(String(200))
    corpo: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
