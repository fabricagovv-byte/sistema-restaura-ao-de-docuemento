"""Monitoramentos e alertas.

Eventos: novo edital, alto valor, prazo próximo, retificação (prazo, valor, objeto ou documento novo),
suspensão e reabertura. Cada alerta tem uma chave única (monitoramento + edital + evento + detalhe),
então o mesmo aviso nunca sai duas vezes. Canais: painel (sempre), e-mail (SMTP), WhatsApp Business
Cloud API e webhook (serve para push via serviços como ntfy, OneSignal ou FCM). Canal sem
configuração fica registrado como "nao_configurado" — nada é dado como enviado sem ter sido.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .busca import Filtros, montar_consulta
from .config import config
from .modelos import Alerta, HistoricoAlteracao, Licitacao, Monitoramento, Usuario, agora

log = logging.getLogger("licitacoes.alertas")


def _brl(v) -> str:
    if v is None:
        return "valor não informado"
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _mensagem(tipo: str, lic: Licitacao, detalhe: str = "") -> str:
    titulos = {"novo": "Novo edital", "alto_valor": "Licitação de alto valor", "prazo_proximo": "Prazo próximo",
               "retificacao": "Edital retificado", "suspensa": "Licitação suspensa", "reaberta": "Licitação reaberta",
               "categoria": "Edital na sua categoria"}
    prazo = lic.data_encerramento.strftime("%d/%m/%Y %H:%M") if lic.data_encerramento else "sem data"
    return (f"{titulos.get(tipo, tipo)}: {lic.orgao_nome or ''} ({lic.uf or ''})\n{lic.objeto[:280]}\n"
            f"Valor: {_brl(lic.valor_estimado)} · Propostas até {prazo}"
            + (f"\n{detalhe}" if detalhe else "") + f"\n{lic.link_pncp or lic.link_origem or ''}")


def _filtros_do_monitoramento(m: Monitoramento) -> Filtros:
    return Filtros(q=", ".join(m.termos) if m.termos else None, ufs=m.ufs or [], modalidades=m.modalidades or [],
                   categorias=m.categorias or [], valor_min=m.valor_min, valor_max=m.valor_max,
                   incluir_sem_valor=True, situacao="todas", incluir_duplicadas=False)


def eventos_do_monitoramento(s: Session, m: Monitoramento, desde: datetime) -> list[tuple[str, Licitacao, str]]:
    cfg = config()
    a = agora()
    q = s.query(Licitacao)
    if m.licitacao_id:
        q = q.filter(Licitacao.id == m.licitacao_id)
    else:
        cond, _ = montar_consulta(_filtros_do_monitoramento(m))
        if cond is not None:
            q = q.filter(cond)
    q = q.filter(Licitacao.excluida.is_(False))
    eventos = []
    ev = set(m.eventos or [])
    # novos e alto valor
    if ev & {"novo", "alto_valor", "categoria"} and not m.licitacao_id:
        for lic in q.filter(Licitacao.criado_em >= desde).all():
            if lic.data_encerramento and lic.data_encerramento < a:
                continue
            if "novo" in ev or "categoria" in ev:
                eventos.append(("novo", lic, ""))
            if "alto_valor" in ev and lic.valor_estimado and float(lic.valor_estimado) >= cfg.valor_alto:
                eventos.append(("alto_valor", lic, ""))
    # prazo próximo (uma vez por edital)
    if "prazo_proximo" in ev:
        lim = a + timedelta(hours=cfg.horas_prazo_proximo)
        for lic in q.filter(Licitacao.data_encerramento.between(a, lim)).all():
            eventos.append(("prazo_proximo", lic, f"encerra em {lic.data_encerramento:%d/%m %H:%M}"))
    # mudanças registradas no histórico
    ids = [x.id for x in q.with_entities(Licitacao.id).all()]
    if ids and ev & {"retificacao", "suspensa", "reaberta"}:
        hist = s.query(HistoricoAlteracao).filter(HistoricoAlteracao.licitacao_id.in_(ids),
                                                   HistoricoAlteracao.em >= desde).all()
        por_id = {lic.id: lic for lic in q.filter(Licitacao.id.in_({h.licitacao_id for h in hist})).all()} if hist else {}
        for h in hist:
            lic = por_id.get(h.licitacao_id)
            if lic is None:
                continue
            if h.evento == "situacao":
                novo = (h.depois or "").lower()
                antigo = (h.antes or "").lower()
                if "suspens" in novo and "suspensa" in ev:
                    eventos.append(("suspensa", lic, f"situação: {h.antes} → {h.depois}"))
                elif "suspens" in antigo and "reaberta" in ev:
                    eventos.append(("reaberta", lic, f"situação: {h.antes} → {h.depois}"))
            elif h.evento in ("prazo", "valor", "retificacao", "documento") and "retificacao" in ev:
                rot = {"data_encerramento": "prazo", "data_abertura": "abertura", "valor_estimado": "valor",
                       "objeto": "objeto", "documento": "documento novo"}.get(h.campo, h.campo)
                eventos.append(("retificacao", lic, f"{rot}: {h.antes or '—'} → {h.depois}"))
    return eventos


def avaliar(s: Session, desde: datetime | None = None, enviar: bool = True) -> dict:
    res = {"monitoramentos": 0, "alertas_novos": 0, "repetidos_ignorados": 0, "entregas": {}}
    for m in s.query(Monitoramento).filter_by(ativo=True).all():
        res["monitoramentos"] += 1
        inicio = desde or m.ultima_avaliacao or (agora() - timedelta(days=1))
        for tipo, lic, detalhe in eventos_do_monitoramento(s, m, inicio):
            chave = f"{m.id}:{lic.id}:{tipo}:{detalhe}"[:200]
            if s.query(Alerta.id).filter_by(chave_dedupe=chave).first():
                res["repetidos_ignorados"] += 1
                continue
            al = Alerta(monitoramento_id=m.id, licitacao_id=lic.id, tipo=tipo, chave_dedupe=chave,
                        mensagem=_mensagem(tipo, lic, detalhe), entrega={"painel": "ok"})
            s.add(al)
            try:
                s.flush()
            except IntegrityError:  # outra execução criou o mesmo alerta ao mesmo tempo
                s.rollback()
                res["repetidos_ignorados"] += 1
                continue
            res["alertas_novos"] += 1
            if enviar:
                al.entrega = entregar(s, m, al)
                for canal, st in al.entrega.items():
                    res["entregas"][f"{canal}:{st}"] = res["entregas"].get(f"{canal}:{st}", 0) + 1
        m.ultima_avaliacao = agora()
        s.commit()
    return res


# ------------------------------------------------------------------ canais
def entregar(s: Session, m: Monitoramento, al: Alerta) -> dict:
    canais = m.canais or {}
    usuario = s.get(Usuario, m.usuario_id) if m.usuario_id else None
    st = {"painel": "ok"}
    if canais.get("email"):
        destino = canais.get("email") if isinstance(canais.get("email"), str) else (usuario.email if usuario else None)
        st["email"] = enviar_email(destino, f"[Licitações] {al.mensagem.splitlines()[0][:120]}", al.mensagem)
    if canais.get("whatsapp"):
        tel = canais.get("whatsapp") if isinstance(canais.get("whatsapp"), str) else (usuario.telefone_whatsapp if usuario else None)
        st["whatsapp"] = enviar_whatsapp(tel, al.mensagem)
    if canais.get("webhook"):
        st["webhook"] = enviar_webhook(canais["webhook"], {"tipo": al.tipo, "mensagem": al.mensagem,
                                                          "licitacao_id": al.licitacao_id})
    return st


def enviar_email(destino: str | None, assunto: str, corpo: str) -> str:
    cfg = config()
    if not (cfg.smtp_host and cfg.smtp_remetente and destino):
        return "nao_configurado"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg.smtp_remetente, destino, assunto
    msg.set_content(corpo)
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=30) as smtp:
            smtp.starttls()
            if cfg.smtp_usuario:
                smtp.login(cfg.smtp_usuario, cfg.smtp_senha or "")
            smtp.send_message(msg)
        return "ok"
    except Exception as e:
        log.warning("e-mail falhou: %s", e)
        return f"erro: {type(e).__name__}"


def enviar_whatsapp(telefone: str | None, texto: str) -> str:
    """WhatsApp Business Cloud API. Fora da janela de 24 h só templates aprovados são entregues."""
    cfg = config()
    if not (cfg.whatsapp_token and cfg.whatsapp_phone_id and telefone):
        return "nao_configurado"
    url = f"https://graph.facebook.com/{cfg.whatsapp_versao_api}/{cfg.whatsapp_phone_id}/messages"
    if cfg.whatsapp_template:
        corpo = {"messaging_product": "whatsapp", "to": telefone, "type": "template",
                 "template": {"name": cfg.whatsapp_template, "language": {"code": "pt_BR"},
                              "components": [{"type": "body", "parameters": [{"type": "text", "text": texto[:1000]}]}]}}
    else:
        corpo = {"messaging_product": "whatsapp", "to": telefone, "type": "text", "text": {"body": texto[:4000]}}
    try:
        r = httpx.post(url, json=corpo, headers={"Authorization": f"Bearer {cfg.whatsapp_token}"}, timeout=30)
        return "ok" if r.status_code < 300 else f"erro: HTTP {r.status_code}"
    except httpx.HTTPError as e:
        return f"erro: {type(e).__name__}"


def enviar_webhook(url: str, dados: dict) -> str:
    try:
        r = httpx.post(url, json=dados, timeout=20)
        return "ok" if r.status_code < 300 else f"erro: HTTP {r.status_code}"
    except httpx.HTTPError as e:
        return f"erro: {type(e).__name__}"
