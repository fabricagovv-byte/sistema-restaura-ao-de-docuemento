"""Leads do dia em texto de WhatsApp: fixo mensal TI, UST/PF, desenvolvimento de software, serviços TIC, digitalização.
Base: lista completa de hoje (todas.json, PNCP). Volume (UST/PF/páginas/horas) só quando lido no edital pelas buscas dos temas.
Uso: python3 leads.py todas.json pasta_saida tema_dir1 tema_dir2 ..."""
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

todas, saida, temas = sys.argv[1], sys.argv[2], sys.argv[3:]
D = json.load(open(todas))
agora = datetime.now(timezone.utc) - timedelta(hours=3)
AG = agora.strftime("%Y-%m-%dT%H:%M")
MIN_FIM = (agora + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M")  # precisa dar tempo de preparar proposta
SUS = 2e9


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


# volumes e notas lidos nos editais pelas buscas dos temas
VOL, NOTA, MENSAL = {}, {}, {}
UNID = {"ust": "UST", "ust_doc": "UST", "pf": "PF", "pf_doc": "PF", "hora": "horas", "pagina": "páginas", "caixa": "caixas",
        "metro_linear": "metros lineares", "registro": "registros"}
for t in temas:
    try:
        L = json.load(open(f"{t}/ultima.json"))["licitacoes"]
    except (OSError, ValueError, KeyError):
        continue
    for e in L:
        c = e["numero_controle_pncp"]
        NOTA[c] = max(NOTA.get(c, 0), e.get("nota") or 0)
        if e.get("mensal") and e["mensal"] >= 1000 and 1 <= (e.get("meses") or 12) <= 120:
            MENSAL[c] = (e["mensal"], e.get("meses"))
        vs, out = set(), []
        for k, q in (e.get("vol") or {}).items():
            u = UNID.get(k)
            if u and q and q >= 10 and u not in vs:
                vs.add(u)
                out.append(f"{q:,.0f}".replace(",", ".") + f" {u}")
        if out:
            VOL[c] = " · ".join(out)

FORA_TI = r"aquisicao de (computador|notebook|equipamento|microcomputador|impressora|toner|cartucho)|material de informatica|equipamentos de informatica|radiolog|raio[ -]?x|mamogra|tomograf|odontolog|veicul|combustivel|merenda|aliment|obra|pavimenta|reforma|medicament|ambulancia|uniforme"
CATS = [
    ("ust", "⚙️ UST E PONTO DE FUNÇÃO",
     r"\bust\b|\busts\b|unidades? de servicos? tecnicos?|pontos? de funcao|\bpf\b.{0,40}(software|sistema)|(software|sistema).{0,40}\bpf\b"),
    ("dev", "💻 DESENVOLVIMENTO E SUSTENTAÇÃO DE SOFTWARE",
     r"desenvolvimento (e (manutencao|sustentacao) )?(de |do |dos )?(novos? )?(software|sistemas?|aplicativos?|aplicacoes|solucoes? (tecnologica|digita)|portal|plataforma)|sustentacao de (sistemas|software|aplicacoes)|manutencao (evolutiva|corretiva|adaptativa)[^.;]{0,40}(software|sistemas? de informac|aplicac)|fabrica de software|devops|desenvolvimento web"),
    ("mensal", "📆 FIXO MENSAL DE TI (locação/licença/SaaS)",
     r"(locacao|licenciamento|licenca|cessao (de direito )?de uso|subscricao|assinatura|software como servico|\bsaas\b|hospedagem|computacao em nuvem|servicos? de nuvem|provimento)[^.;]{0,80}(software|sistemas?|solucao|plataforma|aplicativo|tecnologia|nuvem|informatica)|sistemas? (integrados? )?de gestao (publica|municipal|integrada)|\berp\b|sistema de (folha|contabilidade|tributos|arrecadacao|protocolo|saude|educacao)"),
    ("tic", "🛠️ OUTROS SERVIÇOS DE TIC (suporte, infra, dados, segurança)",
     r"service desk|help ?desk|central de servicos|suporte tecnico (de|em|a) (ti|informatica|usuarios|sistemas)|outsourcing|data ?center|seguranca da informacao|ciberseguranca|\bsoc\b|\bnoc\b|business intelligence|ciencia de dados|inteligencia artificial|banco de dados|infraestrutura de (ti|tecnologia)|servicos? (gerenciados|continuados) de (ti|tecnologia)|tecnologia da informacao e comunicacao|\btic\b|servicos de tecnologia da informacao|rede (logica|corporativa)|link de (dados|internet)|conectividade|telefonia ip|transformacao digital"),
    ("doc", "📄 DIGITALIZAÇÃO E GESTÃO DOCUMENTAL",
     r"digitaliza|indexa|gestao documental|gestao arquivistica|\bged\b|\becm\b|microfilm|guarda (externa )?de (documentos|acervo|arquivos?)|tratamento (documental|arquivistico|de acervo)|organizacao de (acervo|arquivo|documentos)|escaneamento|higienizacao de documentos|custodia de documentos"),
]
FORA_SERV = r"seguranca eletronica|videomonitoramento|outsourcing de impressao|impressao corporativa|servicos? de impressao|alarme|cftv|camera|camara|gravador|motobomba|bombas?\b|automacao predial|climatiza|ar condicionado|elevador|gerador|incendio|estruturas? para|tendas?|palco|sonoriza|eventos|banheiro|revendedora|large solution|microsoft|oracle corporation"
FORA_DOC = r"radiolog|raio[ -]?x|mamogra|imagens? (medica|radiolog)|placa de video|digitalizacao de imagens? (radio|medic)|tv digital|certificado digital|assinatura digital"
RX = {k: re.compile(r) for k, _, r in CATS}
grupos = {k: [] for k, _, _ in CATS}
vistos = set()
for r in D["registros"]:
    c, org, mun, uf, mod, v, sig, fim, obj, portal, ass, esf, ini = r
    if not fim or fim <= MIN_FIM or fim[:4] > str(agora.year + 2):
        continue
    o = norm(obj)
    if ini and ini < (agora - timedelta(days=120)).strftime("%Y-%m-%d"):
        continue  # aberta há mais de 4 meses (credenciamento antigo): fora dos leads do dia
    if (org, v) in vistos and v:
        continue  # republicação/lote duplicado do mesmo órgão e valor
    if re.search(FORA_SERV, o) and not RX["doc"].search(o):
        continue
    vol = VOL.get(c, "")
    if re.search(FORA_TI, o) and not re.search(r"software|sistema|digitaliza|servicos? de (ti|tecnologia)", o):
        continue
    for k, _, _ in CATS:
        if not (RX[k].search(o) or (k == "ust" and re.search(r"UST|PF", vol) and not RX["doc"].search(o))):
            continue
        if k == "doc" and re.search(FORA_DOC, o):
            continue
        if k in ("dev", "mensal", "tic") and ass not in ("Tecnologia (TI)", "Gestão documental", "Educação e cultura", "Outros"):
            continue
        vv = v if v and v < SUS else 0
        score = (NOTA.get(c, 0) * 2e5) + vv + (5e6 if c in VOL else 0) + (1e6 if re.search(r"preg|concorr", norm(mod)) else 0)
        grupos[k].append((score, r)); vistos.add((org, v))
        break  # cada licitação em uma categoria só (a primeira que casar, na ordem acima)


def mi(v):
    if not v:
        return "valor não divulgado"
    if v >= SUS:
        return "valor a conferir"
    return f"R$ {v/1e9:.2f} bi".replace(".", ",") if v >= 1e9 else f"R$ {v/1e6:.1f} mi".replace(".", ",") if v >= 1e6 else f"R$ {v/1e3:.0f} mil" if v >= 1e3 else f"R$ {v:,.0f}".replace(",", ".")


def link(c):
    m = re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})", c)
    return f"https://pncp.gov.br/app/editais/{m.group(1)}/{m.group(3)}/{m.group(2)}"


def dt(s):
    return f"{s[8:10]}/{s[5:7]}{'/' + s[:4] if s[:4] != str(agora.year) else ''} {s[11:16]}"


def tit(s):
    s = " ".join(s.split())
    return s.title().replace(" De ", " de ").replace(" Da ", " da ").replace(" Do ", " do ").replace(" Dos ", " dos ").replace(" Das ", " das ").replace(" E ", " e ")


def curto(s, n):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


TOP = 8
hoje = agora.strftime("%d/%m/%Y")
msgs = []
cab = (f"*🎯 LEADS DO DIA · {hoje}*\nFonte: PNCP (inclui portais parceiros que publicam lá) · lista completa de hoje "
       f"({len(D['registros']):,}".replace(",", ".") + f" licitações abertas, verificada {dt(D['verificado_em'])})." +
       "\nSó prazo de proposta aberto com pelo menos 1 dia e edital aberto nos últimos 4 meses. Ordem: nota da busca + valor + volume lido no edital. ⚠️ = encerra em até 2 dias.")
msgs.append(cab)
resumo = []
for k, nome, _ in CATS:
    L = sorted(grupos[k], key=lambda x: -x[0])
    soma = sum(r[5] for _, r in L if r[5] and r[5] < SUS)
    resumo.append(f"{nome.split(' ', 1)[0]} {len(L)}")
    linhas = [f"*{nome}*", f"{len(L)} abertas · soma estimada {mi(soma)} · as {min(TOP, len(L))} melhores:"]
    top = 12 if k == "ust" else TOP
    linhas[1] = f"{len(L)} abertas · soma estimada {mi(soma)} · as {min(top, len(L))} melhores:"
    for i, (_, r) in enumerate(L[:top], 1):
        c, org, mun, uf, mod, v, sig, fim, obj = r[:9]
        alerta = " ⚠️" if fim <= (agora + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M") else ""
        extra = f" · 📦 *{VOL[c]}*" if c in VOL else ""
        if c in MENSAL:
            m, mm = MENSAL[c]
            extra += f" · 🗓️ {mi(m)}/mês" + (f" × {mm} meses" if mm else "")
        linhas.append(f"\n*{i}. {tit(org)}* ({mun}/{uf})\n{curto(obj, 150)}\n💰 *{mi(v) if not sig else 'sigiloso'}*{extra}\n📅 Encerra {dt(fim)}{alerta} · {mod}\n🔗 {link(c)}")
    if not L:
        linhas.append("NÃO LOCALIZADO nenhuma aberta hoje.")
    msgs.append("\n".join(linhas))
msgs[0] += "\n\n" + " · ".join(resumo)
for i, m in enumerate(msgs):
    open(f"{saida}/lead-{i}.txt", "w").write(m)
json.dump({nome: [link(r[0]) for _, r in sorted(grupos[k], key=lambda x: -x[0])] for k, nome, _ in CATS},
          open(f"{saida}/todos.json", "w"), ensure_ascii=False)
open(f"{saida}/leads-do-dia.txt", "w").write("\n\n————————————\n\n".join(msgs))
print("\n".join(f"{k}: {len(v)}" for k, v in grupos.items()))
