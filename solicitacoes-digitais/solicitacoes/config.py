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

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"


@lru_cache
def config() -> Config:
    ambiente = os.environ.get("SD_AMBIENTE", "desenvolvimento")
    segredo = os.environ.get("SD_SEGREDO", "")
    if ambiente != "desenvolvimento" and ambiente != "teste":
        if len(segredo) < 32:
            raise RuntimeError("SD_SEGREDO com ao menos 32 caracteres é obrigatório fora de desenvolvimento e teste")
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
    )
