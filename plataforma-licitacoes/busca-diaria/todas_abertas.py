"""Todas as licitações com proposta aberta no Brasil (PNCP, UF por UF), em formato compacto para o app.

Uso: PYTHONPATH=plataforma-licitacoes/backend python todas_abertas.py SAIDA.json
Cada registro: [controle, órgão, município, UF, modalidade, valor, sigiloso, fim_propostas, objeto, portal, assunto, esfera, inicio_propostas]
"A vir" = já publicada, mas o recebimento de propostas ainda não começou (inicio_propostas no futuro).
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


FONTE = __import__("os").environ.get("FONTE", "search")  # "consulta" = API oficial /consulta (quando a busca do PNCP cai)
ATE = __import__("os").environ.get("CONSULTA_ATE", "2027-12-31")


def de_consulta(x):
    """Registro da API de consulta no mesmo formato da busca (para o resto do sistema não mudar)."""
    o, u = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}
    return {"numero_controle_pncp": x.get("numeroControlePNCP"), "description": x.get("objetoCompra"), "orgao_cnpj": o.get("cnpj"),
            "orgao_nome": o.get("razaoSocial"), "unidade_nome": u.get("nomeUnidade"), "municipio_nome": u.get("municipioNome"),
            "uf": u.get("ufSigla"), "codigo_ibge": u.get("codigoIbge"), "numero_sequencial": str(x.get("sequencialCompra")),
            "ano": str(x.get("anoCompra")), "modalidade_licitacao_nome": x.get("modalidadeNome"), "esfera_id": o.get("esferaId"),
            "data_publicacao_pncp": x.get("dataPublicacaoPncp"), "data_inicio_vigencia": x.get("dataAberturaProposta"),
            "data_fim_vigencia": x.get("dataEncerramentoProposta"), "valor_total_estimado": x.get("valorTotalEstimado"),
            "indicador_orcamento_sigiloso": False, "usuario_nome": x.get("usuarioNome"), "cancelado": False,
            "situacao_nome": x.get("situacaoCompraNome"), "link_sistema_origem": x.get("linkSistemaOrigem")}


def buscar_uf(uf):
    if FONTE == "consulta":
        r = subprocess.run(["pncp", "consulta", "propostas", "--ate", ATE, "--uf", uf, "--all", "--tam", "50", "--ndjson", "-q",
                            "--pausa", "0.3", "--retries", "8", "--timeout", "120"], capture_output=True, text=True, timeout=5400)
        linhas = [de_consulta(json.loads(x)) for x in r.stdout.splitlines() if x.strip()]
        linhas = [d for d in linhas if (d.get("situacao_nome") or "Divulgada").startswith("Divulgada")]
        open(f"{SAIDA}.{uf}.ndjson", "w").write("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in linhas))
        print(uf, len(linhas), "(consulta)", file=sys.stderr, flush=True)
        return linhas
    r = subprocess.run(["pncp", "search", "--tipo", "edital", "--status", "recebendo_proposta", "--uf", uf, "--all", "--limit", "10000",
                        "--ndjson", "-q", "--pausa", "0.2"], capture_output=True, text=True, timeout=3600)
    linhas = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
    open(f"{SAIDA}.{uf}.ndjson", "w").write(r.stdout)  # bruto, para reprocessar sem baixar de novo
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
if len(todos) < 1000:
    sys.exit(f"ERRO: só {len(todos)} abertas vieram do PNCP; nada foi gravado")
reg = []
for c, d in todos.items():
    obj = " ".join((d.get("description") or "").split())
    obj = re.sub(r"^\[[^\]]*\]\s*-?\s*", "", obj)
    reg.append([c, " ".join((d.get("orgao_nome") or "").split()), d.get("municipio_nome") or "", d.get("uf") or "",
                d.get("modalidade_licitacao_nome") or "", round(float(d.get("valor_total_estimado") or 0), 2),
                1 if d.get("indicador_orcamento_sigiloso") else 0, (d.get("data_fim_vigencia") or "")[:16], obj[:220],
                d.get("usuario_nome") or "", assunto(obj), (d.get("esfera_id") or ""), (d.get("data_inicio_vigencia") or "")[:16]])
reg.sort(key=lambda r: r[7])
json.dump({"verificado_em": AGORA.isoformat(timespec="minutes"), "total": len(reg),
           "campos": ["controle", "orgao", "municipio", "uf", "modalidade", "valor", "sigiloso", "fim", "objeto", "portal", "assunto", "esfera", "inicio"],
           "a_vir": sum(1 for r in reg if r[12] > AGORA.isoformat()[:16]),
           "registros": reg}, open(SAIDA, "w"), ensure_ascii=False, separators=(",", ":"))
print(len(reg), "abertas", file=sys.stderr)
