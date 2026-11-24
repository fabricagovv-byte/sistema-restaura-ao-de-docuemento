"""Paginação como iteradores.

iter_cru, iter_envelope e iter_consulta produzem um registro por vez, sem
acumular a coleta em memória. Os adaptadores _tudo_* e _consulta_paginada
materializam listas; _consulta_paginada é o único que conhece o namespace
do argparse.
"""

import sys

from .client import PncpError, _EXIT, _get_colecao, _progresso, get


def _trava_paginas(path):
    """Trava anti-laço-infinito atingida: avisa e marca resultado parcial."""
    sys.stderr.write(f"⚠ trava de páginas atingida em {path}; "
                     "resultado pode estar incompleto\n")
    _EXIT["code"] = 3


def iter_cru(path, params=None, *, tam=100, limite=None):
    """Registros de um endpoint pncp-api que devolve array puro paginado.

    O servidor usa tamanhoPagina=10 por padrão e trunca sem indicar que faltam
    registros, então a paginação aqui é obrigatória. A última página vem curta;
    o teto de 500 páginas protege contra mudança de contrato da API.

    tam=None: endpoint sem tamanhoPagina no contrato (ex.: /v1/orgaos/) —
    o parâmetro não é enviado e a iteração só para em página vazia.
    """
    emitidos = 0
    pagina = 1
    while pagina <= 500:
        p = dict(params or {}, pagina=pagina)
        if tam:
            p["tamanhoPagina"] = tam
        lote = _get_colecao(path, p)
        if not isinstance(lote, list) or not lote:
            return
        for rec in lote:
            yield rec
            emitidos += 1
            if limite and emitidos >= limite:
                return
        if tam and len(lote) < tam:
            return
        pagina += 1
    _trava_paginas(path)


def iter_envelope(path, params=None, *, tam=50, limite=None):
    """Registros de um endpoint pncp-api com envelope {data, paginasRestantes}."""
    emitidos = 0
    pagina = 1
    while pagina <= 10000:
        res = _get_colecao(path, dict(params or {}, pagina=pagina, tamanhoPagina=tam))
        if not res or isinstance(res, list):
            return
        data = res.get("data") or []
        for rec in data:
            yield rec
            emitidos += 1
            if limite and emitidos >= limite:
                return
        if res.get("paginasRestantes", 0) <= 0 or res.get("empty") or not data:
            return
        pagina += 1
    _trava_paginas(path)


def iter_consulta(path, params, *, tam=50, seguir=False, limite=None, desde=1,
                  ao_paginar=None, stats=None, dica=None):
    """Registros da API /consulta (envelope data/totalPaginas).

    `seguir` pagina até esgotar, `limite` corta o total, `desde` inicia em
    outra página. Falha no meio não descarta o que já foi produzido: o
    generator avisa no stderr, preenche stats["incompleto"] e
    stats["proximaPagina"], marca exit code 3 e encerra.

    stats: dict opcional preenchido durante o consumo com totalRegistros,
    coletados (inclui o registro recém-entregue), incompleto, limite_atingido
    e, em caso de parcial, proximaPagina.

    ao_paginar(proxima_pagina, coletados): gancho de checkpoint, chamado após
    os registros de cada página serem consumidos. Se `limite` truncou a página
    no meio, recebe a página atual em vez da próxima, para que a retomada
    re-busque a página em vez de perder os registros restantes.

    dica: texto de retomada usado no aviso de falha parcial, quando
    "--desde-pagina N" não for o conselho aplicável.
    """
    if stats is None:
        stats = {}
    stats.update(totalRegistros=None, coletados=0, incompleto=False,
                 limite_atingido=False)
    pagina = desde or 1

    def _parcial(motivo):
        sys.stderr.write(f"\n⚠ {motivo}\n"
                         f"⚠ devolvendo {stats['coletados']} registros já "
                         f"coletados; "
                         f"{dica or f'retome com --desde-pagina {pagina}'}\n")
        stats["incompleto"] = True
        stats["proximaPagina"] = pagina
        _EXIT["code"] = 3

    while pagina <= 200_000:  # trava anti-laço; paginasRestantes governa o fim
        try:
            res = get(path, dict(params, pagina=pagina, tamanhoPagina=tam))
        except PncpError as e:
            _parcial(f"falha na página {pagina}: {e}")
            return
        if not res:
            if pagina > (desde or 1):
                # a página anterior prometeu mais (paginasRestantes>0) e veio
                # corpo vazio: fim anômalo, não fim normal — sinalizar truncagem
                _parcial(f"resposta vazia na página {pagina} após a API "
                         "prometer mais páginas")
            return
        stats["totalRegistros"] = res.get("totalRegistros")
        data = res.get("data", []) or []
        bruto = len(data)
        if limite:
            data = data[:max(limite - stats["coletados"], 0)]
        for rec in data:
            stats["coletados"] += 1  # antes do yield: inclui o registro entregue
            yield rec
        _progresso(f"\rpágina {pagina}/{res.get('totalPaginas', '?')} — "
                   f"{stats['coletados']}/{stats['totalRegistros']} registros")
        if ao_paginar:
            # página cortada pelo limite não conta como concluída
            ao_paginar(pagina + (1 if len(data) == bruto else 0),
                       stats["coletados"])
        if limite and stats["coletados"] >= limite:
            stats["limite_atingido"] = True
            return
        if not seguir:
            return
        if res.get("paginasRestantes", 0) <= 0 or res.get("empty"):
            return
        pagina += 1
    _trava_paginas(path)


# --------------------------------------------------------------- adaptadores
def _tudo_cru(path, params=None, *, tam=100, limite=None):
    """Materializa iter_cru em lista."""
    return list(iter_cru(path, params, tam=tam, limite=limite))


def _tudo_envelope(path, params=None, *, tam=50, limite=None):
    """Materializa iter_envelope em lista."""
    return list(iter_envelope(path, params, tam=tam, limite=limite))


def _consulta_paginada(path, base_params, args, escoar=None, ao_paginar=None):
    """Adaptador CLI sobre iter_consulta: traduz o namespace do argparse e
    devolve {totalRegistros, coletados, data[, incompleto, proximaPagina]}.
    Com `escoar`, os registros saem por ele e "data" volta vazio."""
    stats = {}
    coletados = []
    destino = escoar if escoar else coletados.append
    for rec in iter_consulta(path, base_params,
                             tam=args.tam if args.tam else 50,
                             seguir=args.all,
                             limite=args.limit,
                             desde=getattr(args, "desde_pagina", None) or 1,
                             ao_paginar=ao_paginar, stats=stats):
        destino(rec)
    if stats.get("coletados") or stats.get("totalRegistros") is not None:
        _progresso("\n")
    out = {"totalRegistros": stats.get("totalRegistros"),
           "coletados": stats.get("coletados", 0), "data": coletados}
    if stats.get("incompleto"):
        out["incompleto"] = True
        out["proximaPagina"] = stats["proximaPagina"]
    return out
