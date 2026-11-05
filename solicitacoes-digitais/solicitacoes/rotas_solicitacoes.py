"""Categorias e solicitações: cadastro (REQ-002), tramitação e atribuição (REQ-003), histórico e auditoria (REQ-005)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select

from . import auditoria, fluxo
from .dependencias import Atual, Db, exige
from .modelos import Categoria, HistoricoSolicitacao, Solicitacao, Usuario

router = APIRouter(prefix="/api/v1")

Prioridade = Literal["baixa", "normal", "alta", "urgente"]
Status = Literal["recebida", "em_triagem", "em_atendimento", "aguardando_solicitante", "concluida", "indeferida", "cancelada"]


def _texto(v: str) -> str:
    v = " ".join(v.split()) if "\n" not in v else v.strip()
    if not v:
        raise ValueError("não pode ficar em branco")
    return v


# ------------------------------------------------------------------ esquemas
class CategoriaNova(BaseModel):
    nome: str = Field(min_length=2, max_length=60)
    prazo_dias: int = Field(ge=1, le=365)
    _n = field_validator("nome")(lambda cls, v: _texto(v))


class CategoriaAlteracao(BaseModel):
    prazo_dias: int | None = Field(default=None, ge=1, le=365)
    ativa: bool | None = None


class CategoriaSaida(BaseModel):
    id: int
    nome: str
    prazo_dias: int
    ativa: bool


class SolicitacaoNova(BaseModel):
    titulo: str = Field(min_length=5, max_length=200)
    descricao: str = Field(min_length=10, max_length=10000)
    categoria_id: int
    prioridade: Prioridade = "normal"
    _t = field_validator("titulo", "descricao")(lambda cls, v: _texto(v))


class SolicitacaoAlteracao(BaseModel):
    titulo: str | None = Field(default=None, min_length=5, max_length=200)
    descricao: str | None = Field(default=None, min_length=10, max_length=10000)
    categoria_id: int | None = None
    prioridade: Prioridade | None = None
    _t = field_validator("titulo", "descricao")(lambda cls, v: v if v is None else _texto(v))


class Tramitacao(BaseModel):
    para: Status
    comentario: str | None = Field(default=None, max_length=5000)


class Atribuicao(BaseModel):
    responsavel_id: int
    comentario: str | None = Field(default=None, max_length=2000)


class Arquivamento(BaseModel):
    arquivar: bool = True
    comentario: str | None = Field(default=None, max_length=2000)


class PessoaResumo(BaseModel):
    id: int
    nome: str


class SolicitacaoSaida(BaseModel):
    id: int
    protocolo: str
    titulo: str
    descricao: str
    categoria: str
    status: str
    prioridade: str
    solicitante: PessoaResumo
    responsavel: PessoaResumo | None
    prazo_em: datetime | None
    atrasada: bool
    arquivada: bool
    criado_em: datetime
    atualizado_em: datetime
    acoes_possiveis: list[str]


class Pagina(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[SolicitacaoSaida]


class HistoricoSaida(BaseModel):
    id: int
    em: datetime
    ator: PessoaResumo
    evento: str
    de_status: str | None
    para_status: str | None
    comentario: str | None


# ------------------------------------------------------------------ apoio
def _utc(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _acoes(s: Solicitacao, u: Usuario) -> list[str]:
    out = []
    for (de, para), t in fluxo.TRANSICOES.items():
        if de != s.status or s.arquivada:
            continue
        try:
            fluxo.validar(s, para, u, "x")
            out.append(para)
        except fluxo.TransicaoInvalida as e:
            if e.codigo == 409 and "responsável" in str(e):  # possível depois de atribuir
                out.append(para)
    return out


def _saida(s: Solicitacao, u: Usuario, cat: str) -> SolicitacaoSaida:
    prazo = _utc(s.prazo_em)
    return SolicitacaoSaida(
        id=s.id, protocolo=s.protocolo, titulo=s.titulo, descricao=s.descricao, categoria=cat, status=s.status,
        prioridade=s.prioridade, solicitante=PessoaResumo(id=s.solicitante.id, nome=s.solicitante.nome),
        responsavel=PessoaResumo(id=s.responsavel.id, nome=s.responsavel.nome) if s.responsavel else None,
        prazo_em=prazo, atrasada=bool(prazo and s.status not in fluxo.FINAIS and prazo < datetime.now(timezone.utc)),
        arquivada=s.arquivada, criado_em=_utc(s.criado_em), atualizado_em=_utc(s.atualizado_em), acoes_possiveis=_acoes(s, u))


def _nome_cat(db, cid: str) -> str:
    c = db.get(Categoria, int(cid))
    return c.nome if c else "?"


def _buscar(db, sid: int, u: Usuario) -> Solicitacao:
    s = db.get(Solicitacao, sid)
    if s is None or not fluxo.pode_ver(s, u):  # 404 também quando não pode ver, para não revelar que existe
        raise HTTPException(status.HTTP_404_NOT_FOUND, "solicitação não encontrada")
    return s


def _historico(db, s: Solicitacao, ator: Usuario, evento: str, de: str | None = None, para: str | None = None, comentario: str | None = None):
    db.add(HistoricoSolicitacao(solicitacao_id=s.id, ator_id=ator.id, evento=evento, de_status=de, para_status=para,
                                comentario=comentario.strip() if comentario else None))


def _foto(s: Solicitacao) -> dict:
    return {"status": s.status, "titulo": s.titulo, "categoria": s.categoria, "prioridade": s.prioridade,
            "responsavel_id": s.responsavel_id, "arquivada": s.arquivada}


# ------------------------------------------------------------------ categorias
@router.get("/categorias", response_model=list[CategoriaSaida], tags=["categorias"])
def listar_categorias(db: Db, u: Atual, todas: bool = False) -> list[CategoriaSaida]:
    q = select(Categoria).order_by(Categoria.nome)
    if not (todas and u.perfil == "administrador"):
        q = q.where(Categoria.ativa.is_(True))
    return [CategoriaSaida.model_validate(c, from_attributes=True) for c in db.scalars(q)]


@router.post("/categorias", response_model=CategoriaSaida, status_code=201, tags=["categorias"])
def criar_categoria(dados: CategoriaNova, db: Db, adm: Annotated[Usuario, Depends(exige("categorias:gerir"))]) -> CategoriaSaida:
    if db.scalar(select(Categoria).where(func.lower(Categoria.nome) == dados.nome.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "já existe categoria com este nome")
    c = Categoria(nome=dados.nome, prazo_dias=dados.prazo_dias)
    db.add(c)
    db.flush()
    auditoria.registrar(db, acao="criar", recurso="categoria", recurso_id=c.id, ator_id=adm.id, depois=dados.model_dump())
    return CategoriaSaida.model_validate(c, from_attributes=True)


@router.patch("/categorias/{cid}", response_model=CategoriaSaida, tags=["categorias"])
def alterar_categoria(cid: int, dados: CategoriaAlteracao, db: Db, adm: Annotated[Usuario, Depends(exige("categorias:gerir"))]) -> CategoriaSaida:
    c = db.get(Categoria, cid)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
    mud = dados.model_dump(exclude_none=True)
    antes = {k: getattr(c, k) for k in mud}
    for k, v in mud.items():
        setattr(c, k, v)
    auditoria.registrar(db, acao="alterar", recurso="categoria", recurso_id=c.id, ator_id=adm.id, antes=antes, depois=mud)
    return CategoriaSaida.model_validate(c, from_attributes=True)


# ------------------------------------------------------------------ solicitações
@router.post("/solicitacoes", response_model=SolicitacaoSaida, status_code=201, tags=["solicitações"])
def criar_solicitacao(dados: SolicitacaoNova, db: Db, u: Annotated[Usuario, Depends(exige("solicitacoes:criar"))]) -> SolicitacaoSaida:
    cat = db.get(Categoria, dados.categoria_id)
    if cat is None or not cat.ativa:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "categoria inexistente ou inativa")
    agora = datetime.now(timezone.utc)
    s = Solicitacao(protocolo="pendente", titulo=dados.titulo, descricao=dados.descricao, categoria=str(cat.id),
                    prioridade=dados.prioridade, solicitante_id=u.id, status="recebida", prazo_em=agora + timedelta(days=cat.prazo_dias))
    db.add(s)
    db.flush()
    s.protocolo = f"{agora.year}{s.id:06d}"  # ano + sequencial: único e fácil de ditar
    _historico(db, s, u, "criacao", para="recebida")
    auditoria.registrar(db, acao="criar", recurso="solicitacao", recurso_id=s.id, ator_id=u.id, depois=_foto(s))
    db.flush()
    db.refresh(s)
    return _saida(s, u, cat.nome)


@router.get("/solicitacoes", response_model=Pagina, tags=["solicitações"])
def listar_solicitacoes(db: Db, u: Atual,
                        status_: Annotated[Status | None, Query(alias="status")] = None,
                        categoria_id: int | None = None, responsavel_id: int | None = None, prioridade: Prioridade | None = None,
                        q: Annotated[str | None, Query(max_length=100)] = None, arquivada: bool = False, atrasada: bool | None = None,
                        pagina: Annotated[int, Query(ge=1)] = 1, por_pagina: Annotated[int, Query(ge=1, le=100)] = 20) -> Pagina:
    if u.perfil == "administrador":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "o administrador gere o sistema e não acompanha solicitações")
    filtro = [Solicitacao.arquivada.is_(arquivada)]
    if u.perfil == "solicitante":
        filtro.append(Solicitacao.solicitante_id == u.id)
    elif u.perfil == "operador":
        filtro.append(or_(Solicitacao.responsavel_id == u.id,
                          (Solicitacao.responsavel_id.is_(None)) & Solicitacao.status.in_(("recebida", "em_triagem"))))
    if status_:
        filtro.append(Solicitacao.status == status_)
    if categoria_id:
        filtro.append(Solicitacao.categoria == str(categoria_id))
    if responsavel_id:
        filtro.append(Solicitacao.responsavel_id == responsavel_id)
    if prioridade:
        filtro.append(Solicitacao.prioridade == prioridade)
    if q:
        termo = f"%{q.strip().lower()}%"
        filtro.append(or_(func.lower(Solicitacao.titulo).like(termo), func.lower(Solicitacao.descricao).like(termo), Solicitacao.protocolo.like(termo)))
    if atrasada is not None:
        cond = (Solicitacao.prazo_em < datetime.now(timezone.utc)) & Solicitacao.status.not_in(tuple(fluxo.FINAIS))
        filtro.append(cond if atrasada else ~cond)
    total = db.scalar(select(func.count()).select_from(Solicitacao).where(*filtro))
    itens = db.scalars(select(Solicitacao).where(*filtro).order_by(Solicitacao.prazo_em.asc(), Solicitacao.id)
                       .offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    cats = {c.id: c.nome for c in db.scalars(select(Categoria))}
    return Pagina(total=total, pagina=pagina, por_pagina=por_pagina, itens=[_saida(s, u, cats.get(int(s.categoria), "?")) for s in itens])


@router.get("/solicitacoes/{sid}", response_model=SolicitacaoSaida, tags=["solicitações"])
def ver_solicitacao(sid: int, db: Db, u: Atual) -> SolicitacaoSaida:
    s = _buscar(db, sid, u)
    return _saida(s, u, _nome_cat(db, s.categoria))


@router.patch("/solicitacoes/{sid}", response_model=SolicitacaoSaida, tags=["solicitações"])
def editar_solicitacao(sid: int, dados: SolicitacaoAlteracao, db: Db, u: Atual) -> SolicitacaoSaida:
    s = _buscar(db, sid, u)
    if not fluxo.pode_editar(s, u):
        raise HTTPException(status.HTTP_409_CONFLICT, "esta solicitação não pode mais ser editada por você")
    mud = dados.model_dump(exclude_none=True)
    if not mud:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nada para alterar")
    if "categoria_id" in mud:
        cat = db.get(Categoria, mud["categoria_id"])
        if cat is None or not cat.ativa:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "categoria inexistente ou inativa")
        mud["categoria"] = str(cat.id)
        s.prazo_em = _utc(s.criado_em) + timedelta(days=cat.prazo_dias)
        del mud["categoria_id"]
    antes = {k: getattr(s, k) for k in mud}
    for k, v in mud.items():
        setattr(s, k, v)
    _historico(db, s, u, "edicao", comentario="campos alterados: " + ", ".join(sorted(mud)))
    auditoria.registrar(db, acao="alterar", recurso="solicitacao", recurso_id=s.id, ator_id=u.id, antes=antes, depois=mud)
    db.flush()
    return _saida(s, u, _nome_cat(db, s.categoria))


@router.post("/solicitacoes/{sid}/tramitar", response_model=SolicitacaoSaida, tags=["tramitação"])
def tramitar(sid: int, dados: Tramitacao, db: Db, u: Atual) -> SolicitacaoSaida:
    s = _buscar(db, sid, u)
    try:
        fluxo.validar(s, dados.para, u, dados.comentario)
    except fluxo.TransicaoInvalida as e:
        raise HTTPException(e.codigo, str(e)) from None
    de = s.status
    s.status = dados.para
    if de in fluxo.FINAIS and dados.para == "em_triagem":  # reabertura volta para a fila
        s.responsavel_id = None
    _historico(db, s, u, "transicao", de=de, para=dados.para, comentario=dados.comentario)
    auditoria.registrar(db, acao="tramitar", recurso="solicitacao", recurso_id=s.id, ator_id=u.id,
                        antes={"status": de}, depois={"status": dados.para, "comentario": dados.comentario})
    db.flush()
    db.refresh(s)
    return _saida(s, u, _nome_cat(db, s.categoria))


@router.post("/solicitacoes/{sid}/atribuir", response_model=SolicitacaoSaida, tags=["tramitação"])
def atribuir(sid: int, dados: Atribuicao, db: Db, u: Atual) -> SolicitacaoSaida:
    s = _buscar(db, sid, u)
    if s.arquivada or s.status in fluxo.FINAIS:
        raise HTTPException(status.HTTP_409_CONFLICT, "solicitação finalizada ou arquivada não recebe responsável")
    if u.perfil == "operador":
        if dados.responsavel_id != u.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "o operador só pode assumir para si; atribuir a outra pessoa é do gestor")
        if s.responsavel_id not in (None, u.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "solicitação já tem outro responsável")
    elif u.perfil != "gestor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "seu perfil não atribui solicitações")
    alvo = db.get(Usuario, dados.responsavel_id)
    if alvo is None or not alvo.ativo or alvo.perfil not in ("operador", "gestor"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "o responsável precisa ser operador ou gestor ativo")
    antes = s.responsavel_id
    s.responsavel_id = alvo.id
    _historico(db, s, u, "atribuicao", comentario=f"responsável: {alvo.nome}" + (f" — {dados.comentario.strip()}" if dados.comentario else ""))
    auditoria.registrar(db, acao="atribuir", recurso="solicitacao", recurso_id=s.id, ator_id=u.id,
                        antes={"responsavel_id": antes}, depois={"responsavel_id": alvo.id})
    db.flush()
    db.refresh(s)
    return _saida(s, u, _nome_cat(db, s.categoria))


@router.post("/solicitacoes/{sid}/arquivamento", response_model=SolicitacaoSaida, tags=["tramitação"])
def arquivar(sid: int, dados: Arquivamento, db: Db, u: Annotated[Usuario, Depends(exige("solicitacoes:arquivar"))]) -> SolicitacaoSaida:
    s = _buscar(db, sid, u)
    if dados.arquivar and s.status not in fluxo.FINAIS:
        raise HTTPException(status.HTTP_409_CONFLICT, "só solicitações concluídas, indeferidas ou canceladas podem ser arquivadas")
    if s.arquivada == dados.arquivar:
        raise HTTPException(status.HTTP_409_CONFLICT, "a solicitação já está " + ("arquivada" if dados.arquivar else "ativa"))
    s.arquivada = dados.arquivar
    _historico(db, s, u, "arquivamento" if dados.arquivar else "desarquivamento", comentario=dados.comentario)
    auditoria.registrar(db, acao="arquivar" if dados.arquivar else "desarquivar", recurso="solicitacao", recurso_id=s.id,
                        ator_id=u.id, antes={"arquivada": not dados.arquivar}, depois={"arquivada": dados.arquivar})
    db.flush()
    return _saida(s, u, _nome_cat(db, s.categoria))


@router.get("/solicitacoes/{sid}/historico", response_model=list[HistoricoSaida], tags=["tramitação"])
def historico(sid: int, db: Db, u: Atual) -> list[HistoricoSaida]:
    s = _buscar(db, sid, u)
    linhas = db.scalars(select(HistoricoSolicitacao).where(HistoricoSolicitacao.solicitacao_id == s.id).order_by(HistoricoSolicitacao.id))
    pessoas = {p.id: p.nome for p in db.scalars(select(Usuario))}
    return [HistoricoSaida(id=h.id, em=_utc(h.em), ator=PessoaResumo(id=h.ator_id, nome=pessoas.get(h.ator_id, "?")), evento=h.evento,
                           de_status=h.de_status, para_status=h.para_status, comentario=h.comentario) for h in linhas]


@router.delete("/solicitacoes/{sid}", status_code=405, tags=["solicitações"], include_in_schema=False)
def excluir(sid: int) -> Response:
    raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "solicitações não são excluídas; finalize e arquive")
