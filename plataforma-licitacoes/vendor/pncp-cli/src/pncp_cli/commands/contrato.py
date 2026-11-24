"""Contratos e sub-recursos (termos, empenhos, cobrança, da-compra)."""

from ..client import _get_colecao, get
from ..controle import resolve_alvo
from ..output import _emitir_ou_baixar, emit
from ..pagination import _tudo_cru, _tudo_envelope

def cmd_contrato(args):
    cnpj, ano, seq = resolve_alvo(args)
    if args.csub == "da-compra":
        # contratos nascidos de uma CONTRATAÇÃO (o alvo é a compra, não o contrato)
        emit(_tudo_envelope(
            f"/api/pncp/v1/orgaos/{cnpj}/contratos/contratacao/{ano}/{seq}"), args)
        return
    b = f"/api/pncp/v1/orgaos/{cnpj}/contratos/{ano}/{seq}"
    if args.csub == "detalhe":
        emit(get(b), args)
    elif args.csub == "arquivos":
        _emitir_ou_baixar(_tudo_cru(f"{b}/arquivos"), args)
    elif args.csub == "termos":
        if args.seq_termo:
            _emitir_ou_baixar(_tudo_cru(f"{b}/termos/{args.seq_termo}/arquivos"), args)
        else:
            emit(_tudo_cru(f"{b}/termos"), args)
    elif args.csub == "empenhos":
        emit(_tudo_envelope(f"{b}/empenhos"), args)
    elif args.csub == "historico":
        emit(_tudo_cru(f"{b}/historico"), args)
    elif args.csub == "cobranca":
        emit(_get_colecao(f"{b}/instrumentocobranca") or [], args)
