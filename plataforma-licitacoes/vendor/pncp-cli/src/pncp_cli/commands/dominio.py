"""Tabelas de domínio (modalidades, amparos legais, modos de disputa…)."""

from ..client import PncpError, get
from ..constants import DOMINIOS
from ..output import emit

def cmd_dominio(args):
    if not args.tabela:
        emit(sorted(DOMINIOS), args)
        return
    if args.tabela not in DOMINIOS:
        raise PncpError(f"tabela desconhecida: {args.tabela!r} "
                        f"(opções: {', '.join(sorted(DOMINIOS))})")
    emit(get(DOMINIOS[args.tabela]), args)
