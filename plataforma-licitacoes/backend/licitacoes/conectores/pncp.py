"""Conector do Portal Nacional de Contratações Públicas (PNCP) — API oficial, sem autenticação.

APIs usadas:
* Consulta (https://pncp.gov.br/api/consulta/v1): listagens por publicação, por atualização
  e de propostas abertas; consulta individual da contratação.
* Integração (https://pncp.gov.br/api/pncp/v1): itens, resultados e arquivos (edital, TR, anexos).

Comportamentos medidos em chamadas reais (out/2026, ver docs/fontes.md): datas em AAAAMMDD
(ISO dá 422); `codigoModalidadeContratacao` obrigatório em /publicacao e /atualizacao;
`tamanhoPagina` de 10 a 50; 204 = sem registros; 429 com corpo HTML e sem Retry-After
(intervalo de 4 s evita); edital excluído responde 410 na consulta individual.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from ..config import config
from ..util import link_pncp, numero_controle, para_data, para_valor, so_digitos
from .base import ClienteHttp, ErroFonte

CONSULTA = "https://pncp.gov.br/api/consulta/v1"
INTEGRACAO = "https://pncp.gov.br/api/pncp/v1"

MODALIDADES = {
    1: "Leilão - Eletrônico", 2: "Diálogo Competitivo", 3: "Concurso", 4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial", 6: "Pregão - Eletrônico", 7: "Pregão - Presencial", 8: "Dispensa",
    9: "Inexigibilidade", 10: "Manifestação de Interesse", 11: "Pré-qualificação", 12: "Credenciamento",
    13: "Leilão - Presencial", 14: "Inaplicabilidade da Licitação", 15: "Chamada pública",
}
SITUACOES = {1: "Divulgada no PNCP", 2: "Revogada", 3: "Anulada", 4: "Suspensa"}


def fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


class ConectorPncp:
    codigo = "pncp"

    def __init__(self, http: ClienteHttp | None = None):
        cfg = config()
        self.http = http or ClienteHttp(intervalo_minimo_s=cfg.pncp_intervalo_s)
        self.tamanho = max(10, min(50, cfg.pncp_tamanho_pagina))

    # ----------------------------------------------------------------- listagens
    def _paginar(self, caminho: str, params: dict[str, Any], max_paginas: int = 1000) -> Iterator[dict]:
        pagina = 1
        while pagina <= max_paginas:
            corpo = self.http.get_json(f"{CONSULTA}{caminho}", {**params, "pagina": pagina, "tamanhoPagina": self.tamanho})
            if not corpo:
                return
            dados = corpo.get("data") or []
            yield from dados
            restantes = corpo.get("paginasRestantes")
            total = corpo.get("totalPaginas")
            if corpo.get("empty") or not dados:
                return
            if restantes is not None and restantes <= 0:
                return
            if restantes is None and total is not None and pagina >= total:
                return
            pagina += 1
        raise ErroFonte(f"limite de {max_paginas} páginas em {caminho} {params}")

    def por_publicacao(self, inicio: date, fim: date, modalidade: int, uf: str | None = None) -> Iterator[dict]:
        p = {"dataInicial": fmt(inicio), "dataFinal": fmt(fim), "codigoModalidadeContratacao": modalidade}
        if uf:
            p["uf"] = uf
        yield from self._paginar("/contratacoes/publicacao", p)

    def por_atualizacao(self, inicio: date, fim: date, modalidade: int, uf: str | None = None) -> Iterator[dict]:
        """Contratações alteradas no período: pega prorrogação, suspensão, revogação e retificação."""
        p = {"dataInicial": fmt(inicio), "dataFinal": fmt(fim), "codigoModalidadeContratacao": modalidade}
        if uf:
            p["uf"] = uf
        yield from self._paginar("/contratacoes/atualizacao", p)

    def propostas_abertas(self, ate: date, modalidade: int | None = None, uf: str | None = None) -> Iterator[dict]:
        """Contratações com recebimento de propostas aberto que encerram até `ate`."""
        p: dict[str, Any] = {"dataFinal": fmt(ate)}
        if modalidade is not None:
            p["codigoModalidadeContratacao"] = modalidade
        if uf:
            p["uf"] = uf
        yield from self._paginar("/contratacoes/proposta", p)

    def contratacao(self, cnpj: str, ano: int, sequencial: int) -> dict | None:
        """Consulta individual (a fonte mais atual). None se o edital foi excluído (404/410)."""
        try:
            return self.http.get_json(f"{CONSULTA}/orgaos/{so_digitos(cnpj)}/compras/{ano}/{sequencial}")
        except ErroFonte as e:
            if e.status in (404, 410):
                return None
            raise

    # ----------------------------------------------------------------- detalhes
    def itens(self, cnpj: str, ano: int, sequencial: int) -> list[dict]:
        url = f"{INTEGRACAO}/orgaos/{so_digitos(cnpj)}/compras/{ano}/{sequencial}/itens"
        saida: list[dict] = []
        pagina = 1
        while True:
            dados = self.http.get_json(url, {"pagina": pagina, "tamanhoPagina": 500})
            if not dados:
                break
            lote = dados if isinstance(dados, list) else dados.get("data") or []
            saida.extend(lote)
            if len(lote) < 500:
                break
            pagina += 1
        return saida

    def resultados_item(self, cnpj: str, ano: int, sequencial: int, numero_item: int) -> list[dict]:
        url = f"{INTEGRACAO}/orgaos/{so_digitos(cnpj)}/compras/{ano}/{sequencial}/itens/{numero_item}/resultados"
        try:
            dados = self.http.get_json(url)
        except ErroFonte as e:
            if e.status == 404:
                return []
            raise
        if not dados:
            return []
        return dados if isinstance(dados, list) else [dados]

    def arquivos(self, cnpj: str, ano: int, sequencial: int) -> list[dict]:
        url = f"{INTEGRACAO}/orgaos/{so_digitos(cnpj)}/compras/{ano}/{sequencial}/arquivos"
        dados = self.http.get_json(url)
        if not dados:
            return []
        return dados if isinstance(dados, list) else dados.get("data") or []

    @staticmethod
    def url_arquivo(cnpj: str, ano: int, sequencial: int, seq_doc: int) -> str:
        return f"{INTEGRACAO}/orgaos/{so_digitos(cnpj)}/compras/{ano}/{sequencial}/arquivos/{seq_doc}"


def normalizar_contratacao(raw: dict, fonte: str = "pncp") -> dict:
    """Converte o registro do PNCP para o esquema único da plataforma."""
    org = raw.get("orgaoEntidade") or {}
    uni = raw.get("unidadeOrgao") or {}
    cnpj = so_digitos(org.get("cnpj"))
    ano = raw.get("anoCompra")
    seq = raw.get("sequencialCompra")
    controle = raw.get("numeroControlePNCP") or (numero_controle(cnpj, ano, seq) if cnpj and ano and seq else None)
    mod_id = raw.get("modalidadeId")
    valor = para_valor(raw.get("valorTotalEstimado"))
    sit_id = raw.get("situacaoCompraId")
    return {
        "chave": f"pncp:{controle}",
        "numero_controle_pncp": controle,
        "tipo_registro": "contratacao",
        "cnpj_orgao": cnpj or None,
        "orgao_nome": org.get("razaoSocial"),
        "esfera": org.get("esferaId"),
        "poder": org.get("poderId"),
        "unidade_nome": uni.get("nomeUnidade"),
        "ano": ano,
        "sequencial": seq,
        "numero_compra": raw.get("numeroCompra"),
        "processo": raw.get("processo"),
        "modalidade_id": mod_id,
        "modalidade": raw.get("modalidadeNome") or MODALIDADES.get(mod_id),
        "modo_disputa": raw.get("modoDisputaNome"),
        "situacao": raw.get("situacaoCompraNome") or SITUACOES.get(sit_id),
        "srp": raw.get("srp"),
        "objeto": (raw.get("objetoCompra") or "").strip(),
        "informacao_complementar": raw.get("informacaoComplementar"),
        "valor_estimado": valor,
        "valor_homologado": para_valor(raw.get("valorTotalHomologado")),
        # O PNCP manda 0 quando o órgão não informa; orçamento sigiloso (art. 24 da Lei 14.133) aparece assim.
        "orcamento_sigiloso": valor is None,
        "data_publicacao": para_data(raw.get("dataPublicacaoPncp")),
        "data_abertura": para_data(raw.get("dataAberturaProposta")),
        "data_encerramento": para_data(raw.get("dataEncerramentoProposta")),
        "data_atualizacao_fonte": para_data(raw.get("dataAtualizacaoGlobal") or raw.get("dataAtualizacao")),
        "uf": uni.get("ufSigla"),
        "municipio": uni.get("municipioNome"),
        "codigo_ibge": uni.get("codigoIbge"),
        "link_pncp": link_pncp(cnpj, ano, seq) if cnpj and ano and seq else None,
        "link_origem": raw.get("linkSistemaOrigem"),
        "usuario_publicador": raw.get("usuarioNome"),
        "fonte": fonte,
        "bruto": raw,
    }


def normalizar_item(raw: dict) -> dict:
    return {
        "numero": raw.get("numeroItem"),
        "descricao": (raw.get("descricao") or "").strip(),
        "material_servico": raw.get("materialOuServicoNome") or raw.get("materialOuServico"),
        "quantidade": raw.get("quantidade"),
        "unidade": raw.get("unidadeMedida"),
        "valor_unitario": raw.get("valorUnitarioEstimado"),
        "valor_total": raw.get("valorTotal"),
        "situacao": raw.get("situacaoCompraItemNome"),
        "criterio_julgamento": raw.get("criterioJulgamentoNome"),
        "bruto": raw,
    }


def normalizar_arquivo(raw: dict, cnpj: str, ano: int, sequencial: int) -> dict:
    seq_doc = raw.get("sequencialDocumento")
    url = raw.get("url") or raw.get("uri")
    if not url and seq_doc is not None:
        url = ConectorPncp.url_arquivo(cnpj, ano, sequencial, seq_doc)
    return {
        "sequencial": seq_doc,
        "titulo": (raw.get("titulo") or raw.get("tipoDocumentoNome") or f"Documento {seq_doc}").strip(),
        "tipo_fonte": raw.get("tipoDocumentoNome") or raw.get("tipoDocumentoDescricao"),
        "url": url,
        "publicado_em": para_data(raw.get("dataPublicacaoPncp")),
        "ativo": raw.get("statusAtivo", True) is not False,
    }
