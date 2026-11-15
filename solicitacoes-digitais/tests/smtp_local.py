"""Servidor SMTP de homologação local para os testes da integração de e-mail (D8-B).

Fala o protocolo SMTP de verdade (RFC 5321) sobre TCP em 127.0.0.1, com autenticação AUTH PLAIN e LOGIN opcional,
e guarda o que recebe. Também simula recusas: destinatários em `recusar` recebem 550 (definitiva) e em `temporario`
recebem 451 (temporária). Nenhuma mensagem sai da máquina.
"""

from __future__ import annotations

import base64
import socketserver
import threading
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage


@dataclass
class Recebida:
    remetente: str
    destinatarios: list[str]
    dados: bytes

    @property
    def mensagem(self) -> EmailMessage:
        return message_from_bytes(self.dados, policy=policy.default)  # type: ignore[return-value]


@dataclass
class ServidorSmtp:
    usuario: str | None = None
    senha: str | None = None
    recusar: set[str] = field(default_factory=set)
    temporario: set[str] = field(default_factory=set)
    recebidas: list[Recebida] = field(default_factory=list)
    conexoes: int = 0

    def __enter__(self) -> ServidorSmtp:
        dono = self

        class Tratador(socketserver.StreamRequestHandler):
            def responder(self, linha: str) -> None:
                self.wfile.write((linha + "\r\n").encode())
                self.wfile.flush()

            def handle(self) -> None:  # noqa: C901 - uma máquina de estados simples do SMTP
                dono.conexoes += 1
                self.responder("220 homologacao.local ESMTP pronto")
                autenticado = dono.usuario is None
                remetente, destinos = None, []
                while True:
                    bruto = self.rfile.readline()
                    if not bruto:
                        return
                    linha = bruto.decode(errors="replace").rstrip("\r\n")
                    cmd = linha.split(" ", 1)[0].upper()
                    arg = linha[len(cmd):].strip()
                    if cmd == "EHLO":
                        self.responder("250-homologacao.local")
                        if dono.usuario is not None:
                            self.responder("250-AUTH PLAIN LOGIN")
                        self.responder("250 8BITMIME")
                    elif cmd == "HELO":
                        self.responder("250 homologacao.local")
                    elif cmd == "AUTH":
                        partes = arg.split()
                        if partes[0].upper() == "PLAIN":
                            cred = partes[1] if len(partes) > 1 else self._ler_base64("334 ")
                            _, u, s = base64.b64decode(cred).decode().split("\x00")
                        else:  # LOGIN
                            u = base64.b64decode(self._ler_base64("334 VXNlcm5hbWU6")).decode()
                            s = base64.b64decode(self._ler_base64("334 UGFzc3dvcmQ6")).decode()
                        if (u, s) == (dono.usuario, dono.senha):
                            autenticado = True
                            self.responder("235 2.7.0 autenticado")
                        else:
                            self.responder("535 5.7.8 credenciais recusadas")
                    elif cmd == "MAIL":
                        if not autenticado:
                            self.responder("530 5.7.0 autenticacao obrigatoria")
                            continue
                        remetente, destinos = arg.split(":", 1)[1].strip().strip("<>").split()[0] if ":" in arg else "", []
                        self.responder("250 2.1.0 ok")
                    elif cmd == "RCPT":
                        para = arg.split(":", 1)[1].strip().strip("<>")
                        if para in dono.recusar:
                            self.responder("550 5.1.1 caixa inexistente")
                        elif para in dono.temporario:
                            self.responder("451 4.3.0 tente mais tarde")
                        else:
                            destinos.append(para)
                            self.responder("250 2.1.5 ok")
                    elif cmd == "DATA":
                        if not destinos:
                            self.responder("554 5.5.1 sem destinatarios validos")
                            continue
                        self.responder("354 termine com <CRLF>.<CRLF>")
                        linhas = []
                        while True:
                            b = self.rfile.readline()
                            if b in (b".\r\n", b".\n", b""):
                                break
                            linhas.append(b[1:] if b.startswith(b"..") else b)
                        dono.recebidas.append(Recebida(remetente or "", list(destinos), b"".join(linhas)))
                        self.responder("250 2.0.0 aceita")
                        remetente, destinos = None, []
                    elif cmd == "RSET":
                        remetente, destinos = None, []
                        self.responder("250 ok")
                    elif cmd == "NOOP":
                        self.responder("250 ok")
                    elif cmd == "QUIT":
                        self.responder("221 ate logo")
                        return
                    else:
                        self.responder("502 comando nao implementado")

            def _ler_base64(self, pergunta: str) -> str:
                self.responder(pergunta)
                return self.rfile.readline().decode().strip()

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self._srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Tratador)
        self._srv.daemon_threads = True
        self.porta = self._srv.server_address[1]
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc) -> None:
        self._srv.shutdown()
        self._srv.server_close()


def porta_livre() -> int:
    """Uma porta onde ninguém escuta (para simular o servidor de e-mail fora do ar)."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
