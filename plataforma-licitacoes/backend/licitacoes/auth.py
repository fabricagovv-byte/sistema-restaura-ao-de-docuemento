"""Autenticação por JWT e papéis (admin, analista, leitor). Senhas com PBKDF2-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import config
from .modelos import Usuario

ITERACOES = 310_000
PAPEIS = {"leitor": 0, "analista": 1, "admin": 2}
_bearer = HTTPBearer(auto_error=False)


def gerar_hash(senha: str) -> str:
    sal = os.urandom(16)
    d = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, ITERACOES)
    return f"pbkdf2_sha256${ITERACOES}${sal.hex()}${d.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        _, it, sal, d = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), d)
    except ValueError:
        return False


def emitir_token(u: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(u.id), "papel": u.papel, "iat": agora,
                       "exp": agora + timedelta(hours=config().jwt_horas)}, config().jwt_segredo, algorithm="HS256")


def criar_usuario(s: Session, email: str, nome: str, senha: str, papel: str = "analista") -> Usuario:
    if papel not in PAPEIS:
        raise ValueError(f"papel inválido: {papel}")
    u = Usuario(email=email.lower(), nome=nome, senha_hash=gerar_hash(senha), papel=papel)
    s.add(u)
    s.commit()
    return u


def obter_sessao():
    from .db import nova_sessao

    s = nova_sessao()
    try:
        yield s
    finally:
        s.close()


def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                  s: Session = Depends(obter_sessao)) -> Usuario | None:
    if cred is None:
        if config().auth_obrigatoria:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "faça login")
        return None
    try:
        dados = jwt.decode(cred.credentials, config().jwt_segredo, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida ou expirada") from None
    u = s.get(Usuario, int(dados["sub"]))
    if u is None or not u.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuário inativo")
    return u


def exigir(papel: str):
    def dep(u: Usuario | None = Depends(usuario_atual)) -> Usuario | None:
        if u is None and not config().auth_obrigatoria:
            return None
        if u is None or PAPEIS[u.papel] < PAPEIS[papel]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"exige papel {papel}")
        return u
    return dep
