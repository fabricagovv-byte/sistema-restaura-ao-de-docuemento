"""PCA 2027 no PNCP: o que os órgãos compradores de TIC planejam licitar (contratações futuras ainda não publicadas)."""
import csv, json, os, re, subprocess, sys, concurrent.futures as cf, unicodedata

DIR = sys.argv[1]
ANO = sys.argv[2] if len(sys.argv) > 2 else "2027"
orgs = json.load(open(os.path.join(DIR, "orgs.json")))


def baixar(cnpj):
    dest = os.path.join(DIR, f"{cnpj}_{ANO}.csv")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return cnpj, "cache"
    try:
        r = subprocess.run(["pncp", "pca", "csv", cnpj, ANO, "--saida", dest, "-q", "--retries", "3"], capture_output=True, text=True, timeout=420)
        return cnpj, (r.returncode, r.stderr.strip()[-120:])
    except Exception as e:  # noqa: BLE001
        return cnpj, f"erro {e}"


with cf.ThreadPoolExecutor(6) as ex:
    for cnpj, st in ex.map(baixar, orgs):
        print(cnpj, orgs[cnpj][0][:40], st, file=sys.stderr, flush=True)


def norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


TEMA = [("UST/PF/horas", r"\bust\b|unidade de servico tecn|pontos? de funcao|\bhst\b|horas? de servico tecn|banco de horas"),
        ("Fábrica/desenvolvimento", r"fabrica de software|desenvolvimento de (software|sistema|aplica)|desenvolvimento e manutencao|engenharia de software"),
        ("Sustentação/manutenção de sistemas", r"sustentacao|manutencao (evolutiva|corretiva|adaptativa)|manutencao de (software|sistema)"),
        ("Digitalização/gestão documental", r"digitaliza|gestao documental|\bged\b|gerenciamento eletronico de doc|microfilm|guarda de documentos|arquivistic|tratamento documental"),
        ("EAD", r"\bead\b|ensino a distancia|educacao a distancia|ambiente virtual de aprendizagem|\blms\b|moodle"),
        ("Sistemas/licenças/SaaS", r"sistema (de gestao|integrado|informatizado)|software como servico|\bsaas\b|licenca de uso|locacao de (sistema|software)|subscric"),
        ("Serviços de TI", r"service desk|suporte tecnico|servicos (tecnicos )?(especializados )?de (ti|tic|tecnologia)|outsourcing|nuvem|cloud|seguranca da informacao|ciencia de dados|inteligencia artificial")]


def num(s):
    try:
        return float((s or "0").replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


fut = {}
for cnpj, (nome, esfera, _) in orgs.items():
    p = os.path.join(DIR, f"{cnpj}_{ANO}.csv")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        continue
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ident = r.get("Identificador da Futura Contratação") or ""
            k = (cnpj, ident or r.get("Id do item no PCA"))
            e = fut.setdefault(k, {"cnpj": cnpj, "orgao": nome, "esfera": esfera, "unidade": r.get("Unidade Responsável"), "uasg": r.get("UASG"),
                                   "id": ident, "nome": r.get("Nome da Futura Contratação"), "data": r.get("Data Desejada"), "valor": 0.0,
                                   "tic": False, "itens": 0, "desc": set()})
            e["valor"] += num(r.get("Valor Total Estimado (R$)"))
            e["itens"] += 1
            e["tic"] |= (r.get("Categoria do Item") or "").startswith("Soluções de TIC")
            for c in ("Nome da Classificação Superior (Classe/Grupo)", "Nome do PDM do Item", "Descrição do Item"):
                if r.get(c) and len(e["desc"]) < 12:
                    e["desc"].add(r[c][:120])
saida = []
for e in fut.values():
    txt = norm(f"{e['nome']} {' '.join(e['desc'])}")
    temas = [t for t, rx in TEMA if re.search(rx, txt)]
    if not temas or (not e["tic"] and not set(temas) & {"Digitalização/gestão documental", "UST/PF/horas", "EAD"}):
        continue
    e["temas"], e["desc"] = temas, sorted(e["desc"])[:6]
    saida.append(e)
saida.sort(key=lambda e: -e["valor"])
json.dump({"ano": ANO, "orgaos_consultados": len(orgs),
           "orgaos_com_pca": sum(1 for c in orgs if os.path.exists(os.path.join(DIR, f"{c}_{ANO}.csv")) and os.path.getsize(os.path.join(DIR, f"{c}_{ANO}.csv")) > 0),
           "futuras": saida}, open(os.path.join(DIR, f"pca_{ANO}_tic.json"), "w"), ensure_ascii=False)
print("futuras contratações de TIC/documental:", len(saida))
