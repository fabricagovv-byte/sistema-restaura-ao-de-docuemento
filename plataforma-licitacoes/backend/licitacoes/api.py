"""API HTTP (FastAPI). Documentação interativa em /docs."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import alertas, analise, catalogo, coleta, documentos, painel, precificacao, tarefas
from .auth import conferir_senha, emitir_token, exigir, obter_sessao, usuario_atual
from .busca import Filtros, buscar
from .db import iniciar_banco
from .modelos import (
    Alerta, Analise, Categoria, Favorito, HistoricoAlteracao, Licitacao, LogAuditoria, Monitoramento, Proposta, Usuario,
)
from .taxonomia import PADRAO, SEGMENTOS, expandir_consulta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def _ciclo_vida(_app):
    iniciar_banco()
    from .config import config
    from .db import sessao

    if config().jwt_segredo.startswith("troque-este-segredo"):
        logging.getLogger("licitacoes").warning("LIC_JWT_SEGREDO padrão: defina um segredo próprio em produção")
    with sessao() as s:
        catalogo.registrar_fontes(s)
    yield


app = FastAPI(title="Plataforma Nacional de Licitações", version="5.0", lifespan=_ciclo_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LEITOR = Depends(exigir("leitor"))
ANALISTA = Depends(exigir("analista"))
ADMIN = Depends(exigir("admin"))


def _auditar(s: Session, u: Usuario | None, acao: str, alvo: str, **det: Any) -> None:
    s.add(LogAuditoria(usuario_id=u.id if u else None, acao=acao, alvo=alvo, detalhes=det))
    s.commit()


def ser(lic: Licitacao, completo: bool = False) -> dict:
    d = {
        "id": lic.id, "chave": lic.chave, "numero_controle_pncp": lic.numero_controle_pncp, "tipo_registro": lic.tipo_registro,
        "orgao": lic.orgao_nome, "cnpj_orgao": lic.cnpj_orgao, "unidade": lic.unidade_nome, "esfera": lic.esfera,
        "uf": lic.uf, "municipio": lic.municipio, "numero": lic.numero_compra, "processo": lic.processo,
        "modalidade_id": lic.modalidade_id, "modalidade": lic.modalidade, "situacao": lic.situacao, "srp": lic.srp,
        "objeto": lic.objeto, "valor_estimado": float(lic.valor_estimado) if lic.valor_estimado is not None else None,
        "orcamento_sigiloso": lic.orcamento_sigiloso,
        "data_publicacao": lic.data_publicacao.isoformat() if lic.data_publicacao else None,
        "data_abertura": lic.data_abertura.isoformat() if lic.data_abertura else None,
        "data_encerramento": lic.data_encerramento.isoformat() if lic.data_encerramento else None,
        "link_pncp": lic.link_pncp, "link_origem": lic.link_origem, "plataforma_origem": lic.plataforma_origem,
        "categorias": lic.categorias, "aderencia": lic.aderencia, "fontes": lic.fontes_vistas,
        "excluida": lic.excluida, "duplicata_de_id": lic.duplicata_de_id,
        "atualizado_em": lic.atualizado_em.isoformat() if lic.atualizado_em else None,
    }
    if completo:
        d["informacao_complementar"] = lic.informacao_complementar
        d["modo_disputa"] = lic.modo_disputa
        d["valor_homologado"] = float(lic.valor_homologado) if lic.valor_homologado is not None else None
        d["itens"] = [{"numero": i.numero, "descricao": i.descricao, "quantidade": float(i.quantidade) if i.quantidade is not None else None,
                       "unidade": i.unidade, "valor_unitario": float(i.valor_unitario) if i.valor_unitario is not None else None,
                       "valor_total": float(i.valor_total) if i.valor_total is not None else None,
                       "material_servico": i.material_servico, "situacao": i.situacao} for i in sorted(lic.itens, key=lambda x: x.numero)]
        d["documentos"] = [{"id": x.id, "titulo": x.titulo, "tipo": x.tipo, "tipo_fonte": x.tipo_fonte, "status": x.status,
                            "url": x.url, "tamanho": x.tamanho, "erro": x.erro} for x in lic.documentos]
        d["checklist_documentos"] = documentos.checklist(lic)
    return d


# ------------------------------------------------------------------ autenticação
class Login(BaseModel):
    email: str
    senha: str


@app.post("/auth/login")
def login(dados: Login, s: Session = Depends(obter_sessao)):
    u = s.query(Usuario).filter_by(email=dados.email.lower()).one_or_none()
    if u is None or not u.ativo or not conferir_senha(dados.senha, u.senha_hash):
        raise HTTPException(401, "e-mail ou senha incorretos")
    _auditar(s, u, "login", u.email)
    return {"token": emitir_token(u), "usuario": {"id": u.id, "nome": u.nome, "email": u.email, "papel": u.papel}}


@app.get("/auth/eu")
def eu(u: Usuario | None = Depends(usuario_atual)):
    return None if u is None else {"id": u.id, "nome": u.nome, "email": u.email, "papel": u.papel}


@app.get("/saude")
def saude():
    return {"ok": True, "hora": datetime.now().isoformat(timespec="seconds")}


# ------------------------------------------------------------------ busca e licitações
@app.get("/licitacoes")
def listar(
    q: str | None = None, expandir: bool = True, objeto: str | None = None, uf: list[str] = Query(default=[]),
    municipio: str | None = None, codigo_ibge: str | None = None, orgao: str | None = None, numero: str | None = None,
    processo: str | None = None, modalidade: list[int] = Query(default=[]), categoria: list[str] = Query(default=[]),
    situacao: str = "aberta", publicacao_de: datetime | None = None, publicacao_ate: datetime | None = None,
    abertura_de: datetime | None = None, abertura_ate: datetime | None = None, prazo_de: datetime | None = None,
    prazo_ate: datetime | None = None, valor_min: float | None = None, valor_max: float | None = None,
    incluir_sem_valor: bool = True, exigencia: str | None = None, plataforma: str | None = None,
    tipo_registro: str | None = None, ordenar: str = "prazo", pagina: int = 1, por_pagina: int = 20,
    s: Session = Depends(obter_sessao), _u=LEITOR,
):
    f = Filtros(q=q, expandir=expandir, objeto=objeto, ufs=uf, municipio=municipio, codigo_ibge=codigo_ibge, orgao=orgao,
                numero=numero, processo=processo, modalidades=modalidade, categorias=categoria, situacao=situacao,
                publicacao_de=publicacao_de, publicacao_ate=publicacao_ate, abertura_de=abertura_de, abertura_ate=abertura_ate,
                prazo_de=prazo_de, prazo_ate=prazo_ate, valor_min=valor_min, valor_max=valor_max,
                incluir_sem_valor=incluir_sem_valor, exigencia=exigencia, plataforma=plataforma,
                tipo_registro=tipo_registro, ordenar=ordenar, pagina=pagina, por_pagina=por_pagina)
    r = buscar(s, f)
    return {**r, "itens": [ser(x) for x in r["itens"]]}


@app.get("/busca/expandir")
def expandir_termos(q: str, _u=LEITOR):
    return expandir_consulta(q)


def _lic(s: Session, lid: int) -> Licitacao:
    lic = s.get(Licitacao, lid)
    if lic is None:
        raise HTTPException(404, "licitação não encontrada")
    return lic


@app.get("/licitacoes/{lid}")
def detalhe(lid: int, s: Session = Depends(obter_sessao), _u=LEITOR):
    lic = _lic(s, lid)
    d = ser(lic, completo=True)
    d["historico"] = [{"em": h.em.isoformat(), "campo": h.campo, "antes": h.antes, "depois": h.depois, "evento": h.evento}
                      for h in s.query(HistoricoAlteracao).filter_by(licitacao_id=lid).order_by(HistoricoAlteracao.em.desc()).limit(50)]
    an = s.query(Analise).filter_by(licitacao_id=lid).order_by(Analise.criado_em.desc()).first()
    d["analise"] = None if an is None else {"id": an.id, "status": an.status, "criado_em": an.criado_em.isoformat()}
    if lic.duplicata_de_id is None:
        d["republicacoes"] = [x.id for x in s.query(Licitacao).filter_by(duplicata_de_id=lid)]
    return d


@app.post("/licitacoes/{lid}/preparar")
def preparar(lid: int, analisar: bool = True, s: Session = Depends(obter_sessao), u=ANALISTA):
    """Busca itens e documentos no PNCP, baixa os anexos e (opcional) analisa com IA."""
    _lic(s, lid)
    _auditar(s, u, "preparar_edital", str(lid), analisar=analisar)
    return tarefas.disparar("preparar_edital", lid, analisar)


@app.post("/licitacoes/{lid}/documentos/sincronizar")
def sinc_documentos(lid: int, s: Session = Depends(obter_sessao), _u=ANALISTA):
    lic = _lic(s, lid)
    r = coleta.detalhar(s, lic)
    r["download"] = documentos.baixar_todos(s, lic)
    return r


@app.get("/licitacoes/{lid}/zip")
def baixar_zip(lid: int, s: Session = Depends(obter_sessao), u=LEITOR):
    lic = _lic(s, lid)
    if not lic.documentos:
        raise HTTPException(409, "documentos ainda não sincronizados: use POST /licitacoes/{id}/preparar")
    dados, _ = documentos.gerar_zip(lic)
    _auditar(s, u, "baixar_zip", str(lid))
    nome = f"licitacao-{lic.numero_controle_pncp or lic.id}".replace("/", "-")
    return Response(dados, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{nome}.zip"'})


@app.post("/licitacoes/{lid}/analisar")
def analisar(lid: int, s: Session = Depends(obter_sessao), u=ANALISTA):
    lic = _lic(s, lid)
    _auditar(s, u, "analisar", str(lid))
    an = analise.analisar(s, lic)
    return {"id": an.id, "status": an.status, "erro": an.erro}


@app.get("/licitacoes/{lid}/analise")
def ver_analise(lid: int, s: Session = Depends(obter_sessao), _u=LEITOR):
    an = s.query(Analise).filter_by(licitacao_id=lid).order_by(Analise.criado_em.desc()).first()
    if an is None:
        raise HTTPException(404, "ainda sem análise")
    return {"id": an.id, "status": an.status, "modelo": an.modelo, "criado_em": an.criado_em.isoformat(),
            "relatorio": an.relatorio, "verificacao": an.verificacao, "uso_tokens": an.uso_tokens, "erro": an.erro}


class PropostaEntrada(BaseModel):
    nome: str = "Proposta"
    linhas: list[dict]
    tributos_pct: float = 0
    despesas_adm_pct: float = 0
    margem_pct: float = 0
    custos_fornecedores: list[dict] = Field(default_factory=list)
    prazo_meses: int = 12
    descontos_pct: list[float] = Field(default_factory=lambda: [0, 5, 10, 15, 20])


@app.post("/licitacoes/{lid}/propostas")
def nova_proposta(lid: int, p: PropostaEntrada, s: Session = Depends(obter_sessao), u=ANALISTA):
    lic = _lic(s, lid)
    dados = p.model_dump()
    dados["valor_estimado_edital"] = float(lic.valor_estimado) if lic.valor_estimado else None
    try:
        res = precificacao.calcular(precificacao.ParametrosProposta.de_dict(dados))
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e)) from None
    pr = Proposta(licitacao_id=lid, usuario_id=u.id if u else None, nome=p.nome, parametros=dados, resultado=res)
    s.add(pr)
    s.commit()
    return {"id": pr.id, **res}


def _proposta(s: Session, pid: int) -> tuple[Proposta, Licitacao]:
    pr = s.get(Proposta, pid)
    if pr is None:
        raise HTTPException(404, "proposta não encontrada")
    return pr, s.get(Licitacao, pr.licitacao_id)


@app.get("/propostas/{pid}/xlsx")
def proposta_xlsx(pid: int, s: Session = Depends(obter_sessao), _u=LEITOR):
    pr, lic = _proposta(s, pid)
    dados = precificacao.gerar_xlsx(pr.resultado, f"{pr.nome} — {lic.orgao_nome} nº {lic.numero_compra or ''}")
    return Response(dados, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="proposta-{pid}.xlsx"'})


@app.get("/propostas/{pid}/pdf")
def proposta_pdf(pid: int, s: Session = Depends(obter_sessao), _u=LEITOR):
    pr, lic = _proposta(s, pid)
    dados = precificacao.gerar_pdf(pr.resultado, pr.nome, {"orgao": lic.orgao_nome, "numero": lic.numero_compra,
                                                           "objeto": lic.objeto, "link": lic.link_pncp or lic.link_origem})
    return Response(dados, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="proposta-{pid}.pdf"'})


@app.post("/licitacoes/{lid}/favorito")
def favoritar(lid: int, s: Session = Depends(obter_sessao), u=LEITOR):
    if u is None:
        raise HTTPException(401, "faça login para favoritar")
    _lic(s, lid)
    f = s.query(Favorito).filter_by(usuario_id=u.id, licitacao_id=lid).one_or_none()
    if f:
        s.delete(f)
        s.commit()
        return {"favorito": False}
    s.add(Favorito(usuario_id=u.id, licitacao_id=lid))
    s.commit()
    return {"favorito": True}


@app.post("/licitacoes/{lid}/monitorar")
def monitorar_edital(lid: int, canais: dict | None = None, s: Session = Depends(obter_sessao), u=LEITOR):
    lic = _lic(s, lid)
    m = Monitoramento(usuario_id=u.id if u else None, nome=f"Edital {lic.numero_compra or lic.id} — {lic.orgao_nome}",
                      licitacao_id=lid, eventos=["prazo_proximo", "retificacao", "suspensa", "reaberta"],
                      canais=canais or {"painel": True})
    s.add(m)
    s.commit()
    return {"id": m.id}


# ------------------------------------------------------------------ painel, qualidade, fontes
@app.get("/painel")
def ver_painel(s: Session = Depends(obter_sessao), u=LEITOR):
    return painel.painel(s, u.id if u else None)


@app.get("/painel/municipios")
def municipios_da_uf(uf: str, s: Session = Depends(obter_sessao), _u=LEITOR):
    from sqlalchemy import func

    from .coleta import abertas_filtro

    linhas = s.query(Licitacao.municipio, Licitacao.codigo_ibge, func.count(), func.sum(Licitacao.valor_estimado)).filter(
        abertas_filtro(), Licitacao.uf == uf.upper(), Licitacao.municipio.isnot(None)).group_by(
        Licitacao.municipio, Licitacao.codigo_ibge).order_by(func.count().desc()).all()
    return [{"municipio": m, "codigo_ibge": c, "abertos": n, "valor": float(v or 0)} for m, c, n, v in linhas]


@app.get("/qualidade")
def ver_qualidade(s: Session = Depends(obter_sessao), _u=LEITOR):
    return painel.qualidade(s)


@app.post("/fontes/{codigo}/sincronizar")
def sincronizar_fonte(codigo: str, dias: int = 1, s: Session = Depends(obter_sessao), u=ADMIN):
    _auditar(s, u, "sincronizar", codigo, dias=dias)
    if codigo == "pncp":
        r = coleta.sincronizar_pncp(s, modo="diario", dias=dias)
    elif codigo == "espelhos_pncp":
        rs = coleta.sincronizar_espelhos(s)
        return [{"status": r.status, "lidos": r.lidos, "novos": r.novos, "mensagem": r.mensagem} for r in rs]
    elif codigo == "comprasgov":
        r = coleta.sincronizar_comprasgov(s, dias=dias)
    elif codigo == "querido_diario":
        r = coleta.sincronizar_querido_diario(s, [c.nome for c in PADRAO], dias=dias)
    elif codigo == "portal_transparencia":
        r = coleta.sincronizar_transparencia(s, dias=dias)
    else:
        raise HTTPException(404, "fonte sem conector de sincronização")
    return {"status": r.status, "lidos": r.lidos, "novos": r.novos, "atualizados": r.atualizados, "mensagem": r.mensagem}


# ------------------------------------------------------------------ categorias e monitoramentos
@app.get("/categorias")
def categorias(s: Session = Depends(obter_sessao), _u=LEITOR):
    proprias = [{"codigo": c.codigo, "nome": c.nome, "segmento": c.segmento, "termos": c.termos, "excluir": c.excluir,
                 "personalizada": True} for c in s.query(Categoria).filter_by(ativa=True)]
    return {"segmentos": SEGMENTOS, "categorias": [{"codigo": c.codigo, "nome": c.nome, "segmento": c.segmento,
                                                    "termos": c.termos, "excluir": c.excluir, "personalizada": False}
                                                   for c in PADRAO] + proprias}


class CategoriaEntrada(BaseModel):
    codigo: str
    nome: str
    segmento: str = "personalizado"
    termos: list[str]
    excluir: list[str] = Field(default_factory=list)


@app.post("/categorias")
def nova_categoria(c: CategoriaEntrada, s: Session = Depends(obter_sessao), _u=ANALISTA):
    s.add(Categoria(**c.model_dump(), personalizada=True))
    s.commit()
    s.info.pop("categorias", None)
    return {"ok": True, "aviso": "editais novos já usam a categoria; para reclassificar os antigos rode `cli reclassificar`"}


class MonitoramentoEntrada(BaseModel):
    nome: str
    termos: list[str] = Field(default_factory=list)
    categorias: list[str] = Field(default_factory=list)
    ufs: list[str] = Field(default_factory=list)
    modalidades: list[int] = Field(default_factory=list)
    valor_min: float | None = None
    valor_max: float | None = None
    eventos: list[str] = Field(default_factory=lambda: ["novo", "alto_valor", "prazo_proximo", "retificacao", "suspensa", "reaberta"])
    canais: dict = Field(default_factory=lambda: {"painel": True})


@app.get("/monitoramentos")
def listar_monitoramentos(s: Session = Depends(obter_sessao), u=LEITOR):
    q = s.query(Monitoramento)
    if u is not None and u.papel != "admin":
        q = q.filter_by(usuario_id=u.id)
    return [{"id": m.id, "nome": m.nome, "termos": m.termos, "categorias": m.categorias, "ufs": m.ufs,
             "valor_min": m.valor_min, "valor_max": m.valor_max, "eventos": m.eventos, "canais": m.canais,
             "licitacao_id": m.licitacao_id, "ativo": m.ativo} for m in q.order_by(Monitoramento.id)]


@app.post("/monitoramentos")
def novo_monitoramento(m: MonitoramentoEntrada, s: Session = Depends(obter_sessao), u=LEITOR):
    mon = Monitoramento(usuario_id=u.id if u else None, **m.model_dump())
    s.add(mon)
    s.commit()
    return {"id": mon.id}


@app.delete("/monitoramentos/{mid}")
def apagar_monitoramento(mid: int, s: Session = Depends(obter_sessao), _u=LEITOR):
    m = s.get(Monitoramento, mid)
    if m:
        s.delete(m)
        s.commit()
    return {"ok": True}


@app.post("/alertas/avaliar")
def avaliar_alertas(s: Session = Depends(obter_sessao), _u=ANALISTA):
    return alertas.avaliar(s)


@app.get("/alertas")
def listar_alertas(nao_lidos: bool = False, s: Session = Depends(obter_sessao), u=LEITOR):
    q = s.query(Alerta).join(Monitoramento, Monitoramento.id == Alerta.monitoramento_id)
    if u is not None and u.papel != "admin":
        q = q.filter(Monitoramento.usuario_id == u.id)
    if nao_lidos:
        q = q.filter(Alerta.lido.is_(False))
    return [{"id": a.id, "tipo": a.tipo, "mensagem": a.mensagem, "licitacao_id": a.licitacao_id,
             "criado_em": a.criado_em.isoformat(), "entrega": a.entrega, "lido": a.lido}
            for a in q.order_by(Alerta.criado_em.desc()).limit(200)]
