"""Documentos, extração com página/cláusula e análise com IA (cliente da API simulado)."""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

import httpx
import pymupdf

from licitacoes import analise, catalogo, coleta, documentos
from licitacoes.conectores.base import ClienteHttp
from licitacoes.extracao import clausula_em, extrair
from licitacoes.modelos import Documento, Item

from .test_coleta_busca import _registro


def _pdf_do_edital(edital: dict) -> bytes:
    doc = pymupdf.open()
    for p in edital["paginas"]:
        pg = doc.new_page()
        pg.insert_textbox(pymupdf.Rect(36, 36, 560, 806), p["texto"], fontsize=6.5)
    return doc.tobytes()


def test_extracao_pagina_e_clausula(edital_lins):
    pdf = _pdf_do_edital(edital_lins)
    paginas = extrair("Edital PE 083-2026.pdf", pdf)
    assert len(paginas) == len(edital_lins["paginas"])
    p4 = paginas[3]
    assert "2.9.4" in p4.texto
    pos = p4.texto.find("empresas controladoras")
    assert clausula_em(paginas, p4.documento, 4, pos).startswith("2.9.4")


def test_zip_so_com_arquivos_reais_e_manifesto(banco, edital_lins):
    s = banco
    _, lic = coleta.gravar(s, _registro(), catalogo.fonte(s, "pncp"))
    pdf = _pdf_do_edital(edital_lins)
    s.add_all([Documento(licitacao_id=lic.id, sequencial=1, titulo="Edital", tipo="edital", url="https://x/1"),
               Documento(licitacao_id=lic.id, sequencial=2, titulo="Anexo I - Termo de Referência", tipo="termo_referencia",
                         url="https://x/2"),
               Documento(licitacao_id=lic.id, sequencial=3, titulo="Planilha", tipo="planilha_orcamentaria", url="https://x/3")])
    s.commit()

    def handler(r: httpx.Request):
        if r.url.path.endswith("/1"):
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        if r.url.path.endswith("/2"):
            return httpx.Response(404)
        return httpx.Response(403)

    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(handler)), dormir=lambda x: None)
    res = documentos.baixar_todos(s, lic, http)
    assert res == {"baixado": 1, "indisponivel": 1, "requer_autenticacao": 1}
    dados, man = documentos.gerar_zip(lic)
    z = zipfile.ZipFile(io.BytesIO(dados))
    nomes = z.namelist()
    assert "manifesto.json" in nomes and "LEIA-ME.txt" in nomes
    assert sum(n.endswith(".pdf") for n in nomes) == 1  # só o que foi baixado de verdade
    m = json.loads(z.read("manifesto.json"))
    assert {d["status"] for d in m["documentos"]} == {"baixado", "indisponivel", "requer_autenticacao"}
    falta = {c["tipo"] for c in m["checklist"] if not c["publicado"]}
    assert "estudo_tecnico_preliminar" in falta and "edital" not in falta


def test_classificar_documento():
    assert documentos.classificar_documento("ANEXO I - TERMO DE REFERENCIA", "Outros Documentos") == "termo_referencia"
    assert documentos.classificar_documento("Errata nº 1 ao edital", "Edital") == "retificacao"
    assert documentos.classificar_documento("RESPOSTA Esclarecimentos 083-2026") == "esclarecimento"
    assert documentos.classificar_documento("ANEXO II - ESTUDO TECNICO PRELIMINAR") == "estudo_tecnico_preliminar"


class ClienteFalso:
    """Imita o SDK da Anthropic: client.beta.messages.stream(...) -> get_final_message()."""

    def __init__(self, resposta: dict, stop_reason="end_turn"):
        self.resposta, self.stop = resposta, stop_reason
        self.pedidos = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kw):
        self.pedidos.append(kw)
        msg = SimpleNamespace(stop_reason=self.stop, model=kw["model"],
                              content=[SimpleNamespace(type="text", text=json.dumps(self.resposta))],
                              usage=SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0,
                                                    cache_creation_input_tokens=1000))

        class Ctx:
            def __enter__(self_):
                return SimpleNamespace(get_final_message=lambda: msg)

            def __exit__(self_, *a):
                return False
        return Ctx()


def test_analise_confere_citacoes(banco, edital_lins):
    s = banco
    _, lic = coleta.gravar(s, _registro(), catalogo.fonte(s, "pncp"))
    s.add(Item(licitacao_id=lic.id, numero=1, descricao="Locação de ativos de TI", quantidade=12, unidade="mês",
               valor_unitario=305587.86, valor_total=3667054.32))
    doc = Documento(licitacao_id=lic.id, sequencial=1, titulo="Edital PE 083-2026", tipo="edital", url="https://x/1")
    s.add(doc)
    s.commit()
    pdf = _pdf_do_edital(edital_lins)
    from licitacoes.armazenamento import armazenamento

    armazenamento().salvar("documentos/t/1.pdf", pdf)
    doc.status, doc.caminho = "baixado", "documentos/t/1.pdf"
    s.commit()
    resposta = {
        "campos": [
            {"campo": "criterio_julgamento", "valor": "Menor preço global", "natureza": "oficial", "observacao": "",
             "citacoes": [{"documento": "Edital PE 083-2026.pdf", "pagina": 1, "clausula": "",
                           "trecho": "CRITÉRIO DE JULGAMENTO: Menor preço global."}]},
            {"campo": "garantias", "valor": "5% do contrato", "natureza": "oficial", "observacao": "",
             "citacoes": [{"documento": "Edital PE 083-2026.pdf", "pagina": 2, "clausula": "",
                           "trecho": "garantia de 5% do valor do contrato em seguro-fiança"}]},  # inventado
        ],
        "itens": [], "riscos": [{"descricao": "Prazo curto", "gravidade": "media", "natureza": "estimativa_ia",
                                 "base": "data da sessão", "citacoes": []}],
        "custos_operacionais": [], "oportunidades": [], "documentos_citados_nao_enviados": ["Anexo IV"],
    }
    cli = ClienteFalso(resposta)
    an = analise.analisar(s, lic, cliente=cli)
    assert an.status == "concluida"
    pedido = cli.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5" and pedido["output_config"]["format"]["type"] == "json_schema"
    assert "=== DOCUMENTO: Edital PE 083-2026.pdf | PÁGINA 4 ===" in pedido["messages"][0]["content"][0]["text"]
    rel = an.relatorio
    crit = rel["campos"]["criterio_julgamento"]["citacoes"][0]
    gar = rel["campos"]["garantias"]["citacoes"][0]
    assert crit["verificada"] is True
    assert gar["verificada"] is False and "não encontrado" in gar["motivo"]
    assert an.verificacao == {"total": 2, "verificadas": 1, "nao_verificadas": [
        {"documento": "Edital PE 083-2026.pdf", "pagina": 2, "trecho": gar["trecho"], "motivo": gar["motivo"]}]}
    assert rel["campos"]["orgao"]["natureza"] == "oficial"            # dado estruturado do PNCP
    calc = rel["itens_oficiais"][0]["calculo"]
    assert calc["natureza"] == "calculo" and calc["confere"] is True   # 12 × 305.587,86 = 3.667.054,32


def test_analise_sem_ia_disponivel(banco):
    s = banco
    _, lic = coleta.gravar(s, _registro(), catalogo.fonte(s, "pncp"))
    an = analise.analisar(s, lic)  # sem documentos
    assert an.status == "parcial" and "dados estruturados" in an.erro
    assert an.relatorio["campos"]["objeto"]["valor"].startswith("Serviços de digitalização")


def test_detalhar_e_baixar_na_mesma_sessao(banco, edital_lins):
    """Regressão: documentos listados por detalhar() têm de ser baixados na mesma sessão."""
    from licitacoes.conectores.pncp import ConectorPncp

    s = banco
    _, lic = coleta.gravar(s, _registro(), catalogo.fonte(s, "pncp"))
    s.commit()
    pdf = _pdf_do_edital(edital_lins)

    def handler(r: httpx.Request):
        if r.url.path.endswith("/itens"):
            return httpx.Response(200, json=[{"numeroItem": 1, "descricao": "Serviço", "quantidade": 1, "valorUnitarioEstimado": 10}])
        if r.url.path.endswith("/arquivos"):
            return httpx.Response(200, json=[{"sequencialDocumento": 1, "titulo": "Edital.pdf", "tipoDocumentoNome": "Outros Documentos",
                                              "url": "https://pncp.gov.br/pncp-api/v1/orgaos/1/compras/2026/1/arquivos/1"}])
        return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})

    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(handler)), dormir=lambda x: None)
    coleta.detalhar(s, lic, conector=ConectorPncp(http))
    assert documentos.baixar_todos(s, lic, http) == {"baixado": 1}
    assert lic.documentos[0].tipo == "edital"
