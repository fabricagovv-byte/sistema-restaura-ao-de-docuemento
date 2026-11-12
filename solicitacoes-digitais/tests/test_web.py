"""Frontend (dia 5): servido pela própria API, com CSP, sem HTML montado a partir de texto e falando só com rotas
que existem no contrato OpenAPI."""

import re
from pathlib import Path

from solicitacoes import contrato
from solicitacoes.api import CSP

WEB = Path(__file__).resolve().parent.parent / "solicitacoes" / "web"


def test_telas_servidas_com_politica_de_seguranca(app_cliente):
    c = app_cliente
    r = c.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["Content-Security-Policy"] == CSP and "script-src 'self'" in CSP and "unsafe-inline" not in CSP
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Cache-Control"] == "no-store"
    for arquivo, tipo in (("/app.js", "javascript"), ("/app.css", "text/css")):
        a = c.get(arquivo)
        assert a.status_code == 200 and tipo in a.headers["content-type"] and a.headers["Content-Security-Policy"] == CSP
    # a API e a documentação dela não recebem a CSP das telas (o Swagger carrega recursos próprios)
    assert "Content-Security-Policy" not in c.get("/api/v1/saude").headers
    assert c.get("/api/v1/docs").status_code == 200


def test_link_de_redefinir_senha_abre_o_frontend(app_cliente):
    r = app_cliente.get("/redefinir-senha")
    assert r.status_code == 200 and '<script type="module" src="/app.js">' in r.text


def test_rota_inexistente_nao_devolve_a_pagina(app_cliente):
    c = app_cliente
    for metodo, rota, esperado in (("GET", "/api/v1/nao-existe", 404), ("POST", "/api/v1/nao-existe", 405),
                                   ("GET", "/pagina-que-nao-existe.html", 404)):
        r = c.request(metodo, rota)
        assert r.status_code == esperado and r.headers["content-type"].startswith("application/json"), (metodo, rota)
    assert c.delete("/api/v1/auditoria").status_code == 405  # método errado em rota existente continua 405


def test_html_sem_script_ou_estilo_embutido():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "script embutido seria bloqueado pela CSP"
    assert not re.search(r"\sstyle=|<style", html) and not re.search(r"\son[a-z]+=", html)
    assert 'lang="pt-BR"' in html and 'name="viewport"' in html and 'href="#conteudo"' in html


def _codigo_sem_comentarios() -> str:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(^|\s)//.*$", "", js, flags=re.M)


def test_codigo_do_frontend_nao_monta_html_a_partir_de_texto():
    js = _codigo_sem_comentarios()
    for proibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert proibido not in js, proibido
    assert "localStorage" not in js and 'sessionStorage.setItem(TOKEN' in js  # o token some ao fechar a aba


def _chamadas_do_frontend() -> set[tuple[str, str]]:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    chamadas = set()
    for metodo, caminho in re.findall(r'api\("(GET|POST|PUT|PATCH|DELETE)",\s*[`"]([^`"?]+)', js):
        chamadas.add((metodo, re.sub(r"\$\{[^}]+\}", "{}", caminho)))
    return chamadas


def test_frontend_so_chama_rotas_do_contrato():
    ops = {(m, re.sub(r"\{[^}]+\}", "{}", p.removeprefix("/api/v1"))) for m, p in contrato.operacoes(contrato.salvo())}
    chamadas = _chamadas_do_frontend()
    assert {("POST", "/auth/login"), ("GET", "/auth/eu"), ("POST", "/auth/logout"), ("POST", "/auth/recuperar"),
            ("POST", "/auth/redefinir"), ("GET", "/solicitacoes"), ("POST", "/solicitacoes"), ("GET", "/solicitacoes/{}"),
            ("GET", "/categorias"), ("GET", "/usuarios")} <= chamadas
    fora = sorted(chamadas - ops)
    assert not fora, f"o frontend chama rotas que não existem no contrato: {fora}"
