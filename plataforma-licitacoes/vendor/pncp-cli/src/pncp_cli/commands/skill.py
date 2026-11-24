"""Instalação da skill de Claude Code embutida no pacote."""

import os
import shutil
from importlib import resources

from ..output import emit


def _dir_skills():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(base, "skills")


def cmd_skill(args):
    origem = resources.files("pncp_cli").joinpath("skill/SKILL.md")
    destino = args.dir or os.path.join(_dir_skills(), "pncp")
    if args.ssub == "caminho":
        emit({"origem": str(origem), "destino": destino}, args)
        return
    os.makedirs(destino, exist_ok=True)
    alvo = os.path.join(destino, "SKILL.md")
    with resources.as_file(origem) as f:
        shutil.copyfile(f, alvo)
    emit({"instalada": alvo}, args)
