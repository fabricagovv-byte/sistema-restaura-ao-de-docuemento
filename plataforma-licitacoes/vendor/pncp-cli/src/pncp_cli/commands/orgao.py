"""Órgãos/entidades: detalhe, unidades, busca por razão social."""

from ..client import PncpError, get
from ..output import emit
from ..pagination import _tudo_cru

def cmd_orgao(args):
    if args.buscar:
        emit(_tudo_cru("/api/pncp/v1/orgaos/", {"razaoSocial": args.buscar},
                       tam=None, limite=args.limit), args)
        return
    if args.id:
        emit(get(f"/api/pncp/v1/orgaos/id/{args.id}"), args)
        return
    if not args.cnpj:
        raise PncpError("informe CNPJ, --id N ou --buscar 'razão social'")
    if args.unidades:
        emit(get(f"/api/pncp/v1/orgaos/{args.cnpj}/unidades"), args)
    else:
        emit(get(f"/api/pncp/v1/orgaos/{args.cnpj}"), args)
