"""Tabelas de referência. A fonte atualizada é `pncp dominio <tabela>`."""

VERSAO = "2.0.0"

BASE = "https://pncp.gov.br"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MODALIDADES = {
    1: "Leilão - Eletrônico",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Presencial",
    14: "Inaplicabilidade da Licitação",
    15: "Chamada pública",
    16: "Concorrência - Eletrônica Internacional",
    17: "Concorrência - Presencial Internacional",
    18: "Pregão - Eletrônico Internacional",
    19: "Pregão - Presencial Internacional",
}

STATUS = ["recebendo_proposta", "propostas_encerradas", "encerradas", "todos"]

TIPOS_BUSCA = ["edital", "ata", "contrato"]

DOMINIOS = {
    "modalidades": "/api/pncp/v1/modalidades",
    "amparos-legais": "/api/pncp/v1/amparos-legais",
    "modos-disputas": "/api/pncp/v1/modos-disputas",
    "criterios-julgamentos": "/api/pncp/v1/criterios-julgamentos",
    "tipos-documentos": "/api/pncp/v1/tipos-documentos",
    "tipos-contratos": "/api/pncp/v1/tipos-contratos",
    "tipos-instrumentos-convocatorios": "/api/pncp/v1/tipos-instrumentos-convocatorios",
    "tipos-instrumentos-cobranca": "/api/pncp/v1/tipos-instrumentos-cobranca",
    "portes-empresa": "/api/pncp/v1/portes-empresa",
    "fontes-orcamentarias": "/api/pncp/v1/fontes-orcamentarias",
    "catalogos": "/api/pncp/v1/catalogos",
    "categorias-item-pca": "/api/pncp/v1/categoriaItemPcas",
    "tipos-parte-envolvida": "/api/pncp/v1/tipos-parte-envolvida",
    "instrumento-modalidade-amparo": "/api/pncp/v1/instrumento-convocatorio-modalidade-amparo-legal",
    "modalidade-criterio": "/api/pncp/v1/modalidade-criterio-julgamento",
    "modalidade-fonte": "/api/pncp/v1/modalidade-fonte-orcamentaria",
    "instrumento-modo-disputa": "/api/pncp/v1/tipo-instrumento-convocatorio-modo-disputa",
}
