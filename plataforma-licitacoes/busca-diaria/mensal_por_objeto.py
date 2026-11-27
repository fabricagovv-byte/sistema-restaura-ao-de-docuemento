"""Tema 'fixo mensal de TI' de hoje sem a leitura lenta de editais: triagem pelo objeto na lista completa de hoje,
aproveitando valor mensal/meses/volume já lidos em buscas anteriores (mensal_diaria). Saída no formato ultima.json.
Uso: python3 mensal_hoje.py todas.json mensal_antigo_dir saida_dir"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

todas, antigo, saida = sys.argv[1:4]
agora = datetime.now(timezone.utc) - timedelta(hours=3)
AG = agora.strftime("%Y-%m-%dT%H:%M")
norm = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()  # noqa: E731
MENSAL = re.compile(r"(locacao|licenciamento|licenca|cessao (de direito )?de uso|direito de uso|subscricao|assinatura|software como servico|\bsaas\b|hospedagem|computacao em nuvem|servicos? de nuvem|provimento)[^.;]{0,90}(software|sistemas?|solucao|plataforma|aplicativo|tecnologia|nuvem|informatica|\berp\b)|sistemas? (integrados? )?de gestao (publica|municipal|integrada|em saude|hospitalar|escolar|tributaria)|\berp\b|sistemas? informatizados? (de|para) gestao|solucao (tecnologica )?integrada de gestao|outsourcing de (ti|infraestrutura)|service desk|link de (dados|internet)|internet dedicada")
FORA = re.compile(r"aquisicao de (computador|notebook|equipamentos|impressora)|veicul|combustivel|obra|aliment|medicament|impressao|cameras?|cftv|alarme|telefonia movel|microsoft|autodesk|adobe|oracle|vmware|antivirus")
old = {}
try:
    old = {e["numero_controle_pncp"]: e for e in json.load(open(f"{antigo}/ultima.json"))["licitacoes"]}
except (OSError, ValueError, KeyError):
    pass
out = []
for r in json.load(open(todas))["registros"]:
    c, org, mun, uf, mod, v, sig, fim, obj, portal, ass, esf, ini = r
    if not fim or fim <= AG or fim[:4] > str(agora.year + 2) or (ini and ini < (agora - timedelta(days=150)).strftime("%Y-%m-%d")):
        continue
    o = norm(obj)
    if not MENSAL.search(o) or FORA.search(o) or ass not in ("Tecnologia (TI)", "Gestão documental", "Educação e cultura", "Saúde", "Outros"):
        continue
    e = old.get(c, {})
    vv = v if v and v < 2e9 else 0
    nota = e.get("nota") or min(95, 40 + (30 if vv >= 1e7 else 22 if vv >= 1e6 else 12 if vv >= 3e5 else 5) + (10 if re.search(r"preg", norm(mod)) else 0))
    m = re.match(r"(\d{14})-\d-0*(\d+)/(\d{4})", c)
    out.append({"numero_controle_pncp": c, "orgao_nome": org, "municipio_nome": mun, "uf": uf, "modalidade": mod, "valor": v, "objeto": obj,
                "encerramento": fim + ":00", "abertura": (ini or "") + ":00" if ini else None, "situacao": "Divulgada no PNCP", "nota": nota,
                "vol": e.get("vol") or {}, "mensal": e.get("mensal"), "meses": e.get("meses"), "link_origem": e.get("link_origem"),
                "link_pncp": f"https://pncp.gov.br/app/editais/{m.group(1)}/{m.group(3)}/{m.group(2)}"})
out.sort(key=lambda e: -e["nota"])
json.dump({"verificado_em": agora.strftime("%Y-%m-%dT%H:%M"), "abertas": len(out), "triagem": "objeto (sem leitura de edital)", "licitacoes": out},
          open(f"{saida}/ultima.json", "w"), ensure_ascii=False)
print(len(out), "fixo mensal no prazo")
