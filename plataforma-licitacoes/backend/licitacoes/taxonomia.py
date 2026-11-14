"""Categorias de serviço, classificação dos objetos e expansão de consulta por significado.

A busca não depende só da palavra digitada: cada categoria reúne os vários nomes que os editais
usam para o mesmo serviço (ex.: "digitalização" também casa com "conversão de documentos físicos",
"captura de imagens", "OCR", "GED"). Os termos de "excluir" tiram falsos positivos medidos em
dados reais (ex.: "mão de obra" não é obra; "outsourcing de impressão" não é digitalização).
Categorias novas podem ser cadastradas na tabela `categoria`; estas são as padrão.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field

from .util import normalizar

NEG_TI = ["manutencao predial", "ar condicionado", "ar-condicionado", "veiculo", "elevador",
          "material de expediente", "generos alimenticios", "esquadria", "fotovoltaic", "drenagem",
          "iluminacao publica", "videomonitoramento", "video monitoramento", "motobomba", "climatizacao",
          "alarmes", "cameras", "monitoramento eletronico", "seguranca eletronica", "aquisicao de materiais",
          "materiais de informatica", "equipamentos de informatica", "computadores", "perifericos", "aquisicao de equipamentos"]
CTX_TI = ["software", "sistema informatizado", "sistemas informatizados", "tecnologia da informacao", " ti ", " tic ",
          "aplicacao web", "aplicacoes web", "aplicacoes de ti", "aplicativo", " web ", " erp ", "banco de dados", "codigo fonte", "plataforma digital",
          "sistema de gestao", "sistemas de gestao", "solucao tecnologica"]
CTX_DOC = ["documento", "documental", "acervo", "arquivo", "processos fisicos", "prontuario", "papel"]
NEG_IMPRESSAO = ["outsourcing de impressao", "impressao corporativa", "impressao, copia", "impressao e digitalizacao",
                 "impressao/copia", "multifuncion", "impressoras", "equipamentos de impressao", "locacao de scanners",
                 "scanners documentais", "escaneamento intraoral", "videomonitoramento", "video monitoramento", "cameras",
                 "certificado digital e-cpf", "token"]
# digitalização que não é de documento: imagem médica e odontológica, gráfica, plotagem, equipamento avulso
NEG_DIGITALIZACAO = NEG_IMPRESSAO + [
    "radiolog", "radiograf", "radiodiagnost", "raio x", "raios x", "raio-x", "mamograf", "tomograf", "intraora",
    "odontolog", "plotagem", "copia de engenharia", "copias coloridas", "copia e digitalizacao", "copias e digitalizacao",
    "servicos graficos", "impressao 3d", "impressora", "mesa digitalizadora", "mesas digitalizadoras", "digitalizadora",
    "camera fotografica", "escaneamento facial", "escaneamento 3d", "scanner 3d", "digitalizacao de sinais",
    "transformacao digital", "imageamento aereo", "aerofotogram", "aerolevantamento", "georreferenc", "geoprocessamento",
    "cartograf", "aquisicao de equipamentos", "novos equipamentos de digitalizacao", "equipamentos de digitalizacao de imagem"]
# expressões que só aparecem em serviço documental de verdade: valem mesmo com termo de exclusão no texto
# (ex.: "outsourcing de processamento de documentos, compreendendo digitalização, impressão...")
FORTES_DIGITALIZACAO = [
    "digitalizacao de acervo", "digitalizacao do acervo", "digitalizacao de prontuarios", "digitalizacao de processos",
    "digitalizacao e indexacao", "digitalizacao, indexacao", "outsourcing de processamento de documentos",
    "processamento de documentos do tipo outsourcing", "digitalizacao de documentos historicos",
    "documentos fisicos", "preparo e digitalizacao", "preparacao para digitalizacao", "digitalizacao do arquivo",
    "digitalizacao de livros", "digitalizacao de documentos do arquivo", "gestao documental"]

NEG_PESQUISA = ["pesquisa de precos", "pesquisa de preco", "pesquisa mercadologica", "levantamento de precos",
                "aquisicao de materia", "aquisicao de equipamento", "aquisicao do equipamento", "aquisicao de insumos",
                "materiais de consumo", "material de consumo", "materiais permanentes", "generos alimenticios",
                "mobiliario", "permissao de uso", "permissao administrativa de uso", "obras e servicos de engenharia",
                "reagentes", "aquisicao de livros", "fornecimento de livros", "materiais laboratoriais",
                "climatizacao", "ar condicionado"]


@dataclass
class DefCategoria:
    codigo: str
    nome: str
    segmento: str
    termos: list[str]
    excluir: list[str] = field(default_factory=list)
    # termos que só contam se aparecer também uma palavra de contexto (ex.: "manutenção do sistema" + "software")
    ambiguos: list[str] = field(default_factory=list)
    contexto: list[str] = field(default_factory=list)
    # termos que confirmam a categoria mesmo havendo termo de exclusão no texto
    fortes: list[str] = field(default_factory=list)


PADRAO: list[DefCategoria] = [
    # ---------------------------------------------------------------- Gestão documental
    DefCategoria("digitalizacao", "Digitalização", "gestao_documental", [
        "digitalizacao", "escaneamento", "conversao de documentos fisicos", "conversao de suporte",
        "documentos fisicos em digitais", "desmaterializacao", "captura e processamento de imagens",
        "imageamento", "digitalizacao de acervo", "digitalizacao de processos", "digitalizacao de prontuarios",
        "digitalizacao de plantas", "certificacao digital de documentos", "decreto 10.278", "bpo documental",
        "outsourcing de digitalizacao", "microfilmagem", "arquivamento eletronico", "preparo e digitalizacao",
        "imagens digitalizadas", "paginas digitalizadas", "outsourcing de processamento de documentos",
        "processamento de documentos do tipo outsourcing",
        "captura de documentos", "conversao do acervo", "conversao de acervo",
    ], NEG_DIGITALIZACAO, fortes=FORTES_DIGITALIZACAO),
    DefCategoria("indexacao", "Indexação", "gestao_documental", [
        "indexacao", "catalogacao de documentos", "classificacao documental", "plano de classificacao",
        "descricao arquivistica", "indexacao de imagens",
    ], ["indexacao doi", "revista cientifica", "periodico", "indice de reajuste", "videomonitoramento",
        "video monitoramento", "cameras", "indexacao da revista", "revista ", "edicao de video", "gravacao e transmissao",
        "sessoes de julgamento"], ambiguos=["metadados"], contexto=CTX_DOC),
    DefCategoria("restauracao", "Restauração de documentos", "gestao_documental", [
        "restauracao de documentos", "restauracao de acervo", "conservacao e restauracao", "conservacao preventiva",
        "restauracao de livros", "restauracao de bens culturais",
    ], ["restauracao de pavimento", "restauracao de fachada", "restauracao predial"]),
    DefCategoria("higienizacao", "Higienização documental", "gestao_documental", [
        "higienizacao de documentos", "higienizacao documental", "higienizacao de acervo", "desinfestacao de acervo",
        "higienizacao, acondicionamento",
    ]),
    DefCategoria("triagem", "Triagem e organização de acervo", "gestao_documental", [
        "triagem documental", "organizacao de acervo", "organizacao de arquivo", "tratamento documental",
        "tratamento arquivistico", "gestao arquivistica", "massa documental acumulada", "tabela de temporalidade",
        "diagnostico arquivistico", "gestao documental", "servicos arquivisticos",
    ]),
    DefCategoria("guarda", "Guarda e armazenamento físico", "gestao_documental", [
        "guarda de documentos", "custodia de documentos", "armazenamento de documentos", "guarda documental",
        "desarquivamento", "arquivo morto", "guarda terceirizada", "fragmentacao e descarte de documentos",
    ]),
    DefCategoria("ged", "GED / ECM", "gestao_documental", [
        "gestao eletronica de documentos", " ged ", "ged/", "/ged", " ecm ", "gerenciamento eletronico de documentos",
        "processos digitais", "protocolo digital", "repositorio arquivistico", "preservacao digital",
    ]),
    DefCategoria("ocr", "OCR e extração de dados de documentos", "gestao_documental", [
        " ocr ", "reconhecimento optico de caracteres", " icr ", "extracao de dados de documentos",
        "processamento inteligente de documentos",
    ], ["cameras ocr", "ocr/lpr", "leitura de placas"]),
    # ---------------------------------------------------------------- Tecnologia da informação
    DefCategoria("desenvolvimento", "Desenvolvimento de software", "ti", [
        "desenvolvimento de software", "desenvolvimento de sistemas", "desenvolvimento de solucoes de software",
        "desenvolvimento e manutencao de solucoes", "desenvolvimento sob demanda", "desenvolvimento de aplicativos",
        "desenvolvimento de aplicacoes", "software sob medida", "software personalizado", "custom software development",
        "desenvolvimento de portal", "desenvolvimento de plataforma", "desenvolvimento de solucao inovadora",
        "desenvolvimento de sistema",
    ], NEG_TI, ambiguos=["construcao de sistemas", "evolucao de sistemas"], contexto=CTX_TI),
    DefCategoria("fabrica_software", "Fábrica de software", "ti", [
        "fabrica de software", "ponto de funcao", "pontos de funcao", "unidade de servico tecnico", " ust ",
        " squad ", " squads ", "metodos ageis", "praticas ageis", "alocacao de profissionais de ti",
        "servicos tecnicos especializados de tic", "outsourcing de desenvolvimento",
    ], NEG_TI),
    DefCategoria("manutencao_software", "Manutenção de software", "ti", [
        "manutencao corretiva e evolutiva", "manutencao evolutiva", "manutencao adaptativa", "manutencao de software",
        "sistemas legados", "reengenharia de software",
    ], NEG_TI + ["sistema de iluminacao", "sistema de abastecimento", "sistema de rodagem", "sistemas de alarme", "cftv"],
        ambiguos=["manutencao de sistemas", "manutencao do sistema", "manutencao corretiva", "modernizacao de sistemas", "migracao de sistemas",
                  "evolucao funcional"], contexto=CTX_TI),
    DefCategoria("sustentacao", "Sustentação de sistemas", "ti", [
        "sustentacao de sistemas", "sustentacao de software", "sustentacao de aplicacoes", "sustentacao e evolucao",
        "sustentacao de solucoes", "sustentacao do sistema", "application management",
        "suporte n2", "suporte n3", "niveis minimos de servico de sistemas",
    ], NEG_TI, ambiguos=["sustentacao tecnica"], contexto=CTX_TI),
    DefCategoria("ti_mensal", "Tecnologia com valor fixo mensal (locação, licença, SaaS)", "ti", [
        "locacao de software", "locacao de softwares", "locacao de licenca",
        "locacao de licencas", "locacao de programa", "locacao e licenciamento", "locacao mensal de software",
        "licenciamento mensal", "licenca mensal", "licencas mensais", "cessao de uso de software", "cessao de uso de sistema",
        "cessao do direito de uso", "cessao de direito de uso", "direito de uso de software", "direito de uso de sistema",
        "software como servico", "software as a service", " saas ", "assinatura de software", "assinatura de plataforma",
        "assinatura de licencas", "assinatura de sistema", "subscricao de licencas", "subscricao de software",
        "sistema de gestao publica", "sistemas de gestao publica",
        "sistema integrado de gestao publica", "sistemas integrados de gestao publica", "locacao de equipamentos de informatica",
        "locacao de computadores", "locacao de notebooks", "locacao de microcomputadores", "locacao de servidores",
        "outsourcing de ti", "outsourcing de estacoes", "estacoes de trabalho como servico",
        "desktop como servico", "infraestrutura como servico", "plataforma como servico",
    ], ["licenca perpetua", "licencas perpetuas", "locacao de veiculo", "locacao de maquinas", "locacao de imovel",
        "locacao de impressoras", "outsourcing de impressao", "multifuncion",
        "videomonitoramento", "video monitoramento", "fiscalizacao eletronica", "cameras", "radares", "sistema operacional",
        "windows 11", "windows 10"],
        ambiguos=["licenciamento de uso", "licenca de uso", "licencas de uso", "licenciamento de direito de uso",
                  "mensalidade", "valor mensal", "pagamento mensal", "parcelas mensais", "custo mensal", "preco mensal",
                  "assinatura", "hospedagem", "locacao de sistema", "locacao de sistemas", "locacao de solucao",
                  "provimento de sistema", "provimento de solucao"],
        contexto=CTX_TI + ["sistemas de gestao", "sistema web", "software", "licenca"]),
    DefCategoria("tecnologia", "Tecnologia (geral: equipamentos, software, internet, telecom)", "ti", [
        "tecnologia da informacao", "tecnologia de informacao", "tecnologia da informacao e comunicacao", " tic ", " ti ",
        "informatica", "software", "softwares", "sistema informatizado", "sistemas informatizados", "sistema web",
        "aplicativo", "aplicativos", "solucao tecnologica", "solucoes tecnologicas", "plataforma digital", "plataforma web",
        " computador ", " computadores ", " microcomputador ", " microcomputadores ", "notebook", "notebooks", "desktop", "desktops",
        "chromebook", "chromebooks", "tablet", "tablets", "estacoes de trabalho", "workstation", "servidor de rede",
        "servidores de rede", " rack ", " switch ", " switches ", "roteador", "roteadores", "access point", "wi-fi", "wifi",
        "rede logica", "redes logicas", "cabeamento estruturado", "fibra optica", "link de internet", "links de internet",
        "link dedicado", "acesso a internet", "servico de internet", "internet banda larga", "conectividade",
        "telefonia", "telecomunicacao", "telecomunicacoes", " voip ", " pabx ", "central telefonica", "rede de dados",
        "data center", "datacenter", "em nuvem", "computacao em nuvem", " cloud ", "licenca de software", "licencas de software", "antivirus",
        "certificado digital", "certificados digitais", "nobreak", "nobreaks", "lousa digital", "lousas digitais",
        "painel interativo", "paineis interativos", "robotica educacional", "kit de robotica", "impressora 3d",
        "videomonitoramento", "video monitoramento", " cftv ", "biometria", "biometrico", "totem de autoatendimento",
        "inteligencia artificial", "transformacao digital", "governo digital", "cidade inteligente", "cidades inteligentes",
        "internet das coisas", " iot ", "georreferenciamento", "geoprocessamento", "drone", "drones",
    ], ["servidores publicos", "servidores municipais", "servidores efetivos", "capacitacao de servidores",
        "tecnologia de pavimentacao", "tecnologia led", "luminarias", "iluminacao publica", "agenciamento de viagens",
        "tomografia", "pulverizador agricola"]),
    DefCategoria("ia", "Inteligência artificial", "ti", [
        "inteligencia artificial", "aprendizado de maquina", "machine learning", "ia generativa", "modelo de linguagem",
        " llm ", "visao computacional", "chatbot",
    ], ["agenciamento de viagens", "passagens aereas", "reserva, emissao", "emissao, marcacao", "hospedagem em hoteis"]),
    DefCategoria("dados", "Tratamento e processamento de dados", "ti", [
        "tratamento de dados", "ciencia de dados", "engenharia de dados", "analise de dados",
        "business intelligence", "data lake", "data warehouse", "governanca de dados", "qualidade de dados",
        "saneamento cadastral", "saneamento de dados", "requalificacao cadastral", "requalificacao de dados",
        "recadastramento", "higienizacao de dados", "higienizacao de base", "mineracao de dados",
        "inteligencia de dados", "analytics", "cadastro territorial multifinalitario", "geoprocessamento",
    ], ["equipamentos de processamento de dados", "materiais de processamento de dados", "material de processamento de dados",
        "dados variaveis", "centro de processamento de dados", "nobreak", "computadores", "plano de dados",
        "comunicacao de dados", "link de dados", "dados moveis", "teamviewer"],
        ambiguos=["migracao de dados", "processamento de dados", " etl "],
        contexto=["saneamento", "higienizacao", "qualidade de dados", "tratamento de dados", "base de dados",
                  "carga de dados historicos", "legado", "cadastr", "analise de dados", "digitacao"]),
    DefCategoria("cloud", "Cloud computing", "ti", [
        "computacao em nuvem", "cloud computing", "servicos de nuvem", "nuvem publica", " iaas ", " paas ",
        "cloud broker", "hospedagem em nuvem",
    ]),
    DefCategoria("servidores", "Servidores e data center", "ti", [
        # "servidores" sozinho pega servidor público (uniforme, consignado, plano de saúde): só com qualificador de TI
        "servidores de rede", "servidor de rede", "servidores fisicos", "servidores virtuais", "servidores de aplicacao",
        "servidores de banco de dados", "servidores rack", "servidores blade", "servidor rack", "servidores em nuvem",
        "servidor de arquivos", "servidores de arquivos", "data center", "datacenter", "storage", "armazenamento de dados",
        "hiperconvergente", "exadata", "solucao de backup",
    ], ["servidores publicos", "servidores municipais", "servidores do municipio", "capacitacao de servidores"]),
    DefCategoria("seguranca", "Segurança da informação", "ti", [
        "seguranca da informacao", "ciberseguranca", "seguranca cibernetica", "firewall", "siem", "soc ",
        "antivirus", "endpoint", "prevencao de vazamento de dados", "pentest", "teste de intrusao",
    ]),
    DefCategoria("suporte", "Suporte técnico de TI", "ti", [
        "suporte tecnico de ti", "service desk", "central de servicos", "suporte a usuarios", "help desk",
        "atendimento ao usuario de tic",
    ]),
    DefCategoria("integracao", "Integração de sistemas", "ti", [
        "integracao de sistemas", "integracao sistemica", "barramento de servicos", "interoperabilidade", "middleware",
    ], ["instituicao financeira", "instituicoes financeiras", "cobranca bancaria", "consignad", "torniquete"], ambiguos=[" api ", " apis "], contexto=CTX_TI),
    DefCategoria("infra_ti", "Infraestrutura de TI e TIC", "ti", [
        "infraestrutura de ti", "infraestrutura de tic", "infraestrutura de tecnologia",
        "cabeamento estruturado", "rede definida por software", " sdn ", "switches", "wi-fi corporativ", "rede wi-fi", "wi-fi gerenciad",
        "rede sem fio", " polan ", "rede optica passiva",
    ], ["execucao da obra", "execucao de obra", "execucao das obras", "obra de", "obras de", "construcao de", "reforma de", "quadra poliesportiva", "plotter", "cortinas", "climatizacao", "ar condicionado", "pulpito"], ambiguos=["wi-fi", "rede de dados"], contexto=CTX_TI + ["internet", "rede logica", "conectividade", "switch", "access point"]),
    # ---- Tecnologia ampliada (12/11): termos tirados de editais abertos que antes não caíam em categoria de TI
    DefCategoria("sistemas_gestao", "Sistemas de gestão e licenças de software", "ti", [
        "sistema de gestao escolar", "sistemas de gestao escolar", "gestao escolar informatizada", "sistema integrado de gestao",
        "sistemas integrados de gestao", " erp ", "sistema de gestao hospitalar", "gestao hospitalar informatizada",
        "prontuario eletronico", "nota fiscal eletronica", " nfs-e ", " nfse ", "sistema de folha de pagamento",
        "sistema de arrecadacao", "sistema tributario", "sistema de protocolo", "sistema de processo eletronico",
        "solucao de processo eletronico",
        "sistema de gestao patrimonial", "sistema de gestao de pessoas", "sistema de gestao de frota", "sistema de gestao de saude",
        "software de gestao", "softwares de gestao", "solucao sistemica", "licenciamento de software", "licenciamento de sistema",
        "licenca de uso de software", "licencas de uso de software", "sistema de gestao de documentos",
    ], ["sistema de gestao ambiental", "gestao da qualidade", "sistema de gestao de abastecimento", "cartao magnetico",
        "cartao fisico", "alienacao", "leilao", "venda de imovel", "bens imoveis"], ambiguos=["sistema de gestao", "sistemas de gestao", "plataforma de gestao", "sistema web",
                                    "sistema online", "gestao online"],
        # sem "sistema de gestao" no contexto: senão a expressão ambígua confirmaria a si mesma
        contexto=[x for x in CTX_TI if "gestao" not in x] + [" app ", "licenca de uso", "licenciamento", "informatizad", "em nuvem"]),
    DefCategoria("cidades_inteligentes", "Cidades inteligentes e mobilidade", "ti", [
        "cidade inteligente", "cidades inteligentes", "smart city", "monitoramento urbano inteligente", "gestao da mobilidade",
        "mobilidade inteligente", "semaforos inteligentes", "semaforizacao inteligente", "centro de controle operacional",
        "centro integrado de operacoes", "centro de operacoes integradas", "estacionamento rotativo digital",
        "estacionamento rotativo eletronico", "zona azul digital", "telegestao", "iluminacao inteligente",
        "leitura automatica de placas", "cercamento eletronico", "fiscalizacao eletronica de transito", "bilhetagem eletronica",
    ], ["iluminacao publica convencional"]),
    DefCategoria("telecom", "Telecomunicações e conectividade", "ti", [
        "link dedicado", "links dedicados", "link de internet", "links de internet", "acesso a internet", "internet banda larga",
        "banda larga", "rede mundial de computadores", " ip fixo ", " ips fixos ", "fibra optica", "telefonia fixa", "telefonia movel",
        "telefonia ip", "telefonia em nuvem", " pabx ", " voip ", "central telefonica", "comunicacao via satelite",
        "comunicacoes por satelite", "comunicacao por satelite", "internet via satelite", "radiocomunicacao", "radios digitais",
        "rede mpls", " sd-wan ", " sdwan ", "wi-fi publico", "wifi publico", "telecomunicacoes", "servico movel pessoal",
        "chips de dados", "plano de dados", "conectividade",
    ], ["fibra de vidro", "emissoras de radio", "radiodifusao comercial", "veiculacao"]),
    DefCategoria("seguranca_eletronica", "CFTV, videomonitoramento e segurança eletrônica", "ti", [
        " cftv ", "circuito fechado de televisao", "circuito fechado de tv", "videomonitoramento", "video monitoramento",
        "monitoramento por cameras", "monitoria por cameras", "cameras de seguranca", "cameras de videomonitoramento",
        "controle de acesso eletronico", "catraca eletronica", "catracas eletronicas", "reconhecimento facial",
        "alarme monitorado", "monitoramento de alarmes", "seguranca eletronica", "monitoramento eletronico",
    ], ["camera fotografica", "cameras fotograficas"]),
    DefCategoria("iot_telemetria", "Rastreamento, telemetria e IoT", "ti", [
        "telemetria", "videotelemetria", "rastreamento veicular", "rastreamento de veiculos", "rastreador", "rastreadores",
        "rastreamento por gps", "rastreamento via satelite", "sistema de rastreamento", "internet das coisas", " iot ", " rfid ",
        "monitoramento remoto", "sensores inteligentes",
    ], ["rastreamento do cancer", "rastreamento de cancer", "rastreamento neonatal", "rastreamento auditivo", "rastreamento oncologico",
        "locacao de veiculo", "locacao de veiculos", "veiculos zero quilometro", "locacao de caminh", "locacao de onibus"]),
    DefCategoria("edtech", "Tecnologia educacional", "ti", [
        "robotica educacional", "robotica programavel", "kits de robotica", "kit de robotica", "kits educacionais de robotica",
        "laboratorio de robotica", "lousa digital", "lousas digitais", "lousa interativa", "lousas interativas", "painel interativo",
        "paineis interativos", "realidade virtual", "realidade aumentada", "laboratorio maker", "espaco maker", "impressora 3d",
        "impressoras 3d", "plataforma educacional", "plataformas educacionais", "plataforma de ensino", "educacao digital",
        "tecnologia educacional", "tecnologias educacionais", "conteudo educacional digital", "conteudos digitais",
    ], ["lousa de vidro", "lousas de vidro", "quadro branco"]),
    DefCategoria("audiovisual_tec", "Audiovisual, videoconferência e transmissão", "ti", [
        "videoconferencia", "transmissao ao vivo", "streaming", "solucao audiovisual", "sistema audiovisual", "telao de led", "transmissao audiovisual", "transmissao das sessoes",
    ], ["sonorizacao para eventos", "som e iluminacao", "som iluminacao", "palco", "palcos", "tendas", "sonorizacao",
        "iluminacao cenica", "shows", "festividades", "estruturas para eventos"]),
    DefCategoria("impressao", "Outsourcing de impressão", "ti", [
        "outsourcing de impressao", "impressao corporativa", "locacao de impressoras", "locacao de multifuncionais",
        "locacao de equipamentos multifuncionais", "comodato de impressoras", "impressoras em regime de comodato",
        "franquia de impressao", "servicos de impressao e copia", "servico de impressao e copia", "servicos de reprografia",
        "solucao de impressao", "gestao de impressao", "bilhetagem de impressao",
    ], ["impressao grafica", "servicos graficos", "material grafico", "impressao 3d"]),
    DefCategoria("equipamentos_ti", "Equipamentos de informática", "ti", [
        " computador ", " computadores ", " microcomputador ", " microcomputadores ", " notebook ", " notebooks ", " desktop ",
        " desktops ", "all in one", "all-in-one", " tablet ", " tablets ", " chromebook ", " chromebooks ", "monitor de video",
        "monitores de video", "equipamentos de informatica", "equipamentos de tecnologia da informacao", "materiais de informatica",
        "suprimentos de informatica", "perifericos de informatica", " nobreak ", " nobreaks ", " switch ", " switches ",
        " roteador ", " roteadores ", "access point", " scanner ", " scanners ", " impressora ", " impressoras ",
    ], ["tomografia computadorizada", "tomografo computadorizado", "impressora 3d", "impressoras 3d", "rede mundial de computadores",
        "raio x", "raios x", "backscatter", "inspecao de bagagem"]),
    # ---------------------------------------------------------------- EAD, educação digital e pesquisa
    DefCategoria("ead", "EAD e educação a distância", "educacao_pesquisa", [
        "educacao a distancia", "ensino a distancia", "ensino remoto", " ead ", " ead/", "/ead ", "ambiente virtual de aprendizagem",
        " ava ", " lms ", "learning management", "moodle", "e-learning", "elearning", "cursos online", "cursos on-line",
        "curso online", "curso on-line", "cursos a distancia", "curso a distancia", "capacitacao a distancia",
        "capacitacao online", "capacitacao on-line", "treinamento a distancia", "treinamento online", "treinamento on-line",
        "plataforma de ensino", "plataforma educacional", "plataforma de aprendizagem", "plataforma de educacao",
        "plataforma de cursos", "plataforma adaptativa", "conteudos educacionais digitais", "conteudo educacional digital",
        "objetos de aprendizagem", "objetos digitais de aprendizagem", "videoaulas", "video aulas", "aulas gravadas",
        "aulas remotas", "educacao digital", "universidade corporativa", "escola virtual", "trilhas de aprendizagem",
        "trilhas formativas", "microlearning", "gamificacao educacional", "tecnologia educacional", "solucao educacional digital",
        "recursos educacionais digitais", "livro digital interativo", "laboratorio virtual",
    ], ["aquisicao de material", "aquisicao de acervo", "ensino a distancia de motoristas", "transporte escolar", "uniforme", "merenda", "generos alimenticios",
        "kit escolar", "material escolar", "mobiliario"]),
    DefCategoria("pesquisa", "Pesquisa (opinião, satisfação, campo)", "educacao_pesquisa", [
        "pesquisa de opiniao", "pesquisa de satisfacao", "pesquisas de satisfacao", "pesquisa qualitativa",
        "pesquisa quantitativa", "pesquisa quali", "pesquisa domiciliar", "pesquisa de campo", "pesquisas de campo",
        "pesquisa socioeconomica", "diagnostico socioeconomico", "levantamento socioeconomico", "pesquisa amostral",
        "pesquisa censitaria", "pesquisa estatistica", "levantamento estatistico", "realizacao de pesquisa",
        "pesquisa de clima organizacional", "pesquisa de imagem", "pesquisa de percepcao", "pesquisa de avaliacao",
        "pesquisa de origem e destino", "pesquisa origem-destino", "pesquisa de mobilidade", "pesquisa nacional",
        "pesquisa de audiencia", "pesquisa eleitoral", "survey", "grupos focais", "grupo focal",
    ], NEG_PESQUISA + ["cesta de precos", "banco de precos"]),
    DefCategoria("pd_inovacao", "Pesquisa, desenvolvimento e inovação (P&D)", "educacao_pesquisa", [
        "pesquisa e desenvolvimento", "pesquisa, desenvolvimento e inovacao", " p d ", " pd i ", " p d i ",
        "pesquisa aplicada", "pesquisa tecnologica", "pesquisa e inovacao", "encomenda tecnologica",
        "solucao inovadora", "solucoes inovadoras", "marco legal das startups", "lei complementar 182",
        "lei complementar n 182", "contrato publico para solucao inovadora", " cpsi ", "bolsas de pesquisa",
        "laboratorio de inovacao", "hub de inovacao", "sandbox regulatorio", "programa de inovacao aberta",
    ], NEG_PESQUISA, ambiguos=["pesquisa cientifica", "inovacao tecnologica", "desenvolvimento tecnologico",
                                "transferencia de tecnologia", "projetos de pesquisa", "projeto de pesquisa"],
        contexto=["contratacao de servicos", "prestacao de servicos", "desenvolvimento de", "execucao de projeto",
                  "consultoria", "estruturacao", "parceria"]),
    # ---------------------------------------------------------------- Engenharia e obras
    DefCategoria("projetos_engenharia", "Projetos de engenharia", "engenharia", [
        "projeto basico", "projeto executivo", "projetos basicos e executivos", "elaboracao de projetos",
        "projetos de engenharia", "projeto arquitetonico",
    ]),
    DefCategoria("bim", "BIM", "engenharia", [" bim ", "modelagem da informacao da construcao", "geobim"]),
    DefCategoria("fiscalizacao_obras", "Fiscalização e gerenciamento de obras", "engenharia", [
        "fiscalizacao de obras", "supervisao de obras", "gerenciamento de obras", "verificacao independente",
        "apoio a fiscalizacao",
    ]),
    DefCategoria("orcamentos", "Orçamentos e planejamento de obras", "engenharia", [
        "orcamento de obras", "planilha orcamentaria", "composicao de custos", "cronograma fisico-financeiro",
        "planejamento de obras",
    ]),
    DefCategoria("infraestrutura_publica", "Infraestrutura pública", "engenharia", [
        "pavimentacao", "drenagem", "saneamento basico", "recapeamento", "obras de infraestrutura", "construcao de",
        "reforma de", "ampliacao de",
    ], ["mao de obra", "sistema de gestao"]),
    DefCategoria("sistemas_obras", "Sistemas de gestão de obras", "engenharia", [
        "sistema de gestao de obras", "gestao de obras publicas", "software de obras", "plataforma de gestao de obras",
    ]),
]

SEGMENTOS = {
    "gestao_documental": "Gestão documental",
    "ti": "Tecnologia da informação",
    "engenharia": "Engenharia e obras",
    "educacao_pesquisa": "EAD, educação digital e pesquisa",
}


_SEPARADORES = re.compile(r"[^a-z0-9]+")


def texto_busca(texto: str | None) -> str:
    """Texto normalizado para procurar termos: a forma original (para termos com pontuação, como "ged/" ou
    "decreto 10.278") e a forma com pontuação trocada por espaço, para que termos de palavra inteira
    (" cftv ", " ust ") casem também em "CFTV," ou "(UST)". Até 12/11 só a primeira forma era usada."""
    n = normalizar(texto or "")
    return " " + n + " \x00 " + _SEPARADORES.sub(" ", n).strip() + " "


def termo_normalizado(termo: str) -> str:
    """Normaliza o termo, mantendo os espaços de borda que marcam palavra inteira (ex.: " ged ")."""
    n = normalizar(termo)
    return (" " if termo.startswith(" ") else "") + n + (" " if termo.endswith(" ") else "")


def _casa(texto_norm: str, termo: str) -> bool:
    return termo_normalizado(termo) in texto_norm


def classificar(objeto: str, categorias: list[DefCategoria] | None = None) -> list[dict]:
    """Devolve as categorias do objeto, com os termos que casaram. Um termo de exclusão anula a categoria."""
    cats = categorias or PADRAO
    n = texto_busca(objeto)
    saida = []
    for c in cats:
        casados = [t.strip() for t in c.termos if _casa(n, t)]
        if c.ambiguos and any(_casa(n, x) for x in c.contexto):
            casados += [t.strip() for t in c.ambiguos if _casa(n, t)]
        if not casados:
            continue
        bloqueio = [t for t in c.excluir if _casa(n, t)]
        if bloqueio and not any(_casa(n, f) for f in c.fortes):
            continue
        saida.append({
            "codigo": c.codigo, "nome": c.nome, "segmento": c.segmento,
            "termos": casados, "forca": min(1.0, 0.5 + 0.25 * len(casados)),
        })
    # "Tecnologia" reúne tudo o que caiu em alguma categoria de TI (o filtro geral de tecnologia vê todas)
    geral = next((c for c in cats if c.codigo == "tecnologia"), None)
    ti = [x["codigo"] for x in saida if x["segmento"] == "ti" and x["codigo"] != "tecnologia"]
    if geral and ti and not any(x["codigo"] == "tecnologia" for x in saida):
        saida.append({"codigo": "tecnologia", "nome": geral.nome, "segmento": "ti", "termos": [f"via {c}" for c in ti[:3]], "forca": 0.5})
    return saida


# Serviço documental que só aparece nos itens: o objeto diz "gestão documental" ou "gerenciamento eletrônico de
# processos" e os itens trazem "digitalização de documentos (página)", "indexação de documentos"...
_ITEM_DOCUMENTAL = {
    "digitalizacao": re.compile(
        r"digitalizacao (de|do|dos|da|das) (documento|acervo|prontuario|processo|arquivo|livro|jornai|folha|pagina|"
        r"registro|certid|matricula|ficha|pasta|plantas? (de|do|dos) (arquivo|acervo|processo))|"
        r"(paginas?|imagens?|folhas?) digitalizad|escaneamento de document|microfilmagem|"
        r"captura de imagens de document|prepar\w* (e|para) digitalizacao|digitalizacao e indexacao"),
    "indexacao": re.compile(r"indexacao (de|do|dos|da|das) (documento|imagen|acervo|processo|arquivo|registro|pagina|metadado)|"
                            r"digitalizacao e indexacao"),
}
_COMPRA_EQUIPAMENTO = re.compile(r"aquisica\w* .{0,40}(equipamento|materia|perifer|computador|suprimento|move)|"
                                 r"equipamentos e suprimentos|materiais de processamento|equipamentos de informatica|"
                                 r"fornecimento de moveis|aerolevantamento|fotogrametr")


def documental_pelos_itens(objeto: str, itens: list[tuple[str | None, str | None]], ja: set[str]) -> list[dict]:
    """Digitalização e indexação achadas na descrição dos itens, quando o objeto não diz. Compra de equipamento
    (scanner, computador) não conta: o interesse é o serviço."""
    obj = normalizar(objeto or "")
    if natureza(objeto) == "material" or _COMPRA_EQUIPAMENTO.search(obj):
        return []
    textos = [normalizar(d or "") for _, d in itens]
    saida = []
    for codigo, rx in _ITEM_DOCUMENTAL.items():
        if codigo in ja:
            continue
        achados = sorted({m.group(0) for t in textos for m in [rx.search(t)] if m})
        if achados:
            c = por_codigo(codigo)
            saida.append({"codigo": codigo, "nome": c.nome, "segmento": c.segmento,
                          "termos": [f"item: {a}" for a in achados[:3]], "forca": 0.5})
    return saida


# Forma de pagamento dos contratos de TI. O objeto quase nunca diz; a unidade dos itens costuma dizer
# ("UND SERVIÇO TÉCNICO", "PONTO DE FUNÇÃO", "VALOR FIXO MENSAL", "MÊS").
REMUNERACAO = {
    "remun_fixo_mensal": "Pagamento fixo mensal (TI)",
    "remun_ust": "Remuneração por UST",
    "remun_pf": "Remuneração por Ponto de Função",
}
_UST = [" ust ", " usts ", "unidade de servico tecnico", "unidades de servico tecnico",
        "unidade de servicos tecnicos", "unidades de servicos tecnicos", "unidade de servico de tecnologia"]
# "UND SERVIÇO TÉCNICO" é a unidade genérica de serviço do catálogo do Compras.gov (na base de 11/11: mediana
# R$ 5.134 por unidade, até R$ 47 mi), não UST. Só conta como UST com volume e preço de UST.
UST_QTD_MIN, UST_PRECO_MAX = 100, 2000.0
# com a unidade genérica, item que é licença, assinatura, locação, link ou nuvem não é UST mesmo com volume
_NAO_UST = re.compile(r"licen|assinatura|ramal|locacao|link|nuvem|cloud|saas|software como servico|hospedagem|colocation|"
                      r"equipamento|aparelho|telefon|internet|datacenter|data center|armazenamento|backup|certificado|"
                      r"minut|chamada|ligac|voz|sms|dados moveis")
_SIM_UST = re.compile(r"desenvolv|sustenta|suporte|manutencao|analis|consultor|atendimento|operac|implanta|treinament|projeto|especializad|programac|teste|banco de dados|infraestrutura|gestao de servicos")


def item_ust(unidade: str | None, descricao: str | None, qtd: float | None = None, preco: float | None = None) -> bool:
    """Item cobrado em UST: a descrição diz UST, a unidade é "UST", ou a unidade é "serviço técnico" com
    quantidade e preço unitário de UST (>= 100 unidades, até R$ 2.000 cada)."""
    u = texto_busca(unidade)
    d = texto_busca(descricao)
    if set(u.split()) & {"ust", "usts"}:
        return True
    if set(u.split()) & {"hora", "horas", "hst", "hh", "hs", "h"}:  # "Hora Serviço Técnico" (HST) é hora técnica, não UST
        return False
    if any(x in d for x in _UST):
        return True
    if "servico tecnico" in u or "servicos tecnicos" in u:
        return ((qtd or 0) >= UST_QTD_MIN and (preco is None or float(preco) <= UST_PRECO_MAX)
                and _SIM_UST.search(d) is not None and not _NAO_UST.search(d))
    return False
_PF = ["ponto de funcao", "pontos de funcao", "function point", "function points"]
_FIXO = ["valor fixo mensal", "preco fixo mensal", "remuneracao fixa mensal", "pagamento fixo mensal",
         "pagamento mensal fixo", "valor mensal fixo", "parcela fixa mensal", "parcelas fixas mensais", "fixo mensal"]
_MES = {"mes", "meses", "mensal", "mensalidade", "men"}
# no objeto de um edital de tecnologia/documentos, estes termos indicam cobrança mensal (contrato de duração em
# "12 meses" sozinho não indica: todo serviço continuado diz isso)
_MENSAL_TEXTO = [" mensal ", " mensais ", "mensalidade", " por mes ", " ao mes ", "valor mensal", "pagamento mensal",
                 "locacao mensal", "licenca mensal", "assinatura mensal", "parcelas mensais", "cobranca mensal"]
_SEG_TEC = {"ti", "gestao_documental"}
# pagamento fixo mensal que interessa: software e serviço de TI/documentos. Link de internet, telefonia, impressão,
# equipamento, CFTV e afins também são mensais, mas não são "fixo mensal de software" (auditoria de 13/11)
_CATS_MENSAL_SOFTWARE = {"desenvolvimento", "fabrica_software", "manutencao_software", "sustentacao", "ti_mensal", "sistemas_gestao",
                         "dados", "ia", "cloud", "servidores", "seguranca", "suporte", "integracao", "ged", "ocr", "digitalizacao",
                         "indexacao", "triagem", "guarda", "higienizacao"}


def remuneracao(texto: str, itens: list[tuple[str | None, str | None]], categorias: list[dict],
                texto_documentos: str = "") -> list[dict]:
    """Formas de pagamento do edital (UST, ponto de função, fixo mensal), pelo texto, pelos itens (unidade, descrição)
    e pelo texto dos documentos baixados (termo de referência, edital). Fixo mensal só conta em edital de
    tecnologia ou gestão documental."""
    n = texto_busca(texto)
    docs = texto_busca(texto_documentos) if texto_documentos else ""
    itens = [tuple(i) + (None,) * (4 - len(i)) for i in itens]  # (unidade, descrição[, quantidade, preço unitário])
    unids = [texto_busca(i[0]) for i in itens]
    tudo = n + " ".join(texto_busca(i[1]) for i in itens)
    achados: dict[str, list[str]] = {}
    n_ust = sum(item_ust(*i) for i in itens)
    for cod, termos, extra in (("remun_ust", _UST, None), ("remun_pf", _PF, " pf ")):
        ts = [x.strip() for x in termos if x in n]
        if cod == "remun_ust" and n_ust:
            ts.append(f"{n_ust} {'item' if n_ust == 1 else 'itens'} em UST")
        elif cod == "remun_pf":
            ts += [f"item: {x.strip()}" for x in termos if x not in n and (x in tudo or any(x in u for u in unids))]
        ts += [f"documento: {x.strip()}" for x in termos if docs and x in docs and x.strip() not in ts]
        if extra and any(extra in u for u in unids):
            ts.append(f"unidade {extra.strip()}")
        if ts:
            achados[cod] = ts
    if any(c["codigo"] in _CATS_MENSAL_SOFTWARE for c in categorias):
        ts = [x for x in _FIXO if x in tudo or any(x in u for u in unids)]
        if any(set(u.split()) & _MES for u in unids):
            ts.append("itens cobrados por mês")
        ts += [f"objeto: {x.strip()}" for x in _MENSAL_TEXTO if x in n][:2]
        ts += [f"documento: {x}" for x in _FIXO if docs and x in docs][:1]
        if ts:
            achados["remun_fixo_mensal"] = ts
    return [{"codigo": c, "nome": REMUNERACAO[c], "segmento": "ti", "termos": ts, "forca": 1.0} for c, ts in achados.items()]


# ------------------------------------------------------------------ serviço x material e volumes
_AQUISICAO = re.compile(r"\b(aquisicao|aquisicoes|compra|compras|fornecimento de (materia|equipamento|bens|insumos|kits|livros|"
                        r"computador|notebook|tablet|mobiliario|veiculo|generos|medicamento|uniforme)|"
                        r"material permanente|materiais permanentes|material de consumo|materiais de consumo)\b")
_SERVICO = re.compile(r"\b(servico|servicos|prestacao|locacao|licenciamento|cessao de uso|consultoria|assessoria|manutencao|"
                      r"suporte|desenvolvimento|digitalizacao|sustentacao|implantacao|hospedagem|outsourcing|fabrica de software|"
                      r"tratamento|gestao documental|treinamento|capacitacao|saas|software como servico)\b")


def natureza(objeto: str | None, itens: list[tuple[str | None, float | None]] | None = None) -> str | None:
    """'servico', 'material' ou 'misto'. Pelos itens do PNCP (campo material/serviço, pesado pelo valor) quando
    houver; senão pelo objeto. None quando não dá para dizer."""
    if itens:
        tot = {"m": 0.0, "s": 0.0}
        for ms, valor in itens:
            k = "m" if normalizar(ms or "").startswith("m") else "s" if normalizar(ms or "").startswith("s") else None
            if k:
                tot[k] += float(valor or 0) or 1.0
        soma = tot["m"] + tot["s"]
        if soma:
            if tot["m"] / soma >= 0.8:
                return "material"
            if tot["s"] / soma >= 0.8:
                return "servico"
            return "misto"
    n = normalizar(objeto or "")
    aq, sv = bool(_AQUISICAO.search(n)), bool(_SERVICO.search(n))
    return "misto" if aq and sv else "material" if aq else "servico" if sv else None


# tipo de volume -> (nome, quantidade mínima para "grande volume")
VOLUMES = {
    "ust": ("UST", 1_000), "pf": ("pontos de função", 300), "pagina": ("páginas/imagens", 100_000),
    "registro": ("registros de dados", 100_000), "hora": ("horas técnicas", 1_000), "mes": ("meses de serviço", 12),
}
_V_PAGINA_UN = {"pagina", "paginas", "pag", "imagem", "imagens", "folha", "folhas", "lauda", "laudas", "fls", "pgs"}
_V_PAGINA_TXT = ["por pagina", "por imagem", "por folha", "paginas digitalizadas", "imagens digitalizadas",
                 "imagens geradas", "paginas de documentos", "folhas de documentos", "imagem digitalizada", "pagina digitalizada"]
_HORA_UN = {"hora", "horas", "hs", "h", "hrs", "hr", "hst", "hh"}
_HORA_SERV = re.compile(r"tecnic|servico|consultor|customiz|desenvolv|suporte|parametriz|implant|treinament|manutenc|sistema|"
                        r"software|analis|programa|infraestrutura|evoluti|especializad")
_HORA_DESC = re.compile(r"^ ?(horas? tecnicas?|horas? de servicos? tecnicos?|banco de horas tecnicas|horas? homem|homem hora)")
_V_REG_UN = {"registro", "registros", "dado", "dados", "cadastro", "cadastros", "transacao", "transacoes"}
# fora de volume de serviço de TI/documentos: impressão, monitoramento, alarme, área, distância, laudos médicos
_V_FORA = ["impress", "toner", "copia", "videomonitoramento", "video monitoramento", "alarme", "sensores", "seguranca eletronica",
           "laudo", "tomografia", "radiografia", "veiculo", "fibra", "camera", "carro de som", "propaganda", "mecanica"]
_V_REG_DESC = ["cadastr", "recadastr", "digitacao", "saneamento de dados", "saneamento cadastral", "geocodific", "migracao de dados",
               "base de dados", "higienizacao de dados", "processamento de dados", "tratamento de dados", "registros"]
_V_REG_TXT = ["por registro", "registros tratados", "registros saneados", "registros processados", "registros digitados",
              "registros indexados", "registros cadastrados", "registros migrados"]


def tipo_volume(unidade: str | None, descricao: str | None, qtd: float | None, preco: float | None = None) -> str | None:
    """Tipo de volume de um item (ust, pf, pagina, registro, hora, mes) ou None."""
    if not qtd:
        return None
    u = texto_busca(unidade)
    d = texto_busca(descricao)
    pal = set(u.split())
    fora = any(x in d for x in _V_FORA) or pal & {"m2", "km", "quilometro", "metro", "metros"}
    if item_ust(unidade, descricao, qtd, preco):
        return "ust"
    if any(x in u or x in d for x in _PF) or " pf " in u:
        return "pf"
    if fora:
        return None
    if pal & _V_PAGINA_UN or any(x in d for x in _V_PAGINA_TXT):
        return "pagina"
    if qtd >= 10_000 and any(x in d for x in ("digitaliz", "escane", "microfilm", "captura de imagens", "indexac", "higieniza")):
        return "pagina"  # digitalização/indexação cobrada por "unidade" = página/imagem
    if pal & _V_REG_UN or any(x in d for x in _V_REG_TXT):
        return "registro"
    if qtd >= 10_000 and any(x in d for x in _V_REG_DESC):
        return "registro"  # dados cobrados por "unidade" (cadastros, digitação, saneamento)
    # horas técnicas (HST, homem-hora): unidade de hora + descrição de serviço de TI, ou "hora técnica" na descrição
    if (pal & _HORA_UN or any(x in u for x in ("homem hora", "hora homem", "h/h", "hora servico", "hora tecnica"))) and _HORA_SERV.search(u + d):
        return "hora"
    if _HORA_DESC.search(d):
        return "hora"
    if pal & _MES or "fixo mensal" in u:
        return "mes"
    return None


def volumes(itens: list[tuple[str | None, str | None, float | None]]) -> dict[str, float]:
    """Soma das quantidades por tipo de volume (UST, PF, páginas, registros, horas, meses), pelos itens
    (unidade, descrição, quantidade). Só itens de serviço de TI/documentos chegam aqui."""
    tot: dict[str, float] = {}
    for item in itens:
        unidade, descricao, qtd, preco = (tuple(item) + (None,))[:4]
        k = tipo_volume(unidade, descricao, qtd, preco)
        if k:
            tot[k] = tot.get(k, 0.0) + float(qtd)
    return tot


def grande_volume(vol: dict[str, float], valor: float | None = None) -> list[str]:
    """Tipos com volume grande. Meses de itens diferentes não se somam com sentido, então o pagamento
    mensal conta como grande pelo valor do edital (a partir de R$ 1 milhão)."""
    return [k for k, q in vol.items() if (k == "mes" and (valor or 0) >= 1_000_000) or (k != "mes" and q >= VOLUMES[k][1])]


def expandir_consulta(consulta: str, categorias: list[DefCategoria] | None = None) -> dict:
    """Transforma a consulta em grupos de termos equivalentes.

    Cada palavra ou expressão da consulta vira um grupo: ela mesma mais os termos de toda categoria
    em que ela aparece (no nome ou na lista de termos). Os grupos são combinados com E; dentro de
    cada grupo, OU. Ex.: "digitalização" -> [digitalizacao, escaneamento, captura de imagens, ...].
    """
    cats = categorias or PADRAO
    partes = [p.strip() for p in consulta.replace(";", ",").split(",") if p.strip()]
    grupos = []
    for parte in partes:
        n = normalizar(parte)
        termos = {n}
        relacionadas = []
        regras = []
        for c in cats:
            nomes = [normalizar(c.nome), c.codigo.replace("_", " ")] + [normalizar(t) for t in c.termos]
            if any(n == x or (len(n) >= 5 and (n in x or x in n) and len(x) >= 4) for x in nomes):
                termos.update(termo_normalizado(t) for t in c.termos)
                relacionadas.append(c.codigo)
                regras.append({
                    "categoria": c.codigo,
                    "excluir": sorted({termo_normalizado(t) for t in c.excluir}),
                    "ambiguos": sorted({termo_normalizado(t) for t in c.ambiguos}),
                    "contexto": sorted({termo_normalizado(t) for t in c.contexto}),
                })
        grupos.append({"consulta": parte, "termos": sorted(t for t in termos if t.strip()),
                       "categorias": relacionadas, "regras": regras})
    return {"grupos": grupos}


def por_codigo(codigo: str, categorias: list[DefCategoria] | None = None) -> DefCategoria | None:
    for c in categorias or PADRAO:
        if c.codigo == codigo:
            return c
    return None


def categorias_ativas(s) -> list[DefCategoria]:
    """Padrão + categorias cadastradas pelo usuário (tabela `categoria`). Fica em cache na sessão."""
    if "categorias" not in s.info:
        from .modelos import Categoria

        extras = [DefCategoria(c.codigo, c.nome, c.segmento, list(c.termos or []), list(c.excluir or []))
                  for c in s.query(Categoria).filter_by(ativa=True).all()]
        codigos = {c.codigo for c in extras}
        s.info["categorias"] = [c for c in PADRAO if c.codigo not in codigos] + extras
    return s.info["categorias"]


# ------------------------------------------------------------------ volume escrito no texto (objeto, termo de referência)
# Muitos editais têm um único item "serviço" (quantidade 1) e a quantidade real fica no texto:
# "estimativa de 1.250.000 UST", "3,9 milhões de páginas", "32.900 horas técnicas".
# número por extenso entre o valor e a unidade ("1.250.000 (um milhão duzentos e cinquenta mil) UST"; a normalização tira
# os parênteses)
_EXTENSO = (r"(?:(?:um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|"
            r"dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem|cento|duzentos|duzentas|"
            r"trezentos|trezentas|quatrocentos|quatrocentas|quinhentos|quinhentas|seiscentos|seiscentas|setecentos|setecentas|"
            r"oitocentos|oitocentas|novecentos|novecentas|mil|milhao|milhoes|e)\s+){0,16}")
_NUM_TXT = r"(\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)\s*(mil|milhoes|milhao)?\s*(?:\([^)]{0,60}\)\s*)?" + _EXTENSO + r"(?:de\s+)?"
_VOL_TXT = {
    "ust": re.compile(_NUM_TXT + r"(?:ust|usts|unidades? de servicos? tecnicos?)\b"),
    "pf": re.compile(_NUM_TXT + r"(?:pontos? de funcao)\b"),
    "hora": re.compile(_NUM_TXT + r"(?:horas?[ -](?:tecnicas?|de servicos? tecnicos?|homem)|hst|homens?[ -]hora)\b"),
    "pagina": re.compile(_NUM_TXT + r"(?:paginas?|imagens?|folhas?)\b"),
}
VOL_TXT_MIN = {"ust": 100, "pf": 50, "hora": 100, "pagina": 10_000}
VOL_TXT_MAX = {"ust": 50_000_000, "pf": 1_000_000, "hora": 5_000_000, "pagina": 2_000_000_000}


def _numero_txt(n: str, mult: str | None) -> float:
    v = float(n.replace(".", "").replace(",", "."))
    if "." in n:  # "1.800 (mil e oitocentas)": o "mil" é do número por extenso, não multiplicador
        return v
    return v * (1e3 if mult == "mil" else 1e6 if mult and mult.startswith("milh") else 1)


# quantidade exigida em atestado de habilitação não é o volume do contrato
_CTX_HABILITACAO = re.compile(r"atestado|quantitativo minimo|no minimo|minimo de|comprovacao|comprovar|qualificacao tecnica|experiencia|"
                              r"capacidade tecnica|parcela de maior relevancia|similar")


def preco_plausivel(tipo: str, quantidade: float, valor: float | None) -> bool:
    """Valor do edital dividido pela quantidade dentro de uma faixa possível para o tipo (sem valor: aceita)."""
    if not valor or not quantidade:
        return True
    faixa = {"ust": (10, 5_000), "pf": (100, 10_000), "hora": (15, 3_000), "pagina": (0.01, 30)}[tipo]
    return faixa[0] <= valor / quantidade <= faixa[1] * 20  # o edital pode ter outros itens além deste volume


def volumes_no_texto(texto: str, documental: bool = False) -> dict[str, float]:
    """Maior quantidade de UST, ponto de função, horas técnicas e (só em edital de digitalização/indexação) páginas
    citada no texto. Valores fora da faixa plausível são ignorados."""
    n = normalizar(texto or "")
    out: dict[str, float] = {}
    for k, rx in _VOL_TXT.items():
        if k == "pagina" and not documental:
            continue
        vals = [_numero_txt(m.group(1), m.group(2)) for m in rx.finditer(n)
                if not _CTX_HABILITACAO.search(n[max(0, m.start() - 120):m.start()])]
        vals = [v for v in vals if VOL_TXT_MIN[k] <= v <= VOL_TXT_MAX[k]]
        if vals:
            out[k] = max(vals)
    return out
