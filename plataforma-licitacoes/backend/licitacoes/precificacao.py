"""Precificação de propostas.

Fórmula (preço por divisor, como no BDI):
    custo direto     = Σ quantidade × custo unitário (+ custos de fornecedores)
    custo total      = custo direto × (1 + despesas administrativas %)
    preço            = custo total ÷ (1 − tributos % − margem %)
Cada linha recebe o mesmo fator, então preço unitário = custo unitário × (1 + adm) ÷ (1 − trib − margem).
O valor estimado do edital aparece só como referência e nunca é tratado como preço calculado.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field

UNIDADES = {
    "pagina": "página", "caixa": "caixa", "metro_linear": "metro linear", "gb": "GB", "tb": "TB",
    "profissional": "profissional/mês", "hora": "hora técnica", "mes": "mês", "unidade": "unidade", "fixo": "valor fixo",
}


@dataclass
class LinhaCusto:
    descricao: str
    unidade: str
    quantidade: float
    custo_unitario: float
    item_edital: str | None = None


@dataclass
class ParametrosProposta:
    linhas: list[LinhaCusto]
    tributos_pct: float = 0.0            # sobre o preço (ISS, PIS, COFINS, IRPJ, CSLL…)
    despesas_adm_pct: float = 0.0        # sobre o custo
    margem_pct: float = 0.0              # sobre o preço
    custos_fornecedores: list[LinhaCusto] = field(default_factory=list)
    prazo_meses: int = 12
    descontos_pct: list[float] = field(default_factory=lambda: [0, 5, 10, 15, 20])
    valor_estimado_edital: float | None = None

    @classmethod
    def de_dict(cls, d: dict) -> ParametrosProposta:
        conv = lambda xs: [LinhaCusto(**x) for x in xs or []]  # noqa: E731
        return cls(linhas=conv(d.get("linhas")), tributos_pct=float(d.get("tributos_pct", 0)),
                   despesas_adm_pct=float(d.get("despesas_adm_pct", 0)), margem_pct=float(d.get("margem_pct", 0)),
                   custos_fornecedores=conv(d.get("custos_fornecedores")), prazo_meses=int(d.get("prazo_meses", 12)),
                   descontos_pct=[float(x) for x in d.get("descontos_pct", [0, 5, 10, 15, 20])],
                   valor_estimado_edital=d.get("valor_estimado_edital"))


def calcular(p: ParametrosProposta) -> dict:
    trib, adm, marg = p.tributos_pct / 100, p.despesas_adm_pct / 100, p.margem_pct / 100
    if trib + marg >= 1:
        raise ValueError("tributos + margem precisam somar menos de 100%")
    if not p.linhas:
        raise ValueError("informe ao menos uma linha de custo")
    fator = (1 + adm) / (1 - trib - marg)
    linhas = []
    for ln in p.linhas + p.custos_fornecedores:
        custo = ln.quantidade * ln.custo_unitario
        linhas.append({
            **asdict(ln), "unidade_nome": UNIDADES.get(ln.unidade, ln.unidade),
            "fornecedor": ln in p.custos_fornecedores, "custo_total": round(custo, 2),
            "preco_unitario": round(ln.custo_unitario * fator, 4), "preco_total": round(custo * fator, 2),
        })
    custo_direto = sum(x["custo_total"] for x in linhas)
    custo_total = custo_direto * (1 + adm)
    preco = custo_total / (1 - trib - marg)
    tributos = preco * trib
    margem = preco - tributos - custo_total
    sim = []
    for d in p.descontos_pct:
        pd = preco * (1 - d / 100)
        m = pd * (1 - trib) - custo_total
        sim.append({"desconto_pct": d, "preco": round(pd, 2), "margem_valor": round(m, 2),
                    "margem_pct": round(100 * m / pd, 2) if pd else 0.0, "prejuizo": m < 0})
    ref = None
    if p.valor_estimado_edital:
        ve = float(p.valor_estimado_edital)
        ref = {"valor_estimado_edital": ve, "natureza": "oficial (edital)",
               "preco_vs_estimado_pct": round(100 * (preco / ve - 1), 2), "desconto_implicito_pct": round(100 * (1 - preco / ve), 2)}
    return {
        "aviso": "Preço calculado com os custos informados pela empresa. Não é o valor oficial do edital.",
        "fator_preco": round(fator, 6), "linhas": linhas,
        "custo_direto": round(custo_direto, 2), "despesas_adm": round(custo_direto * adm, 2),
        "custo_total": round(custo_total, 2), "tributos": round(tributos, 2), "margem": round(margem, 2),
        "preco_total": round(preco, 2), "preco_mensal": round(preco / max(1, p.prazo_meses), 2),
        "prazo_meses": p.prazo_meses, "margem_pct_efetiva": round(100 * margem / preco, 2),
        "simulacoes": sim, "referencia_edital": ref,
        "parametros": {"tributos_pct": p.tributos_pct, "despesas_adm_pct": p.despesas_adm_pct, "margem_pct": p.margem_pct},
    }


def gerar_xlsx(resultado: dict, titulo: str) -> bytes:
    """Planilha editável: as células de preço são fórmulas, então mudar custo ou percentual recalcula tudo."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Proposta"
    negrito = Font(bold=True)
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = resultado["aviso"]
    ws["A2"].font = Font(italic=True, color="9C3D2E")
    par = resultado["parametros"]
    rotulos = [("Tributos (% do preço)", par["tributos_pct"] / 100), ("Despesas administrativas (% do custo)", par["despesas_adm_pct"] / 100),
               ("Margem de lucro (% do preço)", par["margem_pct"] / 100), ("Prazo do contrato (meses)", resultado["prazo_meses"])]
    for i, (r, v) in enumerate(rotulos, start=4):
        ws.cell(i, 1, r).font = negrito
        c = ws.cell(i, 2, v)
        c.fill = PatternFill("solid", fgColor="FFF4D6")
        if i < 7:
            c.number_format = "0.00%"
    ws["D4"] = "Fator de preço"
    ws["E4"] = "=(1+B5)/(1-B4-B6)"
    ws["E4"].number_format = "0.000000"
    cab = ["Item do edital", "Descrição", "Unidade", "Quantidade", "Custo unitário", "Custo total",
           "Preço unitário", "Preço total", "Fornecedor"]
    linha0 = 9
    for j, h in enumerate(cab, 1):
        c = ws.cell(linha0, j, h)
        c.font = negrito
        c.fill = PatternFill("solid", fgColor="DDE7F0")
        c.alignment = Alignment(wrap_text=True)
    for i, ln in enumerate(resultado["linhas"], start=linha0 + 1):
        ws.cell(i, 1, ln.get("item_edital") or "")
        ws.cell(i, 2, ln["descricao"])
        ws.cell(i, 3, ln["unidade_nome"])
        ws.cell(i, 4, ln["quantidade"]).fill = PatternFill("solid", fgColor="FFF4D6")
        ws.cell(i, 5, ln["custo_unitario"]).fill = PatternFill("solid", fgColor="FFF4D6")
        ws.cell(i, 6, f"=D{i}*E{i}")
        ws.cell(i, 7, f"=E{i}*$E$4")
        ws.cell(i, 8, f"=F{i}*$E$4")
        ws.cell(i, 9, "sim" if ln["fornecedor"] else "")
        for col in (5, 6, 7, 8):
            ws.cell(i, col).number_format = '"R$" #,##0.00'
    ult = linha0 + len(resultado["linhas"])
    t = ult + 2
    tot = [("Custo direto", f"=SUM(F{linha0 + 1}:F{ult})"), ("Despesas administrativas", f"=B{t}*B5"),
           ("Custo total", f"=B{t}+B{t + 1}"), ("Preço total", f"=B{t + 2}/(1-B4-B6)"),
           ("Tributos", f"=B{t + 3}*B4"), ("Margem", f"=B{t + 3}-B{t + 4}-B{t + 2}"),
           ("Preço mensal", f"=B{t + 3}/B7")]
    for k, (r, fml) in enumerate(tot):
        ws.cell(t + k, 1, r).font = negrito
        c = ws.cell(t + k, 2, fml)
        c.number_format = '"R$" #,##0.00'
    for col, larg in zip("ABCDEFGHI", (16, 48, 16, 12, 16, 16, 16, 16, 11)):
        ws.column_dimensions[col].width = larg
    s2 = wb.create_sheet("Simulações de desconto")
    for j, h in enumerate(["Desconto", "Preço", "Margem (R$)", "Margem (%)"], 1):
        s2.cell(1, j, h).font = negrito
    for i, sm in enumerate(resultado["simulacoes"], start=2):
        s2.cell(i, 1, sm["desconto_pct"] / 100).number_format = "0.0%"
        s2.cell(i, 2, f"=Proposta!B{t + 3}*(1-A{i})").number_format = '"R$" #,##0.00'
        s2.cell(i, 3, f"=B{i}*(1-Proposta!B4)-Proposta!B{t + 2}").number_format = '"R$" #,##0.00'
        s2.cell(i, 4, f"=IF(B{i}=0,0,C{i}/B{i})").number_format = "0.00%"
    if resultado.get("referencia_edital"):
        s2.cell(len(resultado["simulacoes"]) + 3, 1, "Valor estimado do edital (oficial)").font = negrito
        s2.cell(len(resultado["simulacoes"]) + 3, 2, resultado["referencia_edital"]["valor_estimado_edital"]).number_format = '"R$" #,##0.00'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(resultado: dict, titulo: str, licitacao: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=titulo)
    est = getSampleStyleSheet()
    el = [Paragraph(titulo, est["Title"])]
    if licitacao:
        el.append(Paragraph(f"<b>{licitacao.get('orgao') or ''}</b> — {licitacao.get('numero') or ''}", est["Normal"]))
        el.append(Paragraph(licitacao.get("objeto") or "", est["Normal"]))
        if licitacao.get("link"):
            el.append(Paragraph(f"Fonte oficial: {licitacao['link']}", est["Normal"]))
    el += [Spacer(1, 8), Paragraph(f"<i>{resultado['aviso']}</i>", est["Normal"]), Spacer(1, 8)]
    dados = [["Descrição", "Unid.", "Qtd.", "Custo unit.", "Preço unit.", "Preço total"]]
    for ln in resultado["linhas"]:
        dados.append([Paragraph(ln["descricao"], est["BodyText"]), ln["unidade_nome"], f"{ln['quantidade']:g}",
                      _brl(ln["custo_unitario"]), _brl(ln["preco_unitario"]), _brl(ln["preco_total"])])
    t = Table(dados, colWidths=[6.2 * cm, 2.2 * cm, 1.6 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE7F0")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    el += [t, Spacer(1, 10)]
    resumo = [["Custo direto", _brl(resultado["custo_direto"])], ["Despesas administrativas", _brl(resultado["despesas_adm"])],
              ["Custo total", _brl(resultado["custo_total"])], ["Tributos", _brl(resultado["tributos"])],
              ["Margem", f"{_brl(resultado['margem'])} ({resultado['margem_pct_efetiva']:.2f}%)"],
              ["Preço total", _brl(resultado["preco_total"])],
              [f"Preço mensal ({resultado['prazo_meses']} meses)", _brl(resultado["preco_mensal"])]]
    if resultado.get("referencia_edital"):
        r = resultado["referencia_edital"]
        resumo.append(["Valor estimado do edital (oficial)", _brl(r["valor_estimado_edital"])])
        resumo.append(["Desconto implícito sobre o estimado", f"{r['desconto_implicito_pct']:.2f}%"])
    t2 = Table(resumo, colWidths=[8 * cm, 6 * cm])
    t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#FFF4D6"))]))
    el += [t2, Spacer(1, 10), Paragraph("Simulações de desconto", est["Heading3"])]
    sim = [["Desconto", "Preço", "Margem", "Margem %"]] + [
        [f"{x['desconto_pct']:g}%", _brl(x["preco"]), _brl(x["margem_valor"]), f"{x['margem_pct']:.2f}%"]
        for x in resultado["simulacoes"]]
    t3 = Table(sim, colWidths=[3 * cm, 4 * cm, 4 * cm, 3 * cm])
    t3.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE7F0"))]))
    el.append(t3)
    doc.build(el)
    return buf.getvalue()
