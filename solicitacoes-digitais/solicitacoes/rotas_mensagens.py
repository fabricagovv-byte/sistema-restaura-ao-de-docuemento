"""Caixa de saída de e-mails (REQ-006, D8-B): o administrador acompanha e dispara o envio.

O corpo das mensagens não é exposto (pode conter link de recuperação de senha); só destinatário, assunto, tipo e
situação do envio.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from . import auditoria, notificacoes
from .dependencias import Db, exige
from .modelos import MensagemSaida, Usuario

router = APIRouter(prefix="/api/v1/mensagens", tags=["mensagens"])
Admin = Annotated[Usuario, Depends(exige("mensagens:gerir"))]


class MensagemSituacao(BaseModel):
    id: int
    para: str
    assunto: str
    tipo: str
    status: str
    tentativas: int
    ultimo_erro: str | None
    criado_em: datetime
    enviado_em: datetime | None
    proxima_tentativa_em: datetime | None
    solicitacao_id: int | None


class Caixa(BaseModel):
    smtp_configurado: bool
    por_status: dict[str, int]
    mensagens: list[MensagemSituacao]


class ResultadoEnvio(BaseModel):
    configurado: bool
    enviadas: int
    reagendadas: int
    falharam: int
    na_fila: int
    erro_conexao: str | None = None


@router.get("", response_model=Caixa)
def listar(db: Db, _: Admin, situacao: Literal["pendente", "enviada", "falhou"] | None = None,
           limite: Annotated[int, Query(ge=1, le=500)] = 100) -> Caixa:
    from .config import config

    q = select(MensagemSaida).order_by(MensagemSaida.id.desc()).limit(limite)
    if situacao:
        q = q.where(MensagemSaida.status == situacao)
    contagem = dict(db.execute(select(MensagemSaida.status, func.count()).group_by(MensagemSaida.status)).all())
    return Caixa(smtp_configurado=config().smtp_configurado,
                 por_status={k: contagem.get(k, 0) for k in ("pendente", "enviada", "falhou")},
                 mensagens=[MensagemSituacao(**notificacoes.situacao(m)) for m in db.scalars(q)])


@router.post("/enviar", response_model=ResultadoEnvio)
def enviar(db: Db, u: Admin, limite: Annotated[int, Query(ge=1, le=500)] = 100) -> ResultadoEnvio:
    r = notificacoes.enviar_pendentes(db, limite=limite)
    auditoria.registrar(db, acao="disparar_envio", recurso="mensagens", ator_id=u.id, depois=r)
    return ResultadoEnvio(**r)
