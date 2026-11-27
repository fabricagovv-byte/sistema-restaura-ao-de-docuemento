"""Brita, areia e material de construção até 150 km de Serro e Diamantina: abertas, histórico, preços, vencedores e recorrência.
Uso: python3 planilha_brita.py raio.json cache.json saida.xlsx"""
import json,re,sys,statistics,unicodedata,collections
from datetime import datetime,timedelta,timezone
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
L=json.load(open(sys.argv[1])); C=json.load(open(sys.argv[2])); OUT=sys.argv[3]
agora=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=3); AG=agora.strftime("%Y-%m-%dT%H:%M")
nm=lambda s:" ".join(re.sub(r"[^a-z0-9 ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split())
limpo=lambda s: ILLEGAL_CHARACTERS_RE.sub("",s) if isinstance(s,str) else s
PROD=[("Brita 0",r"brita (n )?(o )?0\b|brita zero|brita n 0|brita 0"),("Brita 1",r"brita (n )?(o )?0?1\b|brita um"),("Brita 2/3",r"brita (n )?(o )?0?[234]\b"),
      ("Pedrisco",r"pedrisco"),("Pó de pedra/brita",r"po de (pedra|brita)"),("Bica corrida",r"bica corrida"),("Pedra de mão/rachão",r"pedra de mao|rachao|marroada|matacao|pedra pulmao"),
      ("Cascalho",r"cascalho"),("Saibro",r"saibro"),("Areia fina",r"areia fina"),("Areia grossa",r"areia grossa"),("Areia média",r"areia media"),("Areia (outras)",r"\bareia"),
      ("Brita (outras)",r"\bbrita|pedra britada|agregado"),("Cimento",r"\bcimento\b"),("Bloquete/intertravado",r"bloquete|intertravad"),("Meio-fio",r"meio fio")]
def prod(d):
    n=nm(d)
    for p,rx in PROD:
        if re.search(rx,n): return p
    return "Outros"
def un(u):
    n=nm(u)
    return "m³" if re.search(r"m3|metro ?3|metros? cub|metrocub|m cub|^m$|metro c|cubico",n) else "t" if re.search(r"ton",n) else "saco" if re.search(r"saco|sc",n) else (u or "").strip()[:12]
def link(c):
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); return f"https://pncp.gov.br/app/editais/{m.group(1)}/{m.group(3)}/{m.group(2)}"
def situ(e):
    s=e.get("situacao_nome") or ""
    if re.search(r"revog|anul|suspen",s.lower()): return s.upper()
    f=(e.get("data_fim_vigencia") or "")[:16]
    return "ABERTA" if f and f>AG else "ENCERRADA"
# ---------- dados
LIC=[]; ITENS=[]
for e in L:
    c=e["numero_controle_pncp"]; it=C.get(c) or []
    if not it: continue
    st=situ(e); soma=sum(i[5] or 0 for i in it)
    LIC.append(dict(c=c,mun=e["municipio_nome"],org=e["orgao_nome"],km=e["km"],base=e["base"],mod=e["modalidade_licitacao_nome"],st=st,
                    pub=(e.get("data_publicacao_pncp") or "")[:10],fim=(e.get("data_fim_vigencia") or "")[:16],obj=" ".join((e.get("description") or "").split()),
                    soma=soma,n=len(it),venc=sum(1 for i in it if i[7]),link=link(c)))
    for i in it:
        p=prod(i[1]); u=un(i[3])
        res=i[7] or []
        if res:
            for r in res: ITENS.append(dict(c=c,mun=e["municipio_nome"],km=e["km"],pub=LIC[-1]["pub"],st=st,item=i[0],desc=" ".join((i[1] or "").split()),prod=p,un=u,q=i[2],vu=i[4],vt=i[5],forn=r[0],cnpj=r[1],vh=r[2],qh=r[3],link=LIC[-1]["link"]))
        else: ITENS.append(dict(c=c,mun=e["municipio_nome"],km=e["km"],pub=LIC[-1]["pub"],st=st,item=i[0],desc=" ".join((i[1] or "").split()),prod=p,un=u,q=i[2],vu=i[4],vt=i[5],forn="",cnpj="",vh=None,qh=None,link=LIC[-1]["link"]))
LIC.sort(key=lambda x:(x["st"]!="ABERTA",-int(x["pub"].replace("-","") or 0)))
# ---------- estilos
AZ="1F3A5F"; H=Font(bold=True,color="FFFFFF"); HF=PatternFill("solid",fgColor=AZ); B=Side(style="thin",color="D0D5DD"); BD=Border(left=B,right=B,top=B,bottom=B)
COR={"ABERTA":("DCFAE6","067647"),"ENCERRADA":("F2F4F7","475467")}
def cor(st): return COR.get(st,("FDE2E1","B42318"))
def cab(ws,row,cols,widths=None):
    for j,t in enumerate(cols,1):
        x=ws.cell(row=row,column=j,value=t); x.font=H; x.fill=HF; x.alignment=Alignment(wrap_text=True,vertical="center"); x.border=BD
    if widths:
        for j,w in enumerate(widths,1): ws.column_dimensions[get_column_letter(j)].width=w
def tit(ws,t,sub):
    ws["A1"]=t; ws["A1"].font=Font(bold=True,size=15,color=AZ); ws["A2"]=sub; ws["A2"].font=Font(italic=True,color="667085")
BRL='"R$" #,##0.00'; NUM='#,##0.##'
wb=Workbook()
# ---------- Resumo
ws=wb.active; ws.title="Resumo"
tit(ws,"Brita, areia e material de construção · até 150 km de Serro e Diamantina",f"Fonte: PNCP (editais desde jun/2025 com itens lidos) · gerado {agora:%d/%m/%Y %H:%M} · só dado informado pelo PNCP")
ab=[x for x in LIC if x["st"]=="ABERTA"]
k=[("Licitações com brita/areia/material",len(LIC)),("Abertas agora",len(ab)),("Itens de material lidos",len({(i['c'],i['item']) for i in ITENS})),
   ("Itens com vencedor publicado",len({(i['c'],i['item']) for i in ITENS if i['forn']})),("Municípios compradores",len({x['mun'] for x in LIC})),("Fornecedores vencedores",len({i['cnpj'] for i in ITENS if i['cnpj']}))]
for j,(a,b) in enumerate(k):
    ws.cell(row=4,column=1+j*1,value=a).font=Font(color="667085",size=9); c=ws.cell(row=5,column=1+j,value=b); c.font=Font(bold=True,size=16,color=AZ)
r=7; ws.cell(row=r,column=1,value="PREÇO DE REFERÊNCIA POR PRODUTO (mediana)").font=Font(bold=True,color=AZ); r+=1
cab(ws,r,["Produto","Unidade","Itens","Preço estimado (mediana)","Preço homologado (mediana)","Menor homologado","Maior homologado"],[30,12,10,22,24,18,18]); r+=1
g=collections.defaultdict(lambda:{"e":[],"h":[],"n":set()})
for i in ITENS:
    if i["prod"]=="Outros" or not i["un"]: continue
    d=g[(i["prod"],i["un"])]; d["n"].add((i["c"],i["item"]))
    if i["vu"]: d["e"].append(i["vu"])
    if i["vh"]: d["h"].append(i["vh"])
ordem=[p for p,_ in PROD]
for (p,u),d in sorted(g.items(),key=lambda x:(ordem.index(x[0][0]),-len(x[1]["n"]))):
    if len(d["n"])<3 or u not in ("m³","t","saco"): continue
    me=statistics.median(d["e"]) if d["e"] else None
    hh=[h for h in d["h"] if not me or 0.25*me<=h<=4*me]  # descarta valor digitado errado (ex.: R$ 0,18/m³)
    vals=[p,u,len(d["n"]),me,statistics.median(hh) if hh else None,min(hh) if hh else None,max(hh) if hh else None]
    for j,v in enumerate(vals,1):
        c=ws.cell(row=r,column=j,value=v); c.border=BD
        if j>=4: c.number_format=BRL
    r+=1
r+=1; ws.cell(row=r,column=1,value="MAIORES COMPRADORES (soma estimada dos itens de material)").font=Font(bold=True,color=AZ); r+=1
cab(ws,r,["Município","Distância","Licitações","Soma estimada","Abertas agora","Última publicação"]); r+=1
m=collections.defaultdict(lambda:{"n":0,"s":0,"a":0,"u":"","km":0,"b":""})
for x in LIC:
    d=m[x["mun"]]; d["n"]+=1; d["s"]+=x["soma"]; d["a"]+=x["st"]=="ABERTA"; d["u"]=max(d["u"],x["pub"]); d["km"]=x["km"]; d["b"]=x["base"]
for mun,d in sorted(m.items(),key=lambda x:-x[1]["s"])[:20]:
    for j,v in enumerate([mun,f"{d['km']} km de {d['b']}" if d['km'] else f"em {d['b']}" ,d["n"],d["s"],d["a"],f"{d['u'][8:10]}/{d['u'][5:7]}/{d['u'][:4]}"],1):
        c=ws.cell(row=r,column=j,value=v); c.border=BD
        if j==4: c.number_format=BRL
    r+=1
r+=1; ws.cell(row=r,column=1,value="LEGENDA").font=Font(bold=True,color=AZ); r+=1
for st in ("ABERTA","ENCERRADA","SUSPENSA / REVOGADA / ANULADA"):
    f,t=cor(st.split(" ")[0]); c=ws.cell(row=r,column=1,value=st); c.fill=PatternFill("solid",fgColor=f); c.font=Font(bold=True,color=t); r+=1
# ---------- Licitações
ws=wb.create_sheet("Licitações"); tit(ws,"Licitações com brita, areia e material de construção","Abertas primeiro; depois as mais recentes. Clique no link para o edital no PNCP.")
cols=["Situação","Publicação","Prazo proposta","Município","Distância","Órgão","Modalidade","Objeto","Itens de material","Com vencedor","Soma estimada (itens)","Edital PNCP"]
cab(ws,4,cols,[14,12,16,22,18,34,20,70,10,10,18,48])
for k_,x in enumerate(LIC,5):
    f,t=cor(x["st"].split(" ")[0])
    v=[x["st"],f"{x['pub'][8:10]}/{x['pub'][5:7]}/{x['pub'][:4]}",(f"{x['fim'][8:10]}/{x['fim'][5:7]}/{x['fim'][:4]} {x['fim'][11:16]}" if x["fim"] else ""),x["mun"],
       f"{x['km']} km de {x['base']}" if x["km"] else f"em {x['base']}",x["org"],x["mod"],limpo(x["obj"][:400]),x["n"],x["venc"],x["soma"],x["link"]]
    for j,val in enumerate(v,1):
        c=ws.cell(row=k_,column=j,value=val); c.border=BD; c.alignment=Alignment(vertical="top",wrap_text=j==8)
        if j==11: c.number_format=BRL
        if j==12: c.hyperlink=val; c.font=Font(color="1D4ED8",underline="single")
    ws.cell(row=k_,column=1).fill=PatternFill("solid",fgColor=f); ws.cell(row=k_,column=1).font=Font(bold=True,color=t)
ws.auto_filter.ref=f"A4:L{4+len(LIC)}"; ws.freeze_panes="A5"
# ---------- Itens e preços
ws=wb.create_sheet("Itens e preços"); tit(ws,"Itens de brita, areia e material · preço estimado e homologado","Uma linha por item (e por vencedor quando há mais de um). Filtre por Produto.")
cols=["Produto","Município","Publicação","Situação","Item","Descrição","Qtd","Unid.","Preço unit. estimado","Total estimado","Vencedor","CNPJ","Preço unit. homologado","Qtd homologada","Edital PNCP"]
cab(ws,4,cols,[20,20,12,12,6,60,10,8,16,16,36,18,18,12,46])
ITENS.sort(key=lambda i:(ordem.index(i["prod"]) if i["prod"] in ordem else 99,i["pub"]),reverse=False)
for k_,i in enumerate(ITENS,5):
    f,t=cor(i["st"].split(" ")[0])
    v=[i["prod"],i["mun"],f"{i['pub'][8:10]}/{i['pub'][5:7]}/{i['pub'][:4]}",i["st"],i["item"],limpo(i["desc"][:250]),i["q"],i["un"],i["vu"],i["vt"],limpo(i["forn"] or ""),i["cnpj"],i["vh"],i["qh"],i["link"]]
    for j,val in enumerate(v,1):
        c=ws.cell(row=k_,column=j,value=val); c.border=BD
        if j in (9,10,13): c.number_format=BRL
        if j in (7,14): c.number_format=NUM
        if j==15: c.hyperlink=val; c.font=Font(color="1D4ED8",underline="single")
    ws.cell(row=k_,column=4).fill=PatternFill("solid",fgColor=f); ws.cell(row=k_,column=4).font=Font(color=t)
ws.auto_filter.ref=f"A4:O{4+len(ITENS)}"; ws.freeze_panes="A5"
# ---------- Fornecedores
ws=wb.create_sheet("Fornecedores"); tit(ws,"Quem vence brita, areia e material na região","Pelo resultado publicado no PNCP (preço homologado × quantidade homologada).")
cab(ws,4,["Fornecedor","CNPJ/CPF","Itens vencidos","Municípios","Valor homologado (soma)","Produtos"],[42,20,12,50,22,50])
fo=collections.defaultdict(lambda:{"n":0,"m":set(),"v":0,"p":collections.Counter(),"nome":""})
for i in ITENS:
    if not i["cnpj"]: continue
    d=fo[i["cnpj"]]; d["nome"]=i["forn"]; d["n"]+=1; d["m"].add(i["mun"]); d["v"]+=(i["vh"] or 0)*(i["qh"] or 0); d["p"][i["prod"]]+=1
for k_,(cn,d) in enumerate(sorted(fo.items(),key=lambda x:-x[1]["v"]),5):
    for j,val in enumerate([limpo(d["nome"]),cn,d["n"],", ".join(sorted(d["m"])),d["v"],", ".join(p for p,_ in d["p"].most_common(5))],1):
        c=ws.cell(row=k_,column=j,value=val); c.border=BD; c.alignment=Alignment(vertical="top",wrap_text=j in (4,6))
        if j==5: c.number_format=BRL
ws.freeze_panes="A5"
# ---------- Recorrência
ws=wb.create_sheet("Recorrência"); tit(ws,"Quando cada município compra (para prever a próxima)","Mês de publicação de cada licitação de material. Próxima prevista = última + intervalo médio (estimativa simples, não é dado oficial).")
meses=[]; d0=datetime(2025,6,1)
while d0<=agora: meses.append(d0.strftime("%Y-%m")); d0=(d0.replace(day=28)+timedelta(days=4)).replace(day=1)
MES=["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
cab(ws,4,["Município","Distância","Licitações"]+[f"{MES[int(x[5:])-1]}/{x[2:4]}" for x in meses]+["Intervalo médio (dias)","Próxima prevista"],[22,18,10]+[7]*len(meses)+[14,22])
pm=collections.defaultdict(list)
for x in LIC: pm[x["mun"]].append(x)
row=5
for mun,xs in sorted(pm.items(),key=lambda kv:(-len(kv[1]),kv[0])):
    ds=sorted({x["pub"] for x in xs}); km_=xs[0]["km"]
    ws.cell(row=row,column=1,value=mun).border=BD; ws.cell(row=row,column=2,value=f"{km_} km de {xs[0]['base']}" if km_ else f"em {xs[0]['base']}").border=BD; ws.cell(row=row,column=3,value=len(xs)).border=BD
    cnt=collections.Counter(x["pub"][:7] for x in xs)
    for j,mm in enumerate(meses,4):
        c=ws.cell(row=row,column=j,value=cnt.get(mm) or None); c.border=BD; c.alignment=Alignment(horizontal="center")
        if cnt.get(mm): c.fill=PatternFill("solid",fgColor="FEF0C7" if any(x["st"]=="ABERTA" for x in xs if x["pub"][:7]==mm) is False else "DCFAE6"); c.font=Font(bold=True)
    if len(ds)>=2:
        dd=[datetime.strptime(b,"%Y-%m-%d")-datetime.strptime(a,"%Y-%m-%d") for a,b in zip(ds,ds[1:])]; med=sum(x.days for x in dd)/len(dd)
        prox=datetime.strptime(ds[-1],"%Y-%m-%d")+timedelta(days=med)
        ws.cell(row=row,column=4+len(meses),value=round(med)).border=BD
        txt=prox.strftime("%m/%Y") if prox>agora else f"atrasada (era {prox:%m/%Y})"
        c=ws.cell(row=row,column=5+len(meses),value=txt); c.border=BD
        if prox<=agora+timedelta(days=60): c.fill=PatternFill("solid",fgColor="DBEAFE"); c.font=Font(bold=True,color="1D4ED8")
    row+=1
ws.freeze_panes="D5"
wb.save(OUT)
print(f"ok: {len(LIC)} licitações ({len(ab)} abertas), {len(ITENS)} linhas de item, {len(fo)} fornecedores, {len(pm)} municípios")
