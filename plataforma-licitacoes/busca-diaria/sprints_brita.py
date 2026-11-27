"""Plano em sprints para disputar as licitações abertas de brita/areia/agregados.
Uso: python3 sprints_brita.py brita-areia-brasil-abertas.xlsx saida.xlsx saida.txt"""
import sys,re,csv,math,unicodedata,collections
from datetime import datetime,timedelta,timezone,date
from openpyxl import load_workbook,Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
src,OUT,TXT=sys.argv[1:4]
agora=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=3); hoje=agora.date()
nm=lambda s:" ".join(re.sub(r"[^a-z0-9 ]"," ",unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()).split())
UFC={"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"}
G={(nm(r["nome"]),UFC.get(r["codigo_uf"])):(float(r["latitude"]),float(r["longitude"])) for r in csv.DictReader(open("geo/municipios.csv"))}
def km(a,b):
    p=math.pi/180;d=0.5-math.cos((b[0]-a[0])*p)/2+math.cos(a[0]*p)*math.cos(b[0]*p)*(1-math.cos((b[1]-a[1])*p))/2
    return 12742*math.asin(math.sqrt(d))
BASE={"Serro":G[("serro","MG")],"Diamantina":G[("diamantina","MG")]}
ws=load_workbook(src)["Licitações"]
hdr=[c.value for c in ws[4]]
L=[]
for r in ws.iter_rows(min_row=5,values_only=True):
    x=dict(zip(hdr,r))
    if not x["Tipo"].startswith("Forn"): continue
    f=datetime.strptime(x["Encerra"],"%d/%m/%Y %H:%M"); x["f"]=f
    p=G.get((nm(x["Município"]),x["UF"]))
    x["km"]=round(min(km(p,b) for b in BASE.values())) if p else None
    L.append(x)
# pregões de material da região (Serro/Diamantina) que não são agregados puros, mas estão na lista de 10 já enviada
import json
T={r[0]:r for r in json.load(open("d27/todas.json"))["registros"]}
EXTRA={"17754201000187-1-000084/2026":"Cimento CP-II e CP-V","18803072000132-1-000196/2026":"Materiais de construção (cal, tijolo, telha, madeira)","18062414000100-1-000050/2026":"Concreto usinado C20 com brita 0 e 1"}
ja={x["Edital PNCP"] for x in L}
for c,prd in EXTRA.items():
    r=T.get(c)
    if not r: continue
    m=re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})",c); lk=f"https://pncp.gov.br/app/editais/{m.group(1)}/{m.group(3)}/{m.group(2)}"
    if lk in ja: continue
    f=datetime.strptime(r[7][:16],"%Y-%m-%dT%H:%M")
    if f<=agora: continue
    p_=G.get((nm(r[2]),r[3]))
    L.append({"Encerra":f"{f:%d/%m/%Y %H:%M}","f":f,"Município":r[2],"UF":r[3],"Órgão":r[1],"Produtos":prd,"Soma agregados":r[5],"Modalidade":r[4],"Portal":r[9],"Edital PNCP":lk,"Tipo":"Fornecimento de material",
              "km":round(min(km(p_,b) for b in BASE.values())) if p_ else None})
# sprints semanais (seg-dom), sprint 0 = hoje até domingo
def seg(d): return d-timedelta(days=d.weekday())
S0_fim=seg(hoje)+timedelta(days=6)
SPR=[("Sprint 0 · Preparação",hoje,S0_fim),("Sprint 1",S0_fim+timedelta(1),S0_fim+timedelta(7)),("Sprint 2",S0_fim+timedelta(8),S0_fim+timedelta(14)),
     ("Sprint 3",S0_fim+timedelta(15),S0_fim+timedelta(21)),("Sprint 4",S0_fim+timedelta(22),date(hoje.year,12,31)),("Contínuo · 2027",date(hoje.year+1,1,1),date(2030,1,1))]
def spr(d):
    for n,a,b in SPR:
        if a<=d<=b: return n
    return SPR[-1][0]
for x in L:
    x["spr"]=spr(x["f"].date())
    # prioridade: perto da base primeiro, depois valor
    x["prio"]="A · até 150 km de Serro/Diamantina" if x["km"] is not None and x["km"]<=150 else "B · MG e vizinhos (até 500 km)" if x["km"] is not None and x["km"]<=500 else "C · resto do Brasil (frete alto)"
TAREFAS=["Ler edital e termo de referência","Conferir local de entrega e se o frete é por conta do fornecedor","Cotar com pedreira/areal (preço posto na obra)","Montar planilha de preço (mín. 10% abaixo do estimado)","Separar documentos de habilitação","Cadastrar/credenciar no portal da disputa","Enviar proposta até o prazo","Disputa de lances / negociação","Enviar documentos e amostra se pedida","Acompanhar resultado e homologação"]
AZ="1F3A5F"; H=Font(bold=True,color="FFFFFF"); HF=PatternFill("solid",fgColor=AZ); Bd=Side(style="thin",color="D0D5DD"); BD=Border(left=Bd,right=Bd,top=Bd,bottom=Bd)
PC={"A":("DCFAE6","067647"),"B":("FEF0C7","B54708"),"C":("F2F4F7","475467")}
def cab(ws,row,cols,w):
    for j,t in enumerate(cols,1):
        c=ws.cell(row=row,column=j,value=t); c.font=H; c.fill=HF; c.alignment=Alignment(wrap_text=True,vertical="center"); c.border=BD
    for j,x in enumerate(w,1): ws.column_dimensions[get_column_letter(j)].width=x
wb=Workbook(); ws=wb.active; ws.title="Plano"
ws["A1"]="Plano em sprints · brita, areia e agregados (licitações abertas)"; ws["A1"].font=Font(bold=True,size=15,color=AZ)
ws["A2"]=f"Gerado em {agora:%d/%m/%Y %H:%M} a partir do PNCP. Prioridade A = até 150 km de Serro/Diamantina (frete viável)."; ws["A2"].font=Font(italic=True,color="667085")
cab(ws,4,["Sprint","Período","Licitações que encerram","Prioridade A","Prioridade B","Soma agregados (A+B)","Foco"],[24,22,14,12,12,20,70])
FOCO={"Sprint 0 · Preparação":"Documentos de habilitação, cadastro nos portais, tabela de preço com as pedreiras/areais. Propostas que vencem até domingo.",
      "Sprint 1":"Propostas da semana. Começar pelas A, depois as B maiores.","Sprint 2":"Propostas da semana + acompanhar resultados da Sprint 1.",
      "Sprint 3":"Propostas da semana + recursos/homologação.","Sprint 4":"Fim do ano: credenciamentos de Diamantina (31/12) e o que encerra até 31/12.",
      "Contínuo · 2027":"Credenciamentos longos (entram a qualquer momento) e editais de 2027."}
r=5
for n,a,b in SPR:
    xs=[x for x in L if x["spr"]==n]; ab=[x for x in xs if x["prio"][0] in "AB"]
    v=[n,f"{a:%d/%m} a {b:%d/%m/%Y}" if n!="Contínuo · 2027" else "jan/2027 em diante",len(xs),sum(1 for x in xs if x["prio"][0]=="A"),sum(1 for x in xs if x["prio"][0]=="B"),sum(x["Soma agregados"] or 0 for x in ab),FOCO[n]]
    for j,val in enumerate(v,1):
        c=ws.cell(row=r,column=j,value=val); c.border=BD; c.alignment=Alignment(wrap_text=True,vertical="top")
        if j==6: c.number_format='"R$" #,##0'
    r+=1
r+=1; ws.cell(row=r,column=1,value="DOCUMENTOS DE HABILITAÇÃO (separar na Sprint 0)").font=Font(bold=True,color=AZ); r+=1
DOCS=["Contrato social / CCMEI e cartão CNPJ com CNAE de comércio de materiais de construção ou extração de pedra/areia","Certidão federal e INSS (Receita/PGFN)","CRF do FGTS","CNDT (débitos trabalhistas)","Certidões estadual e municipal","Certidão de falência e recuperação judicial","Balanço patrimonial e índices (se o edital pedir)","Atestado de capacidade técnica de fornecimento parecido (brita/areia)","Declarações: ME/EPP, menor, fato impeditivo, inexistência de vínculo (modelos do edital)","Para areia/brita de extração própria: licença ambiental e título na ANM (pedido nos credenciamentos de Diamantina)","Alvará de funcionamento","Dados bancários e procuração do representante"]
for d_ in DOCS:
    c=ws.cell(row=r,column=1,value="☐"); c2=ws.cell(row=r,column=2,value=d_); ws.merge_cells(start_row=r,start_column=2,end_row=r,end_column=7); r+=1
r+=1; ws.cell(row=r,column=1,value="PORTAIS ONDE CADASTRAR (nº de licitações abertas)").font=Font(bold=True,color=AZ); r+=1
pc=collections.Counter(x["Portal"] or "NÃO LOCALIZADO" for x in L)
for p_,n_ in pc.most_common(12):
    ws.cell(row=r,column=1,value="☐"); ws.cell(row=r,column=2,value=p_); ws.cell(row=r,column=3,value=n_); r+=1
dv_cols=["Status","Responsável"]
for n,a,b in SPR:
    xs=sorted([x for x in L if x["spr"]==n],key=lambda x:(x["prio"],x["f"],-(x["Soma agregados"] or 0)))
    if not xs: continue
    w=wb.create_sheet(n.split(" ·")[0].replace(" ","")); w["A1"]=f"{n} · {a:%d/%m} a {b:%d/%m/%Y}" if n!="Contínuo · 2027" else n; w["A1"].font=Font(bold=True,size=14,color=AZ)
    w["A2"]=FOCO[n]; w["A2"].font=Font(italic=True,color="667085")
    cols=["Prioridade","Encerra","Município","UF","Distância (km)","Órgão","Produtos","Soma agregados","Modalidade","Portal","Edital PNCP","Status","Responsável"]+TAREFAS
    cab(w,4,cols,[22,17,20,5,10,30,36,16,18,24,40,14,14]+[11]*len(TAREFAS))
    dv=DataValidation(type="list",formula1='"A fazer,Em andamento,Proposta enviada,Ganhou,Perdeu,Desistiu"',allow_blank=True); w.add_data_validation(dv)
    ck=DataValidation(type="list",formula1='"☐,☑"',allow_blank=True); w.add_data_validation(ck)
    for k,x in enumerate(xs,5):
        v=[x["prio"],f"{x['f']:%d/%m/%Y %H:%M}",x["Município"],x["UF"],x["km"],x["Órgão"],x["Produtos"],x["Soma agregados"],x["Modalidade"],x["Portal"],x["Edital PNCP"],"A fazer",""]+["☐"]*len(TAREFAS)
        for j,val in enumerate(v,1):
            c=w.cell(row=k,column=j,value=val); c.border=BD; c.alignment=Alignment(vertical="top",wrap_text=j in (6,7))
            if j==8: c.number_format='"R$" #,##0'
            if j==11: c.hyperlink=val; c.font=Font(color="1D4ED8",underline="single")
            if j>13: c.alignment=Alignment(horizontal="center")
        fc,tc=PC[x["prio"][0]]; c=w.cell(row=k,column=1); c.fill=PatternFill("solid",fgColor=fc); c.font=Font(bold=True,color=tc)
        dv.add(w.cell(row=k,column=12)); 
        for j in range(14,14+len(TAREFAS)): ck.add(w.cell(row=k,column=j))
    w.auto_filter.ref=f"A4:{get_column_letter(len(cols))}{4+len(xs)}"; w.freeze_panes="D5"
wb.save(OUT)
# texto
mi=lambda v:"não divulgado" if not v else (f"R$ {v/1e6:.2f} mi".replace(".",",") if v>=1e6 else f"R$ {v/1e3:.0f} mil")
SEM=["seg","ter","qua","qui","sex","sáb","dom"]
t=[f"*🏃 SPRINTS · BRITA, AREIA E AGREGADOS · {agora:%d/%m/%Y}*",f"{len(L)} licitações de fornecimento abertas no Brasil. Prioridade *A* = até 150 km de Serro/Diamantina ({sum(1 for x in L if x['prio'][0]=='A')}); *B* = até 500 km ({sum(1 for x in L if x['prio'][0]=='B')}); C = resto do Brasil, frete alto ({sum(1 for x in L if x['prio'][0]=='C')})."]
for n,a,b in SPR:
    xs=sorted([x for x in L if x["spr"]==n and x["prio"][0] in "AB"],key=lambda x:(x["prio"],-(x["Soma agregados"] or 0)))
    t.append(f"\n*{n}* · {a:%d/%m}–{b:%d/%m}" if n!="Contínuo · 2027" else f"\n*{n}*")
    t.append(f"🎯 {FOCO[n]}")
    if n.startswith("Sprint 0"): t.append("☐ Documentos de habilitação (lista na planilha)\n☐ Cadastro nos portais: "+", ".join(p for p,_ in pc.most_common(4))+"\n☐ Tabela de preço com pedreira/areal (brita 0 e 1, pó de pedra, areia fina/média/grossa)")
    for x in xs[:8]:
        t.append(f"• {x['prio'][0]} · {x['Município']}/{x['UF']}"+(f" ({x['km']} km)" if x['km'] is not None else "")+f" · {mi(x['Soma agregados'])} · {SEM[x['f'].weekday()]} {x['f']:%d/%m}{x['f'].strftime('/%Y') if x['f'].year!=agora.year else ''} {x['f']:%H:%M} · {x['Portal']}\n  🔗 {x['Edital PNCP']}")
    if len(xs)>8: t.append(f"• … mais {len(xs)-8} A/B nesta sprint (ver planilha)")
    if not xs: t.append("• Nenhuma A/B encerrando nesta sprint.")
open(TXT,"w").write("\n".join(t))
print(collections.Counter((x["spr"],x["prio"][0]) for x in L))
