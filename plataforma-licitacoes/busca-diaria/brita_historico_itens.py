import json,re,urllib.request,unicodedata
from concurrent.futures import ThreadPoolExecutor
nm=lambda s:" ".join(re.sub(r"[^a-z0-9 ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split())
L=json.load(open("d27/brita/amp/raio.json"))
CF="d27/brita/amp/cache.json"
try: C=json.load(open(CF))
except Exception: C={}
def get(u):
    for t in range(3):
        try: return json.load(urllib.request.urlopen(u,timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (404,204): return []
        except Exception: pass
    return None
AG=re.compile(r"\bbrita|\bareia|pedra (britada|de mao|marroada|rachao|pulmao)|\bpo de (pedra|brita)|cascalho|pedrisco|rachao|bica corrida|saibro|agregado|\bcimento\b|bloquete|intertravad|meio fio")
def itens(e):
    c=e["numero_controle_pncp"]
    if c in C and C[c] is not None: return c,C[c]
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); base=f"https://pncp.gov.br/api/pncp/v1/orgaos/{m.group(1)}/compras/{m.group(3)}/{m.group(2)}"
    it=[]
    for pg in range(1,5):
        x=get(f"{base}/itens?pagina={pg}&tamanhoPagina=500")
        if x is None: return c,None
        it+=x
        if len(x)<500: break
    out=[]
    for i in it:
        if not AG.search(nm(i.get("descricao"))) or re.search(r"odont|endodont|cimento (de|para) (ionomero|hidroxido|resinoso|cirurgico|ortodont|provisorio)|areia (colorida|magica|cinetica|para artesanato)|kit .*areia",nm(i.get("descricao"))): continue
        r=[]
        if i.get("temResultado"):
            x=get(f"{base}/itens/{i['numeroItem']}/resultados") or []
            r=[[y.get("nomeRazaoSocialFornecedor"),y.get("niFornecedor"),y.get("valorUnitarioHomologado"),y.get("quantidadeHomologada"),y.get("dataResultado")] for y in x]
        out.append([i.get("numeroItem"),i.get("descricao"),i.get("quantidade"),i.get("unidadeMedida"),i.get("valorUnitarioEstimado"),i.get("valorTotal"),i.get("situacaoCompraItemNome"),r])
    return c,out
with ThreadPoolExecutor(8) as ex:
    for c,o in ex.map(itens,L):
        C[c]=o
json.dump(C,open(CF,"w"),ensure_ascii=False)
ok=[e for e in L if C.get(e["numero_controle_pncp"])]
print(len(L),"licitações;",sum(1 for e in L if C.get(e["numero_controle_pncp"]) is not None),"lidas;",len(ok),"com brita/areia/cimento etc nos itens;",
      sum(len(C[e["numero_controle_pncp"]]) for e in ok),"itens;",sum(1 for e in ok for i in C[e["numero_controle_pncp"]] if i[7]),"itens com vencedor")
