"""Anexos das solicitações (REQ-002): envio com verificação de tipo pelo conteúdo e de tamanho, listagem,
download e remoção lógica, com histórico e auditoria."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from . import auditoria, fluxo
from .config import config
from .dependencias import Atual, Db
from .modelos import Anexo, HistoricoSolicitacao, Solicitacao, Usuario

router = APIRouter(prefix="/api/v1/solicitacoes", tags=["anexos"])

TIPOS = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


class AnexoSaida(BaseModel):
    id: int
    nome: str
    tipo: str
    tamanho: int
    sha256: str
    enviado_por: int
    em: datetime


def tipo_pelo_conteudo(dados: bytes) -> str | None:
    """Tipo real do arquivo pelos primeiros bytes (não confia na extensão nem no Content-Type do cliente)."""
    if dados.startswith(b"%PDF-"):
        return "pdf"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if dados.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if dados.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                if "word/document.xml" in z.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            return None
    return None


def _nome_seguro(nome: str | None, tipo: str) -> str:
    base = Path(nome or "arquivo").name
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE).strip(" .")[:150] or "arquivo"
    ext = "jpg" if tipo == "jpg" else tipo
    if not base.lower().endswith("." + ext) and not (tipo == "jpg" and base.lower().endswith(".jpeg")):
        base = f"{base}.{ext}"
    return base


def _buscar(db, sid: int, u: Usuario) -> Solicitacao:
    s = db.get(Solicitacao, sid)
    if s is None or not fluxo.pode_ver(s, u):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "solicitação não encontrada")
    return s


def _pode_anexar(s: Solicitacao, u: Usuario) -> bool:
    if s.arquivada or s.status in fluxo.FINAIS:
        return False
    if u.perfil == "solicitante":
        return s.solicitante_id == u.id
    if u.perfil == "operador":
        return s.responsavel_id == u.id
    return u.perfil == "gestor"


@router.post("/{sid}/anexos", response_model=AnexoSaida, status_code=201)
async def enviar(sid: int, arquivo: UploadFile, db: Db, u: Atual) -> AnexoSaida:
    s = _buscar(db, sid, u)
    if not _pode_anexar(s, u):
        raise HTTPException(status.HTTP_409_CONFLICT, "não é possível anexar: solicitação finalizada, arquivada ou fora da sua responsabilidade")
    qtd = db.scalar(select(func.count()).select_from(Anexo).where(Anexo.solicitacao_id == s.id, Anexo.removido.is_(False)))
    if qtd >= config().anexos_por_solicitacao:
        raise HTTPException(status.HTTP_409_CONFLICT, f"limite de {config().anexos_por_solicitacao} anexos por solicitação")
    limite = config().anexo_max_bytes
    dados = await arquivo.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"arquivo maior que {limite // (1024 * 1024)} MB")
    if not dados:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "arquivo vazio")
    tipo = tipo_pelo_conteudo(dados)
    if tipo is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "tipo não aceito: envie PDF, PNG, JPEG ou DOCX")
    sha = hashlib.sha256(dados).hexdigest()
    pasta = Path(config().anexos_dir) / str(s.id)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{uuid.uuid4().hex}.{tipo}"  # nome no disco nunca vem do cliente
    caminho.write_bytes(dados)
    a = Anexo(solicitacao_id=s.id, nome=_nome_seguro(arquivo.filename, tipo), tipo=TIPOS[tipo], tamanho=len(dados),
              sha256=sha, caminho=str(caminho), enviado_por=u.id)
    db.add(a)
    db.flush()
    db.add(HistoricoSolicitacao(solicitacao_id=s.id, ator_id=u.id, evento="anexo", comentario=f"anexado: {a.nome}"))
    auditoria.registrar(db, acao="anexar", recurso="solicitacao", recurso_id=s.id, ator_id=u.id,
                        depois={"anexo_id": a.id, "nome": a.nome, "tipo": a.tipo, "tamanho": a.tamanho, "sha256": sha})
    return AnexoSaida.model_validate(a, from_attributes=True)


@router.get("/{sid}/anexos", response_model=list[AnexoSaida])
def listar(sid: int, db: Db, u: Atual) -> list[AnexoSaida]:
    s = _buscar(db, sid, u)
    q = select(Anexo).where(Anexo.solicitacao_id == s.id, Anexo.removido.is_(False)).order_by(Anexo.id)
    return [AnexoSaida.model_validate(a, from_attributes=True) for a in db.scalars(q)]


def _anexo(db, s: Solicitacao, aid: int) -> Anexo:
    a = db.get(Anexo, aid)
    if a is None or a.solicitacao_id != s.id or a.removido:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "anexo não encontrado")
    return a


@router.get("/{sid}/anexos/{aid}")
def baixar(sid: int, aid: int, db: Db, u: Atual) -> FileResponse:
    s = _buscar(db, sid, u)
    a = _anexo(db, s, aid)
    p = Path(a.caminho)
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != a.sha256:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "arquivo do anexo ausente ou alterado no armazenamento")
    return FileResponse(p, media_type=a.tipo, filename=a.nome, headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{sid}/anexos/{aid}", status_code=204)
def remover(sid: int, aid: int, db: Db, u: Atual) -> None:
    s = _buscar(db, sid, u)
    a = _anexo(db, s, aid)
    if not (_pode_anexar(s, u) and (a.enviado_por == u.id or u.perfil == "gestor")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só quem enviou (ou o gestor) remove o anexo, e só enquanto a solicitação está em andamento")
    a.removido = True  # remoção lógica: o arquivo e o hash ficam para a auditoria
    db.add(HistoricoSolicitacao(solicitacao_id=s.id, ator_id=u.id, evento="anexo", comentario=f"removido: {a.nome}"))
    auditoria.registrar(db, acao="remover_anexo", recurso="solicitacao", recurso_id=s.id, ator_id=u.id,
                        antes={"anexo_id": a.id, "nome": a.nome, "removido": False}, depois={"removido": True})
