"""Roteiro de homologação em contêineres (D8-A + D8-B), rodado contra o docker-compose de verdade.

Pré-requisito: `docker compose --profile homologacao up -d --wait` com SD_SMTP_HOST=mailpit. O roteiro:
1. confere a saúde da API e que rota protegida recusa sem login;
2. com um administrador criado pela linha de comando, cria categoria, gestor e solicitante (dados fictícios);
3. o solicitante abre uma solicitação e o gestor a tramita;
4. espera o serviço `mensagens` entregar o aviso à caixa de homologação (Mailpit) e confere assunto e destinatário;
5. confere a caixa de saída pela API do administrador.

Uso: python tests/homologacao_conteineres.py http://127.0.0.1:8000 http://127.0.0.1:8025 <senha-do-admin>
Imprime um relatório linha a linha; sai com código 1 na primeira verificação que falhar.
"""

from __future__ import annotations

import sys
import time

import httpx


def ok(cond: bool, texto: str) -> None:
    print(("OK    " if cond else "FALHOU") + " " + texto, flush=True)
    if not cond:
        raise SystemExit(1)


def main(api: str, caixa: str, senha_admin: str) -> int:
    c = httpx.Client(base_url=api, timeout=20)
    r = c.get("/api/v1/saude")
    ok(r.status_code == 200, f"saúde da API: {r.json()}")
    ok(c.get("/api/v1/solicitacoes").status_code == 401, "rota protegida sem login responde 401")

    def entrar(email: str, senha: str) -> dict:
        r = c.post("/api/v1/auth/login", json={"email": email, "senha": senha})
        ok(r.status_code == 200, f"login de {email}")
        return {"Authorization": f"Bearer {r.json()['token']}"}

    adm = entrar("admin@exemplo.gov.br", senha_admin)
    cat = c.post("/api/v1/categorias", json={"nome": "Segunda via de documento", "prazo_dias": 5}, headers=adm)
    ok(cat.status_code == 201, "categoria criada")
    senha = "Senha-Ficticia-2026"
    for email, perfil in (("gestora@exemplo.gov.br", "gestor"), ("cidadao@exemplo.gov.br", "solicitante")):
        r = c.post("/api/v1/usuarios", json={"email": email, "nome": email.split("@")[0].title(), "perfil": perfil, "senha": senha}, headers=adm)
        ok(r.status_code == 201, f"usuário {perfil} criado")
    sol_h, ges_h = entrar("cidadao@exemplo.gov.br", senha), entrar("gestora@exemplo.gov.br", senha)
    r = c.post("/api/v1/solicitacoes", json={"titulo": "Segunda via de alvará", "descricao": "Preciso da segunda via do alvará.",
                                              "categoria_id": cat.json()["id"]}, headers=sol_h)
    ok(r.status_code == 201, f"solicitação aberta: protocolo {r.json()['protocolo']}")
    sol = r.json()
    r = c.post(f"/api/v1/solicitacoes/{sol['id']}/tramitar", json={"para": "em_triagem", "comentario": "Recebido, em análise."}, headers=ges_h)
    ok(r.status_code == 200 and r.json()["status"] == "em_triagem", "gestor tramitou para em triagem")

    m = httpx.Client(base_url=caixa, timeout=10)
    achou, t0 = None, time.monotonic()
    while time.monotonic() - t0 < 90 and not achou:
        for msg in m.get("/api/v1/messages").json().get("messages", []):
            if any(t["Address"] == "cidadao@exemplo.gov.br" for t in msg["To"]) and sol["protocolo"] in msg["Subject"]:
                achou = msg
        if not achou:
            time.sleep(2)
    ok(achou is not None, f"aviso entregue na caixa de homologação em {time.monotonic() - t0:.0f}s: {achou and achou['Subject']!r}")
    corpo = m.get(f"/api/v1/message/{achou['ID']}").json()["Text"]
    ok("\"recebida\" para \"em triagem\"" in corpo and "Recebido, em análise." in corpo, "corpo com situação e comentário")
    r = c.get("/api/v1/mensagens", headers=adm)
    ok(r.status_code == 200 and r.json()["smtp_configurado"] and r.json()["por_status"]["enviada"] >= 1,
       f"caixa de saída pela API do administrador: {r.json()['por_status']}")
    print(f"SOLICITACAO_ID={sol['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:4]))
