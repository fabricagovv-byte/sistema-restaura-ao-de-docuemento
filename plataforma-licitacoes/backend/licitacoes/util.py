"""Funções pequenas usadas em vários módulos."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento, espaços simples. Usado na busca e na classificação."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^\w\s/.,%-]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def slug(texto: str, limite: int = 80) -> str:
    t = normalizar(texto)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:limite] or "arquivo"


def para_data(valor: Any) -> datetime | None:
    """Aceita ISO, 'AAAA-MM-DD HH:MM:SS', 'DD/MM/AAAA' e datas do JavaScript."""
    if valor in (None, "", "None"):
        return None
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None) if valor.tzinfo is None else valor.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    s = str(valor).strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}))?", s)
    if m:
        d, mo, a, h, mi = m.groups()
        return datetime(int(a), int(mo), int(d), int(h or 0), int(mi or 0))
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})", s)
        if not m:
            m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
            if not m2:
                return None
            return datetime(*map(int, m2.groups()))
        return datetime(*map(int, m.groups()))
    if dt.tzinfo is not None:
        # Datas do PNCP vêm no horário de Brasília sem fuso; com fuso, guardamos o horário local informado.
        dt = dt.replace(tzinfo=None)
    return dt


def para_valor(valor: Any) -> float | None:
    """Converte valor monetário. Zero e valores simbólicos viram None (o PNCP manda 0 quando não informa)."""
    if valor in (None, "", "None"):
        return None
    if isinstance(valor, (int, float, Decimal)):
        v = float(valor)
    else:
        s = str(valor).strip().replace("R$", "").replace(" ", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            v = float(Decimal(s))
        except (InvalidOperation, ValueError):
            return None
    return v if v >= 1.0 else None


def hash_dados(dados: Any) -> str:
    return hashlib.sha256(json.dumps(dados, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def so_digitos(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def link_pncp(cnpj: str, ano: int | str, sequencial: int | str) -> str:
    return f"https://pncp.gov.br/app/editais/{so_digitos(cnpj)}/{int(ano)}/{int(sequencial)}"


def numero_controle(cnpj: str, ano: int | str, sequencial: int | str) -> str:
    """Formato do PNCP para contratações: CNPJ-1-SEQUENCIAL(6)/ANO."""
    return f"{so_digitos(cnpj)}-1-{int(sequencial):06d}/{int(ano)}"


_RE_LINK = re.compile(r"pncp\.gov\.br/app/editais/(\d{14})/(\d{4})/(\d+)")
_RE_CONTROLE = re.compile(r"^(\d{14})-\d-(\d+)/(\d{4})")


def partes_pncp(texto: str | None) -> tuple[str, int, int] | None:
    """Extrai (cnpj, ano, sequencial) de um link do PNCP ou de um número de controle."""
    if not texto:
        return None
    m = _RE_LINK.search(texto)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3))
    m = _RE_CONTROLE.match(texto.strip())
    if m:
        return m.group(1), int(m.group(3)), int(m.group(2))
    return None
