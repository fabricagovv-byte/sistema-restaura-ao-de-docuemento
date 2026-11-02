"""Análise dos editais abertos com grande volume de UST, pagamento mensal, PF, páginas e dados (pelos itens)."""
import json, sys, collections, statistics
from licitacoes.db import sessao
from licitacoes.modelos import Licitacao, Item, agora
from licitacoes.coleta import abertas_filtro
from licitacoes.taxonomia import tipo_volume, natureza, VOLUMES
num = lambda v: float(v) if v is not None else None  # noqa: E731
SEG = {"ti", "gestao_documental", "educacao_pesquisa"}
with sessao() as s:
    ab = [l for l in s.query(Licitacao).filter(abertas_filtro()).all() if l.tipo_registro == "contratacao"]
    its = collections.defaultdict(list)
    for i in s.query(Item).filter(Item.licitacao_id.in_([l.id for l in ab])).yield_per(2000):
        its[i.licitacao_id].append(i)
    com_itens = [l for l in ab if its.get(l.id)]
    por = collections.defaultdict(list)
    for l in com_itens:
        tec = any(c["segmento"] in SEG for c in l.categorias or [])
        acc = {}
        for i in its[l.id]:
            if (i.material_servico or "").lower().startswith("m"):
                continue
            q = num(i.quantidade) or 0
            k = tipo_volume(i.unidade, i.descricao, q)
            if not k:
                continue
            if k in ("ust", "pf", "hora", "mes") and tipo_volume(i.unidade, None, q) != k:
                continue  # UST/PF/hora/mês só quando a própria unidade diz
            if k == "mes" and not tec:
                continue  # mensal: só editais de tecnologia/documentos
            a = acc.setdefault(k, {"qtd": 0.0, "valor": 0.0, "n": 0, "qmax": 0.0, "itens": []})
            vu = num(i.valor_unitario)
            vt = num(i.valor_total) or ((vu or 0) * q)
            a["qtd"] += q; a["n"] += 1; a["qmax"] = max(a["qmax"], q); a["valor"] += vt or 0
            a["itens"].append([i.numero, " ".join((i.descricao or "").split())[:160], q, (i.unidade or "").strip(), vu, vt])
        for k, a in acc.items():
            a["itens"].sort(key=lambda x: -(x[2] or 0))
            por[k].append({"id": l.id, "o": l.orgao_nome, "uf": l.uf, "m": l.municipio, "obj": " ".join((l.objeto or "").split())[:280],
                           "v": num(l.valor_estimado), "enc": l.data_encerramento.strftime("%Y-%m-%dT%H:%M") if l.data_encerramento else None,
                           "mod": l.modalidade, "n": l.numero_compra, "pncp": l.link_pncp, "plat": l.plataforma_origem,
                           "qtd": round(a["qtd"], 2), "qmax": a["qmax"], "nitens": a["n"], "valor_itens": round(a["valor"], 2),
                           "unit": round(a["valor"] / a["qtd"], 4) if a["qtd"] and a["valor"] else None,
                           "grande": (a["valor"] >= 1_000_000 if k == "mes" else a["qtd"] >= VOLUMES[k][1]), "itens": a["itens"][:6]})
    res = {"gerado": agora().strftime("%d/%m/%Y %H:%M"), "abertas": len(ab), "com_itens": len(com_itens), "tipos": {}}
    for k, lst in por.items():
        lst.sort(key=lambda x: -(x["valor_itens"] if k == "mes" else x["qtd"]))
        us = sorted(x["unit"] for x in lst if x["unit"])
        qs = statistics.quantiles(us, n=4) if len(us) >= 4 else None
        res["tipos"][k] = {"editais": len(lst), "grandes": sum(1 for x in lst if x["grande"]), "qtd": round(sum(x["qtd"] for x in lst)),
                           "valor": round(sum(x["valor_itens"] for x in lst)), "unit_med": round(statistics.median(us), 4) if us else None,
                           "unit_q1": round(qs[0], 4) if qs else None, "unit_q3": round(qs[2], 4) if qs else None, "n_unit": len(us),
                           "por_uf": collections.Counter(x["uf"] for x in lst).most_common(), "lista": lst}
        t = res["tipos"][k]
        print(f"{k}: {t['editais']} editais ({t['grandes']} grandes), qtd {t['qtd']:,}, R$ {t['valor']/1e6:.1f} mi, unit med {t['unit_med']} [{t['unit_q1']}–{t['unit_q3']}] n={t['n_unit']}")
        for x in lst[:4]:
            print(f"    {x['qtd']:>12,.0f} {x['uf']} {x['o'][:38]:38} R$ {x['valor_itens']/1e6:6.2f} mi  unit {x['unit']}")
    json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False)
