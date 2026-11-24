"""Busca textual/facetada (/api/search)."""

from ..client import _progresso, get
from ..filtros import com_link, filtrar
from ..output import emit, formato

# a busca casa contra estes campos do registro (filtro local pós-consulta)
_CAMPOS_FILTRO = ("description", "title", "orgao_nome")


def _refinar(registros, args):
    """Aplica --incluir/--excluir/--link aos registros da busca (sem mutação)."""
    incluir = getattr(args, "incluir", None) or []
    excluir = getattr(args, "excluir", None) or []
    fluxo = iter(registros)
    if incluir or excluir:
        fluxo = filtrar(fluxo, incluir, excluir, args.match, campos=_CAMPOS_FILTRO)
    if getattr(args, "link", False):
        fluxo = (com_link(r) for r in fluxo)
    return fluxo


def cmd_search(args):
    def csv(x):
        return [s.strip() for s in x.split(",")] if x else None

    params = {
        "q": args.termo or None,
        "tipos_documento": args.tipo,
        "ordenacao": args.ordenacao,
        "status": args.status,
        "tam_pagina": args.tam,
        "ufs": csv(args.uf),
        "modalidades": csv(args.modalidade),
        "orgaos": csv(args.orgao),
        "municipios": csv(args.municipio),
        "esferas": csv(args.esfera),
        "poderes": csv(args.poder),
    }
    if not args.all:
        params["pagina"] = args.pagina
        res = get("/api/search/", params)
        itens = list(_refinar(res.get("items", []), args))
        if formato(args) == "ndjson":
            emit(itens, args)  # um registro por linha, sempre
        else:
            emit(dict(res, items=itens), args)
        return

    # --all: itera páginas até esgotar ou atingir --limit (pós-filtro)
    coletados = []
    pagina = args.pagina
    total = None
    while True:
        params["pagina"] = pagina
        res = get("/api/search/", params)
        total = res.get("total", 0)
        itens = res.get("items", [])
        if not itens:
            break
        for it in _refinar(itens, args):
            coletados.append(it)
            if args.limit and len(coletados) >= args.limit:
                break
        _progresso(f"\rpágina {pagina} — {len(coletados)}/{total} coletados")
        if args.limit and len(coletados) >= args.limit:
            break
        # a busca (ElasticSearch) limita paginação profunda em ~10.000 resultados
        if pagina * args.tam >= min(total, 10000):
            break
        pagina += 1
    _progresso("\n")
    if formato(args) == "ndjson":
        emit(coletados, args)
    else:
        emit({"total": total, "coletados": len(coletados), "items": coletados}, args)

def cmd_filtros(args):
    res = get("/api/search/filters", {"tipos_documento": args.tipo})
    filtros = res.get("filters", {})
    if args.faceta:
        emit(filtros.get(args.faceta, []), args)
    else:
        # resumo: nome da faceta -> qtd de opções
        emit({k: len(v) if isinstance(v, list) else v for k, v in filtros.items()}, args)
