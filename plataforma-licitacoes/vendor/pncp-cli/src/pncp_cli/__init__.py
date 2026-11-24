"""Cliente para as APIs públicas do PNCP (pncp.gov.br).

Sem dependências além da stdlib. Cobre os endpoints GET públicos das specs
OpenAPI /api/consulta/v3/api-docs e /api/pncp/v3/api-docs, além da API de
busca do portal. Exit codes do processo: 0 sucesso, 1 erro, 3 sucesso parcial.
"""

from .constants import VERSAO as __version__  # noqa: E402

from .client import (  # noqa: F401
    CONFIG,
    PncpError,
    _EXIT,
    _get_colecao,
    _request,
    baixar,
    get,
)
from .constants import (  # noqa: F401
    BASE,
    DOMINIOS,
    MODALIDADES,
    STATUS,
    TIPOS_BUSCA,
    UA,
)
from .controle import (  # noqa: F401
    parse_controle,
    parse_controle_ata,
    resolve_alvo,
)
from .pagination import (  # noqa: F401
    _consulta_paginada,
    _tudo_cru,
    _tudo_envelope,
    iter_consulta,
    iter_cru,
    iter_envelope,
)
from .filtros import casa, com_link, filtrar, link_pncp, normalizar  # noqa: F401
from .output import _print_table, emit  # noqa: F401
from .commands.consulta import _modalidade_id, _yyyymmdd  # noqa: F401
from .commands.compra import get_itens  # noqa: F401
from .cli import build_parser, main  # noqa: F401
