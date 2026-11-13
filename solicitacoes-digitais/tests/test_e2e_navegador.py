"""Teste ponta a ponta do fluxo crítico no navegador (RNF-07, D6-B).

Sobe a API num processo separado, com banco SQLite temporário e só dados fictícios, e roda
`tests/navegador/e2e_fluxo_critico.js` no Chromium (Playwright do Node). Pulado se o Node ou o Playwright
não estiverem disponíveis na máquina."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ROTEIRO = RAIZ / "tests" / "navegador" / "e2e_fluxo_critico.js"

SEMEAR = """
from solicitacoes.migracoes import aplicar
from solicitacoes.banco import sessao
from solicitacoes.modelos import Usuario, Categoria
from solicitacoes import seguranca
aplicar()
with sessao() as s:
    for e, n, p in [("admin@exemplo.gov.br", "Ana Admin", "administrador"), ("gestor@exemplo.gov.br", "Gil Gestor", "gestor"),
                    ("operador@exemplo.gov.br", "Otto Operador", "operador"), ("cidada@exemplo.gov.br", "Clara Cidadã", "solicitante")]:
        s.add(Usuario(email=e, nome=n, perfil=p, senha_hash=seguranca.gerar_hash("Senha-Forte-2026")))
    s.add(Categoria(nome="Segunda via de documento", prazo_dias=5))
    s.add(Categoria(nome="Certidão", prazo_dias=10))
"""


def _playwright_node() -> bool:
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, cwd=RAIZ)
    return r.returncode == 0


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(not _playwright_node(), reason="Node com Playwright não disponível nesta máquina")
def test_fluxo_critico_no_navegador(tmp_path):
    env = {**os.environ, "SD_AMBIENTE": "teste", "SD_BANCO_URL": f"sqlite:///{tmp_path / 'e2e.db'}", "SD_PBKDF2_ITERACOES": "1000",
           "SD_ANEXOS_DIR": str(tmp_path / "anexos"), "PYTHONPATH": str(RAIZ)}
    subprocess.run([sys.executable, "-c", SEMEAR], env=env, cwd=RAIZ, check=True)
    porta = _porta_livre()
    servidor = subprocess.Popen([sys.executable, "-m", "solicitacoes", "servidor", "--porta", str(porta)], env=env, cwd=RAIZ,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        url = f"http://127.0.0.1:{porta}/"
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "api/v1/saude", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("servidor não subiu: " + servidor.stderr.read1(2000).decode(errors="replace"))
        r = subprocess.run(["node", str(ROTEIRO), url, str(tmp_path)], capture_output=True, text=True, cwd=RAIZ, timeout=240)
        print(r.stdout)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "fluxo crítico aprovado" in r.stdout
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)
