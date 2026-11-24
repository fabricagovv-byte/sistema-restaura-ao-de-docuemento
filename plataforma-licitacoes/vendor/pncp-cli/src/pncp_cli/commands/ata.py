"""Atas de registro de preço de uma contratação."""

from ..client import PncpError, _get_colecao, get
from ..controle import parse_controle_ata
from ..output import _emitir_ou_baixar, emit
from ..pagination import _tudo_cru, _tudo_envelope
from .compra import _base_compra

def cmd_ata(args):
    base = _base_compra(args) + "/atas"
    if args.asub == "listar":
        emit(_tudo_envelope(base), args)
        return
    if not args.seq_ata and getattr(args, "controle", None):
        # controle estendido de ata (CNPJ-1-SEQ/ANO-SEQATA) já identifica a ata
        args.seq_ata = parse_controle_ata(args.controle)
    if not args.seq_ata:
        raise PncpError(f"'ata {args.asub}' exige --seq-ata N (veja 'ata listar')")
    b = f"{base}/{args.seq_ata}"
    if args.asub == "detalhe":
        emit(get(b), args)
    elif args.asub == "arquivos":
        _emitir_ou_baixar(_get_colecao(f"{b}/arquivos"), args)
    elif args.asub == "partes":
        emit(_tudo_envelope(f"{b}/partesenvolvidas"), args)
    elif args.asub == "contratos":
        emit(_tudo_envelope(f"{b}/contratos"), args)
    elif args.asub == "historico":
        emit(_tudo_cru(f"{b}/historico"), args)
