"""Camada HTTP: headers exigidos pelo servidor, retries e downloads."""

import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .constants import BASE, UA

class PncpError(Exception):
    """Erro da API/CLI; `status` carrega o código HTTP quando houver."""

    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


# exit code do processo: 0 ok · 1 erro · 3 sucesso parcial
_EXIT = {"code": 0}

# ajustes globais (--timeout/--retries/--quiet os sobrescrevem em cli.main)
CONFIG = {"timeout": 60, "retries": 5, "quiet": False, "pausa": 0.0}

# --pausa dorme só ENTRE requisições; a primeira nunca espera
_HOUVE_REQUISICAO = {"v": False}


def _progresso(msg):
    """Progresso no stderr; --quiet silencia. Avisos não passam por aqui."""
    if not CONFIG["quiet"]:
        sys.stderr.write(msg)
        sys.stderr.flush()

def _request(url, *, timeout=None, retries=None):
    """GET com headers de navegador e backoff exponencial; retorna JSON.

    429 e 5xx são retentados (Retry-After é respeitado quando presente), assim
    como respostas 200 com HTML do WAF. Os demais 4xx abortam imediatamente.
    """
    timeout = CONFIG["timeout"] if timeout is None else timeout
    retries = CONFIG["retries"] if retries is None else retries
    if CONFIG["pausa"] and _HOUVE_REQUISICAO["v"]:
        time.sleep(CONFIG["pausa"])
    _HOUVE_REQUISICAO["v"] = True
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Referer": BASE + "/app/editais",
    }
    last = None
    for attempt in range(retries):
        wait = 1.5 * (2 ** attempt)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                if resp.status == 204 or not raw:
                    return None
                try:
                    return json.loads(raw.decode("utf-8"))
                except ValueError:
                    # WAF pode responder 200 com página HTML (ex.: limite de requisições)
                    last = "resposta não-JSON (página do WAF?)"
                    wait = max(wait, 30)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                try:
                    wait = min(float(ra), 180) if ra else max(wait, 45)
                except ValueError:
                    wait = max(wait, 45)
                last = "HTTP 429 (limite de requisições)"
            elif 400 <= e.code < 500:
                # 4xx restante é erro do cliente: não adianta repetir
                body = e.read().decode("utf-8", "replace")
                try:
                    msg = json.loads(body).get("message", body)
                except Exception:
                    msg = body[:200]
                raise PncpError(f"HTTP {e.code}: {msg}", status=e.code)
            else:
                last = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = str(getattr(e, "reason", e))
        # backoff antes de repetir; esperas longas são explicadas no stderr
        if attempt < retries - 1:
            if wait >= 10:
                sys.stderr.write(f"\n[{last} — aguardando {wait:.0f}s antes de repetir]\n")
            time.sleep(wait)
    raise PncpError(f"falha após {retries} tentativas: {last}")

def get(path, params=None, **kw):
    url = BASE + path
    if params:
        # descarta None; listas viram chaves repetidas
        parts = []
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                for item in v:
                    parts.append((k, item))
            else:
                parts.append((k, v))
        url += "?" + urllib.parse.urlencode(parts)
    return _request(url, **kw)

def baixar(url, destino, *, timeout=120, retries=3):
    """Baixa um binário (documento, CSV) para `destino`, com retry."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp, \
                    open(destino, "wb") as f:
                f.write(resp.read())
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = str(getattr(e, "reason", e))
            if attempt < retries - 1:
                time.sleep(1.5 * (2 ** attempt))
    raise PncpError(f"download falhou ({url}): {last}")

def _get_colecao(path, params=None):
    """GET de coleção: o servidor sinaliza coleção vazia com 404 e mensagem
    descritiva; aqui isso vira []. Recursos de detalhe usam get() e mantêm
    o 404 como erro."""
    try:
        return get(path, params)
    except PncpError as e:
        if e.status == 404:
            return []
        raise
