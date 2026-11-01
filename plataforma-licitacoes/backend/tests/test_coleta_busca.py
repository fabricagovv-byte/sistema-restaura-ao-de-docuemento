from __future__ import annotations

from datetime import date, timedelta

import httpx

from licitacoes import catalogo, coleta
from licitacoes.busca import Filtros, buscar
from licitacoes.conectores.base import ClienteHttp
from licitacoes.conectores.pncp import ConectorPncp, normalizar_contratacao
from licitacoes.modelos import HistoricoAlteracao, Licitacao, agora
from licitacoes.taxonomia import classificar, expandir_consulta


def _registro(**kw):
    base = {
        "chave": "pncp:12345678000190-1-000001/2026", "numero_controle_pncp": "12345678000190-1-000001/2026",
        "tipo_registro": "contratacao", "cnpj_orgao": "12345678000190", "orgao_nome": "MUNICIPIO DE TESTE",
        "ano": 2026, "sequencial": 1, "numero_compra": "10/2026", "modalidade_id": 6, "modalidade": "Pregão - Eletrônico",
        "situacao": "Divulgada no PNCP", "objeto": "Serviços de digitalização e indexação do acervo documental",
        "valor_estimado": 1_500_000.0, "data_publicacao": agora() - timedelta(days=2),
        "data_abertura": agora() - timedelta(days=1), "data_encerramento": agora() + timedelta(days=10),
        "uf": "SC", "municipio": "Garopaba", "codigo_ibge": "4205704",
        "link_pncp": "https://pncp.gov.br/app/editais/12345678000190/2026/1", "fonte": "pncp", "bruto": {},
    }
    base.update(kw)
    return base


def test_upsert_historico_e_prioridade(banco):
    s = banco
    pncp = catalogo.fonte(s, "pncp")
    esp = catalogo.fonte(s, "espelhos_pncp")
    st, lic = coleta.gravar(s, _registro(), pncp)
    assert st == "novo" and {c["codigo"] for c in lic.categorias} >= {"digitalizacao", "indexacao"}
    novo_prazo = lic.data_encerramento + timedelta(days=7)
    st, lic = coleta.gravar(s, _registro(data_encerramento=novo_prazo), pncp)
    assert st == "atualizado"
    h = s.query(HistoricoAlteracao).filter_by(licitacao_id=lic.id, evento="prazo").one()
    assert h.campo == "data_encerramento"
    # espelho não sobrescreve dado do PNCP, só completa campo vazio
    st, lic = coleta.gravar(s, _registro(valor_estimado=9.0e9, processo="P-1", fonte="espelhos_pncp"), esp)
    assert float(lic.valor_estimado) == 1_500_000.0 and lic.processo == "P-1"
    assert set(lic.fontes_vistas) == {"pncp", "espelhos_pncp"}


def test_republicacao_ligada_ao_original(banco):
    s = banco
    f = catalogo.fonte(s, "pncp")
    _, a = coleta.gravar(s, _registro(), f)
    _, b = coleta.gravar(s, _registro(chave="pncp:12345678000190-1-000002/2026", sequencial=2,
                                      objeto="Serviços de digitalização e indexação do acervo documental. Processo nº 55",
                                      data_encerramento=a.data_encerramento + timedelta(seconds=40)), f)
    assert b.duplicata_de_id == a.id


def test_sincronizar_pncp_com_api_simulada(banco, pncp_pagina):
    ultima = dict(pncp_pagina, paginasRestantes=0)
    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=ultima))), dormir=lambda x: None)
    r = coleta.sincronizar_pncp(banco, modo="propostas", conector=ConectorPncp(http))
    assert r.status == "ok" and r.lidos == 10 and r.novos == 10
    assert banco.query(Licitacao).count() == 10
    assert catalogo.fonte(banco, "pncp").ultimo_sucesso is not None


def test_pncp_para_no_prazo(banco, pncp_pagina):
    import time

    ultima = dict(pncp_pagina, paginasRestantes=0)
    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=ultima))), dormir=lambda x: None)
    r = coleta.sincronizar_pncp(banco, modo="propostas", conector=ConectorPncp(http), ate=time.monotonic() - 1)
    assert r.status == "parcial" and r.lidos == 1 and "limite de tempo" in r.mensagem


def test_falha_da_fonte_fica_registrada(banco):
    http = ClienteHttp(intervalo_minimo_s=0, max_tentativas=2, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(503))), dormir=lambda x: None)
    r = coleta.sincronizar_pncp(banco, modo="propostas", conector=ConectorPncp(http))
    f = catalogo.fonte(banco, "pncp")
    assert r.status == "erro" and f.falhas_consecutivas == 1 and "503" in f.ultimo_erro


def test_conferencia_individual_marca_excluido(banco):
    s = banco
    coleta.gravar(s, _registro(data_encerramento=agora() + timedelta(days=1)), catalogo.fonte(s, "pncp"))
    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(410))), dormir=lambda x: None)
    res = coleta.conferir_individual(s, conector=ConectorPncp(http))
    assert res["excluidos"] == 1
    assert s.query(Licitacao).one().excluida is True


def test_taxonomia_sem_falsos_positivos_medidos():
    assert not classificar("Contratação de serviços continuados de limpeza, esquadrias e mão de obra")
    assert not any(c["codigo"] == "digitalizacao" for c in classificar("Outsourcing de impressão, cópia e digitalização"))
    assert not any(c["codigo"] == "manutencao_software" for c in classificar("Manutenção do sistema de drenagem urbana"))
    assert any(c["codigo"] == "manutencao_software" for c in classificar("Manutenção do sistema de gestão (software) do município"))
    assert any(c["codigo"] == "fabrica_software" for c in classificar("Fábrica de software medida em UST (unidade de serviço técnico)"))


def test_ead_e_pesquisa_com_casos_reais():
    cods = lambda o: {c["codigo"] for c in classificar(o)}  # noqa: E731
    # objetos reais de editais abertos (PNCP, out/2026)
    assert "ead" in cods("Contratação de empresa especializada para produção de cursos na modalidade de educação a distância (EaD)")
    assert "pesquisa" in cods("Eventual contratação de empresa especializada na prestação de serviços de pesquisa de opinião pública")
    assert "pd_inovacao" in cods("Seleção de proposta para celebração de Contrato Público para Solução Inovadora – CPSI")
    # falsos positivos medidos: "ead" dentro de "readequação", nome de órgão, pesquisa de preços, compra de material
    assert "ead" not in cods("[Portal de Compras Públicas] - Contratação de empresa para a readequação da iluminação da quadra")
    assert "pesquisa" not in cods("Aquisição de tintas para as instalações do Instituto de Pesquisas da Marinha")
    assert "pesquisa" not in cods("Aquisição de cadeiras conforme pesquisa de preços e pesquisa de campo")
    assert "pd_inovacao" not in cods("Materiais laboratoriais para o desenvolvimento de projeto de pesquisa e aulas práticas")
    assert "pd_inovacao" not in cods("Manutenção preventiva e corretiva dos sistemas de climatização, com transferência de tecnologia")


def test_tecnologia_valor_fixo_mensal_com_casos_reais():
    cods = lambda o: {c["codigo"] for c in classificar(o)}  # noqa: E731
    assert "ti_mensal" in cods("Contratação de empresa especializada em cessão de direito de uso (locação) de sistemas integrados de Gestão Pública")
    assert "ti_mensal" in cods("Contratação de serviços de subscrição de licenciamento de software na modalidade SaaS (Software as a Service)")
    assert "ti_mensal" in cods("PRESTAÇÃO DE SERVIÇOS DE LOCAÇÃO DE COMPUTADORES")
    assert "ti_mensal" not in cods("Concessão dos serviços de transporte coletivo por ônibus, envolvendo o provimento de solução de bilhetagem")
    assert "ti_mensal" not in cods("Contratação de serviço de LOCAÇÃO DE SISTEMA DE HEMODIÁLISE COM OSMOSE REVERSA")
    assert "ti_mensal" not in cods("Serviço de locação de equipamentos de fiscalização eletrônica de trânsito e videomonitoramento")
    assert "ti_mensal" not in cods("Aquisição de licença de uso do sistema operacional Microsoft Windows 11 Pro")


def test_tecnologia_geral_com_casos_reais():
    cods = lambda o: {c["codigo"] for c in classificar(o)}  # noqa: E731
    assert "tecnologia" in cods("AQUISIÇÃO DE MATERIAL E EQUIPAMENTOS DE INFORMÁTICA PARA ATENDER AS NECESSIDADES DO CEO REGIONAL")
    assert "tecnologia" in cods("Registro de preços para aquisição de tablets destinados aos agentes comunitários de saúde")
    assert "tecnologia" in cods("Contratação de link dedicado de acesso à internet em fibra óptica")
    assert "tecnologia" not in cods("prestação de serviços de exames de Tomografias Computadorizadas e Polissonografias Domiciliares")
    assert "tecnologia" not in cods("Capacitação de servidores municipais em atendimento ao público")


def test_forma_de_pagamento_pelos_itens():
    from licitacoes.taxonomia import remuneracao

    ti = classificar("Contratação de serviços de sustentação de sistemas")
    cods = lambda texto, itens, cats=ti: {c["codigo"] for c in remuneracao(texto, itens, cats)}  # noqa: E731
    # unidades reais de itens do PNCP (nov/2026)
    assert cods("Serviços técnicos de desenvolvimento", [("UND SERVIÇO TÉCNICO", "Desenvolvimento")]) == {"remun_ust"}
    assert cods("Serviços técnicos", [("1 - UST", "Análise e desenvolvimento de sistemas")]) == {"remun_ust"}
    assert cods("Fábrica de software", [("PONTO DE FUNÇÃO", "Implementação ágil de software")]) == {"remun_pf"}
    assert cods("Sustentação", [("FIXO MENSAL", "Sustentação do Portal Institucional")]) == {"remun_fixo_mensal"}
    assert cods("Sistemas de gestão", [("MÊS", "Folha de pagamento e e-Social")]) == {"remun_fixo_mensal"}
    assert cods("Contratação de fábrica de software medida em pontos de função", []) == {"remun_pf"}
    # "mês" fora de tecnologia não é fixo mensal de TI; "ponto de rede" não é ponto de função
    assert cods("Locação de veículos", [("MÊS", "Veículo tipo sedan")], cats=[]) == set()
    assert cods("Manutenção de rede local", [("PONTO DE REDE", "Instalação de ponto")]) == set()


def test_expansao_semantica_digitalizacao():
    termos = expandir_consulta("digitalização")["grupos"][0]["termos"]
    for t in ["escaneamento", "conversao de documentos fisicos", "microfilmagem", "captura e processamento de imagens"]:
        assert t in termos


def test_busca_filtros(banco):
    s = banco
    f = catalogo.fonte(s, "pncp")
    coleta.gravar(s, _registro(), f)
    coleta.gravar(s, _registro(chave="pncp:2", objeto="Outsourcing de impressão e digitalização", valor_estimado=50_000.0), f)
    coleta.gravar(s, _registro(chave="pncp:3", objeto="Fábrica de software por pontos de função", uf="DF",
                               valor_estimado=8_000_000.0, cnpj_orgao="99999999000199"), f)
    coleta.gravar(s, _registro(chave="pncp:4", objeto="Escaneamento de processos físicos", valor_estimado=None,
                               orcamento_sigiloso=True, cnpj_orgao="88888888000188"), f)
    coleta.gravar(s, _registro(chave="pncp:5", objeto="Digitalização de prontuários", cnpj_orgao="77777777000177",
                               data_encerramento=agora() - timedelta(days=1)), f)
    r = buscar(s, Filtros(q="digitalização"))
    objetos = {x.objeto for x in r["itens"]}
    assert "Escaneamento de processos físicos" in objetos            # sinônimo
    assert "Outsourcing de impressão e digitalização" not in objetos  # exclusão
    assert "Digitalização de prontuários" not in objetos              # encerrada
    assert buscar(s, Filtros(q="digitalização", situacao="encerrada"))["total"] == 1
    assert buscar(s, Filtros(q="digitalização", valor_min=1e6, incluir_sem_valor=False))["total"] == 1
    assert buscar(s, Filtros(q="digitalização", valor_min=1e6, incluir_sem_valor=True))["total"] == 2
    assert buscar(s, Filtros(ufs=["DF"]))["itens"][0].objeto.startswith("Fábrica")
    assert buscar(s, Filtros(orgao="99999999000199"))["total"] == 1
    assert buscar(s, Filtros(categorias=["fabrica_software"]))["total"] == 1
    assert buscar(s, Filtros(numero="10/2026"))["total"] >= 1
    assert buscar(s, Filtros(ordenar="valor"))["itens"][0].objeto.startswith("Fábrica")


def test_plataforma_de_origem():
    assert catalogo.plataforma_de("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/x") == "Compras.gov.br"
    assert catalogo.plataforma_de(None, "[Portal de Compras Públicas] - Locação de software") == "Portal de Compras Públicas"
    assert catalogo.plataforma_de("https://www.bllcompras.com/Process/1") == "BLL Compras"
