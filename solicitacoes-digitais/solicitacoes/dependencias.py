"""Dependências comuns das rotas: sessão de banco, usuário autenticado e permissão exigida."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import seguranca
from .banco import nova_sessao
from .modelos import TokenRevogado, Usuario


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
    if u is None or not u.ativo or dados.get("sv", 0) != (u.sessao_versao or 0):  # senha redefinida depois do login
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
