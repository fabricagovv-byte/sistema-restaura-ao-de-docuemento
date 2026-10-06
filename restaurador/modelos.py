from __future__ import annotations

from dataclasses import dataclass, field

INTEGRO = "íntegro"
RESTAURADO = "restaurado"
PARCIAL = "recuperado parcialmente"
IRRECUPERAVEL = "irrecuperável"

ORDEM_STATUS = {INTEGRO: 0, RESTAURADO: 1, PARCIAL: 2, IRRECUPERAVEL: 3}


@dataclass
class Restauracao:
    nome: str
    origem: str
    tipo: str
    status: str = INTEGRO
    arquivo: tuple[str, bytes] | None = None  # (nome, bytes) do documento restaurado
    extras: list[tuple[str, bytes]] = field(default_factory=list)  # páginas restauradas, imagens salvas...
    texto: str = ""
    feito: list[str] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    paginas: int | None = None
    paginas_esperadas: int | None = None
    qualidade: float = 0.0
    como_encontrado: str = "arquivo"

    def piorar(self, status: str) -> None:
        if ORDEM_STATUS[status] > ORDEM_STATUS[self.status]:
            self.status = status
