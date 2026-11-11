"""Linha de comando: migrar o banco, criar o primeiro administrador, subir a API."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from . import auditoria, seguranca
from .banco import sessao
from .migracoes import aplicar, versao_atual
from .modelos import Usuario


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m solicitacoes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrar", help="aplica as migrações pendentes")
    ca = sub.add_parser("criar-admin", help="cria um administrador (senha lida do terminal)")
    ca.add_argument("email"), ca.add_argument("nome")
    ct = sub.add_parser("contrato", help="grava docs/api/openapi-v1.json a partir do código (ou confere com --verificar)")
    ct.add_argument("--verificar", action="store_true")
    sv = sub.add_parser("servidor", help="sobe a API")
    sv.add_argument("--porta", type=int, default=8000), sv.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    if a.cmd == "migrar":
        print("aplicadas:", aplicar() or "nenhuma (já atualizado)", "| versão:", versao_atual())
    elif a.cmd == "criar-admin":
        aplicar()
        senha = getpass.getpass("senha: ")
        motivo = seguranca.senha_aceitavel(senha)
        if motivo:
            print(motivo, file=sys.stderr)
            return 2
        with sessao() as s:
            if s.scalar(select(Usuario).where(func.lower(Usuario.email) == a.email.lower())):
                print("já existe usuário com este e-mail", file=sys.stderr)
                return 2
            u = Usuario(email=a.email.lower(), nome=a.nome, perfil="administrador", senha_hash=seguranca.gerar_hash(senha))
            s.add(u)
            s.flush()
            auditoria.registrar(s, acao="criar", recurso="usuario", recurso_id=u.id, depois={"email": u.email, "perfil": u.perfil, "origem": "linha de comando"})
        print("administrador criado")
    elif a.cmd == "contrato":
        from . import contrato

        return contrato.main(verificar=a.verificar)
    elif a.cmd == "servidor":
        import uvicorn

        uvicorn.run("solicitacoes.api:app", host=a.host, port=a.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
