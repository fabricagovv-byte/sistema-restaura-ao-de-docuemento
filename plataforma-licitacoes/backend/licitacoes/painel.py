"""Números do painel principal e do controle de qualidade."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session

from .catalogo import PLATAFORMAS_DA_FONTE
from .coleta import abertas_filtro
from .modelos import Analise, Documento, Favorito, Fonte, Licitacao, Municipio, Sincronizacao, agora

UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
       "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def _resumo(lic: Licitacao) -> dict:
    return {
        "id": lic.id, "orgao": lic.orgao_nome, "uf": lic.uf, "municipio": lic.municipio, "objeto": lic.objeto[:300],
        "valor_estimado": float(lic.valor_estimado) if lic.valor_estimado is not None else None,
        "data_encerramento": lic.data_encerramento.isoformat() if lic.data_encerramento else None,
        "modalidade": lic.modalidade, "aderencia": lic.aderencia, "link": lic.link_pncp or lic.link_origem,
        "categorias": [c["nome"] for c in lic.categorias or []],
    }


def painel(s: Session, usuario_id: int | None = None) -> dict:
    a = agora()
    abertas = s.query(Licitacao).filter(abertas_filtro(a))
    por_uf = dict(abertas.with_entities(Licitacao.uf, func.count()).group_by(Licitacao.uf).all())
    valor_uf = dict(abertas.with_entities(Licitacao.uf, func.sum(Licitacao.valor_estimado)).group_by(Licitacao.uf).all())
    por_mun = abertas.with_entities(Licitacao.uf, Licitacao.municipio, func.count()).filter(
        Licitacao.municipio.isnot(None)).group_by(Licitacao.uf, Licitacao.municipio).order_by(func.count().desc()).limit(15).all()
    fav = []
    if usuario_id:
        fav = [_resumo(lic) for lic in s.query(Licitacao).join(Favorito, Favorito.licitacao_id == Licitacao.id)
               .filter(Favorito.usuario_id == usuario_id).order_by(Licitacao.data_encerramento).limit(20).all()]
    return {
        "total_coletado": s.query(func.count(Licitacao.id)).scalar(),
        "abertos": abertas.count(),
        "publicados_24h": s.query(func.count(Licitacao.id)).filter(Licitacao.data_publicacao >= a - timedelta(hours=24)).scalar(),
        "coletados_24h": s.query(func.count(Licitacao.id)).filter(Licitacao.criado_em >= a - timedelta(hours=24)).scalar(),
        "valor_estimado_abertos": float(abertas.with_entities(func.sum(Licitacao.valor_estimado)).scalar() or 0),
        "sem_valor_abertos": abertas.filter(Licitacao.valor_estimado.is_(None)).count(),
        "por_uf": [{"uf": uf, "abertos": por_uf.get(uf, 0), "valor": float(valor_uf.get(uf) or 0)} for uf in UFS],
        "por_municipio": [{"uf": u, "municipio": m, "abertos": n} for u, m, n in por_mun],
        "prazos_proximos": [_resumo(x) for x in abertas.filter(Licitacao.data_encerramento <= a + timedelta(days=7))
                            .order_by(Licitacao.data_encerramento).limit(15).all()],
        "maior_aderencia": [_resumo(x) for x in abertas.order_by(Licitacao.aderencia.desc(), Licitacao.valor_estimado.desc().nulls_last()).limit(15).all()],
        "maiores_valores": [_resumo(x) for x in abertas.filter(Licitacao.valor_estimado.isnot(None))
                            .order_by(Licitacao.valor_estimado.desc()).limit(10).all()],
        "analisados": s.query(func.count(func.distinct(Analise.licitacao_id))).scalar(),
        "favoritos": fav,
        "atualizado_em": a.isoformat(),
    }


def qualidade(s: Session) -> dict:
    a = agora()
    fontes = s.query(Fonte).order_by(Fonte.codigo).all()
    lista = []
    for f in fontes:
        ult = s.query(Sincronizacao).filter_by(fonte_id=f.id).order_by(Sincronizacao.inicio.desc()).first()
        if f.status_integracao == "via_pncp":
            nomes = PLATAFORMAS_DA_FONTE.get(f.codigo, [])
            n = s.query(func.count(Licitacao.id)).filter(Licitacao.plataforma_origem.in_(nomes)).scalar() if nomes else 0
        else:
            n = s.query(func.count(Licitacao.id)).filter(cast(Licitacao.fontes_vistas, String).like(f'%"{f.codigo}"%')).scalar()
        if f.status_integracao in ("ativo", "requer_credencial") and f.ultima_sincronizacao:
            saude = "funcionando" if (f.falhas_consecutivas or 0) == 0 else "com_falha"
        elif f.status_integracao in ("ativo",):
            saude = "nunca_sincronizado"
        else:
            saude = f.status_integracao
        lista.append({
            "codigo": f.codigo, "nome": f.nome, "tipo": f.tipo, "status_integracao": f.status_integracao, "saude": saude,
            "como_coberto": f.como_coberto, "procedimento": f.procedimento,
            "ultima_sincronizacao": f.ultima_sincronizacao.isoformat() if f.ultima_sincronizacao else None,
            "ultimo_sucesso": f.ultimo_sucesso.isoformat() if f.ultimo_sucesso else None,
            "ultimo_erro": f.ultimo_erro, "falhas_consecutivas": f.falhas_consecutivas, "editais": n,
            "ultima_execucao": None if ult is None else {"status": ult.status, "lidos": ult.lidos, "novos": ult.novos,
                                                         "atualizados": ult.atualizados, "chamadas": ult.chamadas,
                                                         "mensagem": ult.mensagem},
        })
    total_mun = s.query(func.count(Municipio.codigo_ibge)).scalar() or 0
    desde = a - timedelta(days=90)
    com_edital = s.query(func.count(func.distinct(Licitacao.codigo_ibge))).filter(
        Licitacao.codigo_ibge.isnot(None), Licitacao.criado_em >= desde).scalar() or 0
    sem_por_uf = []
    if total_mun:
        cobertos = {c for (c,) in s.query(Licitacao.codigo_ibge).filter(
            Licitacao.codigo_ibge.isnot(None), Licitacao.criado_em >= desde).distinct()}
        por_uf: dict[str, list[int]] = {}
        for cod, uf in s.query(Municipio.codigo_ibge, Municipio.uf).all():
            tot = por_uf.setdefault(uf, [0, 0])
            tot[0] += 1
            tot[1] += cod in cobertos
        sem_por_uf = [{"uf": uf, "municipios": t, "com_edital": c, "sem_edital": t - c,
                       "percentual": round(100 * c / t, 1)} for uf, (t, c) in sorted(por_uf.items())]
        com_edital = len(cobertos & {c for (c,) in s.query(Municipio.codigo_ibge)})
    plataformas = s.query(Licitacao.plataforma_origem, func.count()).group_by(Licitacao.plataforma_origem).order_by(func.count().desc()).limit(25).all()
    return {
        "portais_cadastrados": len(fontes),
        "funcionando": sum(x["saude"] == "funcionando" for x in lista),
        "com_falha": sum(x["saude"] == "com_falha" for x in lista),
        "sem_integracao": [x["nome"] for x in lista if x["status_integracao"] in ("nao_integrado", "requer_credencial")],
        "fontes": lista,
        "editais_coletados": s.query(func.count(Licitacao.id)).scalar(),
        "atualizados_24h": s.query(func.count(Licitacao.id)).filter(Licitacao.atualizado_em >= a - timedelta(hours=24)).scalar(),
        "com_anexos": s.query(func.count(func.distinct(Documento.licitacao_id))).scalar(),
        "anexos_baixados": s.query(func.count(Documento.id)).filter(Documento.status == "baixado").scalar(),
        "anexos_indisponiveis": s.query(func.count(Documento.id)).filter(Documento.status.in_(["indisponivel", "requer_autenticacao", "erro"])).scalar(),
        "ultima_sincronizacao": max((x["ultima_sincronizacao"] for x in lista if x["ultima_sincronizacao"]), default=None),
        "cobertura": {
            "municipios_na_base_ibge": total_mun,
            "municipios_com_edital_90d": com_edital,
            "percentual_comprovado": round(100 * com_edital / total_mun, 2) if total_mun else None,
            "metodo": "municípios com ao menos um edital coletado nos últimos 90 dias ÷ municípios da lista do IBGE carregada",
            "por_uf": sem_por_uf,
        },
        "por_plataforma_origem": [{"plataforma": p or "não identificada", "editais": n} for p, n in plataformas],
        "duplicatas_ligadas": s.query(func.count(Licitacao.id)).filter(Licitacao.duplicata_de_id.isnot(None)).scalar(),
        "excluidos_detectados": s.query(func.count(Licitacao.id)).filter(Licitacao.excluida.is_(True)).scalar(),
    }
