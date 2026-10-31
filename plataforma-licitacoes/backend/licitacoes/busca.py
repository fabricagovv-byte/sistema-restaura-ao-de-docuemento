"""Busca de licitações com filtros estruturados e expansão por significado.

A palavra-chave passa por `taxonomia.expandir_consulta`: cada parte da consulta vira um grupo de
termos equivalentes (OU dentro do grupo, E entre grupos). No PostgreSQL a busca usa o índice
trigram (pg_trgm) sobre o texto normalizado; no SQLite, LIKE simples. Com OpenSearch configurado,
a mesma consulta pode ir para lá (ver indexacao.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from .coleta import abertas_filtro
from .modelos import Analise, Licitacao, agora
from .taxonomia import expandir_consulta, termo_normalizado
from .util import normalizar, so_digitos


@dataclass
class Filtros:
    q: str | None = None                    # palavra-chave (com expansão semântica)
    expandir: bool = True
    objeto: str | None = None               # texto literal no objeto (sem expansão)
    ufs: list[str] = field(default_factory=list)
    municipio: str | None = None
    codigo_ibge: str | None = None
    orgao: str | None = None                # nome ou CNPJ
    numero: str | None = None               # número do edital/compra
    processo: str | None = None
    modalidades: list[int] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)
    situacao: str = "aberta"                # aberta, futura, em_andamento, encerrada, todas
    publicacao_de: datetime | None = None
    publicacao_ate: datetime | None = None
    abertura_de: datetime | None = None
    abertura_ate: datetime | None = None
    prazo_de: datetime | None = None
    prazo_ate: datetime | None = None
    valor_min: float | None = None
    valor_max: float | None = None
    incluir_sem_valor: bool = True
    exigencia: str | None = None            # texto procurado nas análises (ex.: "atestado", "ISO 27001")
    plataforma: str | None = None
    tipo_registro: str | None = None
    incluir_duplicadas: bool = False
    ordenar: str = "prazo"                  # prazo, valor, publicacao, aderencia
    pagina: int = 1
    por_pagina: int = 20


def _cond_termo(t: str):
    return Licitacao.texto_busca.like(f"%{t}%")


def montar_consulta(f: Filtros):
    conds = []
    explicacao: dict = {}
    if f.q:
        if f.expandir:
            exp = expandir_consulta(f.q)
            explicacao = exp
            for g in exp["grupos"]:
                alternativas = [_cond_termo(t) for t in g["termos"]]
                excluir: set[str] = set()
                for r in g.get("regras", []):
                    if r["ambiguos"] and r["contexto"]:
                        alternativas.append(and_(or_(*[_cond_termo(t) for t in r["ambiguos"]]),
                                                 or_(*[_cond_termo(t) for t in r["contexto"]])))
                    excluir.update(r["excluir"])
                conds.append(or_(*alternativas))
                # A exclusão só vale quando a consulta é uma categoria conhecida (ex.: "digitalização" sem
                # outsourcing de impressão). Quem quiser o termo literal usa expandir=false.
                if excluir:
                    conds.append(~or_(*[_cond_termo(t) for t in sorted(excluir)]))
        else:
            for parte in [p for p in f.q.replace(";", ",").split(",") if p.strip()]:
                conds.append(_cond_termo(termo_normalizado(parte.strip())))
    if f.objeto:
        conds.append(_cond_termo(normalizar(f.objeto)))
    if f.ufs:
        conds.append(Licitacao.uf.in_([u.upper() for u in f.ufs]))
    if f.municipio:
        conds.append(func.lower(Licitacao.municipio).like(f"%{f.municipio.lower()}%"))
    if f.codigo_ibge:
        conds.append(Licitacao.codigo_ibge == f.codigo_ibge)
    if f.orgao:
        dig = so_digitos(f.orgao)
        if len(dig) >= 8:
            conds.append(Licitacao.cnpj_orgao.like(f"{dig}%"))
        else:
            conds.append(Licitacao.texto_busca.like(f"%{normalizar(f.orgao)}%"))
    if f.numero:
        conds.append(Licitacao.numero_compra.ilike(f"%{f.numero}%"))
    if f.processo:
        conds.append(Licitacao.processo.ilike(f"%{f.processo}%"))
    if f.modalidades:
        conds.append(Licitacao.modalidade_id.in_(f.modalidades))
    if f.categorias:
        conds.append(or_(*[cast(Licitacao.categorias, String).like(f'%"codigo": "{c}"%') for c in f.categorias]))
    if f.plataforma:
        conds.append(Licitacao.plataforma_origem == f.plataforma)
    if f.tipo_registro:
        conds.append(Licitacao.tipo_registro == f.tipo_registro)
    a = agora()
    if f.situacao == "aberta":
        conds.append(abertas_filtro(a))
        conds.append(or_(Licitacao.data_abertura.is_(None), Licitacao.data_abertura <= a))
    elif f.situacao == "futura":
        conds.append(abertas_filtro(a))
        conds.append(Licitacao.data_abertura > a)
    elif f.situacao == "em_andamento":  # aberta ou futura, ainda recebendo/vai receber propostas
        conds.append(abertas_filtro(a))
    elif f.situacao == "encerrada":
        conds.append(or_(Licitacao.data_encerramento < a, Licitacao.excluida.is_(True),
                         Licitacao.situacao.ilike("revogad%"), Licitacao.situacao.ilike("anulad%")))
    if not f.incluir_duplicadas:
        conds.append(Licitacao.duplicata_de_id.is_(None))
    for col, de, ate in ((Licitacao.data_publicacao, f.publicacao_de, f.publicacao_ate),
                         (Licitacao.data_abertura, f.abertura_de, f.abertura_ate),
                         (Licitacao.data_encerramento, f.prazo_de, f.prazo_ate)):
        if de:
            conds.append(col >= de)
        if ate:
            conds.append(col <= ate + (timedelta(days=1) if ate.hour == 0 and ate.minute == 0 else timedelta()))
    if f.valor_min is not None or f.valor_max is not None:
        faixa = []
        if f.valor_min is not None:
            faixa.append(Licitacao.valor_estimado >= f.valor_min)
        if f.valor_max is not None:
            faixa.append(Licitacao.valor_estimado <= f.valor_max)
        if f.incluir_sem_valor:
            conds.append(or_(and_(*faixa), Licitacao.valor_estimado.is_(None)))
        else:
            conds.append(and_(*faixa))
    elif not f.incluir_sem_valor:
        conds.append(Licitacao.valor_estimado.isnot(None))
    if f.exigencia:
        sub = select(Analise.licitacao_id).where(
            cast(Analise.relatorio, String).ilike(f"%{f.exigencia}%"))
        conds.append(Licitacao.id.in_(sub))
    return and_(*conds) if conds else None, explicacao


def buscar(s: Session, f: Filtros) -> dict:
    cond, explicacao = montar_consulta(f)
    q = s.query(Licitacao)
    if cond is not None:
        q = q.filter(cond)
    total = q.count()
    ordem = {
        "prazo": [Licitacao.data_encerramento.asc()],
        "valor": [Licitacao.valor_estimado.desc().nulls_last()],
        "publicacao": [Licitacao.data_publicacao.desc().nulls_last()],
        "aderencia": [Licitacao.aderencia.desc(), Licitacao.data_encerramento.asc()],
    }.get(f.ordenar, [Licitacao.data_encerramento.asc()])
    por = max(1, min(200, f.por_pagina))
    itens = q.order_by(*ordem, Licitacao.id).offset((max(1, f.pagina) - 1) * por).limit(por).all()
    return {"total": total, "pagina": f.pagina, "por_pagina": por, "itens": itens, "expansao": explicacao}
