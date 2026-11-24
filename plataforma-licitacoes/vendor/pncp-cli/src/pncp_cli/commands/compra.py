"""Sub-recursos de uma contratação: itens, resultados, arquivos, histórico."""

import sys

from ..client import _get_colecao, _progresso, get
from ..controle import parse_controle, resolve_alvo
from ..output import _emitir_ou_baixar, emit
from ..pagination import _tudo_cru

def get_itens(cnpj, ano, seq, tam=100, limite=None):
    """Todos os itens de uma contratação (array cru paginado — ver _tudo_cru)."""
    return _tudo_cru(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                     tam=tam, limite=limite)

def cmd_itens(args):
    cnpj, ano, seq = resolve_alvo(args)
    emit(get_itens(cnpj, ano, seq, tam=args.tam, limite=args.limit), args)

def cmd_resultados(args):
    """Resultado(s) de item: fornecedor vencedor, valores homologados."""
    cnpj, ano, seq = resolve_alvo(args)
    base = f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    if args.item:
        emit(_get_colecao(f"{base}/{args.item}/resultados") or [], args)
        return
    # sem --item: varre todos os itens que têm resultado informado
    itens = get_itens(cnpj, ano, seq)
    numeros = [i["numeroItem"] for i in itens if i.get("temResultado")]
    todos = []
    for n in numeros:
        for r in _get_colecao(f"{base}/{n}/resultados") or []:
            r.setdefault("numeroItem", n)
            todos.append(r)
        _progresso(f"\rresultados: {len(todos)} registros "
                   f"({numeros.index(n) + 1}/{len(numeros)} itens)")
    if numeros:
        _progresso("\n")
    else:
        sys.stderr.write(f"nenhum dos {len(itens)} itens tem resultado informado\n")
    emit(todos, args)

def cmd_contratacao(args):
    cnpj, ano, seq = resolve_alvo(args)
    emit(get(f"/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}"), args)

def cmd_historico(args):
    cnpj, ano, seq = resolve_alvo(args)
    emit(_tudo_cru(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/historico"), args)

def cmd_arquivos(args):
    cnpj, ano, seq = resolve_alvo(args)
    _emitir_ou_baixar(
        _tudo_cru(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"), args)

def cmd_controle(args):
    cnpj, ano, seq = parse_controle(args.numero)
    info = {"cnpj": cnpj, "ano": ano, "sequencial": seq}
    if args.detalhe:
        info["detalhe"] = get(f"/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}")
    emit(info, args)

def _base_compra(args):
    cnpj, ano, seq = resolve_alvo(args)
    return f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
