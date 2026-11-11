"""Painel gerencial (REQ-004): indicadores por status, categoria, responsável, prioridade e prazo, e exportação CSV.

Regras:
* só quem tem `painel:ver` vê os indicadores e só quem tem `painel:exportar` exporta (gestor, pela matriz central);
* os mesmos filtros valem para os indicadores e para o CSV, de modo que os números conciliam com as linhas exportadas;
* datas de filtro são dias do calendário de Brasília (inclusivos); o banco guarda UTC;
* o CSV não leva a descrição nem o nome do solicitante (minimização de dados pessoais), leva só o identificador;
* células que começam com = + - @ recebem apóstrofo, para a planilha não executar fórmula vinda de texto do usuário;
* cada exportação gera evento de auditoria com filtros, quantidade de linhas e SHA-256 do arquivo entregue.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import case, func, select

from . import auditoria, fluxo
from .dependencias import Db, exige
from .modelos import Categoria, HistoricoSolicitacao, Solicitacao, Usuario

router = APIRouter(prefix="/api/v1/painel", tags=["painel"])

BRASILIA = ZoneInfo("America/Sao_Paulo")
LIMITE_EXPORTACAO = 50_000
JANELA_VENCIMENTO = timedelta(hours=48)
PRIORIDADES = ("baixa", "normal", "alta", "urgente")
ATENDIDAS = ("concluida", "indeferida")  # entram no indicador de prazo; cancelada pelo solicitante não entra

Prioridade = Literal["baixa", "normal", "alta", "urgente"]
Status = Literal["recebida", "em_triagem", "em_atendimento", "aguardando_solicitante", "concluida", "indeferida", "cancelada"]
Arquivadas = Literal["excluir", "incluir", "somente"]


# ------------------------------------------------------------------ filtros
@dataclass(frozen=True)
class Filtro:
    de: date | None
    ate: date | None
    status: str | None
    categoria_id: int | None
    responsavel_id: int | None
    sem_responsavel: bool
    prioridade: str | None
    arquivadas: str

    def como_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in self.__dict__.items() if v not in (None, False)}

    def condicoes(self) -> list:
        f = []
        if self.arquivadas == "excluir":
            f.append(Solicitacao.arquivada.is_(False))
        elif self.arquivadas == "somente":
            f.append(Solicitacao.arquivada.is_(True))
        if self.de:
            f.append(Solicitacao.criado_em >= _inicio_do_dia(self.de))
        if self.ate:
            f.append(Solicitacao.criado_em < _inicio_do_dia(self.ate + timedelta(days=1)))
        if self.status:
            f.append(Solicitacao.status == self.status)
        if self.categoria_id:
            f.append(Solicitacao.categoria == str(self.categoria_id))
        if self.sem_responsavel:
            f.append(Solicitacao.responsavel_id.is_(None))
        elif self.responsavel_id:
            f.append(Solicitacao.responsavel_id == self.responsavel_id)
        if self.prioridade:
            f.append(Solicitacao.prioridade == self.prioridade)
        return f


def _inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time.min, BRASILIA).astimezone(timezone.utc)


def filtro(de: date | None = None, ate: date | None = None,
           status_: Annotated[Status | None, Query(alias="status")] = None,
           categoria_id: Annotated[int | None, Query(ge=1)] = None,
           responsavel_id: Annotated[int | None, Query(ge=1)] = None,
           sem_responsavel: bool = False, prioridade: Prioridade | None = None,
           arquivadas: Arquivadas = "excluir") -> Filtro:
    if de and ate and ate < de:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "a data final é anterior à inicial")
    if sem_responsavel and responsavel_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "use responsavel_id ou sem_responsavel, não os dois")
    return Filtro(de, ate, status_, categoria_id, responsavel_id, sem_responsavel, prioridade, arquivadas)


Filtros = Annotated[Filtro, Depends(filtro)]


# ------------------------------------------------------------------ esquemas
class ContagemCategoria(BaseModel):
    id: int
    nome: str
    total: int
    abertas: int


class ContagemResponsavel(BaseModel):
    id: int | None
    nome: str
    total: int
    abertas: int
    atrasadas: int


class Prazo(BaseModel):
    abertas_no_prazo: int
    abertas_atrasadas: int
    vencem_em_48h: int
    atendidas_no_prazo: int
    atendidas_com_atraso: int
    canceladas: int
    sem_prazo: int
    percentual_atendidas_no_prazo: float | None


class Indicadores(BaseModel):
    gerado_em: datetime
    filtros: dict
    total: int
    abertas: int
    por_status: dict[str, int]
    por_prioridade: dict[str, int]
    por_categoria: list[ContagemCategoria]
    por_responsavel: list[ContagemResponsavel]
    prazo: Prazo
    tempo_medio_conclusao_horas: float | None


# ------------------------------------------------------------------ consulta
def _fim():
    """Momento em que cada solicitação entrou no estado final atual (última transição para um estado final)."""
    return (select(HistoricoSolicitacao.solicitacao_id.label("sid"), HistoricoSolicitacao.para_status.label("para"),
                   func.max(HistoricoSolicitacao.em).label("fim"))
            .where(HistoricoSolicitacao.para_status.in_(tuple(fluxo.FINAIS)))
            .group_by(HistoricoSolicitacao.solicitacao_id, HistoricoSolicitacao.para_status).subquery())


def _soma(cond):
    return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)


def _utc(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


@router.get("/indicadores", response_model=Indicadores)
def indicadores(db: Db, f: Filtros, _: Annotated[Usuario, Depends(exige("painel:ver"))]) -> Indicadores:
    agora = datetime.now(timezone.utc)
    cond = f.condicoes()
    aberta = Solicitacao.status.not_in(tuple(fluxo.FINAIS))
    atrasada = aberta & (Solicitacao.prazo_em < agora)

    por_status = dict.fromkeys(fluxo.ESTADOS, 0)
    for st, n in db.execute(select(Solicitacao.status, func.count()).where(*cond).group_by(Solicitacao.status)):
        por_status[st] = n
    por_prioridade = dict.fromkeys(PRIORIDADES, 0)
    for p, n in db.execute(select(Solicitacao.prioridade, func.count()).where(*cond).group_by(Solicitacao.prioridade)):
        por_prioridade[p] = n

    nomes_cat = {str(c.id): c.nome for c in db.scalars(select(Categoria))}
    por_categoria = [ContagemCategoria(id=int(cid), nome=nomes_cat.get(cid, "?"), total=n, abertas=ab)
                     for cid, n, ab in db.execute(select(Solicitacao.categoria, func.count(), _soma(aberta))
                                                  .where(*cond).group_by(Solicitacao.categoria))]
    por_categoria.sort(key=lambda x: (-x.total, x.nome))

    pessoas = {u.id: u.nome for u in db.scalars(select(Usuario))}
    por_responsavel = [ContagemResponsavel(id=rid, nome=pessoas.get(rid, "?") if rid else "Sem responsável", total=n, abertas=ab, atrasadas=at)
                       for rid, n, ab, at in db.execute(select(Solicitacao.responsavel_id, func.count(), _soma(aberta), _soma(atrasada))
                                                        .where(*cond).group_by(Solicitacao.responsavel_id))]
    por_responsavel.sort(key=lambda x: (x.id is not None, -x.total, x.nome))

    fim = _fim()
    entrou_no_final = (fim.c.sid == Solicitacao.id) & (fim.c.para == Solicitacao.status)
    atendida = Solicitacao.status.in_(ATENDIDAS)
    linha = db.execute(select(
        _soma(aberta & (Solicitacao.prazo_em >= agora)),
        _soma(atrasada),
        _soma(aberta & (Solicitacao.prazo_em >= agora) & (Solicitacao.prazo_em < agora + JANELA_VENCIMENTO)),
        _soma(atendida & (fim.c.fim <= Solicitacao.prazo_em)),
        _soma(atendida & (fim.c.fim > Solicitacao.prazo_em)),
        _soma(Solicitacao.status == "cancelada"),
        _soma(Solicitacao.prazo_em.is_(None)),
    ).select_from(Solicitacao).outerjoin(fim, entrou_no_final).where(*cond)).one()
    no_prazo, atrasadas, vencem, at_ok, at_atraso, canceladas, sem_prazo = (int(x) for x in linha)
    atendidas = at_ok + at_atraso

    duracoes = [(_utc(fim_em) - _utc(criado)).total_seconds() / 3600 for criado, fim_em in db.execute(
        select(Solicitacao.criado_em, fim.c.fim).join(fim, entrou_no_final).where(*cond, Solicitacao.status == "concluida"))]

    total = sum(por_status.values())
    return Indicadores(
        gerado_em=agora, filtros=f.como_dict(), total=total,
        abertas=sum(n for st, n in por_status.items() if st not in fluxo.FINAIS),
        por_status=por_status, por_prioridade=por_prioridade, por_categoria=por_categoria, por_responsavel=por_responsavel,
        prazo=Prazo(abertas_no_prazo=no_prazo, abertas_atrasadas=atrasadas, vencem_em_48h=vencem, atendidas_no_prazo=at_ok,
                    atendidas_com_atraso=at_atraso, canceladas=canceladas, sem_prazo=sem_prazo,
                    percentual_atendidas_no_prazo=round(100 * at_ok / atendidas, 1) if atendidas else None),
        tempo_medio_conclusao_horas=round(sum(duracoes) / len(duracoes), 2) if duracoes else None)


# ------------------------------------------------------------------ exportação
COLUNAS = ("protocolo", "titulo", "categoria", "status", "prioridade", "solicitante_id", "responsavel", "criado_em",
           "prazo_em", "finalizada_em", "situacao_prazo", "arquivada")
PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def celula_segura(v: object) -> str:
    """Texto pronto para planilha: neutraliza fórmula (injeção em CSV) e quebras de linha."""
    t = "" if v is None else str(v)
    t = t.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return "'" + t if t.startswith(PERIGOSOS) else t


def _br(d: datetime | None) -> str:
    return _utc(d).astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M") if d else ""


def situacao_prazo(st: str, prazo: datetime | None, fim_em: datetime | None, agora: datetime) -> str:
    if st == "cancelada":
        return "cancelada"
    if prazo is None:
        return "sem_prazo"
    if st in ATENDIDAS:
        return "atendida_no_prazo" if fim_em and fim_em <= prazo else "atendida_com_atraso"
    return "atrasada" if prazo < agora else "no_prazo"


@router.get("/exportacao.csv", response_class=Response,
            responses={200: {"content": {"text/csv": {}}, "description": "CSV separado por ponto e vírgula, UTF-8 com BOM"}})
def exportar(db: Db, f: Filtros, u: Annotated[Usuario, Depends(exige("painel:exportar"))]) -> Response:
    cond = f.condicoes()
    total = db.scalar(select(func.count()).select_from(Solicitacao).where(*cond))
    if total > LIMITE_EXPORTACAO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"{total} linhas passam do limite de {LIMITE_EXPORTACAO}; restrinja o período ou os filtros")
    agora = datetime.now(timezone.utc)
    fim = _fim()
    nomes_cat = {str(c.id): c.nome for c in db.scalars(select(Categoria))}
    pessoas = {p.id: p.nome for p in db.scalars(select(Usuario))}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(COLUNAS)
    q = (select(Solicitacao, fim.c.fim).outerjoin(fim, (fim.c.sid == Solicitacao.id) & (fim.c.para == Solicitacao.status))
         .where(*cond).order_by(Solicitacao.id))
    linhas = 0
    for s, fim_em in db.execute(q):
        prazo, fim_em = _utc(s.prazo_em), _utc(fim_em)
        w.writerow([celula_segura(x) for x in (
            s.protocolo, s.titulo, nomes_cat.get(s.categoria, "?"), s.status, s.prioridade, s.solicitante_id,
            pessoas.get(s.responsavel_id, "") if s.responsavel_id else "", _br(s.criado_em), _br(prazo), _br(fim_em),
            situacao_prazo(s.status, prazo, fim_em, agora), "sim" if s.arquivada else "não")])
        linhas += 1
    corpo = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM: o Excel em português abre com acentos corretos
    sha = hashlib.sha256(corpo).hexdigest()
    auditoria.registrar(db, acao="exportar", recurso="painel", ator_id=u.id,
                        depois={"filtros": f.como_dict(), "linhas": linhas, "sha256": sha})
    nome = f"solicitacoes-{agora.astimezone(BRASILIA):%Y%m%d-%H%M}.csv"
    return Response(corpo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"', "X-Total-Linhas": str(linhas),
                             "X-Conteudo-SHA256": sha})
