"""Todas as licitações com proposta aberta no Brasil (PNCP, UF por UF), em formato compacto para o app.

Uso: PYTHONPATH=plataforma-licitacoes/backend python todas_abertas.py SAIDA.json
Cada registro: [controle, órgão, município, UF, modalidade, valor, sigiloso, fim_propostas, objeto, portal, assunto, esfera]
Assunto por palavras do objeto (TI pela taxonomia da plataforma). Valor = estimativa oficial (0 quando sigiloso ou não informado).
"""
import json, re, subprocess, sys, unicodedata, concurrent.futures as cf
from datetime import datetime, timedelta, timezone

from licitacoes.taxonomia import classificar

SAIDA = sys.argv[1]
AGORA = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()


def norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def buscar_uf(uf):
    r = subprocess.run(["pncp", "search", "--tipo", "edital", "--status", "recebendo_proposta", "--uf", uf, "--all", "--limit", "10000",
                        "--ndjson", "-q", "--pausa", "0.2"], capture_output=True, text=True, timeout=3600)
    linhas = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
    print(uf, len(linhas), file=sys.stderr, flush=True)
    return linhas


ASSUNTOS = [
    ("Gestão documental", r"digitaliza|indexa|gestao documental|arquivist|\bged\b|microfilm|acervo documental|guarda de documentos"),
    ("Obras e engenharia", r"\bobras?\b|pavimenta|reforma|construcao|engenharia|drenagem|recapeamento|edificacao|ponte"),
    ("Saúde", r"medicament|hospitalar|saude|odontolog|laborator|exames|clinic|enfermagem|insumos medic|ortese|protese|ambulancia"),
    ("Alimentação", r"genero(s)? aliment|merenda|alimentacao|refeic|marmit|lanche|cesta basica|hortifruti|carne|panificacao"),
    ("Veículos e combustível", r"veiculo|combustivel|pneu|pecas automotiv|locacao de (veiculo|caminhao|maquina)|frota|onibus|motocicleta"),
    ("Material de construção", r"materia(l|is) de construcao|cimento|areia|brita|tijol|ferragen|materia(l|is) (hidraulic|eletric)"),
    ("Gráfica e expediente", r"grafic|impress|expediente|papelaria|banner|placa|adesiv|toner"),
    ("Limpeza, vigilância e apoio", r"limpeza|conservacao|vigilancia|portaria|recepcao|copeiragem|apoio administrativo|mao de obra"),
    ("Educação e cultura", r"escolar|didatic|pedagogic|uniforme|evento|show|cultural|esporte|brinquedo|playground"),
    ("Equipamentos e mobiliário", r"equipamento|mobiliario|moveis|eletrodomest|ar condicionado|climatiza"),
]


def assunto(obj):
    n = norm(obj)[:300]
    if classificar(obj[:300]) and not re.search(r"\bobras?\b|pavimenta|medicament|genero(s)? aliment|combustivel|veiculo", n):
        return "Tecnologia (TI)"
    for nome, rx in ASSUNTOS:
        if re.search(rx, n):
            return nome
    return "Outros"


todos = {}
with cf.ThreadPoolExecutor(4) as ex:
    for linhas in ex.map(buscar_uf, UFS):
        for d in linhas:
            c = d.get("numero_controle_pncp")
            if c and (d.get("data_fim_vigencia") or "") > AGORA.isoformat() and not d.get("cancelado"):
                todos[c] = d
reg = []
for c, d in todos.items():
    obj = " ".join((d.get("description") or "").split())
    obj = re.sub(r"^\[[^\]]*\]\s*-?\s*", "", obj)
    reg.append([c, " ".join((d.get("orgao_nome") or "").split()), d.get("municipio_nome") or "", d.get("uf") or "",
                d.get("modalidade_licitacao_nome") or "", round(float(d.get("valor_total_estimado") or 0), 2),
                1 if d.get("indicador_orcamento_sigiloso") else 0, (d.get("data_fim_vigencia") or "")[:16], obj[:220],
                d.get("usuario_nome") or "", assunto(obj), (d.get("esfera_id") or "")])
reg.sort(key=lambda r: r[7])
json.dump({"verificado_em": AGORA.isoformat(timespec="minutes"), "total": len(reg),
           "campos": ["controle", "orgao", "municipio", "uf", "modalidade", "valor", "sigiloso", "fim", "objeto", "portal", "assunto", "esfera"],
           "registros": reg}, open(SAIDA, "w"), ensure_ascii=False, separators=(",", ":"))
print(len(reg), "abertas", file=sys.stderr)
