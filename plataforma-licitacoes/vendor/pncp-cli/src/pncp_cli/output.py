"""Saída (JSON/NDJSON/tabela) e download em lote de documentos."""

import json
import os
import sys

from .client import _progresso, baixar


def formato(args):
    """Formato de saída canônico: --output vence; --ndjson/--table são aliases."""
    if getattr(args, "output", None):
        return args.output
    if getattr(args, "ndjson", False):
        return "ndjson"
    if getattr(args, "table", False):
        return "table"
    return "json"


def escoador():
    """Escreve um registro NDJSON por vez no stdout.

    O flush por registro garante que a linha saiu do buffer antes de o
    checkpoint declarar a página concluída."""
    def escoar(rec):
        sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return escoar

def emit(obj, args):
    """Imprime resultado conforme o formato (--output / aliases --ndjson --table)."""
    f = formato(args)
    if f == "ndjson":
        rows = obj if isinstance(obj, list) else [obj]
        for r in rows:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
    elif f == "table":
        _print_table(obj)
    else:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def _print_table(obj):
    if obj is None:
        print("(vazio)")
        return
    rows = obj if isinstance(obj, list) else obj.get("items") or obj.get("data") or [obj]
    if not rows:
        print("(vazio)")
        return
    if not isinstance(rows[0], dict):
        # lista de escalares (ex.: `dominio` sem argumento)
        for r in rows:
            print(r)
        return
    # colunas enxutas conforme o formato da linha
    if "numero_controle_pncp" in rows[0]:
        cols = ["numero_controle_pncp", "uf", "modalidade_licitacao_nome",
                "orgao_nome", "data_fim_vigencia", "title"]
    elif "numeroControlePNCP" in rows[0]:
        cols = ["numeroControlePNCP", "modalidadeNome", "situacaoCompraNome",
                "dataPublicacaoPncp", "objetoCompra"]
    else:
        cols = list(rows[0].keys())[:6]
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, "")
            v = ("" if v is None else str(v)).replace("\n", " ")
            if len(v) > 45:
                v = v[:44] + "…"
            vals.append(v)
        print(" | ".join(vals))

def _destino_livre(dirpath, nome, usados):
    """Nome de arquivo sem colisão: sufixa -2, -3 etc. se já existir."""
    base, ext = os.path.splitext(nome)
    candidato, i = nome, 2
    while candidato in usados or os.path.exists(os.path.join(dirpath, candidato)):
        candidato = f"{base}-{i}{ext}"
        i += 1
    usados.add(candidato)
    return os.path.join(dirpath, candidato)


def _emitir_ou_baixar(arquivos, args):
    """Lista de documentos: emite, ou baixa todos se --baixar DIR (sem sobrescrever)."""
    arquivos = arquivos or []
    if not getattr(args, "baixar", None):
        emit(arquivos, args)
        return
    os.makedirs(args.baixar, exist_ok=True)
    usados = set()
    baixados = []
    for a in arquivos:
        url = a.get("url") or a.get("uri")
        nome = a.get("titulo") or f"arquivo_{a.get('sequencialDocumento')}"
        # o título pode conter '/' ou outros caracteres inválidos p/ nome de arquivo
        nome = nome.replace("/", "-").replace("\\", "-").strip() or \
            f"arquivo_{a.get('sequencialDocumento')}"
        destino = _destino_livre(args.baixar, nome, usados)
        baixar(url, destino)
        _progresso(f"baixado: {destino}\n")
        baixados.append(destino)
    emit({"baixados": len(baixados), "dir": args.baixar, "arquivos": baixados}, args)
