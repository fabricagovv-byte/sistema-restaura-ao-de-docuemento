"""Notificações por e-mail (REQ-006, entrega D8-B).

Fluxo: as rotas só gravam a mensagem na caixa de saída (`mensagem_saida`), na mesma transação da mudança; o envio
por SMTP é feito depois, em lote (`enviar_pendentes`), pela linha de comando (`python -m solicitacoes enviar-mensagens`,
que pode rodar em laço como serviço) ou pela rota do administrador. Assim uma queda do servidor de e-mail não
impede a tramitação e nenhuma mensagem é perdida.

Regras:
* sem `SD_SMTP_HOST` nada é enviado e as mensagens ficam pendentes;
* recusa definitiva do servidor (código 5xx, destinatário recusado) marca a mensagem como `falhou`, sem nova tentativa;
* falha temporária (conexão, tempo esgotado, código 4xx) gera nova tentativa com espera crescente
  (1, 5, 15 e 60 minutos); na 5ª falha a mensagem fica `falhou`;
* o corpo do e-mail de recuperação de senha (que leva o link com o token) é apagado depois do envio;
* a auditoria registra cada envio e cada falha sem o corpo da mensagem.
"""

from __future__ import annotations

import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import auditoria
from .config import config
from .modelos import MensagemSaida, Solicitacao, Usuario

ESPERAS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=60))
MAX_TENTATIVAS = len(ESPERAS) + 1
TIPOS_SENSIVEIS = {"recuperacao_senha"}
CORPO_APAGADO = "[conteúdo apagado depois do envio]"
NOMES_STATUS = {"recebida": "recebida", "em_triagem": "em triagem", "em_atendimento": "em atendimento",
                "aguardando_solicitante": "aguardando você", "concluida": "concluída", "indeferida": "indeferida",
                "cancelada": "cancelada"}


def _utc(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def enfileirar(s: Session, *, para: str, assunto: str, corpo: str, tipo: str = "geral",
               solicitacao_id: int | None = None) -> MensagemSaida | None:
    if not para:
        return None
    m = MensagemSaida(para=para, assunto=assunto[:200], corpo=corpo, tipo=tipo, status="pendente", tentativas=0,
                      solicitacao_id=solicitacao_id)
    s.add(m)
    return m


def _link(sol: Solicitacao) -> str:
    return f"{config().url_publica.rstrip('/')}/#/solicitacoes/{sol.id}"


def notificar_tramitacao(s: Session, sol: Solicitacao, de: str, para: str, ator: Usuario, comentario: str | None) -> None:
    """Avisa o solicitante quando a situação muda por ação de outra pessoa."""
    dono = s.get(Usuario, sol.solicitante_id)
    if dono is None or not dono.ativo or dono.id == ator.id:
        return
    corpo = (f"Olá, {dono.nome}.\n\nSua solicitação {sol.protocolo} — {sol.titulo} — passou de "
             f"\"{NOMES_STATUS.get(de, de)}\" para \"{NOMES_STATUS.get(para, para)}\".\n")
    if comentario:
        corpo += f"\nComentário: {comentario.strip()}\n"
    if para == "aguardando_solicitante":
        corpo += "\nPrecisamos de uma informação sua para continuar. Abra a solicitação e responda.\n"
    corpo += f"\nAcompanhe em: {_link(sol)}\n"
    enfileirar(s, para=dono.email, assunto=f"Solicitação {sol.protocolo}: {NOMES_STATUS.get(para, para)}", corpo=corpo,
               tipo="tramitacao", solicitacao_id=sol.id)


def notificar_atribuicao(s: Session, sol: Solicitacao, responsavel: Usuario, ator: Usuario) -> None:
    """Avisa quem recebeu a solicitação, quando foi outra pessoa que atribuiu."""
    if responsavel.id == ator.id or not responsavel.ativo:
        return
    corpo = (f"Olá, {responsavel.nome}.\n\n{ator.nome} atribuiu a você a solicitação {sol.protocolo} — {sol.titulo}.\n"
             f"\nAbra em: {_link(sol)}\n")
    enfileirar(s, para=responsavel.email, assunto=f"Solicitação {sol.protocolo} atribuída a você", corpo=corpo,
               tipo="atribuicao", solicitacao_id=sol.id)


def _mensagem(m: MensagemSaida) -> EmailMessage:
    cfg = config()
    e = EmailMessage()
    e["From"] = cfg.smtp_remetente
    e["To"] = m.para
    e["Subject"] = m.assunto
    e["Date"] = format_datetime(datetime.now(timezone.utc))
    e["Message-ID"] = make_msgid(idstring=f"sd-{m.id}", domain=cfg.smtp_remetente.rsplit("@", 1)[-1] or "localhost")
    e.set_content(m.corpo)
    return e


def _conectar() -> smtplib.SMTP:
    cfg = config()
    if cfg.smtp_seguranca == "ssl":
        cx: smtplib.SMTP = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_porta, timeout=cfg.smtp_timeout)
    else:
        cx = smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=cfg.smtp_timeout)
        if cfg.smtp_seguranca == "starttls":
            cx.starttls()
    if cfg.smtp_usuario:
        cx.login(cfg.smtp_usuario, cfg.smtp_senha)
    return cx


def _definitiva(e: Exception) -> bool:
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return all(500 <= codigo < 600 for codigo, _ in e.recipients.values())
    if isinstance(e, smtplib.SMTPResponseException):
        return 500 <= e.smtp_code < 600
    return False


def _falha(s: Session, m: MensagemSaida, e: Exception, agora: datetime, conexao: bool = False) -> str:
    """`conexao`: o erro foi ao conectar/autenticar (vale para o lote inteiro); nunca é definitivo para a mensagem,
    porque é configuração ou servidor, não o destinatário."""
    m.tentativas = (m.tentativas or 0) + 1
    m.ultimo_erro = f"{type(e).__name__}: {e}"[:500]
    if (_definitiva(e) and not conexao) or m.tentativas >= MAX_TENTATIVAS:
        m.status, m.proxima_tentativa_em = "falhou", None
    else:
        m.proxima_tentativa_em = agora + ESPERAS[m.tentativas - 1]
    auditoria.registrar(s, acao="enviar_email", recurso="mensagem", recurso_id=m.id, resultado="falha",
                        depois={"tipo": m.tipo, "status": m.status, "tentativas": m.tentativas, "erro": m.ultimo_erro})
    return m.status


def pendentes(s: Session, agora: datetime, limite: int) -> list[MensagemSaida]:
    q = (select(MensagemSaida).where(MensagemSaida.status == "pendente",
                                     or_(MensagemSaida.proxima_tentativa_em.is_(None), MensagemSaida.proxima_tentativa_em <= agora))
         .order_by(MensagemSaida.id).limit(limite))
    return list(s.scalars(q))


def enviar_pendentes(s: Session, limite: int = 100, agora: datetime | None = None) -> dict:
    """Envia as mensagens pendentes cuja hora chegou. Devolve as contagens do lote."""
    cfg = config()
    agora = agora or datetime.now(timezone.utc)
    res = {"configurado": cfg.smtp_configurado, "enviadas": 0, "reagendadas": 0, "falharam": 0, "na_fila": 0}
    lote = pendentes(s, agora, limite)
    if not cfg.smtp_configurado:
        res["na_fila"] = len(lote)
        return res
    if not lote:
        return res
    try:
        cx = _conectar()
    except (OSError, smtplib.SMTPException) as e:  # servidor fora do ar: todas do lote voltam para a fila
        for m in lote:
            res["falharam" if _falha(s, m, e, agora, conexao=True) == "falhou" else "reagendadas"] += 1
        s.flush()
        res["erro_conexao"] = f"{type(e).__name__}: {e}"[:300]
        return res
    try:
        for m in lote:
            try:
                cx.send_message(_mensagem(m))
            except (smtplib.SMTPException, OSError) as e:
                res["falharam" if _falha(s, m, e, agora) == "falhou" else "reagendadas"] += 1
                if isinstance(e, smtplib.SMTPServerDisconnected) or not isinstance(e, smtplib.SMTPException):
                    break  # conexão caiu (rede, tempo esgotado): o resto do lote fica para a próxima rodada
                continue
            m.status, m.enviado_em, m.tentativas, m.ultimo_erro = "enviada", agora, (m.tentativas or 0) + 1, None
            m.proxima_tentativa_em = None
            if m.tipo in TIPOS_SENSIVEIS:
                m.corpo = CORPO_APAGADO
            auditoria.registrar(s, acao="enviar_email", recurso="mensagem", recurso_id=m.id,
                                depois={"tipo": m.tipo, "status": "enviada", "tentativas": m.tentativas})
            res["enviadas"] += 1
    finally:
        try:
            cx.quit()
        except (smtplib.SMTPException, OSError):
            pass
    s.flush()
    return res


def situacao(m: MensagemSaida) -> dict:
    """Dados de uma mensagem para a tela do administrador, sem o corpo."""
    return {"id": m.id, "para": m.para, "assunto": m.assunto, "tipo": m.tipo, "status": m.status, "tentativas": m.tentativas,
            "ultimo_erro": m.ultimo_erro, "criado_em": _utc(m.criado_em), "enviado_em": _utc(m.enviado_em),
            "proxima_tentativa_em": _utc(m.proxima_tentativa_em), "solicitacao_id": m.solicitacao_id}
