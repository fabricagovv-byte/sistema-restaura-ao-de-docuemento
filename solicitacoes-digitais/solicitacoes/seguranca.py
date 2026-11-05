"""Senhas, tokens de sessão e permissões por perfil."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from .config import config

PERFIS = ("administrador", "gestor", "operador", "solicitante")

# Matriz perfil -> permissões. Cada rota declara a permissão de que precisa.
PERMISSOES: dict[str, frozenset[str]] = {
    "administrador": frozenset({"usuarios:gerir", "usuarios:ver", "auditoria:ver"}),
    "gestor": frozenset({"usuarios:ver", "auditoria:ver", "solicitacoes:ver_todas", "solicitacoes:tramitar",
                         "solicitacoes:atribuir", "solicitacoes:arquivar", "solicitacoes:criar", "painel:ver"}),
    "operador": frozenset({"solicitacoes:ver_fila", "solicitacoes:tramitar", "solicitacoes:criar"}),
    "solicitante": frozenset({"solicitacoes:criar", "solicitacoes:ver_proprias"}),
}

ALGORITMO = "pbkdf2_sha256"


def gerar_hash(senha: str, iteracoes: int | None = None) -> str:
    iteracoes = iteracoes or config().pbkdf2_iteracoes
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, iteracoes)
    return f"{ALGORITMO}${iteracoes}${base64.b64encode(sal).decode()}${base64.b64encode(dk).decode()}"


def conferir_senha(senha: str, armazenado: str) -> bool:
    try:
        alg, it, sal_b64, dk_b64 = armazenado.split("$")
    except ValueError:
        return False
    if alg != ALGORITMO:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), base64.b64decode(sal_b64), int(it))
    return hmac.compare_digest(dk, base64.b64decode(dk_b64))


# hash de uma senha qualquer, para que login com e-mail inexistente custe o mesmo tempo
_HASH_FICTICIO: str | None = None


def hash_ficticio() -> str:
    global _HASH_FICTICIO
    if _HASH_FICTICIO is None:
        _HASH_FICTICIO = gerar_hash(secrets.token_urlsafe(16))
    return _HASH_FICTICIO


def senha_aceitavel(senha: str) -> str | None:
    """Motivo da recusa, ou None se a senha serve."""
    if len(senha) < 10:
        return "a senha precisa ter ao menos 10 caracteres"
    if senha.lower() == senha or senha.upper() == senha or not any(c.isdigit() for c in senha):
        return "a senha precisa ter letras maiúsculas, minúsculas e números"
    return None


def emitir_token(usuario_id: int, perfil: str) -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config().token_minutos)
    corpo = {"sub": str(usuario_id), "perfil": perfil, "jti": uuid.uuid4().hex,
             "iat": datetime.now(timezone.utc), "exp": exp}
    return jwt.encode(corpo, config().segredo, algorithm="HS256"), exp


def ler_token(token: str) -> dict:
    """Decodifica e valida assinatura e expiração; levanta jwt.PyJWTError se inválido."""
    return jwt.decode(token, config().segredo, algorithms=["HS256"], options={"require": ["sub", "jti", "exp"]})


def pode(perfil: str, permissao: str) -> bool:
    return permissao in PERMISSOES.get(perfil, frozenset())
