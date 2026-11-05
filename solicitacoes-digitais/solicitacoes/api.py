"""API REST /api/v1."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import __version__, auditoria, seguranca
from .banco import nova_sessao
from .migracoes import aplicar, versao_atual
from .modelos import EventoAuditoria, TokenRevogado, Usuario

log = logging.getLogger("solicitacoes")


class FormatoJson(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        base = {"em": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "nivel": r.levelname,
                "msg": r.getMessage(), "correlacao": auditoria.correlacao_atual.get()}
        base.update(getattr(r, "extra_campos", {}))
        return json.dumps(base, ensure_ascii=False)


def configurar_log() -> None:
    if not any(isinstance(h.formatter, FormatoJson) for h in log.handlers):
        h = logging.StreamHandler()
        h.setFormatter(FormatoJson())
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False


@asynccontextmanager
async def ciclo(app: FastAPI):
    configurar_log()
    aplicar()
    yield


app = FastAPI(title="Solicitações Digitais", version=__version__, lifespan=ciclo,
              description="API do sistema de solicitações digitais (OS-001/2026). Todas as rotas exigem token, exceto login e saúde.")


@app.middleware("http")
async def correlacao(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
    cid = "".join(c for c in cid if c.isalnum() or c in "-_")[:64] or uuid.uuid4().hex
    token = auditoria.correlacao_atual.set(cid)
    t0 = time.perf_counter()
    try:
        resp = await call_next(request)
    finally:
        auditoria.correlacao_atual.reset(token)
    resp.headers["X-Correlation-ID"] = cid
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    log.info("requisicao", extra={"extra_campos": {"correlacao": cid, "metodo": request.method, "rota": request.url.path,
                                                   "status": resp.status_code, "ms": round((time.perf_counter() - t0) * 1000, 1)}})
    return resp


# ------------------------------------------------------------------ dependências
def db():
    s = nova_sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


Db = Annotated[Session, Depends(db)]
bearer = HTTPBearer(auto_error=False)
NAO_AUTENTICADO = HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida ou expirada", headers={"WWW-Authenticate": "Bearer"})


def usuario_atual(s: Db, cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Usuario:
    if cred is None:
        raise NAO_AUTENTICADO
    try:
        dados = seguranca.ler_token(cred.credentials)
    except jwt.PyJWTError:
        raise NAO_AUTENTICADO from None
    if s.get(TokenRevogado, dados["jti"]):
        raise NAO_AUTENTICADO
    u = s.get(Usuario, int(dados["sub"]))
    if u is None or not u.ativo:
        raise NAO_AUTENTICADO
    u.__dict__["_token"] = dados
    return u


Atual = Annotated[Usuario, Depends(usuario_atual)]


def exige(permissao: str):
    def _dep(u: Atual) -> Usuario:
        if not seguranca.pode(u.perfil, permissao):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "seu perfil não tem permissão para esta ação")
        return u
    return _dep


# ------------------------------------------------------------------ esquemas
Perfil = Literal["administrador", "gestor", "operador", "solicitante"]


class Login(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class TokenSaida(BaseModel):
    token: str
    tipo: str = "Bearer"
    expira_em: datetime


class UsuarioSaida(BaseModel):
    id: int
    email: str
    nome: str
    perfil: str
    ativo: bool
    criado_em: datetime


class UsuarioNovo(BaseModel):
    email: EmailStr
    nome: str = Field(min_length=2, max_length=160)
    perfil: Perfil
    senha: str = Field(max_length=200)

    @field_validator("senha")
    @classmethod
    def _senha(cls, v: str) -> str:
        motivo = seguranca.senha_aceitavel(v)
        if motivo:
            raise ValueError(motivo)
        return v


class UsuarioAlteracao(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=160)
    perfil: Perfil | None = None
    ativo: bool | None = None


class EventoSaida(BaseModel):
    id: int
    em: datetime
    ator_id: int | None
    acao: str
    recurso: str
    recurso_id: str | None
    correlacao: str | None
    antes: dict | None
    depois: dict | None
    resultado: str


def _saida(u: Usuario) -> UsuarioSaida:
    return UsuarioSaida(id=u.id, email=u.email, nome=u.nome, perfil=u.perfil, ativo=u.ativo, criado_em=u.criado_em)


# ------------------------------------------------------------------ rotas
@app.get("/api/v1/saude", tags=["sistema"])
def saude() -> dict:
    return {"situacao": "ok", "versao": __version__, "esquema": versao_atual()}


@app.post("/api/v1/auth/login", response_model=TokenSaida, tags=["autenticação"])
def login(dados: Login, s: Db) -> TokenSaida:
    u = s.scalar(select(Usuario).where(func.lower(Usuario.email) == dados.email.lower()))
    ok = seguranca.conferir_senha(dados.senha, u.senha_hash if u else seguranca.hash_ficticio())
    if not (u and ok and u.ativo):
        auditoria.registrar(s, acao="login", recurso="sessao", recurso_id=u.id if u else None,
                            depois={"email": dados.email.lower()}, resultado="recusado")
        s.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "e-mail ou senha incorretos")
    token, exp = seguranca.emitir_token(u.id, u.perfil)
    auditoria.registrar(s, acao="login", recurso="sessao", recurso_id=u.id, ator_id=u.id)
    return TokenSaida(token=token, expira_em=exp)


@app.post("/api/v1/auth/logout", status_code=204, tags=["autenticação"])
def logout(u: Atual, s: Db) -> None:
    dados = u.__dict__["_token"]
    s.add(TokenRevogado(jti=dados["jti"], expira_em=datetime.fromtimestamp(dados["exp"], timezone.utc)))
    auditoria.registrar(s, acao="logout", recurso="sessao", recurso_id=u.id, ator_id=u.id)


@app.get("/api/v1/auth/eu", response_model=UsuarioSaida, tags=["autenticação"])
def eu(u: Atual) -> UsuarioSaida:
    return _saida(u)


@app.get("/api/v1/usuarios", response_model=list[UsuarioSaida], tags=["usuários"])
def listar_usuarios(s: Db, _: Annotated[Usuario, Depends(exige("usuarios:ver"))], perfil: Perfil | None = None,
                    ativo: bool | None = None) -> list[UsuarioSaida]:
    q = select(Usuario).order_by(Usuario.nome)
    if perfil:
        q = q.where(Usuario.perfil == perfil)
    if ativo is not None:
        q = q.where(Usuario.ativo == ativo)
    return [_saida(u) for u in s.scalars(q)]


@app.post("/api/v1/usuarios", response_model=UsuarioSaida, status_code=201, tags=["usuários"])
def criar_usuario(dados: UsuarioNovo, s: Db, admin: Annotated[Usuario, Depends(exige("usuarios:gerir"))]) -> UsuarioSaida:
    if s.scalar(select(Usuario).where(func.lower(Usuario.email) == dados.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "já existe usuário com este e-mail")
    u = Usuario(email=dados.email.lower(), nome=dados.nome.strip(), perfil=dados.perfil, senha_hash=seguranca.gerar_hash(dados.senha))
    s.add(u)
    s.flush()
    auditoria.registrar(s, acao="criar", recurso="usuario", recurso_id=u.id, ator_id=admin.id,
                        depois={"email": u.email, "nome": u.nome, "perfil": u.perfil, "senha": "***"})
    return _saida(u)


@app.patch("/api/v1/usuarios/{uid}", response_model=UsuarioSaida, tags=["usuários"])
def alterar_usuario(uid: int, dados: UsuarioAlteracao, s: Db,
                    admin: Annotated[Usuario, Depends(exige("usuarios:gerir"))]) -> UsuarioSaida:
    u = s.get(Usuario, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "usuário não encontrado")
    mudancas = dados.model_dump(exclude_none=True)
    if u.id == admin.id and (mudancas.get("ativo") is False or mudancas.get("perfil", "administrador") != "administrador"):
        raise HTTPException(status.HTTP_409_CONFLICT, "um administrador não pode desativar a si mesmo nem perder o próprio perfil")
    antes = {k: getattr(u, k) for k in mudancas}
    for k, v in mudancas.items():
        setattr(u, k, v)
    auditoria.registrar(s, acao="alterar", recurso="usuario", recurso_id=u.id, ator_id=admin.id, antes=antes, depois=mudancas)
    return _saida(u)


@app.get("/api/v1/auditoria", response_model=list[EventoSaida], tags=["auditoria"])
def listar_auditoria(s: Db, _: Annotated[Usuario, Depends(exige("auditoria:ver"))], recurso: str | None = None,
                     recurso_id: str | None = None, correlacao: str | None = None,
                     limite: int = 100) -> list[EventoSaida]:
    q = select(EventoAuditoria).order_by(EventoAuditoria.id.desc()).limit(max(1, min(limite, 500)))
    if recurso:
        q = q.where(EventoAuditoria.recurso == recurso)
    if recurso_id:
        q = q.where(EventoAuditoria.recurso_id == recurso_id)
    if correlacao:
        q = q.where(EventoAuditoria.correlacao == correlacao)
    return [EventoSaida.model_validate(e, from_attributes=True) for e in s.scalars(q)]
