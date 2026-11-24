"""Plano de Contratações Anual de um órgão (demanda futura declarada)."""

from ..client import PncpError, _progresso, baixar, get
from ..constants import BASE
from ..output import emit
from ..pagination import _tudo_cru

def cmd_pca(args):
    b = f"/api/pncp/v1/orgaos/{args.cnpj}/pca"
    if args.psub == "consolidado":
        if args.unidades:
            emit(_tudo_cru(f"{b}/{args.ano}/consolidado/unidades"), args)
        elif args.seq:
            emit(get(f"{b}/{args.ano}/{args.seq}/consolidado"), args)
        else:
            emit(get(f"{b}/{args.ano}/consolidado"), args)
    elif args.psub == "itens":
        if not args.seq:
            raise PncpError("'pca itens' exige --seq N (veja 'pca planos')")
        emit(_tudo_cru(f"{b}/{args.ano}/{args.seq}/itens",
                       {"categoria": args.categoria}, limite=args.limit), args)
    elif args.psub == "valores":
        if args.seq:
            emit(get(f"{b}/{args.ano}/{args.seq}/valorescategoriaitem"), args)
        else:
            emit(get(f"{b}/{args.ano}/valorescategoriaitem"), args)
    elif args.psub == "planos":
        if not args.uasg:
            raise PncpError("'pca planos' exige --uasg CODIGO (código da unidade)")
        emit(get(f"/api/pncp/v1/orgaos/{args.cnpj}/pca/{args.uasg}/{args.ano}"
                 "/sequenciaisplano") or {}, args)
    elif args.psub == "csv":
        destino = args.saida or f"pca_{args.cnpj}_{args.ano}.csv"
        baixar(f"{BASE}{b}/{args.ano}/csv", destino)
        _progresso(f"baixado: {destino}\n")
        emit({"arquivo": destino}, args)
