"""Conectores além do PNCP.

* Compras.gov.br — API de Dados Abertos (dadosabertos.compras.gov.br), sem autenticação.
  Traz as contratações da Lei 14.133 (espelho do PNCP para o SIASG) e o módulo legado (Lei 8.666).
* Querido Diário (Open Knowledge Brasil) — busca textual em diários oficiais municipais.
  Cobre avisos de licitação de prefeituras que não publicam no PNCP.
* Portal da Transparência (CGU) — licitações federais do SIASG. Exige chave gratuita.
* IBGE — lista oficial dos municípios, usada para medir a cobertura comprovada.
* Espelhos públicos do PNCP no GitHub — cópias diárias da API do PNCP feitas por projetos abertos.
  Servem quando o acesso direto ao PNCP está bloqueado na rede; cada registro mantém o link oficial.

Os nomes de campo do Compras.gov foram tirados da documentação pública (Swagger) e o mapeamento
aceita variações; o conector ainda não foi validado ao vivo (ver docs/fontes.md).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Iterator
from datetime import date
from typing import Any

from ..config import config
from ..util import link_pncp, numero_controle, para_data, para_valor, partes_pncp, so_digitos
from .base import ClienteHttp, ErroFonte
from .pncp import MODALIDADES


def _primeiro(raw: dict, *chaves: str) -> Any:
    for c in chaves:
        if c in raw and raw[c] not in (None, ""):
            return raw[c]
    return None


# --------------------------------------------------------------------------- Compras.gov.br
class ConectorComprasGov:
    codigo = "comprasgov"
    BASE = "https://dadosabertos.compras.gov.br"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp(intervalo_minimo_s=1.5)

    def _paginar(self, caminho: str, params: dict) -> Iterator[dict]:
        pagina = 1
        while True:
            corpo = self.http.get_json(f"{self.BASE}{caminho}", {**params, "pagina": pagina, "tamanhoPagina": 500})
            if not corpo:
                return
            lote = corpo.get("resultado") or corpo.get("data") or corpo.get("_embedded", {}).get("licitacoes") or []
            yield from lote
            restantes = corpo.get("paginasRestantes")
            total = corpo.get("totalPaginas")
            if not lote or (restantes is not None and restantes <= 0) or (restantes is None and total and pagina >= total):
                return
            pagina += 1

    def contratacoes_14133(self, inicio: date, fim: date, modalidade: int) -> Iterator[dict]:
        yield from self._paginar("/modulo-contratacoes/1_consultarContratacoes_PNCP_14133", {
            "dataPublicacaoPncpInicial": inicio.isoformat(),
            "dataPublicacaoPncpFinal": fim.isoformat(),
            "codigoModalidade": modalidade,
        })

    def licitacoes_legado(self, inicio: date, fim: date) -> Iterator[dict]:
        yield from self._paginar("/modulo-legado/1_consultarLicitacao", {
            "data_publicacao_inicial": inicio.isoformat(),
            "data_publicacao_final": fim.isoformat(),
        })


def normalizar_comprasgov_14133(raw: dict) -> dict:
    cnpj = so_digitos(_primeiro(raw, "orgaoEntidadeCnpj", "cnpjOrgao", "orgaoCnpj"))
    ano = _primeiro(raw, "anoCompraPncp", "anoCompra")
    seq = _primeiro(raw, "sequencialCompraPncp", "sequencialCompra")
    controle = _primeiro(raw, "numeroControlePNCP", "numeroControlePncp") or (
        numero_controle(cnpj, ano, seq) if cnpj and ano and seq else None)
    valor = para_valor(_primeiro(raw, "valorTotalEstimado", "valorEstimado"))
    mod = _primeiro(raw, "codigoModalidade", "modalidadeId")
    return {
        "chave": f"pncp:{controle}" if controle else f"comprasgov:{_primeiro(raw, 'idCompra', 'id')}",
        "numero_controle_pncp": controle,
        "tipo_registro": "contratacao",
        "cnpj_orgao": cnpj or None,
        "orgao_nome": _primeiro(raw, "orgaoEntidadeRazaoSocial", "nomeOrgao"),
        "esfera": _primeiro(raw, "orgaoEntidadeEsferaId", "esferaId"),
        "unidade_nome": _primeiro(raw, "unidadeOrgaoNomeUnidade", "nomeUnidade"),
        "ano": ano, "sequencial": seq,
        "numero_compra": _primeiro(raw, "numeroCompra"),
        "processo": _primeiro(raw, "processo"),
        "modalidade_id": mod,
        "modalidade": _primeiro(raw, "modalidadeNome") or MODALIDADES.get(mod),
        "modo_disputa": _primeiro(raw, "modoDisputaNomePncp", "modoDisputaNome"),
        "situacao": _primeiro(raw, "situacaoCompraNomePncp", "situacaoCompraNome"),
        "srp": _primeiro(raw, "srp"),
        "objeto": (_primeiro(raw, "objetoCompra", "objeto") or "").strip(),
        "informacao_complementar": _primeiro(raw, "informacaoComplementar"),
        "valor_estimado": valor,
        "valor_homologado": para_valor(_primeiro(raw, "valorTotalHomologado")),
        "orcamento_sigiloso": valor is None,
        "data_publicacao": para_data(_primeiro(raw, "dataPublicacaoPncp", "dataPublicacao")),
        "data_abertura": para_data(_primeiro(raw, "dataAberturaPropostaPncp", "dataAberturaProposta")),
        "data_encerramento": para_data(_primeiro(raw, "dataEncerramentoPropostaPncp", "dataEncerramentoProposta")),
        "uf": _primeiro(raw, "unidadeOrgaoUfSigla", "ufSigla", "uf"),
        "municipio": _primeiro(raw, "unidadeOrgaoMunicipioNome", "municipioNome"),
        "codigo_ibge": _primeiro(raw, "unidadeOrgaoCodigoIbge", "codigoIbge"),
        "link_pncp": link_pncp(cnpj, ano, seq) if cnpj and ano and seq else None,
        "link_origem": _primeiro(raw, "linkSistemaOrigem"),
        "fonte": "comprasgov",
        "bruto": raw,
    }


def normalizar_comprasgov_legado(raw: dict) -> dict:
    ident = _primeiro(raw, "identificador", "id_compra", "numero_aviso")
    valor = para_valor(_primeiro(raw, "valor_estimado_total", "valor_estimado"))
    uasg = _primeiro(raw, "uasg", "co_uasg")
    return {
        "chave": f"siasg:{ident}",
        "numero_controle_pncp": None,
        "tipo_registro": "contratacao",
        "cnpj_orgao": None,
        "orgao_nome": _primeiro(raw, "nome_orgao", "no_orgao", "orgao"),
        "unidade_nome": f"UASG {uasg}" if uasg else None,
        "esfera": "F",
        "numero_compra": _primeiro(raw, "numero_aviso", "nu_aviso"),
        "processo": _primeiro(raw, "numero_processo", "nu_processo"),
        "modalidade_id": None,
        "modalidade": _primeiro(raw, "nome_modalidade", "modalidade"),
        "situacao": _primeiro(raw, "situacao_aviso", "situacao"),
        "objeto": (_primeiro(raw, "objeto", "ds_objeto") or "").strip(),
        "valor_estimado": valor,
        "orcamento_sigiloso": False,
        "data_publicacao": para_data(_primeiro(raw, "data_publicacao", "dt_publicacao")),
        "data_abertura": para_data(_primeiro(raw, "data_abertura_proposta", "data_entrega_proposta")),
        "data_encerramento": para_data(_primeiro(raw, "data_entrega_proposta", "data_abertura_proposta")),
        "uf": _primeiro(raw, "uf", "sg_uf"),
        "municipio": _primeiro(raw, "municipio", "no_municipio"),
        "link_origem": _primeiro(raw, "link_edital", "url"),
        "fonte": "comprasgov",
        "bruto": raw,
    }


# --------------------------------------------------------------------------- Querido Diário
class ConectorQueridoDiario:
    codigo = "querido_diario"
    BASE = "https://api.queridodiario.ok.org.br"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp(intervalo_minimo_s=1.0)

    def buscar(self, consulta: str, inicio: date, fim: date, tamanho: int = 100, max_paginas: int = 20) -> Iterator[dict]:
        offset = 0
        for _ in range(max_paginas):
            corpo = self.http.get_json(f"{self.BASE}/gazettes", {
                "querystring": consulta, "published_since": inicio.isoformat(), "published_until": fim.isoformat(),
                "excerpt_size": 600, "number_of_excerpts": 5, "size": tamanho, "offset": offset,
                "sort_by": "descending_date",
            })
            if not corpo:
                return
            diarios = corpo.get("gazettes") or []
            yield from diarios
            offset += len(diarios)
            if not diarios or offset >= (corpo.get("total_gazettes") or 0):
                return


def normalizar_diario(diario: dict, consulta: str) -> list[dict]:
    """Cada trecho do diário que cita a consulta vira um aviso. O link é o diário oficial original."""
    saida = []
    for trecho in diario.get("excerpts") or []:
        t = " ".join(trecho.split())
        h = hashlib.sha1(t.encode()).hexdigest()[:16]
        saida.append({
            "chave": f"qd:{diario.get('territory_id')}:{diario.get('date')}:{h}",
            "numero_controle_pncp": None,
            "tipo_registro": "aviso_diario",
            "orgao_nome": f"Município de {diario.get('territory_name')}",
            "esfera": "M",
            "modalidade": "Aviso em diário oficial",
            "situacao": "Publicado em diário oficial",
            "objeto": t[:4000],
            "orcamento_sigiloso": False,
            "valor_estimado": None,
            "data_publicacao": para_data(diario.get("date")),
            "uf": diario.get("state_code"),
            "municipio": diario.get("territory_name"),
            "codigo_ibge": diario.get("territory_id"),
            "link_origem": diario.get("url"),
            "fonte": "querido_diario",
            "bruto": {"diario": {k: v for k, v in diario.items() if k != "excerpts"}, "trecho": t, "consulta": consulta},
        })
    return saida


# --------------------------------------------------------------------------- Portal da Transparência
class ConectorTransparencia:
    codigo = "portal_transparencia"
    BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"

    def __init__(self, chave: str | None = None, http: ClienteHttp | None = None):
        self.chave = chave or config().transparencia_chave
        if not self.chave:
            raise ErroFonte("Portal da Transparência exige chave (LIC_TRANSPARENCIA_CHAVE)")
        self.http = http or ClienteHttp(intervalo_minimo_s=0.7, cabecalhos={"chave-api-dados": self.chave})

    def licitacoes(self, inicio: date, fim: date, codigo_orgao: str) -> Iterator[dict]:
        pagina = 1
        while True:
            lote = self.http.get_json(f"{self.BASE}/licitacoes", {
                "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": fim.strftime("%d/%m/%Y"),
                "codigoOrgao": codigo_orgao, "pagina": pagina,
            })
            if not lote:
                return
            yield from lote
            pagina += 1


def normalizar_transparencia(raw: dict) -> dict:
    lic = raw.get("licitacao") or {}
    org = raw.get("unidadeGestora", {}).get("orgaoVinculado", {}) if isinstance(raw.get("unidadeGestora"), dict) else {}
    mun = raw.get("municipio") or {}
    return {
        "chave": f"cgu:{raw.get('id')}",
        "numero_controle_pncp": None,
        "tipo_registro": "contratacao",
        "orgao_nome": org.get("nome") or (raw.get("unidadeGestora") or {}).get("nome"),
        "esfera": "F",
        "numero_compra": lic.get("numero"),
        "processo": lic.get("numeroProcesso"),
        "modalidade": (raw.get("modalidadeLicitacao") or {}).get("descricao"),
        "situacao": raw.get("situacaoCompra") or raw.get("situacao"),
        "objeto": (lic.get("objeto") or "").strip(),
        "valor_estimado": para_valor(raw.get("valor")),
        "orcamento_sigiloso": False,
        "data_publicacao": para_data(raw.get("dataPublicacao")),
        "data_abertura": para_data(raw.get("dataAbertura")),
        "data_encerramento": para_data(raw.get("dataAbertura")),
        "uf": (mun.get("uf") or {}).get("sigla"),
        "municipio": mun.get("nomeIBGE"),
        "codigo_ibge": mun.get("codigoIBGE"),
        "link_origem": "https://portaldatransparencia.gov.br/licitacoes/" + str(raw.get("id")),
        "fonte": "portal_transparencia",
        "bruto": raw,
    }


# --------------------------------------------------------------------------- IBGE
CODIGO_UF = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE",
             24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP",
             41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF"}


class ConectorIbge:
    """Lista de municípios: API do IBGE; se ela não responder, a cópia pública (MIT) de kelvins/municipios-brasileiros."""

    codigo = "ibge"
    URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    COPIA = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp(intervalo_minimo_s=0.5, max_tentativas=2, cabecalhos={"Accept": "*/*"})
        self.origem = None

    def municipios(self) -> list[dict]:
        try:
            dados = self.http.get_json(self.URL) or []
            self.origem = self.URL
        except ErroFonte:
            r = self.http.requisitar("GET", self.COPIA)
            self.origem = self.COPIA
            linhas = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))) if r is not None else []
            return [{"codigo_ibge": x["codigo_ibge"], "nome": x["nome"], "uf": CODIGO_UF.get(int(x["codigo_uf"]))}
                    for x in linhas]
        saida = []
        for m in dados:
            uf = None
            micro = m.get("microrregiao") or {}
            meso = micro.get("mesorregiao") or {}
            uf = (meso.get("UF") or {}).get("sigla")
            if not uf:
                ri = m.get("regiao-imediata") or {}
                uf = ((ri.get("regiao-intermediaria") or {}).get("UF") or {}).get("sigla")
            saida.append({"codigo_ibge": str(m["id"]), "nome": m["nome"], "uf": uf})
        return saida


# --------------------------------------------------------------------------- Espelhos do PNCP
ESPELHOS = [
    {
        "codigo": "radar_pncp_victor_ozores",
        "descricao": "Radar-PNCP (MIT) — editais do PNCP, exportação diária em CSV",
        "url": "https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/editais.csv",
        "formato": "csv_radar",
    },
    {
        "codigo": "painel_novatrindade",
        "descricao": "Painel NovaTrindade — editais abertos de gestão pública municipal (JSON diário)",
        "url": "https://raw.githubusercontent.com/NovaTrindade/painel-983b65a9ddb7/main/dados/editais.json",
        "formato": "json_novatrindade",
    },
    {
        "codigo": "painel_novatrindade_ia",
        "descricao": "Painel NovaTrindade — editais de TI e documentos (JSON diário)",
        "url": "https://raw.githubusercontent.com/NovaTrindade/painel-983b65a9ddb7/main/dados/editais-ia.json",
        "formato": "json_novatrindade",
    },
]


class ConectorEspelhos:
    codigo = "espelhos_pncp"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp(intervalo_minimo_s=0.5, timeout_s=180, cabecalhos={"Accept": "*/*"})

    def baixar(self, espelho: dict) -> bytes:
        r = self.http.requisitar("GET", espelho["url"])
        return r.content if r is not None else b""

    def registros(self, espelho: dict, conteudo: bytes | None = None) -> Iterator[dict]:
        dados = conteudo if conteudo is not None else self.baixar(espelho)
        if espelho["formato"] == "csv_radar":
            yield from (r for r in (_de_radar(x) for x in csv.DictReader(io.StringIO(dados.decode("utf-8-sig")))) if r)
        elif espelho["formato"] == "json_novatrindade":
            corpo = json.loads(dados.decode("utf-8"))
            for e in corpo.get("editais") or []:
                r = _de_novatrindade(e, corpo.get("gerado"))
                if r:
                    yield r


def _base_espelho(cnpj: str, ano: int, seq: int) -> dict:
    controle = numero_controle(cnpj, ano, seq)
    return {"chave": f"pncp:{controle}", "numero_controle_pncp": controle, "tipo_registro": "contratacao",
            "cnpj_orgao": cnpj, "ano": ano, "sequencial": seq, "link_pncp": link_pncp(cnpj, ano, seq),
            "fonte": "espelhos_pncp"}


def _de_radar(r: dict) -> dict | None:
    partes = partes_pncp(r.get("link_pncp")) or partes_pncp(r.get("id") or r.get("﻿id"))
    if not partes:
        return None
    cnpj, ano, seq = partes
    valor = para_valor(r.get("valor_estimado"))
    mod = r.get("modalidade_id")
    d = _base_espelho(cnpj, ano, seq)
    d.update({
        "orgao_nome": r.get("orgao"), "esfera": r.get("esfera") or None,
        "modalidade_id": int(mod) if mod and str(mod).isdigit() else None, "modalidade": r.get("modalidade"),
        "situacao": r.get("situacao"), "objeto": (r.get("objeto") or "").strip(),
        "valor_estimado": valor, "orcamento_sigiloso": valor is None,
        "data_publicacao": para_data(r.get("data_publicacao")),
        "data_abertura": para_data(r.get("data_abertura_proposta")),
        "data_encerramento": para_data(r.get("data_encerramento_proposta")),
        "uf": r.get("uf") or None, "municipio": r.get("municipio") or None,
        "link_origem": r.get("link_origem") or None, "bruto": {"espelho": "radar_pncp", **r},
    })
    return d


def _de_novatrindade(e: dict, gerado: str | None) -> dict | None:
    partes = partes_pncp(e.get("pncpUrl"))
    if not partes:
        return None
    cnpj, ano, seq = partes
    valor = para_valor(e.get("valorEstimado"))
    d = _base_espelho(cnpj, ano, seq)
    d.update({
        "orgao_nome": e.get("orgao"), "modalidade": e.get("modalidade"), "numero_compra": e.get("numero"),
        "objeto": (e.get("objeto") or "").strip(), "valor_estimado": valor, "orcamento_sigiloso": valor is None,
        "data_encerramento": para_data(e.get("fimVigencia")), "uf": e.get("uf"), "municipio": e.get("municipio"),
        "bruto": {"espelho": "novatrindade", "gerado": gerado, **{k: v for k, v in e.items() if k != "modulos"}},
    })
    return d
