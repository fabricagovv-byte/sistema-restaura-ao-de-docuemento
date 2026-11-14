"""Testes no navegador (RNF-07 e RNF-09).

Sobem a API num processo separado, com banco SQLite temporário e só dados fictícios, e rodam roteiros do
Playwright do Node no Chromium. Pulados se o Node com Playwright (ou o axe-core, para acessibilidade) não estiver
na máquina."""

from __future__ import annotations

import pytest

from .servidor_local import NAVEGADOR, playwright_node, rodar_node, servidor

sem_navegador = pytest.mark.skipif(not playwright_node(), reason="Node com Playwright não disponível nesta máquina")


@sem_navegador
def test_fluxo_critico_no_navegador(tmp_path):
    """D6-B: fluxo crítico com três perfis."""
    with servidor(tmp_path) as url:
        r = rodar_node("e2e_fluxo_critico.js", url, str(tmp_path))
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fluxo crítico aprovado" in r.stdout


@sem_navegador
@pytest.mark.skipif(not (NAVEGADOR / "node_modules" / "axe-core" / "axe.min.js").exists(),
                    reason="axe-core não instalado (npm install em tests/navegador)")
def test_acessibilidade_e_responsividade_das_telas(tmp_path):
    """D7-A: todas as telas sem violação grave ou crítica de acessibilidade (WCAG 2 A e AA, axe-core) e sem rolagem
    lateral no celular (390 px) e no computador (1280 px)."""
    with servidor(tmp_path) as url:
        r = rodar_node("acessibilidade.js", url, str(tmp_path), timeout=300)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "acessibilidade aprovada" in r.stdout
