"""Linha de comando: migrar o banco, criar o primeiro administrador, subir a API."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from . import auditoria, notificacoes, seguranca
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
    em = sub.add_parser("enviar-mensagens", help="envia por SMTP os e-mails pendentes da caixa de saída")
    em.add_argument("--continuo", action="store_true", help="repete a cada --intervalo segundos (serviço)")
    em.add_argument("--intervalo", type=float, default=60.0), em.add_argument("--limite", type=int, default=100)
    em.add_argument("--voltas", type=int, default=0, help="com --continuo, para depois de N rodadas (0 = sem fim)")
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
    elif a.cmd == "enviar-mensagens":
        import json
        import time

        if not a.continuo:
            aplicar()
            with sessao() as s:
                r = notificacoes.enviar_pendentes(s, limite=a.limite)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            return 0 if not r.get("erro_conexao") else 1
        # serviço: banco ou SMTP fora do ar numa rodada não derruba o processo; tenta de novo na próxima
        volta = 0
        while True:
            volta += 1
            try:
                aplicar()
                with sessao() as s:
                    r = notificacoes.enviar_pendentes(s, limite=a.limite)
            except Exception as e:  # noqa: BLE001 - registra e segue
                r = {"erro": f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"}
            print(json.dumps(r, ensure_ascii=False, default=str), flush=True)
            if a.voltas and volta >= a.voltas:
                return 0
            time.sleep(a.intervalo)
    elif a.cmd == "servidor":
        import uvicorn

        uvicorn.run("solicitacoes.api:app", host=a.host, port=a.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
