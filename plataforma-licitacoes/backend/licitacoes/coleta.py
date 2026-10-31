"""Gravação dos editais coletados e rotinas de sincronização de cada fonte.

* Um edital é identificado pelo número de controle do PNCP quando existe (`pncp:<controle>`), então
  o mesmo edital vindo do PNCP, do Compras.gov ou de um espelho vira um registro só.
* Fonte oficial vence espelho: um espelho só preenche campos vazios de um registro que o PNCP já trouxe.
* Mudanças de prazo, situação, valor e objeto ficam no histórico (alimentam os alertas de
  retificação, suspensão e reabertura).
* Editais republicados (mesmo órgão, valor, prazo e texto) são ligados ao original.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import catalogo
from .config import config
from .conectores.base import ErroFonte
from .modelos import (
    Documento, Fonte, HistoricoAlteracao, Item, Licitacao, Municipio, Orgao, Sincronizacao, agora,
)
from .taxonomia import categorias_ativas, classificar
from .util import hash_dados, normalizar

log = logging.getLogger("licitacoes.coleta")

PRIORIDADE = {"pncp": 3, "comprasgov": 2, "portal_transparencia": 2, "querido_diario": 1, "espelhos_pncp": 1}
CAMPOS_HISTORICO = {
    "data_encerramento": "prazo", "data_abertura": "prazo", "situacao": "situacao",
    "valor_estimado": "valor", "objeto": "retificacao",
}
CAMPOS = [
    "numero_controle_pncp", "tipo_registro", "cnpj_orgao", "orgao_nome", "unidade_nome", "esfera", "ano",
    "sequencial", "numero_compra", "processo", "modalidade_id", "modalidade", "modo_disputa", "situacao", "srp",
    "objeto", "informacao_complementar", "valor_estimado", "valor_homologado", "orcamento_sigiloso",
    "data_publicacao", "data_abertura", "data_encerramento", "uf", "municipio", "codigo_ibge", "link_pncp",
    "link_origem",
]
INATIVAS = ("revogada", "anulada", "suspensa", "excluida")


def calcular_aderencia(lic: Licitacao) -> float:
    """0 a 100: categoria prioritária (50), valor (20), prazo viável (20), dados completos (10)."""
    prio = set(config().prioritarias)
    forca = max([c["forca"] for c in lic.categorias or [] if c["codigo"] in prio] or [0.0])
    pontos = 50 * forca
    v = float(lic.valor_estimado or 0)
    if v >= 5_000_000:
        pontos += 20
    elif v >= 1_000_000:
        pontos += 15
    elif v >= 100_000:
        pontos += 8
    elif lic.orcamento_sigiloso:
        pontos += 8
    if lic.data_encerramento:
        dias = (lic.data_encerramento - agora()).total_seconds() / 86400
        if dias >= 5:
            pontos += 20
        elif dias >= 2:
            pontos += 10
    if lic.link_pncp or lic.link_origem:
        pontos += 5
    if lic.data_encerramento and lic.objeto:
        pontos += 5
    if (lic.situacao or "").lower().startswith(INATIVAS) or lic.excluida:
        pontos = 0
    return round(pontos, 1)


def _texto_busca(d: dict) -> str:
    partes = [d.get("objeto"), d.get("informacao_complementar"), d.get("orgao_nome"), d.get("unidade_nome"),
              d.get("municipio"), d.get("modalidade"), d.get("numero_compra"), d.get("processo")]
    return " " + normalizar(" ".join(str(p) for p in partes if p)) + " "


def _orgao(s: Session, d: dict) -> int | None:
    cnpj = d.get("cnpj_orgao")
    if not cnpj:
        return None
    o = s.query(Orgao).filter_by(cnpj=cnpj).one_or_none()
    if o is None:
        o = Orgao(cnpj=cnpj, nome=d.get("orgao_nome") or cnpj, esfera=d.get("esfera"), poder=d.get("poder"),
                  uf=d.get("uf"), municipio=d.get("municipio"), codigo_ibge=d.get("codigo_ibge"))
        s.add(o)
        s.flush()
    return o.id


def _fmt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="minutes")
    return str(v)


def gravar(s: Session, d: dict, fonte: Fonte) -> tuple[str, Licitacao]:
    """Insere ou atualiza um edital. Devolve ('novo' | 'atualizado' | 'igual', licitação)."""
    if not d.get("objeto"):
        d["objeto"] = "(objeto não informado pela fonte)"
    lic = s.query(Licitacao).filter_by(chave=d["chave"]).one_or_none()
    h = hash_dados({k: d.get(k) for k in CAMPOS})
    so_preencher = False
    if lic is None:
        lic = Licitacao(chave=d["chave"], fonte_id=fonte.id, fontes_vistas=[fonte.codigo])
        for k in CAMPOS:
            setattr(lic, k, d.get(k))
        lic.bruto = d.get("bruto") or {}
        estado = "novo"
        s.add(lic)
    else:
        if lic.hash_conteudo == h:
            if fonte.codigo not in (lic.fontes_vistas or []):
                lic.fontes_vistas = [*(lic.fontes_vistas or []), fonte.codigo]
            return "igual", lic
        so_preencher = PRIORIDADE.get(fonte.codigo, 1) < PRIORIDADE.get(lic.fonte.codigo if lic.fonte else "", 1)
        mudou = False
        for k in CAMPOS:
            novo = d.get(k)
            antigo = getattr(lic, k)
            if novo is None or (so_preencher and antigo not in (None, "")):
                continue
            if _fmt(novo) != _fmt(antigo) and not (k == "valor_estimado" and antigo is not None and abs(float(antigo) - float(novo)) < 0.01):
                if k in CAMPOS_HISTORICO and antigo is not None:
                    s.add(HistoricoAlteracao(licitacao_id=lic.id, campo=k, antes=_fmt(antigo), depois=_fmt(novo),
                                             evento=CAMPOS_HISTORICO[k], fonte_codigo=fonte.codigo))
                setattr(lic, k, novo)
                mudou = True
        if not so_preencher:
            lic.bruto = d.get("bruto") or lic.bruto
            lic.fonte_id = fonte.id
        if fonte.codigo not in (lic.fontes_vistas or []):
            lic.fontes_vistas = [*(lic.fontes_vistas or []), fonte.codigo]
        estado = "atualizado" if mudou else "igual"
    if not lic.codigo_ibge and lic.municipio and lic.uf:
        lic.codigo_ibge = codigo_ibge_por_nome(s, lic.municipio, lic.uf)
    lic.orgao_id = _orgao(s, d) or lic.orgao_id
    lic.plataforma_origem = catalogo.plataforma_de(lic.link_origem, lic.objeto, d.get("usuario_publicador")) or lic.plataforma_origem
    lic.texto_busca = _texto_busca({k: getattr(lic, k) for k in CAMPOS})
    lic.categorias = classificar(f"{lic.objeto} {lic.informacao_complementar or ''}", categorias_ativas(s))
    if not so_preencher:
        lic.hash_conteudo = h
    lic.aderencia = calcular_aderencia(lic)
    lic.atualizado_em = agora()
    s.flush()
    if estado == "novo":
        detectar_gemeo(s, lic)
    return estado, lic


def codigo_ibge_por_nome(s: Session, municipio: str, uf: str) -> str | None:
    if "municipios" not in s.info:
        s.info["municipios"] = {(normalizar(m.nome), m.uf): m.codigo_ibge for m in s.query(Municipio).all()}
    return s.info["municipios"].get((normalizar(municipio), (uf or "").upper()))


def detectar_gemeo(s: Session, lic: Licitacao) -> Licitacao | None:
    """Liga republicações: mesmo órgão e valor, prazo a até 1 minuto e um texto igual ou contido no outro."""
    if not (lic.cnpj_orgao and lic.valor_estimado and lic.data_encerramento):
        return None
    janela = timedelta(minutes=1)
    candidatos = s.query(Licitacao).filter(
        Licitacao.id != lic.id, Licitacao.cnpj_orgao == lic.cnpj_orgao, Licitacao.valor_estimado == lic.valor_estimado,
        Licitacao.data_encerramento.between(lic.data_encerramento - janela, lic.data_encerramento + janela),
        Licitacao.duplicata_de_id.is_(None),
    ).all()
    a = normalizar(lic.objeto)
    for c in candidatos:
        b = normalizar(c.objeto)
        if a == b or (len(a) > 30 and a in b) or (len(b) > 30 and b in a):
            original, copia = (c, lic) if c.id < lic.id else (lic, c)
            copia.duplicata_de_id = original.id
            return original
    return None


# ------------------------------------------------------------------ controle de sincronização
class Execucao:
    def __init__(self, s: Session, codigo_fonte: str, parametros: dict):
        self.s = s
        self.fonte = catalogo.fonte(s, codigo_fonte)
        self.reg = Sincronizacao(fonte_id=self.fonte.id, parametros=parametros)
        s.add(self.reg)
        s.flush()

    def contar(self, estado: str) -> None:
        self.reg.lidos += 1
        if estado == "novo":
            self.reg.novos += 1
        elif estado == "atualizado":
            self.reg.atualizados += 1

    def concluir(self, erro: Exception | None = None, chamadas: int = 0, parcial: bool = False) -> Sincronizacao:
        self.reg.fim = agora()
        self.reg.chamadas = chamadas
        self.fonte.ultima_sincronizacao = self.reg.fim
        if erro is None:
            self.reg.status = "parcial" if parcial else "ok"
            self.fonte.ultimo_sucesso = self.reg.fim
            self.fonte.falhas_consecutivas = 0
            self.fonte.ultimo_erro = None
        else:
            self.reg.status = "parcial" if self.reg.lidos else "erro"
            self.reg.erros += 1
            self.reg.mensagem = f"{type(erro).__name__}: {erro}"[:2000]
            self.fonte.ultimo_erro = self.reg.mensagem
            self.fonte.falhas_consecutivas = (self.fonte.falhas_consecutivas or 0) + 1
        self.s.commit()
        return self.reg


def sincronizar_pncp(s: Session, *, modo: str = "monitoramento", dias: int = 1, modalidades: list[int] | None = None,
                     ufs: list[str] | None = None, conector=None, hoje: date | None = None) -> Sincronizacao:
    """modo: 'monitoramento' (alterados e publicados hoje), 'diario' (últimos `dias`), 'propostas' (abertas)."""
    from .conectores.pncp import ConectorPncp, normalizar_contratacao

    c = conector or ConectorPncp()
    hoje = hoje or date.today()
    mods = modalidades or config().modalidades_pncp
    ex = Execucao(s, "pncp", {"modo": modo, "dias": dias, "modalidades": mods, "ufs": ufs})
    erro = None
    try:
        for uf in ufs or [None]:
            if modo == "propostas":
                series = [c.propostas_abertas(hoje + timedelta(days=config().pncp_dias_proposta), None, uf)]
            else:
                inicio = hoje - timedelta(days=max(0, dias - 1))
                series = []
                for m in mods:
                    series.append(c.por_publicacao(inicio, hoje, m, uf))
                    series.append(c.por_atualizacao(inicio, hoje, m, uf))
            for serie in series:
                for i, raw in enumerate(serie, 1):
                    estado, _ = gravar(s, normalizar_contratacao(raw), ex.fonte)
                    ex.contar(estado)
                    if i % 200 == 0:
                        s.commit()
                s.commit()
    except ErroFonte as e:
        erro = e
        log.warning("PNCP: %s", e)
    return ex.concluir(erro, c.http.stats.chamadas)


def conferir_individual(s: Session, *, dias_prazo: int = 3, limite: int = 100, conector=None) -> dict:
    """Consulta um a um os editais abertos que vencem logo: a listagem do PNCP pode demorar horas para
    refletir prorrogações, e exclusões (HTTP 410) não aparecem em listagem nenhuma."""
    from .conectores.pncp import ConectorPncp, normalizar_contratacao

    c = conector or ConectorPncp()
    fonte = catalogo.fonte(s, "pncp")
    limite_data = agora() + timedelta(days=dias_prazo)
    alvos = s.query(Licitacao).filter(
        Licitacao.cnpj_orgao.isnot(None), Licitacao.sequencial.isnot(None), Licitacao.excluida.is_(False),
        Licitacao.data_encerramento.between(agora(), limite_data),
    ).order_by(Licitacao.data_encerramento).limit(limite).all()
    res = {"conferidos": 0, "alterados": 0, "excluidos": 0, "erros": 0}
    for lic in alvos:
        try:
            raw = c.contratacao(lic.cnpj_orgao, lic.ano, lic.sequencial)
        except ErroFonte:
            res["erros"] += 1
            if res["erros"] >= 2:
                break
            continue
        res["conferidos"] += 1
        lic.conferido_em = agora()
        if raw is None:
            lic.excluida = True
            lic.aderencia = 0
            s.add(HistoricoAlteracao(licitacao_id=lic.id, campo="excluida", antes="false", depois="true",
                                     evento="excluida", fonte_codigo="pncp"))
            res["excluidos"] += 1
        else:
            estado, _ = gravar(s, normalizar_contratacao(raw), fonte)
            res["alterados"] += estado == "atualizado"
        s.commit()
    return res


def detalhar(s: Session, lic: Licitacao, conector=None) -> dict:
    """Busca itens e lista de arquivos do edital no PNCP."""
    from .conectores.pncp import ConectorPncp, normalizar_arquivo, normalizar_item
    from .documentos import classificar_documento

    if not (lic.cnpj_orgao and lic.ano and lic.sequencial):
        return {"itens": 0, "documentos": 0, "motivo": "edital sem identificação do PNCP"}
    c = conector or ConectorPncp()
    itens = c.itens(lic.cnpj_orgao, lic.ano, lic.sequencial)
    existentes = {i.numero: i for i in lic.itens}
    for raw in itens:
        d = normalizar_item(raw)
        if d["numero"] is None:
            continue
        it = existentes.get(d["numero"]) or Item(licitacao_id=lic.id, numero=d["numero"], descricao="")
        for k, v in d.items():
            setattr(it, k, v)
        if it.id is None:
            s.add(it)
    arquivos = c.arquivos(lic.cnpj_orgao, lic.ano, lic.sequencial)
    docs = {(d.sequencial, d.titulo): d for d in lic.documentos}
    novos_docs = 0
    for raw in arquivos:
        d = normalizar_arquivo(raw, lic.cnpj_orgao, lic.ano, lic.sequencial)
        doc = docs.get((d["sequencial"], d["titulo"]))
        if doc is None:
            doc = Documento(licitacao_id=lic.id, **d, tipo=classificar_documento(d["titulo"], d["tipo_fonte"]))
            s.add(doc)
            novos_docs += 1
            if lic.criado_em and lic.criado_em < agora() - timedelta(hours=1):
                s.add(HistoricoAlteracao(licitacao_id=lic.id, campo="documento", antes=None, depois=d["titulo"],
                                         evento="documento", fonte_codigo="pncp"))
        else:
            doc.ativo = d["ativo"]
            doc.url = d["url"] or doc.url
    s.commit()
    return {"itens": len(itens), "documentos": len(arquivos), "documentos_novos": novos_docs}


def sincronizar_espelhos(s: Session, conector=None, conteudos: dict[str, bytes] | None = None) -> list[Sincronizacao]:
    from .conectores.outras import ESPELHOS, ConectorEspelhos

    c = conector or ConectorEspelhos()
    saida = []
    for esp in ESPELHOS:
        ex = Execucao(s, "espelhos_pncp", {"espelho": esp["codigo"], "url": esp["url"]})
        erro = None
        try:
            conteudo = (conteudos or {}).get(esp["codigo"])
            for i, d in enumerate(c.registros(esp, conteudo), 1):
                estado, _ = gravar(s, d, ex.fonte)
                ex.contar(estado)
                if i % 500 == 0:
                    s.commit()
        except (ErroFonte, ValueError) as e:
            erro = e
        saida.append(ex.concluir(erro, c.http.stats.chamadas))
    return saida


def sincronizar_comprasgov(s: Session, *, dias: int = 1, modalidades: list[int] | None = None, conector=None) -> Sincronizacao:
    from .conectores.outras import ConectorComprasGov, normalizar_comprasgov_14133

    c = conector or ConectorComprasGov()
    hoje = date.today()
    ex = Execucao(s, "comprasgov", {"dias": dias})
    erro = None
    try:
        for m in modalidades or config().modalidades_pncp:
            for raw in c.contratacoes_14133(hoje - timedelta(days=dias), hoje, m):
                estado, _ = gravar(s, normalizar_comprasgov_14133(raw), ex.fonte)
                ex.contar(estado)
            s.commit()
    except ErroFonte as e:
        erro = e
    return ex.concluir(erro, c.http.stats.chamadas)


def sincronizar_querido_diario(s: Session, termos: list[str], *, dias: int = 7, conector=None) -> Sincronizacao:
    from .conectores.outras import ConectorQueridoDiario, normalizar_diario

    c = conector or ConectorQueridoDiario()
    hoje = date.today()
    ex = Execucao(s, "querido_diario", {"termos": termos, "dias": dias})
    erro = None
    try:
        for termo in termos:
            consulta = f'"{termo}" licitação'
            for diario in c.buscar(consulta, hoje - timedelta(days=dias), hoje):
                for d in normalizar_diario(diario, consulta):
                    estado, _ = gravar(s, d, ex.fonte)
                    ex.contar(estado)
            s.commit()
    except ErroFonte as e:
        erro = e
    return ex.concluir(erro, c.http.stats.chamadas)


def sincronizar_transparencia(s: Session, *, dias: int = 7, orgaos: list[str] | None = None, conector=None) -> Sincronizacao:
    from .conectores.outras import ConectorTransparencia, normalizar_transparencia

    ex = Execucao(s, "portal_transparencia", {"dias": dias})
    erro = None
    chamadas = 0
    try:
        c = conector or ConectorTransparencia()
        hoje = date.today()
        lista = orgaos or [o for o in config().transparencia_orgaos.split(",") if o.strip()]
        if not lista:
            raise ErroFonte("defina LIC_TRANSPARENCIA_ORGAOS (códigos SIAFI dos órgãos)")
        for org in lista:
            for raw in c.licitacoes(hoje - timedelta(days=dias), hoje, org.strip()):
                estado, _ = gravar(s, normalizar_transparencia(raw), ex.fonte)
                ex.contar(estado)
            s.commit()
        chamadas = c.http.stats.chamadas
    except ErroFonte as e:
        erro = e
    return ex.concluir(erro, chamadas)


def carregar_municipios(s: Session, conector=None, lista: list[dict] | None = None) -> int:
    from .conectores.outras import ConectorIbge

    dados = lista if lista is not None else (conector or ConectorIbge()).municipios()
    s.info.pop("municipios", None)
    for m in dados:
        if not m.get("uf"):
            continue
        reg = s.get(Municipio, m["codigo_ibge"])
        if reg is None:
            s.add(Municipio(**m))
        else:
            reg.nome, reg.uf = m["nome"], m["uf"]
    s.commit()
    # completa o código IBGE dos editais que só trazem o nome do município
    for lic in s.query(Licitacao).filter(Licitacao.codigo_ibge.is_(None), Licitacao.municipio.isnot(None)).yield_per(1000):
        lic.codigo_ibge = codigo_ibge_por_nome(s, lic.municipio, lic.uf)
    s.commit()
    return len(dados)


def municipios_dos_editais(s: Session) -> int:
    """Sem acesso ao IBGE, monta a lista de municípios com o código IBGE que vem nos próprios editais."""
    linhas = s.query(Licitacao.codigo_ibge, Licitacao.municipio, Licitacao.uf).filter(
        Licitacao.codigo_ibge.isnot(None), Licitacao.uf.isnot(None)).distinct().all()
    n = 0
    for cod, nome, uf in linhas:
        if cod and s.get(Municipio, cod) is None:
            s.add(Municipio(codigo_ibge=cod, nome=nome or cod, uf=uf))
            n += 1
    s.commit()
    return n


def abertas_filtro(agora_: datetime | None = None):
    a = agora_ or agora()
    return and_(
        Licitacao.excluida.is_(False), Licitacao.duplicata_de_id.is_(None),
        Licitacao.data_encerramento >= a,
        or_(Licitacao.situacao.is_(None), ~Licitacao.situacao.ilike("revogad%")),
        or_(Licitacao.situacao.is_(None), ~Licitacao.situacao.ilike("anulad%")),
        or_(Licitacao.situacao.is_(None), ~Licitacao.situacao.ilike("suspens%")),
    )
