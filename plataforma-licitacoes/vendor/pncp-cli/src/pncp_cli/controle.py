"""Números de controle PNCP (CNPJ-TIPO-SEQ/ANO, com sufixo de ata)."""

from .client import PncpError

def parse_controle(numero):
    """'07424905000138-1-000212/2026' -> (cnpj, ano, sequencial).

    Aceita também o formato estendido de ata '...-000212/2024-000001'
    (sufixo = sequencial da ata), ignorando o sufixo aqui — quem precisa dele
    usa parse_controle_ata().
    """
    try:
        left, resto = numero.split("/")
        cnpj, _tipo, seq = left.split("-")
        ano = resto.split("-")[0]
        return cnpj, int(ano), int(seq)
    except Exception:
        raise PncpError(f"número de controle inválido: {numero!r} "
                        "(esperado CNPJ-TIPO-SEQ/ANO)")

def parse_controle_ata(numero):
    """Sequencial da ata do formato estendido 'CNPJ-1-SEQ/ANO-SEQATA', se houver."""
    try:
        partes = numero.split("/")[1].split("-")
        return int(partes[1]) if len(partes) > 1 else None
    except Exception:
        return None

def resolve_alvo(args):
    """Resolve CNPJ/ANO/SEQ a partir de posicionais ou de --controle."""
    if getattr(args, "controle", None):
        return parse_controle(args.controle)
    if args.cnpj and args.ano and args.seq:
        return args.cnpj, args.ano, args.seq
    raise PncpError("informe CNPJ ANO SEQ ou --controle NUMERO")
