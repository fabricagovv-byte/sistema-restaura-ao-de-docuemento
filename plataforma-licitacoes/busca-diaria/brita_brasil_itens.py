import json,re,urllib.request,unicodedata
from concurrent.futures import ThreadPoolExecutor
nm=lambda s:" ".join(re.sub(r"[^a-z0-9 ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split())
L=json.load(open("d27/brita/brasil_cand2.json")); CF="d27/brita/brasil_itens.json"
try: C=json.load(open(CF))
except Exception: C={}
def get(u):
    for t in range(3):
        try: return json.load(urllib.request.urlopen(u,timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (404,204): return []
        except Exception: pass
    return None
def itens(r):
    c=r[0]
    if C.get(c) is not None: return c,C[c]
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); base=f"https://pncp.gov.br/api/pncp/v1/orgaos/{m.group(1)}/compras/{m.group(3)}/{m.group(2)}"
    it=[]
    for pg in range(1,5):
        x=get(f"{base}/itens?pagina={pg}&tamanhoPagina=500")
        if x is None: return c,None
        it+=x
        if len(x)<500: break
    return c,[[i.get("numeroItem"),i.get("descricao"),i.get("quantidade"),i.get("unidadeMedida"),i.get("valorUnitarioEstimado"),i.get("valorTotal"),i.get("orcamentoSigiloso"),i.get("situacaoCompraItemNome")] for i in it]
with ThreadPoolExecutor(10) as ex:
    for n,(c,o) in enumerate(ex.map(itens,L),1):
        C[c]=o
        if n%100==0: json.dump(C,open(CF,"w"),ensure_ascii=False); print(n,flush=True)
json.dump(C,open(CF,"w"),ensure_ascii=False)
print("lidas",sum(1 for r in L if C.get(r[0]) is not None),"de",len(L))
