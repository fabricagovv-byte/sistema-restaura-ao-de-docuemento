"""Coleta em massa via /api/consulta/v1 (períodos, PCA, cobrança).

Em NDJSON cada registro sai no stdout assim que a página chega; json e table
materializam. Intervalos maiores que 365 dias são divididos em janelas (a API
rejeita períodos maiores com 422). `--checkpoint` grava o progresso por
trabalho (modalidade × janela) e permite retomar coletas interrompidas.
Os filtros locais (`--incluir`/`--excluir`) são aplicados em streaming, com
`--limit` contando registros após o filtro.
"""

import argparse
import datetime
import json
import os
import sys

from ..client import PncpError, _progresso
from ..constants import MODALIDADES
from ..filtros import com_link, filtrar
from ..output import emit, escoador, formato
from ..pagination import _consulta_paginada, iter_consulta


def _yyyymmdd(d):
    return d.replace("-", "")


def _modalidade_id(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise PncpError(f"--modalidade inválida: {valor!r} (esperado um ID "
                        "numérico ou 'all'; veja `pncp dominio modalidades`)")


def _validar_intervalo(args):
    if getattr(args, "de", None) and getattr(args, "ate", None) and args.de > args.ate:
        raise PncpError(f"intervalo invertido: --de {args.de} > --ate {args.ate}")


def _validar_tam(args, maximo):
    if args.tam and not 10 <= args.tam <= maximo:
        raise PncpError(f"--tam {args.tam} fora do aceito por este endpoint "
                        f"(10 a {maximo})")


def _janelas(de, ate, max_dias=365):
    """Divide [de, ate] em janelas de no máximo max_dias dias corridos.

    A API /consulta devolve 422 para períodos maiores que 365 dias. Um
    intervalo que já cabe no limite vira janela única.
    """
    d0 = datetime.date.fromisoformat(de)
    fim = datetime.date.fromisoformat(ate)
    janelas = []
    while d0 <= fim:
        d1 = min(d0 + datetime.timedelta(days=max_dias - 1), fim)
        janelas.append((d0.isoformat(), d1.isoformat()))
        d0 = d1 + datetime.timedelta(days=1)
    return janelas


def _coletar(path, base, args, ao_paginar=None):
    """Uma passada de _consulta_paginada honrando o formato (NDJSON escoa)."""
    escoar = escoador() if formato(args) == "ndjson" else None
    return _consulta_paginada(path, base, args, escoar=escoar,
                              ao_paginar=ao_paginar)


def _saida(r, args):
    """Fecha a saída de uma coleta: NDJSON já escoou; JSON/tabela emitem agora."""
    if formato(args) != "ndjson":
        emit(r, args)


def _coletar_janelas(path, montar_base, args, de, ate):
    """Coleta um endpoint de período dividindo em janelas de 365 dias.

    montar_base(j_de, j_ate) -> params da janela. Janela única preserva o
    formato de saída de uma coleta simples; múltiplas agregam {coletados,
    data} e, em falha parcial, incluem incompleto/janela/proximaPagina.
    """
    janelas = _janelas(de, ate)
    if len(janelas) > 1 and getattr(args, "desde_pagina", None):
        raise PncpError("--desde-pagina é ambíguo com intervalo dividido em "
                        f"{len(janelas)} janelas (de qual janela?) — encurte o "
                        "intervalo para retomar a janela que falhou")
    if len(janelas) == 1:
        _saida(_coletar(path, montar_base(de, ate), args), args)
        return
    todos = []
    coletados = 0
    parcial = None
    for j_de, j_ate in janelas:
        _progresso(f"[janela {j_de} → {j_ate}]\n")
        a = argparse.Namespace(**vars(args))
        if args.limit:
            a.limit = args.limit - coletados
        r = _coletar(path, montar_base(j_de, j_ate), a)
        coletados += r["coletados"]
        todos.extend(r["data"])
        if r.get("incompleto"):
            parcial = {"incompleto": True, "janela": [j_de, j_ate],
                       "proximaPagina": r.get("proximaPagina")}
            break
        if args.limit and coletados >= args.limit:
            break
    if formato(args) != "ndjson":
        out = {"coletados": coletados, "data": todos}
        if parcial:
            out.update(parcial)
        emit(out, args)


# ------------------------------------------------------------------ checkpoint
def _impressao_consulta(args):
    """Identidade da coleta: um checkpoint só vale para a consulta que o criou."""
    return {"de": args.de, "ate": args.ate, "por": args.por,
            "modalidade": str(args.modalidade), "uf": args.uf,
            "municipio": args.municipio, "cnpj": args.cnpj,
            "unidade": args.unidade, "modo_disputa": args.modo_disputa,
            "tam": args.tam,
            # --all muda o que "trabalho concluído" significa e --link muda
            # a forma dos registros; --limit fica de fora para permitir
            # retomada com um limite maior.
            "all": bool(getattr(args, "all", False)),
            "link": bool(getattr(args, "link", False))}


def _checkpoint_ler(caminho, impressao):
    if caminho and os.path.exists(caminho):
        with open(caminho) as f:
            estado = json.load(f)
        if estado.get("consulta") != impressao:
            raise PncpError(
                f"o checkpoint {caminho!r} é de OUTRA consulta "
                f"(datas/filtros diferentes) — use outro arquivo ou apague-o")
        return estado
    return {"consulta": impressao, "concluidos": [], "atual": None,
            "proxima_pagina": 1, "coletados": 0}


def _checkpoint_gravar(caminho, estado):
    tmp = caminho + ".tmp"
    with open(tmp, "w") as f:
        json.dump(estado, f)
    os.replace(tmp, caminho)  # atômico: nunca fica meio-escrito


# --------------------------------------------------------------- contratações
def cmd_consulta_contratacoes(args):
    _validar_intervalo(args)
    _validar_tam(args, 50)
    path = f"/api/consulta/v1/contratacoes/{args.por}"
    modalidades = ([_modalidade_id(args.modalidade)] if args.modalidade != "all"
                   else list(MODALIDADES))
    janelas = _janelas(args.de, args.ate)
    # trabalho = (modalidade, janela); é a unidade de retomada do checkpoint
    trabalhos = [(m, ji) for m in modalidades for ji in range(len(janelas))]
    if len(trabalhos) > 1 and getattr(args, "desde_pagina", None):
        raise PncpError("--desde-pagina é ambíguo com múltiplas modalidades ou "
                        "janelas (de qual trabalho?) — use --checkpoint, que "
                        "guarda modalidade, janela e página juntas")
    filtros_cli = {
        "uf": args.uf,
        "codigoMunicipioIbge": args.municipio,
        "cnpj": args.cnpj,
        "codigoUnidadeAdministrativa": args.unidade,
        "codigoModoDisputa": args.modo_disputa,
    }
    incluir = getattr(args, "incluir", None) or []
    excluir = getattr(args, "excluir", None) or []
    filtros_ativos = bool(incluir or excluir)
    ck = getattr(args, "checkpoint", None)
    if ck and filtros_ativos:
        raise PncpError("--checkpoint com --incluir/--excluir não é "
                        "suportado: a contagem de retomada ficaria ambígua. "
                        "Colete sem filtro e filtre depois")
    streaming = formato(args) == "ndjson"
    if ck and not streaming:
        # em json/table os registros ficam em memória até o fim; um estado
        # avançado sem os registros correspondentes no stdout perderia dados
        raise PncpError("--checkpoint exige saída NDJSON (--ndjson ou "
                        "--output ndjson): em json/table os registros só saem "
                        "no fim, e uma interrupção perderia dados que o "
                        "checkpoint já contabilizou")
    estado = _checkpoint_ler(ck, _impressao_consulta(args))
    escoar = escoador() if streaming else None
    todos = []
    coletados = estado["coletados"]  # retomada preserva a contagem p/ --limit
    incompleto = False
    limite_cortou = False

    for m, ji in trabalhos:
        chave = f"{m}:{ji}"
        if chave in estado["concluidos"]:
            _progresso(f"[trabalho {chave} — já concluído no checkpoint]\n")
            continue
        if args.limit and coletados >= args.limit:
            break
        j_de, j_ate = janelas[ji]
        base = dict(filtros_cli,
                    dataInicial=_yyyymmdd(j_de),
                    dataFinal=_yyyymmdd(j_ate),
                    codigoModalidadeContratacao=m)
        if len(trabalhos) > 1:
            _progresso(f"[modalidade {m} — {MODALIDADES.get(m, '?')} · "
                       f"{j_de} → {j_ate}]\n")
        ao_paginar = None
        if ck:
            def ao_paginar(prox, emitidos, _chave=chave, _base=coletados):
                sys.stdout.flush()  # linhas NDJSON no disco antes do estado
                _checkpoint_gravar(ck, dict(estado, atual=_chave,
                                            proxima_pagina=prox,
                                            coletados=_base + emitidos))
        desde = (estado["proxima_pagina"]
                 if ck and estado["atual"] == chave else
                 (getattr(args, "desde_pagina", None) or 1))
        if ck:
            # Persiste o trabalho antes da primeira requisição; assim uma falha
            # já na página 1 também deixa um checkpoint retomável.
            _checkpoint_gravar(ck, dict(estado, atual=chave,
                                        proxima_pagina=desde,
                                        coletados=coletados))
        stats = {}
        fluxo = iter_consulta(
            path, base,
            tam=args.tam if args.tam else 50,
            seguir=args.all,
            # com filtro local, o corte acontece DEPOIS do filtro (aqui fora)
            limite=None if filtros_ativos else (
                args.limit - coletados if args.limit else None),
            desde=desde, ao_paginar=ao_paginar, stats=stats,
            dica=("use o mesmo --checkpoint para retomar deste ponto" if ck
                  else "use --checkpoint para retomadas com múltiplos trabalhos"
                  if len(trabalhos) > 1 else None))
        if filtros_ativos:
            fluxo = filtrar(fluxo, incluir, excluir, args.match,
                            campos=("objetoCompra", "informacaoComplementar"))
        if getattr(args, "link", False):
            fluxo = (com_link(r) for r in fluxo)
        for rec in fluxo:
            (escoar if streaming else todos.append)(rec)
            coletados += 1
            if filtros_ativos and args.limit and coletados >= args.limit:
                # corte pós-filtro. Sem filtro o corte é do próprio
                # iter_consulta, que roda o gancho de checkpoint da página
                # truncada antes de encerrar.
                fluxo.close()
                break
        _progresso("\n")
        if stats.get("incompleto"):
            incompleto = {"trabalho": chave, "janela": list(janelas[ji]),
                          "proximaPagina": stats.get("proximaPagina")}
            # Sem checkpoint, uma modalidade indisponível não deve impedir a
            # varredura das demais. O exit global permanece 3 (parcial), e os
            # avisos no stderr identificam cada trabalho que falhou.
            if args.modalidade == "all" and not ck:
                continue
            break
        if ck:
            if stats.get("limite_atingido"):
                # trabalho cortado pelo --limit não é concluído: o estado
                # gravado pelo gancho fica no disco para retomada com um
                # limite maior
                limite_cortou = True
                break
            estado["concluidos"].append(chave)
            estado["atual"] = None
            estado["proxima_pagina"] = 1
            estado["coletados"] = coletados
            _checkpoint_gravar(ck, estado)

    if ck and not incompleto and not limite_cortou:
        try:
            os.remove(ck)
        except FileNotFoundError:
            pass
    if ck and limite_cortou:
        _progresso(f"[--limit atingido; checkpoint mantido em {ck} para "
                   "retomada com limite maior]\n")
    if streaming:
        return  # registros já escoaram linha a linha
    out = {"coletados": coletados, "data": todos}
    if incompleto:
        out["incompleto"] = True
        out.update(incompleto)
    emit(out, args)


# ------------------------------------------------------------ demais períodos
def cmd_consulta_propostas(args):
    _validar_tam(args, 50)
    base = {
        "dataFinal": _yyyymmdd(args.ate),
        "uf": args.uf,
        "codigoMunicipioIbge": args.municipio,
        "cnpj": args.cnpj,
        "codigoUnidadeAdministrativa": args.unidade,
    }
    if args.modalidade:
        base["codigoModalidadeContratacao"] = _modalidade_id(args.modalidade)
    _saida(_coletar("/api/consulta/v1/contratacoes/proposta", base, args), args)


def cmd_consulta_atas(args):
    _validar_intervalo(args)
    _validar_tam(args, 500)
    path = ("/api/consulta/v1/atas/atualizacao" if args.por == "atualizacao"
            else "/api/consulta/v1/atas")
    _coletar_janelas(
        path,
        lambda de, ate: {"dataInicial": _yyyymmdd(de), "dataFinal": _yyyymmdd(ate),
                         "cnpj": args.cnpj,
                         "codigoUnidadeAdministrativa": args.unidade},
        args, args.de, args.ate)


def cmd_consulta_contratos(args):
    _validar_intervalo(args)
    _validar_tam(args, 500)
    path = ("/api/consulta/v1/contratos/atualizacao" if args.por == "atualizacao"
            else "/api/consulta/v1/contratos")
    _coletar_janelas(
        path,
        lambda de, ate: {"dataInicial": _yyyymmdd(de), "dataFinal": _yyyymmdd(ate),
                         "cnpjOrgao": args.cnpj,
                         "codigoUnidadeAdministrativa": args.unidade},
        args, args.de, args.ate)


def cmd_consulta_cobranca(args):
    """Instrumentos de cobrança (notas fiscais etc.) incluídos no período."""
    _validar_intervalo(args)
    _validar_tam(args, 100)
    _coletar_janelas(
        "/api/consulta/v1/instrumentoscobranca/inclusao",
        lambda de, ate: {"dataInicial": _yyyymmdd(de), "dataFinal": _yyyymmdd(ate),
                         "tipoInstrumentoCobranca": args.tipo,
                         "cnpjOrgao": args.cnpj},
        args, args.de, args.ate)


def cmd_consulta_pca(args):
    """PCA (Plano de Contratações Anual) via API de consulta, em 3 modos."""
    if args.por == "atualizacao":
        if not (args.de and args.ate):
            raise PncpError("pca --por atualizacao exige --de e --ate")
        _validar_intervalo(args)
        _coletar_janelas(
            "/api/consulta/v1/pca/atualizacao",
            lambda de, ate: {"dataInicio": _yyyymmdd(de), "dataFim": _yyyymmdd(ate),
                             "cnpj": args.cnpj, "codigoUnidade": args.unidade},
            args, args.de, args.ate)
        return
    if args.usuario:
        if not args.ano:
            raise PncpError("pca --usuario exige --ano")
        base = {"anoPca": args.ano, "idUsuario": args.usuario,
                "codigoClassificacaoSuperior": args.classificacao,
                "cnpj": args.cnpj}
        _saida(_coletar("/api/consulta/v1/pca/usuario", base, args), args)
        return
    if not (args.ano and args.classificacao):
        raise PncpError("pca exige --ano e --classificacao COD "
                        "(classificação superior do catálogo; "
                        "alternativas: --usuario ID ou --por atualizacao)")
    base = {"anoPca": args.ano,
            "codigoClassificacaoSuperior": args.classificacao}
    _saida(_coletar("/api/consulta/v1/pca/", base, args), args)
