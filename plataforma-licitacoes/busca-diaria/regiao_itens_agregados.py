import json,re,csv,math,unicodedata,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
norm=lambda s: re.sub(r"[^a-z ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split()
nm=lambda s:" ".join(norm(s))
ag=(datetime.now(timezone.utc)-timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
C={nm(r["nome"]):(float(r["latitude"]),float(r["longitude"])) for r in csv.DictReader(open("geo/municipios.csv")) if r["codigo_uf"]=="31"}
def km(a,b):
    p=math.pi/180;d=0.5-math.cos((b[0]-a[0])*p)/2+math.cos(a[0]*p)*math.cos(b[0]*p)*(1-math.cos((b[1]-a[1])*p))/2
    return 12742*math.asin(math.sqrt(d))
B={"Serro":C["serro"],"Diamantina":C["diamantina"]}
reg=[]
for r in json.load(open("d27/todas.json"))["registros"]:
    if r[3]!="MG" or not r[7] or r[7]<=ag or "preg" not in nm(r[4]): continue
    p=C.get(nm(r[2]))
    if not p: continue
    d={k:km(p,b) for k,b in B.items()}; base=min(d,key=d.get)
    if d[base]<=150: reg.append((r,round(d[base]),base))
try: CACHE=json.load(open("brita_itens.cache.json"))
except Exception: CACHE={}
def itens(c):
    if c in CACHE: return c,CACHE[c]
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); out=[]
    try:
        for pg in range(1,6):
            L=json.load(urllib.request.urlopen(f"https://pncp.gov.br/api/pncp/v1/orgaos/{m.group(1)}/compras/{m.group(3)}/{m.group(2)}/itens?pagina={pg}&tamanhoPagina=500",timeout=60))
            out+= [[i.get("numeroItem"),i.get("descricao"),i.get("quantidade"),i.get("unidadeMedida"),i.get("valorUnitarioEstimado"),i.get("valorTotal"),i.get("orcamentoSigiloso")] for i in L]
            if len(L)<500: break
    except Exception: return c,None
    return c,out
with ThreadPoolExecutor(8) as ex:
    for c,o in ex.map(itens,[r[0] for r,_,_ in reg]):
        if o is not None: CACHE[c]=o
json.dump(CACHE,open("brita_itens.cache.json","w"),ensure_ascii=False)
AG=re.compile(r"\bbrita|\bareia|pedra (britada|de mao|marroada|rachao|pulmao)|\bpo de pedra|cascalho|pedrisco|rachao|bica corrida|saibro|agregado|seixo|\bcal (hidratada|virgem)|\bcimento|bloquete|intertravad|meio fio|manilha|tubo de concreto|concreto usinado|cbuq|massa asfaltica|emulsao")
res=[]
for r,k,base in reg:
    it=CACHE.get(r[0])
    if it is None: continue
    hit=[i for i in it if AG.search(nm(i[1]))]
    forte=[i for i in hit if re.search(r"\bbrita|\bareia|pedra|cascalho|pedrisco|rachao|bica corrida|saibro|agregado|po de pedra",nm(i[1]))]
    if hit: res.append(dict(r=r,km=k,base=base,hit=hit,forte=len(forte),n=len(it),soma=sum((i[5] or 0) for i in hit)))
res.sort(key=lambda e:(-(e["forte"]>0),-e["soma"]))
json.dump(res,open("brita_res.json","w"),ensure_ascii=False)
print(len(reg),"pregões no raio;",sum(1 for r,_,_ in reg if r[0] in CACHE),"com itens lidos;",len(res),"com brita/areia/cimento etc nos itens;",sum(1 for e in res if e["forte"]),"com brita/areia/pedra")
for e in res[:25]:
    r=e["r"];print(e["forte"],len(e["hit"]),"/",e["n"],e["km"],e["base"],r[2],r[7][:10],round(e["soma"]),"|",r[8][:80],"|",[i[1][:30] for i in e["hit"][:3]])
