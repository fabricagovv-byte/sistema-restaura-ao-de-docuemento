# Painel estático (artifact)

Gera o painel publicado como página do Claude: licitações abertas, ficha de cada pregão, precificação
por pisos, pesquisa de preços, CRM privado, mapa e distância da sede.

```bash
cd plataforma-licitacoes/backend
export PYTHONPATH=. LIC_DATABASE_URL=postgresql+psycopg://licit:licit@localhost/licitacoes
python3 -m licitacoes.cli importar-coleta <pasta do branch dados-licitacoes>
python3 ../painel-estatico/exportar_painel.py ../painel-estatico/painel_dados.json
python3 ../painel-estatico/montar_painel.py ../painel-estatico/painel_modelo.html ../painel-estatico/painel_dados.json saida.html
```

* `painel_modelo.html`: página com marcadores `__DADOS__`, `__CATS__`, `__PRIO__`, `__TODAS__`, `__GEO__`, `__GERADO__`.
* Dados do usuário (CRM, precificações, sede e pisos) ficam no banco da página, em `data/users/<id>/`,
  privado por pessoa; fora do Claude, no armazenamento do navegador. Capacidades: `db`, `user`, `downloads`.
* `geo/municipios.csv`: coordenadas dos municípios, de kelvins/municipios-brasileiros (MIT).
* `testes/*.js`: verificações com Playwright (`node testes/crm.js saida.html`).
