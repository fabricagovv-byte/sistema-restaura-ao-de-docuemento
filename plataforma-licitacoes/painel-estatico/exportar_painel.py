import json, collections, os, sys
from datetime import timedelta
from licitacoes.db import sessao
from licitacoes.modelos import Licitacao, agora
from licitacoes.coleta import abertas_filtro
from licitacoes import painel
from licitacoes.taxonomia import natureza, volumes, grande_volume, tipo_volume
SAIDA = sys.argv[1]
seg = {"gestao_documental", "ti", "educacao_pesquisa"}
fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M") if d else None  # noqa: E731
num = lambda v: float(v) if v is not None else None  # noqa: E731
limpa = lambda t, n: " ".join((t or "").split())[:n] or None  # noqa: E731
with sessao() as s:
    ab = s.query(Licitacao).filter(abertas_filtro()).all()
    contr = [l for l in ab if l.tipo_registro == "contratacao"]
    rel = [l for l in contr if any(c["segmento"] in seg for c in l.categorias or [])]
    out = []
    precos = collections.defaultdict(list)  # pesquisa de preços: valor unitário estimado por tipo de volume
    for l in rel:
        b = l.bruto or {}
        ii = l.itens
        for i in ii:
            k = tipo_volume(i.unidade, i.descricao, num(i.quantidade), num(i.valor_unitario))
            # só quando a própria unidade diz o tipo (ou digitalização em volume): "UST" citada na descrição
            # de um item cobrado por pacote daria preços sem sentido
            forte = k and (tipo_volume(i.unidade, None, num(i.quantidade), num(i.valor_unitario)) == k or (k == "pagina" and (num(i.quantidade) or 0) >= 10_000))
            if forte and not (i.material_servico or "").lower().startswith("m") and num(i.valor_unitario):
                precos[k].append([round(num(i.valor_unitario), 2), l.id, l.uf])
        vol = volumes([(i.unidade, i.descricao, num(i.quantidade), num(i.valor_unitario)) for i in ii if not (i.material_servico or "").lower().startswith("m")])
        out.append({"ms": natureza(l.objeto, [(i.material_servico, num(i.valor_total)) for i in ii]),
                    "ib": l.codigo_ibge, "vol": {k: round(q) for k, q in vol.items()}, "gv": grande_volume(vol, num(l.valor_estimado)),"id": l.id, "o": l.orgao_nome, "un": l.unidade_nome, "uf": l.uf, "m": l.municipio, "obj": limpa(l.objeto, 2500),
                    "inf": limpa(l.informacao_complementar, 1500), "v": num(l.valor_estimado), "pub": fmt(l.data_publicacao),
                    "ab": fmt(l.data_abertura), "enc": fmt(l.data_encerramento), "mod": l.modalidade, "md": l.modo_disputa,
                    "sit": l.situacao, "srp": l.srp, "n": l.numero_compra, "proc": l.processo, "amp": (b.get("amparoLegal") or {}).get("nome"),
                    "pncp": l.link_pncp, "orig": l.link_origem, "pe": b.get("linkProcessoEletronico"), "plat": l.plataforma_origem,
                    "c": [c["codigo"] for c in l.categorias if c["segmento"] in seg], "a": round(l.aderencia), "ctl": l.numero_controle_pncp,
                    "it": [[i.numero, limpa(i.descricao, 300), num(i.quantidade), i.unidade, num(i.valor_unitario), num(i.valor_total), tipo_volume(i.unidade, i.descricao, num(i.quantidade), num(i.valor_unitario))]
                           for i in sorted(l.itens, key=lambda x: x.numero)[:60]],
                    "nit": len(l.itens),
                    "doc": [[d.titulo, d.tipo, d.url, d.paginas] for d in sorted(l.documentos, key=lambda x: x.sequencial or 0)]})
    lim = agora() - timedelta(days=10)
    avisos = [l for l in s.query(Licitacao).filter(Licitacao.tipo_registro == "aviso_diario", Licitacao.data_publicacao >= lim).all()
              if any(c["segmento"] in seg for c in l.categorias or [])]
    av = [{"id": l.id, "m": l.municipio, "uf": l.uf, "d": fmt(l.data_publicacao), "t": limpa(l.objeto, 900), "url": l.link_origem,
           "c": [c["codigo"] for c in l.categorias if c["segmento"] in seg]} for l in sorted(avisos, key=lambda x: x.data_publicacao, reverse=True)]
    plat = collections.Counter((l.plataforma_origem or "não informado") for l in contr)
    q = painel.qualidade(s)
    dados = {"total_coletado": q["editais_coletados"], "abertas": len(contr), "relevantes": len(out),
             "por_uf": dict(collections.Counter(l.uf for l in contr)), "plataformas": plat.most_common(60), "n_plataformas": len(plat),
             "cobertura": {k: q["cobertura"][k] for k in ("municipios_na_base_ibge", "municipios_com_edital_90d", "percentual_comprovado")},
             "fontes": [{"nome": f["nome"], "saude": f["saude"], "editais": f["editais"]} for f in q["fontes"]],
             "gerado": agora().strftime("%d/%m/%Y"), "itens": out, "avisos": av, "precos": precos}
    ja = {x["id"] for x in out}
    dados["todas"] = [[l.id, l.orgao_nome, l.uf, l.municipio, limpa(l.objeto, 600), num(l.valor_estimado), fmt(l.data_encerramento),
                       l.modalidade, l.numero_compra, l.numero_controle_pncp, l.link_origem, l.plataforma_origem,
                       [c["codigo"] for c in l.categorias or []], natureza(l.objeto), l.codigo_ibge] for l in contr if l.id not in ja]
    json.dump(dados, open(SAIDA, "w"), ensure_ascii=False, separators=(",", ":"))
print("todas", len(dados["todas"]), "editais", len(out), "com itens", sum(1 for x in out if x["it"]), "com docs", sum(1 for x in out if x["doc"]),
      "avisos", len(av), "plataformas", len(plat), "bytes", os.path.getsize(SAIDA))
print(plat.most_common(15))
