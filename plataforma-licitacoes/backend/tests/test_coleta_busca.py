from __future__ import annotations

from datetime import date, timedelta

import httpx

from licitacoes import catalogo, coleta
from licitacoes.busca import Filtros, buscar
from licitacoes.conectores.base import ClienteHttp
from licitacoes.conectores.pncp import ConectorPncp, normalizar_contratacao
from licitacoes.modelos import HistoricoAlteracao, Item, Licitacao, agora
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


def test_registro_defeituoso_e_pulado_sem_derrubar_a_etapa(banco, pncp_pagina, monkeypatch):
    """01-11/2026: um registro com data fora do intervalo derrubou a etapa inteira depois de 48 mil lidos."""
    from licitacoes.conectores import pncp as mod_pncp
    from licitacoes.util import para_data

    assert para_data("0001-01-01T00:00:00+14:00") is None and para_data("31/02/2026") is None
    original = mod_pncp.normalizar_contratacao
    defeituoso = pncp_pagina["data"][3]["numeroControlePNCP"]

    def normalizar(raw, *a, **k):
        if raw.get("numeroControlePNCP") == defeituoso:
            raise OverflowError("date value out of range")
        return original(raw, *a, **k)

    monkeypatch.setattr(mod_pncp, "normalizar_contratacao", normalizar)
    ultima = dict(pncp_pagina, paginasRestantes=0)
    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=ultima))), dormir=lambda x: None)
    r = coleta.sincronizar_pncp(banco, modo="propostas", conector=ConectorPncp(http))
    assert r.status == "ok" and r.lidos == 9 and r.erros == 1 and "1 registros com dados inválidos" in r.mensagem
    assert banco.query(Licitacao).count() == 9


def test_busca_de_30_dias_so_por_publicacao(banco):
    chamadas = []

    def responder(req):
        chamadas.append(req.url.path)
        return httpx.Response(204)

    http = ClienteHttp(intervalo_minimo_s=0, http=httpx.Client(transport=httpx.MockTransport(responder)), dormir=lambda x: None)
    r = coleta.sincronizar_pncp(banco, modo="diario", dias=30, modalidades=[6, 4], so_publicacao=True, conector=ConectorPncp(http))
    assert r.status == "ok" and chamadas and all(c.endswith("/contratacoes/publicacao") for c in chamadas) and len(chamadas) == 2


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
    # "UND SERVIÇO TÉCNICO" é unidade genérica do catálogo: só é UST com volume e preço de UST
    assert cods("Serviços técnicos de desenvolvimento", [("UND SERVIÇO TÉCNICO", "Desenvolvimento", 60_000, 150)]) == {"remun_ust"}
    assert cods("Serviços técnicos de desenvolvimento", [("UND SERVIÇO TÉCNICO", "Desenvolvimento", 1, 900_000)]) == set()
    assert cods("Serviços técnicos", [("1 - UST", "Análise e desenvolvimento de sistemas")]) == {"remun_ust"}
    assert cods("Fábrica de software", [("PONTO DE FUNÇÃO", "Implementação ágil de software")]) == {"remun_pf"}
    assert cods("Sustentação", [("FIXO MENSAL", "Sustentação do Portal Institucional")]) == {"remun_fixo_mensal"}
    assert cods("Sistemas de gestão", [("MÊS", "Folha de pagamento e e-Social")]) == {"remun_fixo_mensal"}
    assert cods("Contratação de fábrica de software medida em pontos de função", []) == {"remun_pf"}
    # "mês" fora de tecnologia não é fixo mensal de TI; "ponto de rede" não é ponto de função
    assert cods("Locação de veículos", [("MÊS", "Veículo tipo sedan")], cats=[]) == set()
    assert cods("Manutenção de rede local", [("PONTO DE REDE", "Instalação de ponto")]) == set()


def test_natureza_e_grande_volume():
    from licitacoes.taxonomia import grande_volume, natureza, volumes

    assert natureza("Aquisição de computadores e notebooks") == "material"
    assert natureza("Prestação de serviços de digitalização de documentos") == "servico"
    assert natureza("Objeto qualquer", [("Material", 100.0), ("Serviço", 900.0)]) == "servico"
    assert natureza("Objeto qualquer", [("Material", 950.0), ("Serviço", 50.0)]) == "material"
    v = volumes([("UND SERVIÇO TÉCNICO", "Desenvolvimento", 60000), ("UNIDADE", "Digitalização de documentos", 2_000_000),
                 ("PONTO DE FUNÇÃO", "Implementação ágil", 24000), ("MÊS", "Sustentação", 12), ("UNIDADE", "Cadeira", 500)])
    assert v == {"ust": 60000, "pagina": 2_000_000, "pf": 24000, "mes": 12}
    assert set(grande_volume(v)) == {"ust", "pagina", "pf"}
    assert "mes" in grande_volume(v, valor=3_000_000)
    assert grande_volume(volumes([("UST", "Suporte", 87)])) == []
    # casos reais medidos (nov/2026)
    assert volumes([("UNIDADE (UN)", "INDEXAÇÃO - tratamento, validação e indexação de documento digital", 2_000_000)]) == {"pagina": 2_000_000}
    assert volumes([("U.I", "Integração dos dados de campo e chaveamento das informações cadastrais", 33_900)]) == {"registro": 33_900}
    assert volumes([("PAGINA", "Outsourcing de impressão - páginas impressas A4", 418_000)]) == {}
    assert volumes([("m²", "Levantamento topográfico planialtimétrico cadastral", 400_000)]) == {}
    assert volumes([("MÊS", "Serviço de videomonitoramento 24h", 2988)]) == {}


def test_mensal_pelo_objeto_e_ust_pf_pelos_documentos():
    from licitacoes.taxonomia import remuneracao

    ti = classificar("Contratação de serviços de sustentação de sistemas")
    cods = lambda texto, docs="", cats=ti: {c["codigo"] for c in remuneracao(texto, [], cats, docs)}  # noqa: E731
    assert cods("Locação de sistema de gestão pública com pagamento mensal") == {"remun_fixo_mensal"}
    assert cods("Licenciamento de software, cobrado por mensalidade") == {"remun_fixo_mensal"}
    assert cods("Sustentação de sistemas pelo período de 12 meses") == set()  # duração não é forma de pagamento
    assert cods("Sustentação de sistemas", docs="Os serviços serão medidos em Unidade de Serviço Técnico (UST)") == {"remun_ust"}
    assert cods("Fábrica de software", docs="estimativa de 2.000 pontos de função") == {"remun_pf"}
    assert cods("Locação de veículos com pagamento mensal", cats=[]) == set()  # fora de tecnologia não conta


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


def test_digitalizacao_de_documento_e_nao_de_imagem_medica_grafica_ou_equipamento():
    from licitacoes.taxonomia import classificar

    def dig(t):
        return "digitalizacao" in {c["codigo"] for c in classificar(t)}

    # casos reais da base (11/11/2026) que eram falsos positivos
    for t in ("Locação de sistema de digitalização de imagens radiográficas",
              "Serviços de plotagem, cópia de engenharia, digitalização e cópias coloridas",
              "Aquisição de impressora colorida com funções de cópia e digitalização para papel A4",
              "Equipamentos de tecnologia: impressão 3D, digitalização, realidade virtual e audiovisual",
              "Mocho odontológico e sistema de digitalização de imagens intraorais",
              "Prestação de serviços gráficos e de digitalização para a Câmara Municipal",
              "Exames de radiologia convencional digitalizada",
              "Aerolevantamento aerofotogramétrico e imageamento aéreo de alta resolução",
              "Aquisição de 15 novos equipamentos de digitalização de imagem",
              "Aquisição de equipamentos de informática, impressão, digitalização e periféricos"):
        assert not dig(t), t
    for t in ("Serviços de digitalização, indexação e certificação do acervo documental",
              "Outsourcing de processamento de documentos, compreendendo digitalização, impressão e guarda",
              "Preparo e digitalização de documentos em meio físico",
              "Conversão do acervo físico para documentos digitalizados com OCR",
              "Microfilmagem e digitalização de prontuários"):
        assert dig(t), t


def test_indexacao_de_documento_e_nao_de_revista_ou_video():
    from licitacoes.taxonomia import classificar

    def idx(t):
        return "indexacao" in {c["codigo"] for c in classificar(t)}

    assert not idx("Indexação da Revista CFMV")
    assert not idx("Gravação e transmissão das sessões de julgamento, transcrição, edição de vídeo, indexação e publicação")
    assert idx("Serviços de digitalização, indexação e certificação do acervo documental")


def test_digitalizacao_e_indexacao_pelos_itens_quando_o_objeto_nao_diz():
    from licitacoes.taxonomia import documental_pelos_itens

    itens = [("PÁGINA", "Digitalização de documentos A4 com OCR"), ("UN", "Indexação de documentos por 3 campos")]
    r = documental_pelos_itens("Contratação de serviços de gestão documental, física e digital", itens, set())
    assert {c["codigo"] for c in r} == {"digitalizacao", "indexacao"}
    assert r[0]["termos"][0].startswith("item: ") and r[0]["forca"] == 0.5
    # o que o objeto já trouxe não se repete
    assert {c["codigo"] for c in documental_pelos_itens("Gestão documental", itens, {"digitalizacao"})} == {"indexacao"}
    # compra de equipamento com scanner nos itens não é serviço de digitalização
    assert documental_pelos_itens("Aquisição de equipamentos de informática e periféricos", itens, set()) == []
    assert documental_pelos_itens("Gestão documental", [("UN", "Scanner de mesa 60 ppm")], set()) == []


def test_classificar_licitacao_usa_os_itens_para_digitalizacao(banco):
    s = banco
    _, lic = coleta.gravar(s, _registro(objeto="Serviços contínuos de gestão documental e arquivística"), catalogo.fonte(s, "pncp"))
    assert "digitalizacao" not in {c["codigo"] for c in lic.categorias}
    s.add(Item(licitacao_id=lic.id, numero=1, descricao="Digitalização de documentos (imagem)", quantidade=2_000_000, unidade="imagem"))
    s.flush()
    coleta.classificar_licitacao(s, lic)
    assert "digitalizacao" in {c["codigo"] for c in lic.categorias}


def test_unidade_servico_tecnico_generica_nao_e_ust():
    from licitacoes.taxonomia import item_ust, remuneracao, tipo_volume

    # catálogo do Compras.gov: "UND SERVIÇO TÉCNICO" vale para qualquer serviço (ex.: SaaS de R$ 47 mi, 1 unidade)
    assert not item_ust("UND SERVIÇO TÉCNICO", "Software como Serviço - SaaS", 1, 47_016_200)
    assert not item_ust("UND SERVIÇO TÉCNICO", "Central de Serviços de TIC", 12, 1_328_476)
    assert item_ust("UND SERVIÇO TÉCNICO", "Serviços técnicos especializados de TIC", 5_000, 180)
    assert not item_ust("UND SERVIÇO TÉCNICO", "Solução de telefonia em nuvem: licença ramal PABX virtual", 11_800, 46.9)
    assert not item_ust("UND SERVIÇO TÉCNICO", "Central de Serviços de TIC - minutagem ilimitada, chamadas LDN", 11_800, 9.45)
    assert not item_ust("UND SERVIÇO TÉCNICO", "Serviço comum", 500, 100)  # sem sinal de serviço técnico de TI
    assert item_ust("UST", "Desenvolvimento sob demanda", 20, 4_409)
    assert item_ust("UN", "Serviço técnico medido em UST - perfil sênior", 10, 900)
    assert tipo_volume("UND SERVIÇO TÉCNICO", "Central de Serviços", 12, 1_328_476) is None
    assert tipo_volume("UND SERVIÇO TÉCNICO", "Sustentação de sistemas", 12_000, 210) == "ust"
    cats = [{"codigo": "desenvolvimento", "segmento": "ti"}]
    assert not any(c["codigo"] == "remun_ust" for c in remuneracao("Serviços de TIC", [("UND SERVIÇO TÉCNICO", "Central de serviços", 12, 1_328_476)], cats))
    r = {c["codigo"]: c for c in remuneracao("Serviços de TIC", [("UND SERVIÇO TÉCNICO", "Sustentação de sistemas", 12_000, 210)], cats)}
    assert r["remun_ust"]["termos"] == ["1 item em UST"]
    # sem quantidade e preço (chamada antiga com 2 campos) a unidade genérica sozinha não decide
    assert not any(c["codigo"] == "remun_ust" for c in remuneracao("Serviços de TIC", [("UND SERVIÇO TÉCNICO", "Suporte")], cats))
    assert any(c["codigo"] == "remun_ust" for c in remuneracao("Contratação de serviços medidos em UST", [], cats))


def test_termo_de_palavra_inteira_casa_junto_de_pontuacao():
    """Até 12/11 " microcomputadores " não casava em "microcomputadores," nem " ust " em "(UST)"."""
    cods = lambda t: {c["codigo"] for c in classificar(t)}  # noqa: E731
    assert {"equipamentos_ti", "tecnologia"} <= cods("Compra de microcomputadores, conforme TR.")
    assert "fabrica_software" in cods("Fábrica de software (UST), sob demanda")
    assert {"ged", "ocr"} <= cods("Solução GED/ECM com OCR.")


def test_tecnologia_ampliada():
    cods = lambda t: {c["codigo"] for c in classificar(t)}  # noqa: E731
    casos = {
        "Serviços continuados de CFTV, monitoria por câmeras": "seguranca_eletronica",
        "Prestação continuada de serviços de monitoramento urbano inteligente": "cidades_inteligentes",
        "Acesso à rede mundial de computadores, internet de links dedicados e IPs fixos": "telecom",
        "Licenças de sistema integrado de gestão escolar (SIGE), com customização e conversão de dados": "sistemas_gestao",
        "Kits educacionais de robótica programável para as escolas": "edtech",
        "Cartuchos de toner com impressoras em regime de comodato": "impressao",
        "Transmissão ao vivo das sessões da Câmara Municipal": "audiovisual_tec",
        "Solução informatizada de videotelemetria embarcada": "iot_telemetria",
        "Sistema de gestão online via app para a prefeitura": "sistemas_gestao",
    }
    for texto, cod in casos.items():
        r = cods(texto)
        assert cod in r and "tecnologia" in r, (texto, r)  # toda categoria de TI também entra em "Tecnologia"
    for texto in ("Rastreamento do câncer do colo do útero", "Serviços de vigilância armada", "Aquisição de lousas de vidro",
                  "Contratação de emissoras de rádio para publicidade", "Tomografia computadorizada e ressonância",
                  "Sistema de gestão ambiental ISO 14001", "Locação de veículos zero quilômetro com sistema de rastreamento",
                  "Registro de preços de uniformes para servidores do Departamento de Saúde",
                  "Alienação de bem imóvel registrado no Sistema de Gestão de Bens Imóveis",
                  "Assessoria e consultoria técnica em gestão documental, com sistema de gestão de arquivos físicos",
                  "Painel de LED quadrado para embutir, 40 x 40 cm, 36 W",
                  "Equipamento de inspeção por scanner portátil de raio X por backscatter",
                  "Projeto executivo e obra; processo eletrônico SEI nº 123/2026",
                  "Locação de estruturas para eventos, como som, iluminação, palco e transmissão ao vivo"):
        assert not cods(texto) & {"tecnologia", "iot_telemetria", "equipamentos_ti", "sistemas_gestao", "edtech", "servidores",
                                  "audiovisual_tec"}, texto
    assert "servidores" in cods("Aquisição de servidores de rede e storage para o data center")
    assert "equipamentos_ti" not in cods("Internet de links dedicados (rede mundial de computadores)")


def test_horas_tecnicas_hst_e_homem_hora():
    from licitacoes.taxonomia import tipo_volume

    for un, desc in (("HORA", "CONSULTORIA DAS FUNCIONALIDADES DOS SISTEMAS"), ("H", "HORAS DE CUSTOMIZAÇÃO"), ("HST", "Desenvolvimento sob demanda"),
                     ("H/H", "Suporte técnico especializado"), ("UNID", "Hora técnica para customização do sistema"),
                     ("UNIDADE (UN)", "HORA TÉCNICA de serviços suplementares"), ("HRS", "Horas técnicas para treinamentos"),
                     ("HORAS", "Customização extraordinária")):
        assert tipo_volume(un, desc, 500, 200) == "hora", (un, desc)
    for un, desc in (("HORA", "Sistema de som PDR - propaganda de rua (carro de som)"), ("HORAS", "Instalação e reparo de câmeras de segurança"),
                     ("UN", "Computador desktop"), ("HORA", "Serviços de mecânica (hora/homem)")):
        assert tipo_volume(un, desc, 500, 200) is None, (un, desc)


def test_volume_escrito_no_texto_do_edital():
    from licitacoes.taxonomia import volumes_no_texto

    assert volumes_no_texto("Quantidade estimada de 1.250.000 (um milhão duzentos e cinquenta mil) UST por ano") == {"ust": 1_250_000}
    assert volumes_no_texto("até 3.067 pontos de função e 32.900 horas técnicas") == {"pf": 3067, "hora": 32_900}
    assert volumes_no_texto("digitalização de 3,9 milhões de páginas", documental=True) == {"pagina": 3_900_000}
    assert volumes_no_texto("digitalização de 3,9 milhões de páginas") == {}  # páginas só em edital documental
    # números separados por espaço não se juntam; quantidades pequenas demais ou absurdas são ignoradas
    assert volumes_no_texto("serão 384 000 768 000 UST") == {}
    assert volumes_no_texto("tabela 1 com 12 UST") == {}


def test_volume_no_texto_ignora_atestado_e_extenso_com_mil():
    from licitacoes.taxonomia import preco_plausivel, volumes_no_texto

    assert volumes_no_texto("o quantitativo mínimo de 1.800 (mil e oitocentas) horas de serviços técnicos no atestado") == {}
    assert volumes_no_texto("serão contratadas 1.800 (mil e oitocentas) horas técnicas") == {"hora": 1800}
    assert volumes_no_texto("estimativa de 20 mil UST") == {"ust": 20_000}
    assert preco_plausivel("hora", 1_800_000, 7_200_000) is False  # R$ 4 a hora
    assert preco_plausivel("ust", 1_250_000, 97_900_000) is True
    assert preco_plausivel("pagina", 900_000, None) is True


def test_hora_de_servico_tecnico_nao_e_ust():
    from licitacoes.taxonomia import item_ust, tipo_volume

    # MJSP 2026: "768.000 HST" em 24 meses, unidade "Hora Serviço Técnico"
    assert not item_ust("HORA SERVIÇO TÉCNICO", "Desenvolvimento, manutenção e sustentação de software", 768_000, 139.8)
    assert tipo_volume("HORA SERVIÇO TÉCNICO", "Desenvolvimento, manutenção e sustentação de software", 768_000, 139.8) == "hora"
    assert item_ust("UST", "Desenvolvimento", 1000, 150)


def test_auditoria_de_precisao_13_11():
    """Casos reais de editais abertos que caíam em categoria errada (auditoria de 13/11)."""
    from licitacoes.taxonomia import remuneracao

    def cods(t):
        return {c["codigo"] for c in classificar(t)}

    errados = {
        "Fornecimento de bomba de deslocamento positivo para recalque de lodo adensado na ETL": "dados",
        "Contratação de instituição financeira para cobrança bancária registrada via API": "integracao",
        "Credenciamento de instituições financeiras para integração de sistemas de crédito consignado": "integracao",
        "Execução de obra de quadra poliesportiva coberta com cabeamento estruturado e wi-fi": "infra_ti",
        "Aquisição de impressora plotter A1 com conexão wi-fi": "infra_ti",
        "Contratação de serviços de limpeza com aplicação de saneantes e sistema de gestão de equipes": "sistemas_gestao",
        "Serviços técnicos de engenharia consultiva com sustentação técnica das obras": "sustentacao",
        "Agenciamento de viagens: reserva, emissão, marcação de passagens aéreas e hospedagem com inteligência artificial": "ia",
        "Manutenção predial preventiva e corretiva com aplicação de material": "manutencao_software",
        "Substituição do sistema de climatização da sala de energia com nobreaks e rede de dados": "infra_ti",
        "Aquisição de equipamentos de TI destinados ao desenvolvimento de aplicações": "desenvolvimento",
    }
    for texto, cod in errados.items():
        assert cod not in cods(texto), (cod, texto)
    certos = {
        "Integração de sistemas via API REST para o sistema informatizado de saúde": "integracao",
        "Solução de rede wi-fi gerenciada para a rede lógica do campus": "infra_ti",
        "Serviços de implantação e integração de solução POLAN e Wi-Fi corporativa para a creche": "infra_ti",
        "Manutenção corretiva e evolutiva do software de gestão": "manutencao_software",
        "Processo de ETL e data warehouse para o banco de dados corporativo": "dados",
    }
    for texto, cod in certos.items():
        assert cod in cods(texto), (cod, texto)
    # fixo mensal só para software e serviço de TI: link de internet mensal não entra
    link = classificar("Prestação de serviços de link de internet por fibra óptica")
    assert not any(c["codigo"] == "remun_fixo_mensal" for c in remuneracao("link de internet", [("MÊS", "Link dedicado 500 Mbps", 12, 900)], link))
    soft = classificar("Locação de software de gestão pública")
    assert any(c["codigo"] == "remun_fixo_mensal" for c in remuneracao("locação de software", [("MÊS", "Licença do sistema", 12, 9000)], soft))
