"""Para cada contratação prevista no PCA (2026 ainda por fazer + 2027 do 1º trimestre), procura no PNCP a publicação mais recente
do mesmo órgão sobre o mesmo objeto. Sem publicação: devolve o link oficial do PCA (CSV da API do PNCP)."""
import json, re, subprocess, sys, unicodedata, concurrent.futures as cf
from datetime import date

DIR = sys.argv[1]
SAIDA = sys.argv[2]
NUCLEO = {"UST/PF/horas", "Fábrica/desenvolvimento", "Sustentação/manutenção de sistemas", "Digitalização/gestão documental", "EAD"}
HOJE = date(2026, 11, 21)
LIXO = re.compile(r"hipoclorito|pneu|aro:|multivitamin|desfibrilador|raio-x|odontolog|artroscopia|bobinas", re.I)


def norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def dt(s):
    try:
        d, m, a = (s or "").split("/")
        return date(int(a), int(m), int(d))
    except ValueError:
        return None


NUC_RX = re.compile(r"\bust\b|unidade de servico tecn|pontos? de funcao|fabrica de (software|teste|metrica)|desenvolvimento (de|e) (software|sistema|aplica|solu)|sustentacao|manutencao (evolutiva|corretiva|adaptativa|de (software|sistema))|digitaliza|arquivist|gestao documental|tratamento documental|\bged\b|ensino a distancia|educacao a distancia|\bead\b|ambiente virtual de aprendizagem|moodle")
cands = []
for ano, fim in (("2026", None), ("2027", date(2027, 3, 31))):
    for e in json.load(open(f"{DIR}/pca_{ano}_tic.json"))["futuras"]:
        d = dt(e["data"])
        if not (set(e["temas"]) & NUCLEO) or e["valor"] < 1e6 or e["valor"] > 1e9 or not d:
            continue
        if ano == "2026" and d < HOJE:
            continue
        if fim and d > fim:
            continue
        texto = f"{e['nome'] or ''} {' '.join(e['desc'])}"
        if not e["nome"] and LIXO.search(texto):
            # agrupamento sem identificador misturou itens; fica só se algum item é do núcleo
            e["desc"] = [x for x in e["desc"] if not LIXO.search(x)]
        if not NUC_RX.search(norm(e["nome"] if e["nome"] else " ".join(e["desc"]))):
            continue
        e["ano_pca"] = ano
        cands.append(e)
print("candidatas:", len(cands), file=sys.stderr)


def pncp(*a, timeout=120):
    r = subprocess.run(["pncp", *a, "-q", "--retries", "3"], capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout) if r.stdout.strip() else {}


ORG = {}


def orgao_id(cnpj):
    if cnpj not in ORG:
        try:
            its = pncp("search", cnpj, "--tipo", "edital", "--status", "todos", "--tam", "5").get("items") or []
            ORG[cnpj] = next((i["orgao_id"] for i in its if i.get("orgao_cnpj") == cnpj), None)
        except Exception:  # noqa: BLE001
            ORG[cnpj] = None
    return ORG[cnpj]


TERMO = {"UST/PF/horas": ["unidade de servico tecnico", "ponto de funcao", "fabrica de software"],
         "Fábrica/desenvolvimento": ["desenvolvimento", "fabrica de software"],
         "Sustentação/manutenção de sistemas": ["sustentacao", "manutencao de sistemas"],
         "Digitalização/gestão documental": ["digitalizacao", "gestao documental", "arquivistica"],
         "EAD": ["ensino a distancia", "ead", "plataforma"]}
PARE = set("de da do das dos e em para a o com na no por servicos servico contratacao empresa especializada prestacao tecnicos especializados "
           "solucao sistema sistemas tic ti tecnologia informacao".split())


def palavras(s):
    return {w for w in re.findall(r"[a-z]{4,}", norm(s)) if w not in PARE}


for c in cands:
    orgao_id(c["cnpj"])
print("órgãos com id:", sum(1 for v in ORG.values() if v), "/", len(ORG), file=sys.stderr)


def procurar(c):
    oid = ORG.get(c["cnpj"])
    alvo = palavras(f"{c['nome'] or ''} {' '.join(c['desc'])}")
    melhor = None
    if oid:
        vistos = {}
        for t in c["temas"]:
            for termo in TERMO.get(t, []):
                try:
                    its = pncp("search", termo, "--tipo", "edital", "--status", "todos", "--orgao", oid, "--tam", "50").get("items") or []
                except Exception:  # noqa: BLE001
                    its = []
                for i in its:
                    vistos[i["numero_controle_pncp"]] = i
        for i in vistos.values():
            if (i.get("data_publicacao_pncp") or "") < "2026-01-01":
                continue
            comum = alvo & palavras(i.get("description"))
            if len(comum) < 3 or not NUC_RX.search(norm(i.get("description"))):
                continue
            k = (len(comum) >= 3, i.get("data_publicacao_pncp") or "")
            if not melhor or k > melhor[0]:
                melhor = (k, i, sorted(comum)[:6])
    c["orgao_id"] = oid
    c["pca_link"] = f"https://pncp.gov.br/api/pncp/v1/orgaos/{c['cnpj']}/pca/{c['ano_pca']}/csv"
    if melhor:
        i = melhor[1]
        cnpj, ano, seq = i["orgao_cnpj"], i["ano"], int(i["numero_sequencial"])
        c["publicado"] = {"link": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}", "titulo": i.get("title"),
                          "objeto": (i.get("description") or "")[:220], "publicado_em": (i.get("data_publicacao_pncp") or "")[:10],
                          "fim_propostas": (i.get("data_fim_vigencia") or "")[:16], "situacao": i.get("situacao_nome"),
                          "modalidade": i.get("modalidade_licitacao_nome"), "tem_resultado": i.get("tem_resultado"),
                          "cancelado": i.get("cancelado"), "palavras_em_comum": melhor[2]}
    return c


with cf.ThreadPoolExecutor(4) as ex:
    cands = list(ex.map(procurar, cands))
cands.sort(key=lambda c: (c["ano_pca"], dt(c["data"]) or HOJE, -c["valor"]))
json.dump(cands, open(SAIDA, "w"), ensure_ascii=False, default=list)
print("com publicação encontrada:", sum(1 for c in cands if c.get("publicado")), "de", len(cands), file=sys.stderr)
