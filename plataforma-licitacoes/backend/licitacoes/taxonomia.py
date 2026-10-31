"""Categorias de serviço, classificação dos objetos e expansão de consulta por significado.

A busca não depende só da palavra digitada: cada categoria reúne os vários nomes que os editais
usam para o mesmo serviço (ex.: "digitalização" também casa com "conversão de documentos físicos",
"captura de imagens", "OCR", "GED"). Os termos de "excluir" tiram falsos positivos medidos em
dados reais (ex.: "mão de obra" não é obra; "outsourcing de impressão" não é digitalização).
Categorias novas podem ser cadastradas na tabela `categoria`; estas são as padrão.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .util import normalizar

NEG_TI = ["manutencao predial", "ar condicionado", "ar-condicionado", "veiculo", "elevador",
          "material de expediente", "generos alimenticios", "esquadria", "fotovoltaic", "drenagem",
          "iluminacao publica", "videomonitoramento", "video monitoramento", "motobomba", "climatizacao",
          "alarmes", "cameras", "monitoramento eletronico", "seguranca eletronica", "aquisicao de materiais",
          "materiais de informatica", "equipamentos de informatica", "computadores", "perifericos"]
CTX_TI = ["software", "sistema informatizado", "sistemas informatizados", "tecnologia da informacao", " ti ", " tic ",
          "aplicac", "aplicativo", " web ", " erp ", "banco de dados", "codigo fonte", "plataforma digital",
          "sistema de gestao", "sistemas de gestao", "solucao tecnologica"]
CTX_DOC = ["documento", "documental", "acervo", "arquivo", "processos fisicos", "prontuario", "papel"]
NEG_IMPRESSAO = ["outsourcing de impressao", "impressao corporativa", "impressao, copia", "impressao e digitalizacao",
                 "impressao/copia", "multifuncion", "impressoras", "equipamentos de impressao", "locacao de scanners",
                 "scanners documentais", "escaneamento intraoral", "videomonitoramento", "video monitoramento", "cameras",
                 "certificado digital e-cpf", "token"]


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


PADRAO: list[DefCategoria] = [
    # ---------------------------------------------------------------- Gestão documental
    DefCategoria("digitalizacao", "Digitalização", "gestao_documental", [
        "digitalizacao", "escaneamento", "conversao de documentos fisicos", "conversao de suporte",
        "documentos fisicos em digitais", "desmaterializacao", "captura e processamento de imagens",
        "imageamento", "digitalizacao de acervo", "digitalizacao de processos", "digitalizacao de prontuarios",
        "digitalizacao de plantas", "certificacao digital de documentos", "decreto 10.278", "bpo documental",
        "outsourcing de digitalizacao", "microfilmagem", "arquivamento eletronico",
    ], NEG_IMPRESSAO),
    DefCategoria("indexacao", "Indexação", "gestao_documental", [
        "indexacao", "catalogacao de documentos", "classificacao documental", "plano de classificacao",
        "descricao arquivistica", "indexacao de imagens",
    ], ["indexacao doi", "revista cientifica", "periodico", "indice de reajuste", "videomonitoramento",
        "video monitoramento", "cameras"], ambiguos=["metadados"], contexto=CTX_DOC),
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
        "sustentacao tecnica", "sustentacao de solucoes", "sustentacao do sistema", "application management",
        "suporte n2", "suporte n3", "niveis minimos de servico de sistemas",
    ], NEG_TI),
    DefCategoria("ia", "Inteligência artificial", "ti", [
        "inteligencia artificial", "aprendizado de maquina", "machine learning", "ia generativa", "modelo de linguagem",
        " llm ", "visao computacional", "chatbot",
    ]),
    DefCategoria("dados", "Tratamento e processamento de dados", "ti", [
        "tratamento de dados", "ciencia de dados", "engenharia de dados", "analise de dados",
        "business intelligence", "data lake", "data warehouse", " etl ", "governanca de dados", "qualidade de dados",
        "saneamento cadastral", "saneamento de dados", "requalificacao cadastral", "requalificacao de dados",
        "recadastramento", "higienizacao de dados", "higienizacao de base", "mineracao de dados",
        "inteligencia de dados", "analytics", "cadastro territorial multifinalitario", "geoprocessamento",
    ], ["equipamentos de processamento de dados", "materiais de processamento de dados", "material de processamento de dados",
        "dados variaveis", "centro de processamento de dados", "nobreak", "computadores", "plano de dados",
        "comunicacao de dados", "link de dados", "dados moveis", "teamviewer"],
        ambiguos=["migracao de dados", "processamento de dados"],
        contexto=["saneamento", "higienizacao", "qualidade de dados", "tratamento de dados", "base de dados",
                  "carga de dados historicos", "legado", "cadastr", "analise de dados", "digitacao"]),
    DefCategoria("cloud", "Cloud computing", "ti", [
        "computacao em nuvem", "cloud computing", "servicos de nuvem", "nuvem publica", " iaas ", " paas ",
        "cloud broker", "hospedagem em nuvem",
    ]),
    DefCategoria("servidores", "Servidores e data center", "ti", [
        "servidores", "data center", "datacenter", "storage", "armazenamento de dados", "hiperconvergente", "exadata",
        "solucao de backup",
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
        "integracao de sistemas", "integracao sistemica", "barramento de servicos", "interoperabilidade", " api ",
        " apis ", "middleware",
    ]),
    DefCategoria("infra_ti", "Infraestrutura de TI e TIC", "ti", [
        "infraestrutura de ti", "infraestrutura de tic", "infraestrutura de tecnologia", "rede de dados",
        "cabeamento estruturado", "rede definida por software", " sdn ", "wi-fi", "switches",
    ]),
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
}


def termo_normalizado(termo: str) -> str:
    """Normaliza o termo, mantendo os espaços de borda que marcam palavra inteira (ex.: " ged ")."""
    n = normalizar(termo)
    return (" " if termo.startswith(" ") else "") + n + (" " if termo.endswith(" ") else "")


def _casa(texto_norm: str, termo: str) -> bool:
    return termo_normalizado(termo) in texto_norm


def classificar(objeto: str, categorias: list[DefCategoria] | None = None) -> list[dict]:
    """Devolve as categorias do objeto, com os termos que casaram. Um termo de exclusão anula a categoria."""
    cats = categorias or PADRAO
    n = " " + normalizar(objeto) + " "
    saida = []
    for c in cats:
        casados = [t.strip() for t in c.termos if _casa(n, t)]
        if c.ambiguos and any(_casa(n, x) for x in c.contexto):
            casados += [t.strip() for t in c.ambiguos if _casa(n, t)]
        if not casados:
            continue
        bloqueio = [t for t in c.excluir if _casa(n, t)]
        if bloqueio:
            continue
        saida.append({
            "codigo": c.codigo, "nome": c.nome, "segmento": c.segmento,
            "termos": casados, "forca": min(1.0, 0.5 + 0.25 * len(casados)),
        })
    return saida


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
