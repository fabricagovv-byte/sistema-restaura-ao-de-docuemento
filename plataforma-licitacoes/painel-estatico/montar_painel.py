import base64, gzip, json, sys
from licitacoes.taxonomia import PADRAO, REMUNERACAO, GRUPOS, OUTROS_TI
from licitacoes.config import config
modelo, dados, saida = sys.argv[1:4]
D = json.load(open(dados))
todas = base64.b64encode(gzip.compress(json.dumps(D.pop("todas", []), ensure_ascii=False, separators=(",", ":")).encode(), 9)).decode()
cats = {**REMUNERACAO, **{c.codigo: c.nome for c in PADRAO}, OUTROS_TI[0]: OUTROS_TI[1]}
grupos = [[g, n, cs] for g, n, cs in GRUPOS]
# coordenadas dos municípios (kelvins/municipios-brasileiros, MIT) para o mapa e a distância até a sede
import csv, os
UF = {11:"RO",12:"AC",13:"AM",14:"RR",15:"PA",16:"AP",17:"TO",21:"MA",22:"PI",23:"CE",24:"RN",25:"PB",26:"PE",27:"AL",28:"SE",29:"BA",
      31:"MG",32:"ES",33:"RJ",35:"SP",41:"PR",42:"SC",43:"RS",50:"MS",51:"MT",52:"GO",53:"DF"}
geo = [[r["codigo_ibge"], r["nome"], UF[int(r["codigo_uf"])], round(float(r["latitude"]), 4), round(float(r["longitude"]), 4)]
       for r in csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(dados)), "geo", "municipios.csv"), encoding="utf-8"))]
j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("\ufffd", "")  # caractere perdido na origem
# pesquisa nacional ao vivo no PNCP (licitacoes-ti-abertas.json da pasta docs/pesquisas/<data>), opcional
pesq = {"meta": None, "itens": []}
if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
    P = json.load(open(sys.argv[4]))
    docs = lambda e, f: [a["url"] for a in e.get("arquivos") or [] if f(a)][:2]  # noqa: E731
    pesq = {"meta": {"verificado": P.get("verificado_em_txt") or "", "examinados": P["resumo"]["examinados"], "termos": 71},
            "itens": [{"c": e["numero_controle_pncp"], "n": e["nota"], "a": e["area"], "o": e["orgao_nome"], "m": e.get("municipio_nome"),
                       "uf": e.get("uf"), "mod": e.get("modalidade"), "num": e.get("numero"), "proc": e.get("processo"), "v": e.get("valor"),
                       "vs": e.get("valor_suspeito"), "vol": {k: q for k, q in (e.get("vol") or {}).items() if k in ("ust", "pf", "hora", "pagina")},
                       "ab": e.get("abertura"), "enc": e.get("encerramento"), "srp": bool(e.get("srp")), "pl": e.get("plataforma"),
                       "obj": " ".join((e.get("objeto") or "").split())[:500], "lp": e.get("link_pncp"), "lo": e.get("link_origem"), "men": bool(e.get("mensal")),
                       "ed": docs(e, lambda a: (a.get("tipo") or "").lower().startswith("edital")),
                       "tr": docs(e, lambda a: "refer" in (a.get("tipo") or "").lower())} for e in P["lista"]]}
h = open(modelo).read().replace("__DADOS__", j(D)).replace("__CATS__", j(cats)).replace("__GRUPOS__", j(grupos)).replace("__PESQUISA__", j(pesq)).replace("__PRIO__", j(list(config().prioritarias))).replace("__GERADO__", D["gerado"]).replace("__TODAS__", todas).replace("__GEO__", j(geo))
open(saida, "w").write(h)
print(len(h)//1024, "KB", len(cats), "categorias")
