"""Filtros e enriquecimentos locais, aplicados sobre registros já obtidos.

Casamento de termos: um termo de uma palavra casa token inteiro ("rede" não
casa "credenciamento"); um termo com espaços casa como frase (sequência
contígua de tokens). A comparação ignora caixa e acentos. Nenhuma função
deste módulo muta os dicionários recebidos.
"""

import re
import unicodedata

from .client import PncpError
from .controle import parse_controle


def normalizar(texto):
    """Minúsculas sem acentos (NFKD): base de toda comparação local."""
    nfkd = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _tokens(texto):
    return re.findall(r"\w+", normalizar(texto))


def casa(termo, texto):
    """True se `termo` (token ou frase) ocorre em `texto`."""
    alvo = _tokens(texto)
    seq = _tokens(termo)
    if not seq:
        return False
    if len(seq) == 1:
        return seq[0] in alvo
    return any(alvo[i:i + len(seq)] == seq
               for i in range(len(alvo) - len(seq) + 1))


def filtrar(registros, incluir=(), excluir=(), match="any",
            campos=("objetoCompra",)):
    """Generator que deixa passar registros conforme os termos.

    incluir: o registro passa se any/all (conforme `match`) dos termos casam.
    excluir: o registro cai se qualquer termo casa. Não muta os registros.
    """
    op = any if match == "any" else all
    for r in registros:
        texto = "\n".join(str(r.get(c) or "") for c in campos)
        if incluir and not op(casa(t, texto) for t in incluir):
            continue
        if excluir and any(casa(t, texto) for t in excluir):
            continue
        yield r


def link_pncp(registro):
    """URL oficial da contratação no portal, ou None se não identificável."""
    nc = registro.get("numeroControlePNCP") or registro.get("numero_controle_pncp")
    if not nc:
        return None
    try:
        cnpj, ano, seq = parse_controle(nc)
    except PncpError:
        return None
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"


def com_link(registro):
    """Cópia do registro com o campo sintético _link_pncp (original intacto)."""
    novo = dict(registro)
    novo["_link_pncp"] = link_pncp(registro)
    return novo
