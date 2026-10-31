"""Cliente HTTP comum aos conectores: ritmo de chamadas, novas tentativas e estatísticas.

Regras:
* respeita um intervalo mínimo entre chamadas (limite de acesso de cada fonte);
* 429: espera em degraus (30, 60, 120 s por padrão) e tenta de novo;
* 5xx e falha de rede: espera exponencial, até `max_tentativas`;
* 204: "nenhum registro", devolve None;
* outros 4xx: erro definitivo (repetir não adianta), com o status para quem chamou decidir.
Não contorna CAPTCHA, login nem bloqueio: 401/403 viram `AcessoNegado`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import config

log = logging.getLogger("licitacoes.http")


class ErroFonte(Exception):
    def __init__(self, mensagem: str, status: int | None = None, url: str | None = None):
        super().__init__(mensagem)
        self.status = status
        self.url = url


class AcessoNegado(ErroFonte):
    """401/403: a fonte exige autenticação ou bloqueou o acesso. Não tentamos contornar."""


class LimiteDeAcesso(ErroFonte):
    """429 persistente depois de todas as esperas."""


class FalhaTemporaria(ErroFonte):
    """5xx ou rede, persistente depois de todas as tentativas."""


@dataclass
class Estatisticas:
    chamadas: int = 0
    novas_tentativas: int = 0
    http_429: int = 0
    http_5xx: int = 0
    http_204: int = 0
    falhas_rede: int = 0
    por_status: dict[int, int] = field(default_factory=dict)


class ClienteHttp:
    def __init__(
        self,
        *,
        intervalo_minimo_s: float = 1.0,
        esperas_429_s: tuple[float, ...] = (30, 60, 120),
        max_tentativas: int = 4,
        timeout_s: float = 60,
        cabecalhos: dict[str, str] | None = None,
        http: httpx.Client | None = None,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ):
        self.intervalo_minimo_s = intervalo_minimo_s
        self.esperas_429_s = list(esperas_429_s)
        self.max_tentativas = max_tentativas
        self.stats = Estatisticas()
        h = {"User-Agent": config().user_agent, "Accept": "application/json"}
        h.update(cabecalhos or {})
        self._http = http or httpx.Client(timeout=timeout_s, headers=h, follow_redirects=True)
        if http is not None:
            self._http.headers.update(h)
        self._dormir = dormir
        self._relogio = relogio
        self._ultima: float | None = None

    def _ritmo(self) -> None:
        if self._ultima is not None:
            espera = self.intervalo_minimo_s - (self._relogio() - self._ultima)
            if espera > 0:
                self._dormir(espera)
        self._ultima = self._relogio()

    def requisitar(self, metodo: str, url: str, **kw: Any) -> httpx.Response | None:
        t429 = 0
        tfalha = 0
        while True:
            self._ritmo()
            self.stats.chamadas += 1
            try:
                r = self._http.request(metodo, url, **kw)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self.stats.falhas_rede += 1
                tfalha += 1
                if tfalha >= self.max_tentativas:
                    raise FalhaTemporaria(f"falha de rede: {type(exc).__name__}: {exc}", url=url) from exc
                self.stats.novas_tentativas += 1
                self._dormir(2 ** tfalha)
                continue
            st = r.status_code
            self.stats.por_status[st] = self.stats.por_status.get(st, 0) + 1
            if st == 204:
                self.stats.http_204 += 1
                return None
            if st == 429:
                self.stats.http_429 += 1
                if t429 >= len(self.esperas_429_s):
                    raise LimiteDeAcesso("limite de acesso (429) persistente", 429, url)
                espera = _retry_after(r) or self.esperas_429_s[t429]
                t429 += 1
                self.stats.novas_tentativas += 1
                log.warning("429 em %s; esperando %.0fs", url, espera)
                self._dormir(espera)
                continue
            if st >= 500:
                self.stats.http_5xx += 1
                tfalha += 1
                if tfalha >= self.max_tentativas:
                    raise FalhaTemporaria(f"HTTP {st} persistente", st, url)
                self.stats.novas_tentativas += 1
                self._dormir(2 ** tfalha)
                continue
            if st in (401, 403):
                raise AcessoNegado(f"HTTP {st}: acesso exige autenticação ou foi bloqueado", st, url)
            if st >= 400:
                raise ErroFonte(f"HTTP {st}: {r.text[:300]}", st, url)
            return r

    def get_json(self, url: str, params: dict | None = None, **kw: Any) -> Any | None:
        r = self.requisitar("GET", url, params=params, **kw)
        if r is None:
            return None
        if not r.content:
            return None
        try:
            return r.json()
        except ValueError as exc:
            raise ErroFonte(f"resposta não é JSON: {r.text[:200]}", r.status_code, url) from exc

    def fechar(self) -> None:
        self._http.close()


def _retry_after(r: httpx.Response) -> float | None:
    v = r.headers.get("Retry-After")
    if v and v.isdigit():
        return float(v)
    return None
