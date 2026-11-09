"""Coletor remoto: roda onde há acesso às fontes (ex.: GitHub Actions) e exporta um pacote de dados
que outra instalação importa sem precisar de acesso direto às fontes.

Pacote (pasta):
  contratacoes.jsonl.gz   um edital por linha (campos normalizados + registro bruto da fonte)
  detalhes.jsonl.gz       itens e documentos dos editais detalhados
  textos/<id>.json        texto dos documentos baixados, página a página (número de página original)
  execucoes.json          cada sincronização (fonte, status, lidos, novos, chamadas, erro)
  municipios.json         lista do IBGE usada na cobertura
  resumo.json             totais, horário e identificação da execução

Nada é recalculado na importação além da classificação: os dados vêm da fonte oficial, e a
fonte de cada edital continua sendo a original (pncp, comprasgov, querido_diario...).
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import catalogo, coleta, documentos
from .armazenamento import armazenamento
from .coleta import CAMPOS
from .config import config
from .conectores.base import FalhaTemporaria
from .extracao import extrair
from .taxonomia import natureza
from .modelos import Documento, Fonte, Item, Licitacao, Municipio, Sincronizacao, agora
from .util import para_data, slug

log = logging.getLogger("licitacoes.coletor")

TERMOS_DIARIOS = ["digitalização", "indexação", "gestão documental", "fábrica de software",
                  "sustentação de sistemas", "desenvolvimento de software", "tratamento de dados",
                  "manutenção de software", "licença de uso de software", "sistema de gestão", "inteligência artificial",
                  "arquivo", "microfilmagem", "educação a distância", "EAD", "plataforma educacional",
                  "pesquisa de opinião", "pesquisa de satisfação", "inovação", "ponto de função",
                  "unidade de serviço técnico", "digitalização de documentos", "gestão eletrônica de documentos",
                  "locação de software", "computação em nuvem", "outsourcing", "sustentação", "registro de preços tecnologia"]


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _passo(nome: str, func, resumo: dict):
    log.info("== %s", nome)
    try:
        r = func()
        resumo["passos"][nome] = r if isinstance(r, (dict, list, int, str)) else str(r)
    except Exception as e:  # um passo com falha não impede os outros
        log.exception("passo %s falhou", nome)
        resumo["passos"][nome] = {"erro": f"{type(e).__name__}: {e}"}


def _sync(r) -> dict:
    return {"status": r.status, "lidos": r.lidos, "novos": r.novos, "atualizados": r.atualizados,
            "chamadas": r.chamadas, "mensagem": r.mensagem}


def coletar(s: Session, *, dias: int = 2, detalhar_top: int = 40, listar: int = 1200, rapido: bool = False,
            minutos: float | None = None) -> dict:
    """`minutos`: orçamento total. Cada etapa longa para no seu prazo e o pacote sai com o que foi coletado,
    em vez de a execução estourar o tempo do runner e não publicar nada."""
    t0 = time.monotonic()
    prazo = (lambda frac: t0 + minutos * 60 * frac) if minutos else (lambda frac: None)  # noqa: E731
    resumo = {"inicio": agora().isoformat(), "execucao": os.environ.get("GITHUB_RUN_ID"), "passos": {},
              "orcamento_minutos": minutos}
    catalogo.registrar_fontes(s)
    s.commit()
    _passo("ibge", lambda: coleta.carregar_municipios(s), resumo)
    # ordem por importância: editais, itens/documentos do foco e só depois os diários (lentos e instáveis)
    _passo("pncp_propostas_abertas", lambda: _sync(coleta.sincronizar_pncp(s, modo="propostas", ate=prazo(0.4))), resumo)
    if not rapido:
        _passo("pncp_publicados_e_alterados", lambda: _sync(coleta.sincronizar_pncp(s, modo="diario", dias=dias, ate=prazo(0.45))), resumo)
        # busca maior de pregões: tudo o que foi publicado nos últimos 30 dias em pregão e concorrência,
        # inclusive os que ainda não abriram propostas (a consulta de propostas abertas não traz esses)
        _passo("pncp_pregoes_30_dias", lambda: _sync(coleta.sincronizar_pncp(
            s, modo="diario", dias=30, modalidades=[6, 4, 7, 5], so_publicacao=True, ate=prazo(0.6))), resumo)
        _passo("comprasgov", lambda: _sync(coleta.sincronizar_comprasgov(s, dias=7)), resumo)
        _passo("conferencia_individual", lambda: coleta.conferir_individual(s, limite=150), resumo)
    dj = Disjuntor()
    _passo("documentos_relevantes", lambda: detalhar_relevantes(s, detalhar_top, ate=prazo(0.68), disjuntor=dj), resumo)
    _passo("itens_e_documentos_listados", lambda: listar_segmento(s, listar, ate=prazo(0.85), disjuntor=dj), resumo)
    if not rapido:
        _passo("querido_diario", lambda: _sync(coleta.sincronizar_querido_diario(s, TERMOS_DIARIOS, dias=15, ate=prazo(1.0))), resumo)
        if config().transparencia_chave:
            _passo("transparencia", lambda: _sync(coleta.sincronizar_transparencia(s, dias=7)), resumo)
    resumo["fim"] = agora().isoformat()
    return resumo


def relevantes(s: Session, limite: int) -> list[Licitacao]:
    prio = set(config().prioritarias)
    abertas = s.query(Licitacao).filter(coleta.abertas_filtro(), Licitacao.cnpj_orgao.isnot(None),
                                        Licitacao.sequencial.isnot(None)).all()
    cand = [lic for lic in abertas if any(c["codigo"] in prio for c in lic.categorias or [])
            and (lic.valor_estimado is None or float(lic.valor_estimado) >= 1_000_000) and natureza(lic.objeto) != "material"]
    cand.sort(key=lambda x: (-(x.aderencia or 0), -float(x.valor_estimado or 0)))
    return cand[:limite]


SEGMENTOS_LISTADOS = {"gestao_documental", "ti", "educacao_pesquisa"}


class Disjuntor:
    """Para a etapa quando a fonte devolve falha temporária (5xx ou rede) em vários editais seguidos.

    Em 01-02/11 a API de itens/arquivos do PNCP respondeu 503 a tudo por horas, enquanto a de consulta
    funcionava; cada edital esgotava as novas tentativas e a coleta inteira se foi nisso."""

    def __init__(self, limite: int = 8):
        self.limite, self.seguidas, self.motivo = limite, 0, None

    def sucesso(self) -> None:
        self.seguidas = 0

    def falhou(self, erro: Exception) -> bool:
        self.seguidas = self.seguidas + 1 if isinstance(erro, FalhaTemporaria) else 0
        if self.seguidas >= self.limite:
            self.motivo = f"{self.seguidas} falhas seguidas da fonte ({type(erro).__name__}: {erro})"[:300]
            return True
        return False

    def nova_chance(self, tentativas: int = 3) -> None:
        """Antes de outra etapa, alguns editais de teste: a fonte pode ter voltado."""
        self.seguidas = min(self.seguidas, max(0, self.limite - tentativas))


def listar_segmento(s: Session, limite: int, ate: float | None = None, disjuntor: Disjuntor | None = None) -> dict:
    """Itens e lista de documentos (sem baixar) de todos os editais abertos de TI e gestão documental,
    para o painel abrir cada pregão com itens e links diretos dos arquivos."""
    abertas = s.query(Licitacao).filter(coleta.abertas_filtro(), Licitacao.cnpj_orgao.isnot(None),
                                        Licitacao.sequencial.isnot(None)).all()
    # compra de material (computadores, livros...) não interessa: o foco são serviços medidos em volume
    alvo = [x for x in abertas if any(c["segmento"] in SEGMENTOS_LISTADOS for c in x.categorias or [])
            and natureza(x.objeto) != "material"]
    alvo.sort(key=lambda x: (-(x.aderencia or 0), -float(x.valor_estimado or 0)))
    res = {"alvo": len(alvo), "detalhados": 0, "itens": 0, "documentos": 0, "falhas": 0}
    dj = disjuntor or Disjuntor()
    dj.nova_chance()
    for lic in alvo[:limite]:
        if ate is not None and time.monotonic() > ate:
            res["interrompido_por_tempo"] = True
            break
        if lic.itens or lic.documentos:  # já detalhado nesta execução (documentos relevantes)
            res["detalhados"] += 1
            continue
        try:
            d = coleta.detalhar(s, lic)
        except Exception as e:
            s.rollback()
            res["falhas"] += 1
            if dj.falhou(e):
                res["interrompido_fonte_indisponivel"] = dj.motivo
                break
            continue
        dj.sucesso()
        res["detalhados"] += 1
        res["itens"] += d.get("itens", 0)
        res["documentos"] += d.get("documentos", 0)
    return res


def detalhar_relevantes(s: Session, limite: int, ate: float | None = None, disjuntor: Disjuntor | None = None) -> dict:
    res = {"editais": 0, "itens": 0, "documentos": 0, "baixados": 0, "falhas": []}
    dj = disjuntor or Disjuntor()
    for lic in relevantes(s, limite):
        if ate is not None and time.monotonic() > ate:
            res["interrompido_por_tempo"] = True
            break
        try:
            d = coleta.detalhar(s, lic) if not lic.documentos else {"itens": len(lic.itens), "documentos": len(lic.documentos)}
            b = documentos.baixar_todos(s, lic)
        except Exception as e:
            s.rollback()
            res["falhas"].append({"id": lic.chave, "erro": f"{type(e).__name__}: {e}"[:300]})
            if dj.falhou(e):
                res["interrompido_fonte_indisponivel"] = dj.motivo
                break
            continue
        dj.sucesso()
        res["editais"] += 1
        res["itens"] += d.get("itens", 0)
        res["documentos"] += d.get("documentos", 0)
        res["baixados"] += b.get("baixado", 0) + b.get("ja_baixado", 0)
    return res


def exportar(s: Session, pasta: str | Path, resumo: dict) -> dict:
    p = Path(pasta)
    (p / "textos").mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(p / "contratacoes.jsonl.gz", "wt", encoding="utf-8") as f:
        for lic in s.query(Licitacao).filter(Licitacao.excluida.is_(False)).yield_per(1000):
            linha = {k: _iso(getattr(lic, k)) for k in CAMPOS}
            linha["valor_estimado"] = float(lic.valor_estimado) if lic.valor_estimado is not None else None
            linha["valor_homologado"] = float(lic.valor_homologado) if lic.valor_homologado is not None else None
            linha.update(chave=lic.chave, fonte=lic.fonte.codigo, fontes_vistas=lic.fontes_vistas, bruto=lic.bruto)
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
            n += 1
    det = 0
    with gzip.open(p / "detalhes.jsonl.gz", "wt", encoding="utf-8") as f:
        for lic in s.query(Licitacao).filter(or_(Licitacao.documentos.any(), Licitacao.itens.any())).all():
            docs = []
            for d in lic.documentos:
                item = {k: _iso(getattr(d, k)) for k in ("sequencial", "titulo", "tipo_fonte", "tipo", "url", "publicado_em",
                                                       "ativo", "status", "tamanho", "sha256", "mime", "erro")}
                if d.status == "baixado" and d.caminho:
                    try:
                        paginas = extrair(d.titulo + "." + d.caminho.rsplit(".", 1)[-1], armazenamento().ler(d.caminho))
                    except Exception as e:
                        paginas = []
                        item["erro_extracao"] = f"{type(e).__name__}"
                    nome = f"{slug(lic.chave, 90)}-{d.sequencial or 0:03d}.json"
                    (p / "textos" / nome).write_text(json.dumps({
                        "documento": d.titulo, "url": d.url, "sha256": d.sha256,
                        "paginas": [{"documento": pg.documento, "numero": pg.numero, "texto": pg.texto, "ocr": pg.ocr}
                                    for pg in paginas]}, ensure_ascii=False), encoding="utf-8")
                    item["texto"] = nome
                    item["paginas"] = len(paginas)
                docs.append(item)
            itens = [{"numero": i.numero, "descricao": i.descricao, "material_servico": i.material_servico,
                      "quantidade": float(i.quantidade) if i.quantidade is not None else None, "unidade": i.unidade,
                      "valor_unitario": float(i.valor_unitario) if i.valor_unitario is not None else None,
                      "valor_total": float(i.valor_total) if i.valor_total is not None else None,
                      "situacao": i.situacao, "criterio_julgamento": i.criterio_julgamento, "bruto": i.bruto} for i in lic.itens]
            f.write(json.dumps({"chave": lic.chave, "itens": itens, "documentos": docs}, ensure_ascii=False, default=str) + "\n")
            det += 1
    execs = [{"fonte": e.fonte.codigo, "inicio": _iso(e.inicio), "fim": _iso(e.fim), "status": e.status,
              "parametros": e.parametros, "lidos": e.lidos, "novos": e.novos, "atualizados": e.atualizados,
              "erros": e.erros, "chamadas": e.chamadas, "mensagem": e.mensagem} for e in s.query(Sincronizacao).all()]
    (p / "execucoes.json").write_text(json.dumps(execs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    muns = [{"codigo_ibge": m.codigo_ibge, "nome": m.nome, "uf": m.uf} for m in s.query(Municipio).all()]
    (p / "municipios.json").write_text(json.dumps(muns, ensure_ascii=False), encoding="utf-8")
    resumo.update(editais_exportados=n, editais_detalhados=det, municipios=len(muns), exportado_em=agora().isoformat())
    (p / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return resumo


def importar(s: Session, pasta: str | Path) -> dict:
    p = Path(pasta)
    resumo = json.loads((p / "resumo.json").read_text(encoding="utf-8"))
    origem = f"coletor remoto (execução {resumo.get('execucao') or 'local'}, {resumo.get('exportado_em')})"
    res = {"novos": 0, "atualizados": 0, "iguais": 0, "documentos": 0, "textos": 0}
    muns = json.loads((p / "municipios.json").read_text(encoding="utf-8"))
    if muns:
        coleta.carregar_municipios(s, lista=muns)
    fontes: dict[str, Fonte] = {}
    with gzip.open(p / "contratacoes.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, linha in enumerate(f, 1):
            d = json.loads(linha)
            for k in ("data_publicacao", "data_abertura", "data_encerramento"):
                d[k] = para_data(d.get(k))
            cod = d.pop("fonte")
            fonte = fontes.get(cod) or fontes.setdefault(cod, catalogo.fonte(s, cod))
            estado, lic = coleta.gravar(s, d, fonte)
            for extra in d.get("fontes_vistas") or []:
                if extra not in (lic.fontes_vistas or []):
                    lic.fontes_vistas = [*(lic.fontes_vistas or []), extra]
            res[{"novo": "novos", "atualizado": "atualizados"}.get(estado, "iguais")] += 1
            if i % 1000 == 0:
                s.commit()
    s.commit()
    if (p / "detalhes.jsonl.gz").exists():
        with gzip.open(p / "detalhes.jsonl.gz", "rt", encoding="utf-8") as f:
            for linha in f:
                d = json.loads(linha)
                lic = s.query(Licitacao).filter_by(chave=d["chave"]).one_or_none()
                if lic is None:
                    continue
                atuais = {i.numero: i for i in lic.itens}
                for it in d["itens"]:
                    obj = atuais.get(it["numero"]) or Item(licitacao_id=lic.id, numero=it["numero"], descricao="")
                    for k, v in it.items():
                        setattr(obj, k, v)
                    if obj.id is None:
                        s.add(obj)
                docs = {(x.sequencial, x.titulo): x for x in lic.documentos}
                for dd in d["documentos"]:
                    doc = docs.get((dd["sequencial"], dd["titulo"])) or Documento(licitacao_id=lic.id, sequencial=dd["sequencial"],
                                                                                  titulo=dd["titulo"], tipo=dd["tipo"])
                    for k in ("tipo_fonte", "tipo", "url", "ativo", "status", "tamanho", "sha256", "mime", "erro"):
                        setattr(doc, k, dd.get(k))
                    doc.publicado_em = para_data(dd.get("publicado_em"))
                    if dd.get("texto") and (p / "textos" / dd["texto"]).exists():
                        chave = f"documentos/{slug(lic.chave, 120)}/{dd['texto'].rsplit('-', 1)[-1].replace('.json', '')}.paginas.json"
                        armazenamento().salvar(chave, (p / "textos" / dd["texto"]).read_bytes(), "application/json")
                        doc.caminho = chave
                        doc.paginas = dd.get("paginas")
                        res["textos"] += 1
                    if doc.id is None:
                        s.add(doc)
                    res["documentos"] += 1
                s.flush()
                coleta.classificar_licitacao(s, lic)
                lic.aderencia = coleta.calcular_aderencia(lic)
                s.commit()
    for e in json.loads((p / "execucoes.json").read_text(encoding="utf-8")):
        fonte = catalogo.fonte(s, e["fonte"])
        fim = para_data(e["fim"])
        s.add(Sincronizacao(fonte_id=fonte.id, inicio=para_data(e["inicio"]), fim=fim, status=e["status"],
                            parametros={**(e["parametros"] or {}), "origem": origem}, lidos=e["lidos"], novos=e["novos"],
                            atualizados=e["atualizados"], erros=e["erros"], chamadas=e["chamadas"], mensagem=e["mensagem"]))
        if fim and (fonte.ultima_sincronizacao is None or fim > fonte.ultima_sincronizacao):
            fonte.ultima_sincronizacao = fim
            if e["status"] in ("ok", "parcial"):
                fonte.ultimo_sucesso, fonte.falhas_consecutivas, fonte.ultimo_erro = fim, 0, None
            else:
                fonte.falhas_consecutivas = (fonte.falhas_consecutivas or 0) + 1
                fonte.ultimo_erro = e["mensagem"]
    s.commit()
    res["origem"] = origem
    return res
