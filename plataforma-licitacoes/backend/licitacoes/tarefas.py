"""Tarefas de fundo (Celery + Redis) e o ciclo de monitoramento.

Agenda (Celery beat):
* a cada `intervalo_monitoramento_min` (15 min): PNCP publicados e alterados hoje, alertas;
* a cada 6 h: propostas abertas no PNCP (pega o que a listagem por data não trouxe);
* todo dia 06:10: PNCP dos últimos 3 dias, Compras.gov, diários municipais, espelhos e conferência
  individual dos editais que vencem em até 3 dias.
O ritmo respeita os limites das fontes (4 s entre chamadas no PNCP), então um ciclo pode durar mais
que 15 min em dias de muito volume; o Celery não sobrepõe execuções da mesma tarefa (lock no Redis).
Sem Redis, `python -m licitacoes.cli agendador` roda o mesmo ciclo num processo só.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import timedelta

from .config import config

log = logging.getLogger("licitacoes.tarefas")


def ciclo_monitoramento() -> dict:
    from . import alertas, coleta
    from .db import sessao

    with sessao() as s:
        r = coleta.sincronizar_pncp(s, modo="monitoramento", dias=1)
        res = {"pncp": {"status": r.status, "lidos": r.lidos, "novos": r.novos, "atualizados": r.atualizados}}
        res["alertas"] = alertas.avaliar(s)
    return res


def ciclo_propostas() -> dict:
    from . import coleta
    from .db import sessao

    with sessao() as s:
        r = coleta.sincronizar_pncp(s, modo="propostas")
        return {"status": r.status, "lidos": r.lidos, "novos": r.novos}


def ciclo_diario() -> dict:
    from . import alertas, coleta
    from .db import sessao
    from .taxonomia import PADRAO

    res = {}
    with sessao() as s:
        r = coleta.sincronizar_pncp(s, modo="diario", dias=3)
        res["pncp"] = r.status
        res["conferencia"] = coleta.conferir_individual(s)
        res["comprasgov"] = coleta.sincronizar_comprasgov(s, dias=1).status
        termos = sorted({c.nome for c in PADRAO if c.codigo in config().prioritarias})
        res["querido_diario"] = coleta.sincronizar_querido_diario(s, termos, dias=2).status
        res["espelhos"] = [x.status for x in coleta.sincronizar_espelhos(s)]
        if config().transparencia_chave:
            res["transparencia"] = coleta.sincronizar_transparencia(s, dias=2).status
        res["alertas"] = alertas.avaliar(s)
    return res


def preparar_edital(licitacao_id: int, analisar: bool = True) -> dict:
    """Itens + documentos + download + análise com IA de um edital."""
    from . import analise, coleta, documentos
    from .db import sessao
    from .modelos import Licitacao

    with sessao() as s:
        lic = s.get(Licitacao, licitacao_id)
        if lic is None:
            return {"erro": "não encontrado"}
        from .conectores.base import ErroFonte

        try:
            res = {"detalhe": coleta.detalhar(s, lic)}
        except ErroFonte as e:  # fonte fora do ar: segue com o que já está guardado
            s.rollback()
            res = {"detalhe": {"erro": f"{type(e).__name__}: {e}"}}
        res["download"] = documentos.baixar_todos(s, lic)
        if analisar:
            an = analise.analisar(s, lic)
            res["analise"] = {"id": an.id, "status": an.status, "erro": an.erro}
        return res


# ------------------------------------------------------------------ Celery (opcional)
try:
    from celery import Celery
    from celery.schedules import crontab

    app = Celery("licitacoes", broker=config().redis_url, backend=config().redis_url)
    app.conf.timezone = "America/Sao_Paulo"
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1

    @contextmanager
    def _trava(nome: str, segundos: int):
        import redis

        r = redis.Redis.from_url(config().redis_url)
        ok = r.set(f"trava:{nome}", "1", nx=True, ex=segundos)
        try:
            yield bool(ok)
        finally:
            if ok:
                r.delete(f"trava:{nome}")

    @app.task(name="monitoramento")
    def t_monitoramento():
        with _trava("monitoramento", 3600) as ok:
            return ciclo_monitoramento() if ok else {"ignorado": "ciclo anterior ainda em execução"}

    @app.task(name="propostas")
    def t_propostas():
        with _trava("propostas", 4 * 3600) as ok:
            return ciclo_propostas() if ok else {"ignorado": "em execução"}

    @app.task(name="diario")
    def t_diario():
        with _trava("diario", 8 * 3600) as ok:
            return ciclo_diario() if ok else {"ignorado": "em execução"}

    @app.task(name="preparar_edital")
    def t_preparar(licitacao_id: int, analisar: bool = True):
        return preparar_edital(licitacao_id, analisar)

    app.conf.beat_schedule = {
        "monitoramento": {"task": "monitoramento", "schedule": timedelta(minutes=config().intervalo_monitoramento_min)},
        "propostas": {"task": "propostas", "schedule": timedelta(hours=6)},
        "diario": {"task": "diario", "schedule": crontab(hour=6, minute=10)},
    }
except ImportError:  # pragma: no cover
    app = None


def disparar(nome: str, *args) -> dict:
    """Manda para o Celery ou executa na hora, conforme LIC_EXECUCAO."""
    if config().execucao == "celery" and app is not None:
        tarefa = {"preparar_edital": "preparar_edital", "monitoramento": "monitoramento", "diario": "diario",
                  "propostas": "propostas"}[nome]
        r = app.send_task(tarefa, args=list(args))
        return {"enfileirado": True, "tarefa_id": r.id}
    funcs = {"preparar_edital": preparar_edital, "monitoramento": ciclo_monitoramento, "diario": ciclo_diario,
             "propostas": ciclo_propostas}
    return {"enfileirado": False, "resultado": funcs[nome](*args)}


def agendador_simples() -> None:  # pragma: no cover - laço infinito
    ultimo_diario = None
    ultimo_propostas = 0.0
    while True:
        inicio = time.monotonic()
        try:
            log.info("monitoramento: %s", ciclo_monitoramento())
            if time.monotonic() - ultimo_propostas > 6 * 3600:
                log.info("propostas: %s", ciclo_propostas())
                ultimo_propostas = time.monotonic()
            hoje = time.strftime("%Y-%m-%d")
            if ultimo_diario != hoje and time.localtime().tm_hour >= 6:
                log.info("diário: %s", ciclo_diario())
                ultimo_diario = hoje
        except Exception:
            log.exception("ciclo falhou")
        espera = config().intervalo_monitoramento_min * 60 - (time.monotonic() - inicio)
        time.sleep(max(30, espera))
