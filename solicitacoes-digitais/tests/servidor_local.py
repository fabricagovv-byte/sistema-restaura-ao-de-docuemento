"""Servidor local com dados fictícios para os testes no navegador (ponta a ponta e acessibilidade)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NAVEGADOR = RAIZ / "tests" / "navegador"

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


def playwright_node() -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, cwd=RAIZ).returncode == 0


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def servidor(pasta: Path):
    """Sobe a API com SQLite temporário e os 4 perfis fictícios; devolve a URL base."""
    env = {**os.environ, "SD_AMBIENTE": "teste", "SD_BANCO_URL": f"sqlite:///{pasta / 'navegador.db'}", "SD_PBKDF2_ITERACOES": "1000",
           "SD_ANEXOS_DIR": str(pasta / "anexos"), "PYTHONPATH": str(RAIZ)}
    subprocess.run([sys.executable, "-c", SEMEAR], env=env, cwd=RAIZ, check=True)
    porta = _porta_livre()
    proc = subprocess.Popen([sys.executable, "-m", "solicitacoes", "servidor", "--porta", str(porta)], env=env, cwd=RAIZ,
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
            raise RuntimeError("servidor não subiu: " + proc.stderr.read1(2000).decode(errors="replace"))
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def rodar_node(roteiro: str, *args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(NAVEGADOR / roteiro), *args], capture_output=True, text=True, cwd=RAIZ, timeout=timeout)
