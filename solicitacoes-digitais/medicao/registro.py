"""Registro de medição da OS-001 (UST), conforme o protocolo de medição da minuta DG-CONT-001.

Etapas: PLANEJADA -> EM_EXECUCAO -> DECLARADA (entregue com evidência) -> VERIFICADA_TECNICAMENTE
(testes automáticos com log e hash) -> HOMOLOGADA (somente pelo contratante; este programa nunca homologa).

Regras aplicadas aqui:
* horários de início e fim são os do relógio no momento do comando, nunca digitados;
* evidência sem arquivo existente e hash SHA-256 é recusada;
* o executor é o agente de IA que fez o trabalho; nenhuma UST vai para nome ou CPF de pessoa;
* horas humanas comprovadas ficam em zero até alguém registrar participação real.

Uso:
  python medicao/registro.py iniciar D1-A
  python medicao/registro.py concluir D1-A --evidencia docs/MATRIZ_REQUISITOS.md --evidencia ...
  python medicao/registro.py verificar D1-B --log medicao/evidencias/testes-dia1.txt
  python medicao/registro.py relatorio 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
PLANO = RAIZ / "medicao" / "plano_os001.json"
REGISTRO = RAIZ / "medicao" / "registro.json"
FUSO = ZoneInfo("America/Sao_Paulo")
EXECUTOR = "Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas"


def agora() -> str:
    return datetime.now(FUSO).isoformat(timespec="seconds")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def commit_atual() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def carregar() -> tuple[dict, dict]:
    plano = json.loads(PLANO.read_text(encoding="utf-8"))
    reg = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else {"tarefas": {}}
    return plano, reg


def salvar(reg: dict) -> None:
    REGISTRO.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def entrega(plano: dict, tid: str) -> tuple[int, dict]:
    for d in plano["dias"]:
        for e in d["entregas"]:
            if e["id"] == tid:
                return d["dia"], e
    sys.exit(f"tarefa {tid} não existe no plano")


def ajustada(plano: dict, e: dict) -> int:
    return e["base"] * plano["catalogo_proposto"][e["item"]]["fator"]


def cmd_iniciar(a, plano, reg):
    dia, e = entrega(plano, a.tarefa)
    t = reg["tarefas"].setdefault(a.tarefa, {})
    if t.get("inicio"):
        sys.exit(f"{a.tarefa} já iniciada em {t['inicio']}")
    t.update({"dia": dia, "item": e["item"], "entrega": e["entrega"], "base_planejada": e["base"],
              "ajustada_planejada": ajustada(plano, e), "executor": EXECUTOR, "inicio": agora(),
              "situacao": "EM_EXECUCAO", "horas_humanas_comprovadas": 0})
    salvar(reg)
    print(f"{a.tarefa} iniciada em {t['inicio']}")


def evidencias(caminhos: list[str]) -> list[dict]:
    out = []
    for c in caminhos:
        p = (RAIZ / c).resolve()
        if not p.is_file():
            sys.exit(f"evidência inexistente: {c}")
        out.append({"arquivo": str(p.relative_to(RAIZ)), "sha256": sha256(p), "bytes": p.stat().st_size})
    return out


def cmd_concluir(a, plano, reg):
    t = reg["tarefas"].get(a.tarefa)
    if not t or not t.get("inicio"):
        sys.exit(f"{a.tarefa} não foi iniciada")
    if not a.evidencia:
        sys.exit("concluir exige ao menos uma evidência (--evidencia)")
    base = a.base if a.base is not None else t["base_planejada"]
    if base > t["base_planejada"]:
        sys.exit("base declarada não pode passar da planejada para a entrega")
    fator = plano["catalogo_proposto"][t["item"]]["fator"]
    t.update({"fim": agora(), "evidencias": evidencias(a.evidencia), "commit_base": commit_atual(),
              "base_declarada": base, "ajustada_declarada": base * fator, "situacao": "DECLARADA",
              "observacao": a.obs or t.get("observacao")})
    salvar(reg)
    print(f"{a.tarefa} declarada: {base} UST base x {fator} = {base * fator} ajustadas ({t['fim']})")


def cmd_verificar(a, plano, reg):
    t = reg["tarefas"].get(a.tarefa)
    if not t or t.get("situacao") not in ("DECLARADA", "VERIFICADA_TECNICAMENTE"):
        sys.exit(f"{a.tarefa} precisa estar declarada")
    log = (RAIZ / a.log).resolve()
    if not log.is_file():
        sys.exit("log de testes inexistente")
    texto = log.read_text(encoding="utf-8", errors="replace")
    if " failed" in texto or " error" in texto.lower().split("\n")[-2:][0] or "passed" not in texto:
        sys.exit("o log não mostra testes aprovados; a tarefa continua só declarada")
    t.update({"verificacao": {"tipo": "testes automatizados (verificação técnica interna, não é aceite)",
                              "log": str(log.relative_to(RAIZ)), "sha256": sha256(log), "em": agora()},
              "ajustada_verificada": t["ajustada_declarada"], "situacao": "VERIFICADA_TECNICAMENTE",
              "revisor_independente": "PENDENTE — indicar pessoa da contratante"})
    salvar(reg)
    print(f"{a.tarefa} verificada tecnicamente com {log.name}")


def cmd_relatorio(a, plano, reg):
    dia = a.dia
    entregas = [e for d in plano["dias"] if d["dia"] == dia for e in d["entregas"]]
    linhas, tot = [], {"plan": 0, "decl": 0, "verif": 0, "glosa": 0, "homol": 0}
    for e in entregas:
        t = reg["tarefas"].get(e["id"], {})
        plan = ajustada(plano, e)
        decl = t.get("ajustada_declarada", 0)
        verif = t.get("ajustada_verificada", 0)
        glosa = t.get("ajustada_glosada", 0)
        tot["plan"] += plan; tot["decl"] += decl; tot["verif"] += verif; tot["glosa"] += glosa
        ev = "<br>".join(f"`{x['arquivo']}` ({x['sha256'][:12]}…)" for x in t.get("evidencias", [])) or "—"
        linhas.append(f"| {e['id']} | {e['item']} {plano['catalogo_proposto'][e['item']]['servico']} | {e['entrega']} | {plan} | {decl} | "
                      f"{verif} | {glosa} | 0 | {t.get('inicio', '—')} | {t.get('fim', '—')} | {t.get('situacao', 'PLANEJADA')} | {ev} |")
    acum = {"decl": 0, "verif": 0}
    for t in reg["tarefas"].values():
        acum["decl"] += t.get("ajustada_declarada", 0); acum["verif"] += t.get("ajustada_verificada", 0)
    total_os = sum(v["base"] * v["fator"] for v in plano["catalogo_proposto"].values())
    md = [f"# Medição do dia {dia} — OS-001/2026", "",
          f"Gerado em {agora()}. **Situação contratual:** {plano['contrato']}; OS {plano['situacao_os']}. "
          "Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.", "",
          f"Executor de todas as tarefas: {EXECUTOR}. Horas humanas comprovadas: **0**.", "",
          "| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |",
          "|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|", *linhas,
          f"| **Total do dia** | | | **{tot['plan']}** | **{tot['decl']}** | **{tot['verif']}** | **{tot['glosa']}** | **0** | | | | |", "",
          f"**Acumulado da OS:** declaradas {acum['decl']} · verificadas tecnicamente {acum['verif']} · homologadas 0 · "
          f"saldo planejado {total_os - acum['verif']} de {total_os} UST ajustadas.", ""]
    for t in [reg["tarefas"].get(e["id"], {}) for e in entregas]:
        if t.get("verificacao"):
            v = t["verificacao"]
            md.append(f"* Verificação técnica: `{v['log']}` (SHA-256 {v['sha256']}), {v['em']}. Revisor independente: {t.get('revisor_independente')}.")
        if t.get("commit_base"):
            md.append(f"* Commit de referência na conclusão: `{t['commit_base']}`.")
        if t.get("observacao"):
            md.append(f"* Observação: {t['observacao']}")
    saida = RAIZ / "medicao" / "relatorios" / f"medicao-dia-{dia:02d}.md"
    saida.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"relatório: {saida.relative_to(RAIZ)} — planejadas {tot['plan']}, declaradas {tot['decl']}, verificadas {tot['verif']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("iniciar"); s.add_argument("tarefa")
    s = sub.add_parser("concluir"); s.add_argument("tarefa"); s.add_argument("--evidencia", action="append")
    s.add_argument("--base", type=int, help="UST base efetivamente entregues, se menor que a planejada"); s.add_argument("--obs")
    s = sub.add_parser("verificar"); s.add_argument("tarefa"); s.add_argument("--log", required=True)
    s = sub.add_parser("relatorio"); s.add_argument("dia", type=int)
    a = ap.parse_args(argv)
    plano, reg = carregar()
    {"iniciar": cmd_iniciar, "concluir": cmd_concluir, "verificar": cmd_verificar, "relatorio": cmd_relatorio}[a.cmd](a, plano, reg)


if __name__ == "__main__":
    main()
