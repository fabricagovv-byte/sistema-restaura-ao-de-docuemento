"""Configuração por ambiente (variáveis SD_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

SEGREDO_DESENVOLVIMENTO = "desenvolvimento-nao-usar-em-producao-0000000000000000"


@dataclass(frozen=True)
class Config:
    ambiente: str
    banco_url: str
    segredo: str
    token_minutos: int
    pbkdf2_iteracoes: int
    anexos_dir: str
    anexo_max_bytes: int
    anexos_por_solicitacao: int
    url_publica: str
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""
    smtp_seguranca: str = "starttls"  # starttls | ssl | nenhuma
    smtp_remetente: str = "nao-responda@solicitacoes.local"
    smtp_timeout: float = 15.0

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def smtp_configurado(self) -> bool:
        return bool(self.smtp_host)


@lru_cache
def config() -> Config:
    ambiente = os.environ.get("SD_AMBIENTE", "desenvolvimento")
    segredo = os.environ.get("SD_SEGREDO", "")
    if ambiente != "desenvolvimento" and ambiente != "teste":
        if len(segredo) < 32:
            raise RuntimeError("SD_SEGREDO com ao menos 32 caracteres é obrigatório fora de desenvolvimento e teste")
    seguranca_smtp = os.environ.get("SD_SMTP_SEGURANCA", "starttls").lower()
    if seguranca_smtp not in ("starttls", "ssl", "nenhuma"):
        raise RuntimeError("SD_SMTP_SEGURANCA deve ser starttls, ssl ou nenhuma")
    host_smtp = os.environ.get("SD_SMTP_HOST", "")
    if ambiente == "producao" and host_smtp and seguranca_smtp == "nenhuma" and host_smtp not in ("localhost", "127.0.0.1"):
        raise RuntimeError("em produção o SMTP fora da própria máquina exige SD_SMTP_SEGURANCA=starttls ou ssl")
    if ambiente == "producao" and os.environ.get("SD_BANCO_URL", "sqlite").startswith("sqlite"):
        raise RuntimeError("em produção SD_BANCO_URL deve apontar para o PostgreSQL")
    return Config(
        ambiente=ambiente,
        banco_url=os.environ.get("SD_BANCO_URL", "sqlite:///./solicitacoes.db"),
        segredo=segredo or SEGREDO_DESENVOLVIMENTO,
        token_minutos=int(os.environ.get("SD_TOKEN_MINUTOS", "60")),
        pbkdf2_iteracoes=int(os.environ.get("SD_PBKDF2_ITERACOES", "600000")),
        anexos_dir=os.environ.get("SD_ANEXOS_DIR", "./anexos"),
        anexo_max_bytes=int(float(os.environ.get("SD_ANEXO_MAX_MB", "10")) * 1024 * 1024),
        anexos_por_solicitacao=int(os.environ.get("SD_ANEXOS_POR_SOLICITACAO", "20")),
        url_publica=os.environ.get("SD_URL_PUBLICA", "http://127.0.0.1:8000"),
        smtp_host=host_smtp,
        smtp_porta=int(os.environ.get("SD_SMTP_PORTA", "465" if seguranca_smtp == "ssl" else "587")),
        smtp_usuario=os.environ.get("SD_SMTP_USUARIO", ""),
        smtp_senha=os.environ.get("SD_SMTP_SENHA", ""),
        smtp_seguranca=seguranca_smtp,
        smtp_remetente=os.environ.get("SD_SMTP_REMETENTE", "nao-responda@solicitacoes.local"),
        smtp_timeout=float(os.environ.get("SD_SMTP_TIMEOUT", "15")),
    )
