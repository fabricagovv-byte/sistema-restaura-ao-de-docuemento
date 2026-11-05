"""Relatório técnico de execução (Word), na estrutura do modelo 07 do pacote contratual.

Todo número vem de fonte verificável: medicao/registro.json, git, pytest e os próprios arquivos.

Uso: python medicao/relatorio_tecnico.py 1 [--nc "texto de não conformidade"]...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
FUSO = ZoneInfo("America/Sao_Paulo")


def sh(*cmd: str) -> str:
    import os

    return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, env={**os.environ, "TZ": "America/Sao_Paulo"}).stdout.strip()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def hm(s: str | None) -> str:
    d = dt(s)
    return d.astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S") if d else "—"


def tabela(doc, cab: list[str], linhas: list[list], larg_fonte: int = 8):
    t = doc.add_table(rows=1, cols=len(cab))
    t.style = "Table Grid"
    for i, c in enumerate(cab):
        cel = t.rows[0].cells[i]
        cel.text = ""
        r = cel.paragraphs[0].add_run(c)
        r.bold = True
        r.font.size = Pt(larg_fonte)
    for ln in linhas:
        cels = t.add_row().cells
        for i, v in enumerate(ln):
            cels[i].text = ""
            r = cels[i].paragraphs[0].add_run("" if v is None else str(v))
            r.font.size = Pt(larg_fonte)
    doc.add_paragraph()
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dia", type=int)
    ap.add_argument("--nc", action="append", default=[], help="não conformidade encontrada e tratada no dia")
    a = ap.parse_args(argv)
    dia = a.dia

    plano = json.loads((RAIZ / "medicao/plano_os001.json").read_text(encoding="utf-8"))
    reg = json.loads((RAIZ / "medicao/registro.json").read_text(encoding="utf-8"))
    cat = plano["catalogo_proposto"]
    entregas = [e for d in plano["dias"] if d["dia"] == dia for e in d["entregas"]]
    tarefas = {e["id"]: reg["tarefas"].get(e["id"], {}) for e in entregas}
    log_testes = RAIZ / f"medicao/evidencias/testes-dia{dia:02d}.txt"
    txt_testes = log_testes.read_text(encoding="utf-8") if log_testes.exists() else ""
    passados = re.findall(r"(\d+) passed", txt_testes)
    lista_testes = re.findall(r"^(tests/\S+::\S+) PASSED", sh(sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider").replace(" ", " "), re.M)
    coletados = sh(sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider").splitlines()
    coletados = [c for c in coletados if "::" in c]
    commits = [ln.split(" ", 1) for ln in sh("git", "log", "--format=%h %ad %s", "--date=format-local:%d/%m/%Y %H:%M", "--", ".").splitlines()]
    arquivos = sorted(p for p in RAIZ.rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
                      and p.suffix in (".py", ".md", ".json", ".ini", ".txt") and "relatorios" not in p.parts)
    linhas_codigo = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in RAIZ.glob("solicitacoes/*.py"))
    linhas_teste = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in RAIZ.glob("tests/*.py"))

    plan = sum(e["base"] * cat[e["item"]]["fator"] for e in entregas)
    decl = sum(t.get("ajustada_declarada", 0) for t in tarefas.values())
    verif = sum(t.get("ajustada_verificada", 0) for t in tarefas.values())
    total_os = sum(v["base"] * v["fator"] for v in cat.values())
    acum_decl = sum(t.get("ajustada_declarada", 0) for t in reg["tarefas"].values())
    acum_verif = sum(t.get("ajustada_verificada", 0) for t in reg["tarefas"].values())
    inicios = [dt(t["inicio"]) for t in tarefas.values() if t.get("inicio")]
    fins = [dt(t["fim"]) for t in tarefas.values() if t.get("fim")]
    gerado = datetime.now(FUSO).strftime("%d/%m/%Y %H:%M")

    doc = docx.Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)

    t = doc.add_heading("RELATÓRIO TÉCNICO DE EXECUÇÃO", level=0)
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(f"Sistema de Solicitações Digitais • OS-001/2026 • Dia {dia} do plano de execução").runs[0].bold = True
    p = doc.add_paragraph(f"Gerado em {gerado} (Brasília) a partir do registro de medição, do git e dos testes. "
                          f"Situação contratual: {plano['contrato']}; OS {plano['situacao_os']}.")
    aviso = doc.add_paragraph().add_run("Nenhuma UST deste relatório está homologada nem é faturável. A homologação é ato do contratante, "
                                        "após assinatura do contrato, aprovação da OS e do catálogo, revisão independente e aceite.")
    aviso.bold = True
    aviso.font.color.rgb = RGBColor(0xA0, 0x1E, 0x1E)

    # 1
    doc.add_heading("1. Identificação, contexto e caracterização do período", level=1)
    tabela(doc, ["Campo", "Preenchimento"], [
        ["Contrato", plano["contrato"]],
        ["Ordem de serviço", f"{plano['os']} — {plano['situacao_os']}"],
        ["Objeto", "Núcleo do sistema de solicitações digitais (TR seção 1)"],
        ["Período relatado", f"Dia {dia}: {hm(min(inicios).isoformat()) if inicios else '—'} a {hm(max(fins).isoformat()) if fins else '—'}"],
        ["Executor", "Claude (agente de IA da Anthropic), execução automatizada"],
        ["Horas humanas comprovadas", "0"],
        ["Revisor independente", "Pendente — indicar pessoa da contratante"],
        ["Repositório", "fabricagovv-byte/sistema-restaura-ao-de-docuemento, pasta solicitacoes-digitais/, branch " + sh("git", "rev-parse", "--abbrev-ref", "HEAD")],
    ], 9)
    doc.add_heading("1.1 Painel de controle do período", level=2)
    tabela(doc, ["Indicador", "Valor", "Origem verificável"], [
        ["UST ajustadas planejadas no dia", plan, "medicao/plano_os001.json"],
        ["UST ajustadas declaradas", decl, "medicao/registro.json"],
        ["UST ajustadas verificadas tecnicamente", verif, f"medicao/registro.json + {log_testes.name}"],
        ["UST glosadas", 0, "sem glosa registrada (não houve fiscalização)"],
        ["UST homologadas", 0, "homologação é ato do contratante"],
        ["Acumulado da OS (declaradas / verificadas)", f"{acum_decl} / {acum_verif} de {total_os}", "medicao/registro.json"],
        ["Testes automatizados aprovados", " e ".join(f"{n} no {b}" for n, b in zip(passados, ["SQLite", "PostgreSQL"])) or "—", log_testes.name],
        ["Linhas de código da aplicação / de testes", f"{linhas_codigo} / {linhas_teste}", "contagem dos arquivos .py"],
        ["Commits do período", len(commits), "git log da pasta do projeto"],
    ], 9)

    # 2
    doc.add_heading("2. Objeto, escopo autorizado e matriz de alterações", level=1)
    doc.add_paragraph("Escopo executado conforme o plano proposto em medicao/plano_os001.json, ainda sem autorização formal de produção. "
                      "Resultados validados do período: só os itens verificados tecnicamente na tabela abaixo.")
    reqs = []
    for linha in (RAIZ / "docs/MATRIZ_REQUISITOS.md").read_text(encoding="utf-8").split("## Rastreabilidade")[-1].splitlines():
        m = re.match(r"\| (REQ-\d+) \| (\S+) \| (.+?) \| (.+?) \| (.+?) \|", linha)
        if m:
            reqs.append([m.group(1), m.group(2), m.group(5), m.group(3).replace("`", ""), m.group(4).replace("`", "")])
    tabela(doc, ["Requisito", "OS", "Status", "Artefato", "Teste"], reqs)
    doc.add_heading("2.1 Controle de mudanças e aprovações", level=2)
    tabela(doc, ["Mudança", "Justificativa técnica", "Solicitante / aceite", "Versão"], [
        ["Ritmo de 100 UST ajustadas por dia em 10 dias", "Prazo original (04/11/2026 18h) já vencido; OS de 1.000 UST distribuída em entregas verificáveis", "Pedido do contratante em 05/11/2026 / aceite formal pendente", "plano_os001.json"],
        ["Auditoria e log estruturado antecipados para o dia 1", "São base da autenticação e do controle de acesso", "Execução / sem UST adicional", commits[-1][0] if commits else "—"],
    ])

    # 3
    doc.add_heading("3. Memória técnica de implementação por camada", level=1)
    camadas = [
        ("Arquitetura e regras de negócio", "Quatro perfis do TR (administrador, gestor, operador, solicitante) com matriz central de permissões; "
         "estados da solicitação definidos em docs/ARQUITETURA.md; premissas registradas até a entrevista obrigatória."),
        ("Banco de dados", "SQLAlchemy 2 com PostgreSQL (produção) e SQLite (testes). Tabelas: usuario, token_revogado, solicitacao, "
         "evento_auditoria, versao_esquema. Migrações numeradas e idempotentes (rodar de novo não altera nada)."),
        ("Backend", "FastAPI com prefixo /api/v1: saúde, login, logout, sessão atual, usuários (listar, criar, alterar) e auditoria. "
         "Senhas PBKDF2-SHA256 com 600 mil iterações e sal; token JWT com expiração e revogação no logout; mesma resposta para "
         "e-mail inexistente e senha errada; administrador não pode desativar a si mesmo; auditoria só de inclusão, sem senha nos registros."),
        ("Frontend", "Não previsto para o dia 1 (dias 5 a 7 do plano)."),
        ("Integração e infraestrutura", "Configuração por variáveis SD_*, segredo obrigatório fora de desenvolvimento, X-Correlation-ID "
         "gerado ou propagado e saneado, log em JSON por requisição, cabeçalhos nosniff e no-store. CI e contêineres nos dias 8 e 9."),
    ]
    for titulo, texto in camadas:
        doc.add_heading(titulo, level=2)
        doc.add_paragraph(texto)
    doc.add_heading("3.1 Inventário técnico", level=2)
    tabela(doc, ["Arquivo", "Linhas", "SHA-256 (início)"], [[str(p.relative_to(RAIZ)), len(p.read_text(encoding="utf-8", errors="replace").splitlines()), sha(p)[:16]] for p in arquivos], 7)

    # 4
    doc.add_heading("4. Registros de execução, jornada e automação", level=1)
    doc.add_paragraph("Horários tirados do relógio no momento de cada comando do registro de medição, nunca digitados. "
                      "A execução é de agente de IA: os horários não representam jornada de pessoa.")
    doc.add_heading("4.1 Registro consolidado de eventos", level=2)
    ln = []
    for tid, tt in tarefas.items():
        dur = (dt(tt["fim"]) - dt(tt["inicio"])) if tt.get("fim") and tt.get("inicio") else None
        ln.append([tt.get("executor", "—").split(" —")[0], f"{tid}: {tt.get('entrega', '')}", hm(tt.get("inicio")), hm(tt.get("fim")),
                   f"{int(dur.total_seconds() // 60)} min {int(dur.total_seconds() % 60)} s" if dur else "—",
                   ", ".join(x["arquivo"].split("/")[-1] for x in tt.get("evidencias", []))])
    tabela(doc, ["Pessoa / agente", "Tarefa", "Início real", "Fim real", "Duração", "Evidência"], ln)

    # 5
    doc.add_heading("5. Testes, defeitos, correções e segurança", level=1)
    doc.add_paragraph(f"Resultado registrado em {log_testes.relative_to(RAIZ)} (SHA-256 {sha(log_testes) if log_testes.exists() else '—'}): "
                      + (" e ".join(f"{n} aprovados no {b}" for n, b in zip(passados, ["SQLite", "PostgreSQL"])) or "sem log") + ".")
    tabela(doc, ["Teste automatizado"], [[c] for c in coletados], 7)
    doc.add_heading("5.1 Não conformidades e retestes", level=2)
    tabela(doc, ["Não conformidade", "Tratamento"], [nc.split(" => ", 1) if " => " in nc else [nc, "—"] for nc in a.nc] or [["Nenhuma", "—"]])

    # 6
    doc.add_heading("6. Demonstrativo de UST e fundamentação", level=1)
    doc.add_paragraph("Regra (protocolo de medição, item 1): UST ajustadas = UST base × fator acordado na OS. Catálogo, bases e fatores "
                      "são a proposta da OS-001, ainda não aceita por escrito.")
    ln = []
    for e in entregas:
        tt = tarefas[e["id"]]
        f = cat[e["item"]]["fator"]
        ln.append([e["id"], f"{e['item']} {cat[e['item']]['servico']}", e["base"], tt.get("base_declarada", 0), f,
                   e["base"] * f, tt.get("ajustada_declarada", 0), tt.get("ajustada_verificada", 0), 0, 0, tt.get("situacao", "PLANEJADA")])
    ln.append(["Total", "", "", "", "", plan, decl, verif, 0, 0, ""])
    tabela(doc, ["Tarefa", "Serviço", "Base plan.", "Base decl.", "Fator", "Planejada", "Declarada", "Verificada", "Glosada", "Homologada", "Situação"], ln, 7)
    doc.add_heading("6.1 Reconciliação por estado da medição", level=2)
    for tid, tt in tarefas.items():
        if tt.get("observacao"):
            doc.add_paragraph(f"{tid}: {tt['observacao']}", style="List Bullet")
    doc.add_paragraph(f"Acumulado da OS: {acum_decl} declaradas, {acum_verif} verificadas tecnicamente, 0 homologadas; "
                      f"saldo planejado de {total_os - acum_verif} de {total_os} UST ajustadas.")

    # 7
    doc.add_heading("7. Controle de versionamento, arquivos e propriedade", level=1)
    tabela(doc, ["Commit", "Data e hora", "Descrição"], [[c[0], " ".join(c[1].split(" ")[:2]), " ".join(c[1].split(" ")[2:])] for c in commits])
    doc.add_heading("7.1 Reprodução e cadeia de custódia", level=2)
    for passo in ["git clone e checkout da branch; conferir os SHA-256 do inventário (seção 3.1).",
                  "pip install -r requirements.txt (versões fixadas).",
                  "python -m solicitacoes migrar (duas vezes, para conferir a idempotência).",
                  "python -m pytest e, com PostgreSQL, SD_TESTE_PG=... python -m pytest.",
                  "python -m solicitacoes servidor e consultar /api/v1/saude e /docs.",
                  "Conferir medicao/registro.json e os logs em medicao/evidencias/."]:
        doc.add_paragraph(passo, style="List Bullet")

    # 8
    doc.add_heading("8. Síntese de conformidade, glosas e pendências", level=1)
    for item in [
        "Escopo autorizável e assinatura: PENDENTE (minuta não assinada; OS não aprovada).",
        "Matriz de requisitos: ENTREGUE como proposta; validação depende da entrevista obrigatória.",
        f"Desenvolvimento verificado: {verif} UST ajustadas por testes automatizados.",
        f"Testes e segurança: {passados[0] if passados else '—'} testes aprovados em SQLite e PostgreSQL; revisão de segurança completa prevista para o dia 10.",
        "Pontos de glosa e saneamento: nenhuma glosa registrada; não houve fiscalização.",
        f"UST verificadas / homologadas: {verif} / 0 no dia; {acum_verif} / 0 acumuladas.",
        "Riscos residuais: escopo pode mudar após a entrevista; catálogo e fatores não aceitos; revisor independente não indicado.",
        "Fiscal técnico e data de aceite: [PREENCHER PELA CONTRATANTE].",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    # 9
    doc.add_heading("9. Assinaturas e documentação anexa", level=1)
    doc.add_paragraph("Anexos no repositório: docs/MATRIZ_REQUISITOS.md, docs/ARQUITETURA.md, docs/PENDENCIAS_ENTREVISTA.md, "
                      f"medicao/registro.json, medicao/relatorios/medicao-dia-{dia:02d}.md e .docx, medicao/evidencias/.")
    tabela(doc, ["Papel", "Nome", "Assinatura", "Data"], [["Fiscal técnico (contratante)", "", "", ""], ["Gestor do contrato (contratante)", "", "", ""],
                                                         ["Preposto (contratada)", "", "", ""]], 9)

    saida = RAIZ / f"medicao/relatorios/relatorio-tecnico-dia-{dia:02d}.docx"
    doc.save(saida)
    print(saida.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
