import base64, gzip, json, sys
from licitacoes.taxonomia import PADRAO, REMUNERACAO
from licitacoes.config import config
modelo, dados, saida = sys.argv[1:4]
D = json.load(open(dados))
todas = base64.b64encode(gzip.compress(json.dumps(D.pop("todas", []), ensure_ascii=False, separators=(",", ":")).encode(), 9)).decode()
cats = {**REMUNERACAO, **{c.codigo: c.nome for c in PADRAO}}
# coordenadas dos municípios (kelvins/municipios-brasileiros, MIT) para o mapa e a distância até a sede
import csv, os
UF = {11:"RO",12:"AC",13:"AM",14:"RR",15:"PA",16:"AP",17:"TO",21:"MA",22:"PI",23:"CE",24:"RN",25:"PB",26:"PE",27:"AL",28:"SE",29:"BA",
      31:"MG",32:"ES",33:"RJ",35:"SP",41:"PR",42:"SC",43:"RS",50:"MS",51:"MT",52:"GO",53:"DF"}
geo = [[r["codigo_ibge"], r["nome"], UF[int(r["codigo_uf"])], round(float(r["latitude"]), 4), round(float(r["longitude"]), 4)]
       for r in csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(dados)), "geo", "municipios.csv"), encoding="utf-8"))]
j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
h = open(modelo).read().replace("__DADOS__", j(D)).replace("__CATS__", j(cats)).replace("__PRIO__", j(list(config().prioritarias))).replace("__GERADO__", D["gerado"]).replace("__TODAS__", todas).replace("__GEO__", j(geo))
open(saida, "w").write(h)
print(len(h)//1024, "KB", len(cats), "categorias")
