"""Recuperação de conta (REQ-001): pedido por e-mail e redefinição de senha com token de uso único."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select

from . import auditoria, seguranca
from .config import config
from .dependencias import Db
from .modelos import MensagemSaida, TokenRecuperacao, Usuario

router = APIRouter(prefix="/api/v1/auth", tags=["autenticação"])

VALIDADE = timedelta(minutes=30)
PEDIDOS_POR_HORA = 3


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class Pedido(BaseModel):
    email: EmailStr


class Redefinicao(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nova_senha: str = Field(max_length=200)

    @field_validator("nova_senha")
    @classmethod
    def _senha(cls, v: str) -> str:
        motivo = seguranca.senha_aceitavel(v)
        if motivo:
            raise ValueError(motivo)
        return v


@router.post("/recuperar", status_code=202)
def pedir_recuperacao(dados: Pedido, s: Db) -> dict:
    """Sempre responde igual, exista ou não a conta, para não revelar quais e-mails estão cadastrados."""
    resposta = {"mensagem": "Se o e-mail estiver cadastrado, enviaremos um link para criar uma nova senha."}
    u = s.scalar(select(Usuario).where(func.lower(Usuario.email) == dados.email.lower()))
    if u is None or not u.ativo:
        auditoria.registrar(s, acao="pedir_recuperacao", recurso="sessao", depois={"email": dados.email.lower()}, resultado="ignorado")
        return resposta
    uma_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    recentes = s.scalar(select(func.count()).select_from(TokenRecuperacao).where(
        TokenRecuperacao.usuario_id == u.id, TokenRecuperacao.criado_em >= uma_hora))
    if recentes >= PEDIDOS_POR_HORA:
        auditoria.registrar(s, acao="pedir_recuperacao", recurso="sessao", recurso_id=u.id, resultado="limitado")
        return resposta
    token = secrets.token_urlsafe(32)
    s.add(TokenRecuperacao(usuario_id=u.id, hash=_hash(token), expira_em=datetime.now(timezone.utc) + VALIDADE))
    link = f"{config().url_publica.rstrip('/')}/redefinir-senha#token={token}"
    s.add(MensagemSaida(para=u.email, assunto="Criar nova senha — Solicitações Digitais",
                        corpo=f"Olá, {u.nome}.\n\nPara criar uma nova senha, abra o link abaixo em até 30 minutos:\n{link}\n\n"
                              "Se você não pediu, ignore esta mensagem; sua senha continua a mesma."))
    auditoria.registrar(s, acao="pedir_recuperacao", recurso="sessao", recurso_id=u.id)
    return resposta


@router.post("/redefinir", status_code=204)
def redefinir_senha(dados: Redefinicao, s: Db) -> Response:
    t = s.scalar(select(TokenRecuperacao).where(TokenRecuperacao.hash == _hash(dados.token)))
    agora = datetime.now(timezone.utc)
    if t is None or t.usado_em is not None or _utc(t.expira_em) < agora:
        auditoria.registrar(s, acao="redefinir_senha", recurso="sessao", recurso_id=t.usuario_id if t else None, resultado="recusado")
        s.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "link inválido ou expirado; peça um novo")
    u = s.get(Usuario, t.usuario_id)
    if u is None or not u.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "link inválido ou expirado; peça um novo")
    u.senha_hash = seguranca.gerar_hash(dados.nova_senha)
    u.sessao_versao = (u.sessao_versao or 0) + 1  # encerra as sessões abertas antes da troca
    t.usado_em = agora
    # os outros links pendentes deste usuário deixam de valer
    for outro in s.scalars(select(TokenRecuperacao).where(TokenRecuperacao.usuario_id == u.id, TokenRecuperacao.usado_em.is_(None))):
        outro.usado_em = agora
    auditoria.registrar(s, acao="redefinir_senha", recurso="usuario", recurso_id=u.id, ator_id=u.id, depois={"senha": "***"})
    return Response(status_code=204)
