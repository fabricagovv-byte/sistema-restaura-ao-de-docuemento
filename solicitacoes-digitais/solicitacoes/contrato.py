"""Contrato OpenAPI versionado (REQ-006, RNF-05).

O contrato gerado do código fica salvo em docs/api/openapi-v1.json. O teste de contrato falha quando a API muda
sem o contrato salvo ser atualizado (`python -m solicitacoes contrato`), e quando uma mudança quebra clientes:
remover rota, remover campo obrigatório de resposta ou tornar obrigatório um parâmetro antes opcional.
"""

from __future__ import annotations

import json
from pathlib import Path

CAMINHO = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi-v1.json"
METODOS = ("get", "post", "put", "patch", "delete")


def gerar() -> dict:
    from .api import app

    app.openapi_schema = None  # sempre do código atual
    return app.openapi()


def texto(contrato: dict) -> str:
    return json.dumps(contrato, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def salvo(caminho: Path = CAMINHO) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def operacoes(c: dict) -> dict[tuple[str, str], dict]:
    return {(m.upper(), p): op for p, item in c.get("paths", {}).items() for m, op in item.items() if m in METODOS}


def _esquema(c: dict, ref_ou_esquema: dict | None) -> dict:
    e = ref_ou_esquema or {}
    while "$ref" in e:
        e = c["components"]["schemas"][e["$ref"].rsplit("/", 1)[1]]
    return e


def _resposta_ok(c: dict, op: dict) -> dict:
    for cod in ("200", "201"):
        conteudo = op.get("responses", {}).get(cod, {}).get("content", {}).get("application/json")
        if conteudo:
            return _esquema(c, conteudo.get("schema"))
    return {}


def quebras(antigo: dict, novo: dict) -> list[str]:
    """Mudanças incompatíveis de `antigo` para `novo` (lista vazia = compatível)."""
    erros = []
    ops_novo = operacoes(novo)
    for chave, op in operacoes(antigo).items():
        if chave not in ops_novo:
            erros.append(f"rota removida: {chave[0]} {chave[1]}")
            continue
        n = ops_novo[chave]
        obrig_antes = {p["name"] for p in op.get("parameters", []) if p.get("required")}
        for p in n.get("parameters", []):
            if p.get("required") and p["name"] not in obrig_antes:
                erros.append(f"parâmetro passou a ser obrigatório: {chave[0]} {chave[1]} {p['name']}")
        ra, rn = _resposta_ok(antigo, op), _resposta_ok(novo, n)
        for campo in ra.get("required", []):
            if campo not in rn.get("properties", {}):
                erros.append(f"campo removido da resposta: {chave[0]} {chave[1]} {campo}")
    return erros


def main(verificar: bool = False, caminho: Path = CAMINHO) -> int:
    atual = gerar()
    if verificar:
        if not caminho.exists():
            print(f"contrato ausente: {caminho}")
            return 1
        antigo = salvo(caminho)
        problemas = quebras(antigo, atual)
        igual = texto(antigo) == texto(atual)
        for q in problemas:
            print("INCOMPATÍVEL:", q)
        print("contrato em dia" if igual else "contrato desatualizado: rode `python -m solicitacoes contrato`")
        return 0 if igual and not problemas else 1
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto(atual), encoding="utf-8")
    print(f"contrato salvo em {caminho} ({len(operacoes(atual))} operações, versão {atual['info']['version']})")
    return 0
