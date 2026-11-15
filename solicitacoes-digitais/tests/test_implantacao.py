"""Implantação (REQ-007, D8-A): contêineres, configuração por ambiente e pipeline de CI conferidos pelo conteúdo.

A subida real dos contêineres está em `tests/homologacao_conteineres.py` (roteiro contra o docker-compose) e no job
`imagem` da CI; aqui ficam as regras que não podem regredir sem ninguém ver.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
REPO = RAIZ.parent


def _compose() -> dict:
    return yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))


def test_toda_variavel_lida_pelo_codigo_esta_no_env_de_exemplo():
    lidas = set()
    for arq in (RAIZ / "solicitacoes").glob("*.py"):
        lidas |= set(re.findall(r"""os\.environ(?:\.get)?\(\s*["'](SD_[A-Z0-9_]+)""", arq.read_text(encoding="utf-8")))
    exemplo = (RAIZ / ".env.exemplo").read_text(encoding="utf-8")
    declaradas = set(re.findall(r"^#?\s*(SD_[A-Z0-9_]+)=", exemplo, re.M))
    assert lidas, "nenhuma variável encontrada: o padrão de leitura mudou?"
    faltam = lidas - declaradas - {"SD_TESTE_PG"}
    assert not faltam, f"documente no .env.exemplo: {sorted(faltam)}"
    # segredos ficam em branco no exemplo
    for chave in ("SD_SEGREDO", "POSTGRES_PASSWORD", "SD_SMTP_SENHA"):
        assert re.search(rf"^{chave}=\s*$", exemplo, re.M), chave


def test_compose_sobe_banco_api_e_envio_sem_segredo_no_arquivo():
    c = _compose()
    s = c["services"]
    assert {"banco", "api", "mensagens", "mailpit"} <= set(s)
    assert s["api"]["depends_on"]["banco"]["condition"] == "service_healthy"
    assert s["mensagens"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert "enviar-mensagens" in " ".join(s["mensagens"]["command"]) and "--continuo" in " ".join(s["mensagens"]["command"])
    assert s["mailpit"]["profiles"] == ["homologacao"]  # caixa de e-mail falsa só no perfil de homologação
    assert "${POSTGRES_PASSWORD:?" in s["banco"]["environment"]["POSTGRES_PASSWORD"]  # sem senha definida, não sobe
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert not re.search(r"(SENHA|PASSWORD|SEGREDO)\s*[:=]\s*[\"']?[A-Za-z0-9]{8,}", texto), "segredo escrito no compose"
    # API publicada só na própria máquina por padrão (atrás de proxy HTTPS)
    assert s["api"]["ports"] == ["${SD_PORTA_PUBLICA:-127.0.0.1:8000}:8000"]
    assert s["mailpit"]["ports"] == ["127.0.0.1:8025:8025"]
    assert set(c["volumes"]) == {"banco", "anexos"}


def test_imagem_sem_root_com_saude_e_migracao_na_subida():
    d = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12-slim$", d, re.M)
    assert re.search(r"^USER sd$", d, re.M) and "useradd --system" in d
    assert "HEALTHCHECK" in d and "/api/v1/saude" in d
    assert "python -m solicitacoes migrar && exec python -m solicitacoes servidor --host 0.0.0.0" in d
    assert "--mount=type=secret,id=ca,required=false" in d  # certificado da rede só na construção, fora da imagem
    ignorados = (RAIZ / ".dockerignore").read_text(encoding="utf-8").split()
    assert {".env", "tests", "medicao", "*.db"} <= set(ignorados)
    assert ".env" in (RAIZ / ".gitignore").read_text(encoding="utf-8").split()


def test_pipeline_de_ci_roda_testes_nos_dois_bancos_contrato_e_imagem():
    w = yaml.safe_load((REPO / ".github" / "workflows" / "solicitacoes-ci.yml").read_text(encoding="utf-8"))
    gatilhos = w.get("on") or w.get(True)  # o YAML lê a chave "on" como booleano
    assert "solicitacoes-digitais/**" in gatilhos["push"]["paths"] and "pull_request" in gatilhos
    testes = w["jobs"]["testes"]
    assert testes["strategy"]["matrix"]["banco"] == ["sqlite", "postgresql"]
    assert testes["services"]["postgres"]["image"].startswith("postgres:16")
    passos = " ".join(str(p.get("run", "")) + str(p.get("env", "")) for p in testes["steps"])
    assert "contrato --verificar" in passos and "pytest" in passos and "SD_TESTE_PG" in passos
    imagem = w["jobs"]["imagem"]
    assert imagem["needs"] == "testes"
    corpo = " ".join(str(p.get("run", "")) for p in imagem["steps"])
    assert "docker build" in corpo and "/api/v1/saude" in corpo and "docker compose down -v" in corpo
    assert w["permissions"] == {"contents": "read"}


def test_requisitos_tem_o_driver_do_postgresql():
    req = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^psycopg\[binary\]==", req, re.M)
