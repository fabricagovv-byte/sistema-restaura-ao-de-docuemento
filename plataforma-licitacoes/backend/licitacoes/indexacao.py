"""Índices opcionais: OpenSearch (busca textual em grande volume) e pgvector (similaridade semântica).

Sem configuração, a plataforma funciona só com o PostgreSQL (pg_trgm) e a expansão por categorias.
* OpenSearch: defina LIC_OPENSEARCH_URL. `indexar_opensearch` envia em lote; `buscar_opensearch`
  devolve ids ordenados por relevância (analisador brazilian, com stemming).
* Semântica: defina LIC_EMBEDDINGS_MODELO (ex.: paraphrase-multilingual-MiniLM-L12-v2, 384 dimensões)
  e instale sentence-transformers. Exige a extensão pgvector no PostgreSQL.
"""

from __future__ import annotations

import json

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import config
from .db import pgvector_disponivel
from .modelos import Licitacao

MAPEAMENTO = {
    "settings": {"analysis": {"analyzer": {"pt": {"type": "brazilian"}}}},
    "mappings": {"properties": {
        "objeto": {"type": "text", "analyzer": "pt"}, "orgao": {"type": "text", "analyzer": "pt"},
        "uf": {"type": "keyword"}, "municipio": {"type": "keyword"}, "modalidade_id": {"type": "integer"},
        "valor_estimado": {"type": "double"}, "data_encerramento": {"type": "date"},
        "categorias": {"type": "keyword"},
    }},
}


def _os(caminho: str) -> str:
    return f"{config().opensearch_url.rstrip('/')}/{config().opensearch_indice}{caminho}"


def indexar_opensearch(s: Session, ids: list[int] | None = None, lote: int = 500) -> int:
    if not config().opensearch_url:
        return 0
    with httpx.Client(timeout=60) as cli:
        cli.put(_os(""), json=MAPEAMENTO)  # 400 se já existe: ignorado
        q = s.query(Licitacao)
        if ids:
            q = q.filter(Licitacao.id.in_(ids))
        n = 0
        buf: list[str] = []
        for lic in q.yield_per(lote):
            buf.append(json.dumps({"index": {"_id": lic.id}}))
            buf.append(json.dumps({
                "objeto": f"{lic.objeto} {lic.informacao_complementar or ''}", "orgao": lic.orgao_nome, "uf": lic.uf,
                "municipio": lic.municipio, "modalidade_id": lic.modalidade_id,
                "valor_estimado": float(lic.valor_estimado) if lic.valor_estimado else None,
                "data_encerramento": lic.data_encerramento.isoformat() if lic.data_encerramento else None,
                "categorias": [c["codigo"] for c in lic.categorias or []],
            }, ensure_ascii=False))
            n += 1
            if len(buf) >= 2 * lote:
                cli.post(_os("/_bulk"), content="\n".join(buf) + "\n", headers={"Content-Type": "application/x-ndjson"})
                buf = []
        if buf:
            cli.post(_os("/_bulk"), content="\n".join(buf) + "\n", headers={"Content-Type": "application/x-ndjson"})
    return n


def buscar_opensearch(consulta: str, tamanho: int = 100) -> list[int]:
    r = httpx.post(_os("/_search"), json={"size": tamanho, "query": {"multi_match": {
        "query": consulta, "fields": ["objeto^3", "orgao"]}}}, timeout=30)
    r.raise_for_status()
    return [int(h["_id"]) for h in r.json()["hits"]["hits"]]


_modelo = None


def _embedder():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer  # dependência opcional

        _modelo = SentenceTransformer(config().embeddings_modelo)
    return _modelo


def gerar_embeddings(s: Session, limite: int = 5000) -> int:
    if not (config().embeddings_modelo and pgvector_disponivel(s)):
        return 0
    pend = s.execute(text(
        "SELECT l.id, l.objeto FROM licitacao l LEFT JOIN licitacao_embedding e ON e.licitacao_id = l.id "
        "WHERE e.licitacao_id IS NULL LIMIT :n"), {"n": limite}).all()
    if not pend:
        return 0
    vetores = _embedder().encode([o for _, o in pend], normalize_embeddings=True, batch_size=64)
    for (i, _), v in zip(pend, vetores):
        s.execute(text("INSERT INTO licitacao_embedding (licitacao_id, modelo, vetor) VALUES (:i, :m, :v)"),
                  {"i": i, "m": config().embeddings_modelo, "v": "[" + ",".join(f"{x:.6f}" for x in v) + "]"})
    s.commit()
    return len(pend)


def similares(s: Session, consulta: str, limite: int = 50) -> list[tuple[int, float]]:
    """Editais mais parecidos com a consulta (similaridade de cosseno)."""
    if not (config().embeddings_modelo and pgvector_disponivel(s)):
        return []
    v = _embedder().encode([consulta], normalize_embeddings=True)[0]
    linhas = s.execute(text(
        "SELECT licitacao_id, 1 - (vetor <=> CAST(:v AS vector)) AS sim FROM licitacao_embedding "
        "ORDER BY vetor <=> CAST(:v AS vector) LIMIT :n"), {"v": "[" + ",".join(f"{x:.6f}" for x in v) + "]", "n": limite}).all()
    return [(i, float(sm)) for i, sm in linhas]
