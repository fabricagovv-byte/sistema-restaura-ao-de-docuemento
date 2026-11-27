"""Brita, areia e agregados ABERTOS no Brasil todo (PNCP, itens lidos), com filtros por região, UF, cidade, produto e tipo.
Uso: python3 planilha_brita_br.py brasil_cand2.json brasil_itens.json saida.xlsx saida_whatsapp.txt"""
import json,re,sys,statistics,unicodedata,collections
from datetime import datetime,timedelta,timezone
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet.datavalidation import DataValidation
L=json.load(open(sys.argv[1])); C=json.load(open(sys.argv[2])); OUT=sys.argv[3]; WA=sys.argv[4]
agora=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=3); AG=agora.strftime("%Y-%m-%dT%H:%M")
nm=lambda s:" ".join(re.sub(r"[^a-z0-9 ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split())
limpo=lambda s: ILLEGAL_CHARACTERS_RE.sub("",s) if isinstance(s,str) else s
REG={"Norte":"AC AM AP PA RO RR TO","Nordeste":"AL BA CE MA PB PE PI RN SE","Centro-Oeste":"DF GO MS MT","Sudeste":"ES MG RJ SP","Sul":"PR RS SC"}
REGIAO={uf:r for r,s in REG.items() for uf in s.split()}
N_=r"brita (no? |n o |numero |n\. )?"
PROD=[("Brita 0",N_+r"0\b|brita zero"),("Brita 1",N_+r"0?1\b|brita um"),("Brita 2/3/4",N_+r"0?[234]\b"),
      ("Pedrisco",r"pedrisco"),("Pó de pedra/brita",r"po de (pedra|brita)"),("Bica corrida",r"bica corrida"),("Pedra de mão/rachão",r"pedra de mao|rachao|marroada|matacao|pedra pulmao|pedra amarroada"),
      ("Cascalho",r"cascalh"),("Saibro/piçarra/laterita",r"saibro|picarra|laterita|solo (para|de) (aterro|emprestimo)|material de jazida"),("Areia fina",r"areia fina"),("Areia média",r"areia media"),("Areia grossa",r"areia grossa"),
      ("Areia (outras)",r"\bareia"),("Brita (outras)",r"\bbrita|pedra britada|agregado graudo|agregado"),("Cimento",r"\bcimento\b"),("Bloquete/intertravado",r"bloquete|intertravad|paver"),("Meio-fio",r"meio fio")]
NAO=re.compile(r"odont|endodont|ionomero|hidroxido|cimento (cirurgico|resinoso|provisorio|ortodont|de zinco|fosfato)|areia (colorida|magica|cinetica|para artesanato|de silica para filtro)|kit .*areia|brinquedo|ampulheta|aquario|caixa de areia para gato|areia sanitaria|higienica|gato|filtro|jateamento|lixa|saco de areia para|tenis|bola")
INI=re.compile(r"^(cota (ampla|reservada|principal) (participacao|paricipacao)? ?)?(obras?|contratacao|servic|prestacao|coleta|tratamento|credenciamento|chamamento|selecao|execucao|tinta|aterro|conjunto|ferragem|tampa|recepcao|portico|planetario|guarda|elaboracao|construcao civil|seminovo|locacao|transporte|frete)")
def prod(d):
    n=nm(d)
    if NAO.search(n) or INI.search(n) or re.search(r"cimento asfaltico|\bcap 50|asfalt|betume|emulsao|tinta|cola|argamassa colante|rejunte",n): return None
    for p,rx in PROD:
        if re.search(rx,n): return p
    return None
def un(u):
    n=nm(u)
    return "m³" if re.search(r"m3|metro ?3|metros? cub|metrocub|m cub|^m$|metro c|cubico",n) else "t" if re.search(r"ton|^t$",n) else "saco" if re.search(r"saco|^sc",n) else (u or "").strip()[:12]
def link(c):
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); return f"https://pncp.gov.br/app/editais/{m.group(1)}/{m.group(3)}/{m.group(2)}"
OBRA=re.compile(r"execucao|obra|engenharia|reforma|construcao d|pavimentacao (asfaltica )?(de|em|da|do)|recapeamento|drenagem")
LIC=[];IT=[]
for r in L:
    c,org,mun,uf,mod,v,sig,fim,obj,portal,ass,esf,ini=r
    it=C.get(c) or []
    hit=[(i,prod(i[1])) for i in it]; hit=[(i,p) for i,p in hit if p]
    for i,p in hit:
        i.append(bool((i[5] or 0)>3e7 or ((i[4] or 0)>3000 and p not in ("Cimento",))))  # valor provavelmente digitado errado
    ruim=any(i[-1] for i,_ in hit)
    if not hit or not fim or fim<=AG: continue
    n=nm(obj)
    tipo="Obra/serviço (usa o material)" if ("concorr" in nm(mod) or (OBRA.search(n) and not re.search(r"aquisicao|fornecimento|compra|registro de precos para (futura e eventual )?aquisicao",n))) else "Fornecimento de material"
    agreg=[(i,p) for i,p in hit if p not in ("Cimento","Bloquete/intertravado","Meio-fio")]
    soma=sum(i[5] or 0 for i,_ in hit if not i[-1]); sa=sum(i[5] or 0 for i,_ in agreg if not i[-1])
    prods=collections.Counter(p for _,p in hit)
    f=datetime.strptime(fim[:16],"%Y-%m-%dT%H:%M"); dias=(f.date()-agora.date()).days
    LIC.append(dict(c=c,org=org,mun=mun,uf=uf,reg=REGIAO.get(uf,""),mod=mod,fim=fim,dias=dias,obj=" ".join(obj.split()),portal=portal,tipo=tipo,
                    ruim=ruim,n=len(hit),nag=len(agreg),soma=soma,sa=sa,prods=", ".join(p for p,_ in prods.most_common()),link=link(c),ini=ini or "",v=v,sig=sig))
    for i,p in hit:
        IT.append(dict(c=c,uf=uf,reg=REGIAO.get(uf,""),mun=mun,tipo=tipo,item=i[0],desc=" ".join((i[1] or "").split()),prod=p,q=i[2],un=un(i[3]),vu=i[4],vt=i[5],sig=i[6],ruim=i[-1],fim=fim,dias=dias,link=link(c)))
LIC.sort(key=lambda x:(x["tipo"]!="Fornecimento de material",-x["sa"],-x["soma"]))
AZ="1F3A5F"; H=Font(bold=True,color="FFFFFF"); HF=PatternFill("solid",fgColor=AZ); B=Side(style="thin",color="D0D5DD"); BD=Border(left=B,right=B,top=B,bottom=B)
def st(d): return ("URGENTE","FDE2E1","B42318") if d<=2 else ("ESTA SEMANA","FEF0C7","B54708") if d<=7 else ("NO PRAZO","DCFAE6","067647")
def cab(ws,row,cols,widths):
    for j,t in enumerate(cols,1):
        x=ws.cell(row=row,column=j,value=t); x.font=H; x.fill=HF; x.alignment=Alignment(wrap_text=True,vertical="center"); x.border=BD
    for j,w in enumerate(widths,1): ws.column_dimensions[get_column_letter(j)].width=w
def tit(ws,t,sub):
    ws["A1"]=t; ws["A1"].font=Font(bold=True,size=15,color=AZ); ws["A2"]=sub; ws["A2"].font=Font(italic=True,color="667085")
BRL='"R$" #,##0.00'; NUM='#,##0.##'
dt=lambda s:f"{s[8:10]}/{s[5:7]}/{s[:4]} {s[11:16]}"
wb=Workbook(); ws=wb.active; ws.title="Resumo"
tit(ws,"Brita, areia e agregados · licitações ABERTAS no Brasil",f"PNCP, lista de {agora:%d/%m/%Y %H:%M}, com os itens lidos de cada edital. Use os filtros (setinha no cabeçalho) nas abas Licitações e Itens.")
forn=[x for x in LIC if x["tipo"].startswith("Forn")]; ob=[x for x in LIC if not x["tipo"].startswith("Forn")]
K=[("Licitações abertas",len(LIC)),("Fornecimento de material",len(forn)),("Obras que usam o material",len(ob)),("Itens de material",len(IT)),("Soma estimada (agregados)",sum(x["sa"] for x in LIC)),("Municípios",len({(x['mun'],x['uf']) for x in LIC}))]
for j,(a,b) in enumerate(K,1):
    ws.cell(row=4,column=j,value=a).font=Font(color="667085",size=9); c=ws.cell(row=5,column=j,value=b); c.font=Font(bold=True,size=15,color=AZ)
    if j==5: c.number_format='"R$" #,##0'
r=7; ws.cell(row=r,column=1,value="POR UF (abertas)").font=Font(bold=True,color=AZ); r+=1
cab(ws,r,["UF","Região","Licitações","Fornecimento","Obras","Soma agregados","Soma total material"],[26,16,14,14,12,20,20]); r+=1
u=collections.defaultdict(lambda:[0,0,0,0,0])
for x in LIC:
    d=u[x["uf"]]; d[0]+=1; d[1]+=x["tipo"].startswith("Forn"); d[2]+=not x["tipo"].startswith("Forn"); d[3]+=x["sa"]; d[4]+=x["soma"]
for uf,d in sorted(u.items(),key=lambda kv:-kv[1][3]):
    for j,v in enumerate([uf,REGIAO.get(uf,"")]+d,1):
        c=ws.cell(row=r,column=j,value=v); c.border=BD
        if j>=6: c.number_format='"R$" #,##0'
    r+=1
r+=1; ws.cell(row=r,column=1,value="PREÇO ESTIMADO NOS EDITAIS ABERTOS (mediana por produto)").font=Font(bold=True,color=AZ); r+=1
cab(ws,r,["Produto","Unidade","Itens","Mediana","Menor","Maior","Quantidade somada"],[26,16,14,14,12,20,20]); r+=1
g=collections.defaultdict(list)
for i in IT:
    if i["vu"] and not i["ruim"] and i["un"] in ("m³","t","saco"): g[(i["prod"],i["un"])].append(i)
ordem=[p for p,_ in PROD]
for (p,un_),xs in sorted(g.items(),key=lambda kv:(ordem.index(kv[0][0]),kv[0][1])):
    if len(xs)<3: continue
    vs=sorted(x["vu"] for x in xs); me=statistics.median(vs); ok=[v for v in vs if 0.25*me<=v<=4*me]
    for j,v in enumerate([p,un_,len(xs),me,min(ok),max(ok),sum(x["q"] or 0 for x in xs)],1):
        c=ws.cell(row=r,column=j,value=v); c.border=BD
        if 4<=j<=6: c.number_format=BRL
        if j==7: c.number_format=NUM
    r+=1
r+=1
for lab,(t,fc,tc) in [("URGENTE · encerra em até 2 dias",st(0)),("ESTA SEMANA · até 7 dias",st(5)),("NO PRAZO · mais de 7 dias",st(30))]:
    c=ws.cell(row=r,column=1,value=lab); c.fill=PatternFill("solid",fgColor=fc); c.font=Font(bold=True,color=tc); r+=1
# Licitações
ws=wb.create_sheet("Licitações"); tit(ws,"Licitações abertas com brita, areia e agregados","Filtre por Região, UF, Município, Tipo ou Produtos (setinha no cabeçalho). Ordem: fornecimento primeiro, maior soma de agregados.")
cols=["Prazo","Encerra","Região","UF","Município","Órgão","Tipo","Modalidade","Produtos","Itens de material","Soma agregados","Soma material","Valor total do edital","Objeto","Portal","Edital PNCP","Alerta"]
cab(ws,4,cols,[13,17,13,6,22,34,24,20,40,9,16,16,18,70,26,46,30])
for k,x in enumerate(LIC,5):
    s,fc,tc=st(x["dias"])
    v=[s,dt(x["fim"]),x["reg"],x["uf"],x["mun"],x["org"],x["tipo"],x["mod"],x["prods"],x["n"],x["sa"],x["soma"],("sigiloso" if x["sig"] else x["v"]),limpo(x["obj"][:400]),x["portal"],x["link"],"⚠️ item com valor fora do normal (conferir edital; fora das somas)" if x["ruim"] else ""]
    for j,val in enumerate(v,1):
        c=ws.cell(row=k,column=j,value=val); c.border=BD; c.alignment=Alignment(vertical="top",wrap_text=j in (9,14))
        if j in (11,12,13) and not isinstance(val,str): c.number_format='"R$" #,##0.00'
        if j==16: c.hyperlink=val; c.font=Font(color="1D4ED8",underline="single")
    c=ws.cell(row=k,column=1); c.fill=PatternFill("solid",fgColor=fc); c.font=Font(bold=True,color=tc)
ws.auto_filter.ref=f"A4:Q{4+len(LIC)}"; ws.freeze_panes="F5"
# Itens
ws=wb.create_sheet("Itens"); tit(ws,"Itens de brita, areia e agregados (editais abertos)","Uma linha por item. Filtre por Produto, UF ou Unidade para comparar preços.")
cols=["Produto","Região","UF","Município","Tipo","Encerra","Item","Descrição","Qtd","Unid.","Preço unit. estimado","Total estimado","Edital PNCP","Alerta"]
cab(ws,4,cols,[20,13,6,22,24,17,6,64,12,8,16,16,46,22])
IT.sort(key=lambda i:(ordem.index(i["prod"]),i["uf"],i["mun"]))
for k,i in enumerate(IT,5):
    v=[i["prod"],i["reg"],i["uf"],i["mun"],i["tipo"],dt(i["fim"]),i["item"],limpo(i["desc"][:250]),i["q"],i["un"],(None if i["sig"] else i["vu"]),(None if i["sig"] else i["vt"]),i["link"],"⚠️ valor a conferir" if i["ruim"] else ""]
    for j,val in enumerate(v,1):
        c=ws.cell(row=k,column=j,value=val); c.border=BD
        if j in (11,12): c.number_format=BRL
        if j==9: c.number_format=NUM
        if j==13: c.hyperlink=val; c.font=Font(color="1D4ED8",underline="single")
    s,fc,tc=st(i["dias"]); ws.cell(row=k,column=6).fill=PatternFill("solid",fgColor=fc)
ws.auto_filter.ref=f"A4:N{4+len(IT)}"; ws.freeze_panes="B5"
wb.save(OUT)
# WhatsApp: top por região (fornecimento)
mi=lambda v: "não divulgado" if not v else (f"R$ {v/1e6:.2f} mi".replace(".",",") if v>=1e6 else f"R$ {v/1e3:.0f} mil")
SEM=["seg","ter","qua","qui","sex","sáb","dom"]
tt=lambda s:" ".join(w if w in ("de","da","do","dos","das","e") else w.capitalize() for w in s.lower().split())
m=[f"*🧱 BRITA, AREIA E AGREGADOS · ABERTAS NO BRASIL · {agora:%d/%m/%Y}*",f"PNCP, itens lidos em cada edital. *{len(LIC)} abertas* ({len(forn)} de fornecimento de material e {len(ob)} obras que usam o material) em {len({x['uf'] for x in LIC})} UFs. Soma estimada dos agregados: *{mi(sum(x['sa'] for x in LIC))}*.",
   "Abaixo, as 5 maiores de *fornecimento* por região (soma dos itens de brita, areia, pedra e cascalho). A lista completa, com filtro por UF, cidade e produto, está na planilha. ⚠️ = encerra em até 2 dias."]
for rg in REG:
    xs=[x for x in forn if x["reg"]==rg and x["sa"]>0][:5]
    if not xs: continue
    m.append(f"\n*📍 {rg.upper()}* ({sum(1 for x in forn if x['reg']==rg)} de fornecimento abertas)")
    for n,x in enumerate(xs,1):
        f=datetime.strptime(x["fim"][:16],"%Y-%m-%dT%H:%M")
        m.append(f"\n*{n}. {x['mun']}/{x['uf']}* · {tt(x['org'])[:60]}\n🪨 {x['prods']}\n💰 Agregados: *{mi(x['sa'])}* · {x['mod']}\n📅 {SEM[f.weekday()]} {f:%d/%m}{f.strftime('/%Y') if f.year!=agora.year else ''} {f:%H:%M}{' ⚠️' if x['dias']<=2 else ''}\n🔗 {x['link']}")
open(WA,"w").write("\n".join(m))
print(f"ok: {len(LIC)} abertas ({len(forn)} fornecimento, {len(ob)} obras), {len(IT)} itens, {len({x['uf'] for x in LIC})} UFs")
