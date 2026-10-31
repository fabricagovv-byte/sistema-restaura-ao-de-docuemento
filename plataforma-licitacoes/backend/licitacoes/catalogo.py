"""Catálogo de portais e como cada um é coberto.

Status:
* ativo — conector próprio funcionando por API oficial ou dados públicos;
* requer_credencial — conector pronto, falta a chave/cadastro do usuário;
* via_pncp — o portal publica no PNCP (obrigatório pela Lei 14.133, art. 54 e 174), então os editais
  dele chegam pelo conector do PNCP; a plataforma identifica a origem pelo link do sistema;
* nao_integrado — sem API pública ou exige login/CAPTCHA; listado para não ficar escondido.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .modelos import Fonte

CATALOGO = [
    dict(codigo="pncp", nome="Portal Nacional de Contratações Públicas (PNCP)", tipo="api_oficial",
         url_base="https://pncp.gov.br", status_integracao="ativo",
         como_coberto="API de consulta (publicação, atualização, propostas abertas) e API de integração (itens, arquivos).",
         procedimento="Sem credencial. Liberar o acesso de rede a pncp.gov.br."),
    dict(codigo="comprasgov", nome="Compras.gov.br — Dados Abertos", tipo="api_oficial",
         url_base="https://dadosabertos.compras.gov.br", status_integracao="ativo",
         como_coberto="Contratações da Lei 14.133 e módulo legado (Lei 8.666) do SIASG.",
         procedimento="Sem credencial. Liberar dadosabertos.compras.gov.br."),
    dict(codigo="portal_transparencia", nome="Portal da Transparência (CGU)", tipo="api_oficial",
         url_base="https://api.portaldatransparencia.gov.br", status_integracao="requer_credencial",
         como_coberto="Licitações federais por órgão SIAFI.",
         procedimento="Cadastrar e-mail em portaldatransparencia.gov.br/api-de-dados/cadastrar-email e definir "
                      "LIC_TRANSPARENCIA_CHAVE e LIC_TRANSPARENCIA_ORGAOS."),
    dict(codigo="querido_diario", nome="Diários oficiais municipais (Querido Diário)", tipo="diario_oficial",
         url_base="https://queridodiario.ok.org.br/api", status_integracao="ativo",
         como_coberto="Busca textual de avisos de licitação nos diários de centenas de municípios.",
         procedimento="Sem credencial. A cobertura de municípios é a do projeto Querido Diário."),
    dict(codigo="dou", nome="Diário Oficial da União (INLABS)", tipo="diario_oficial",
         url_base="https://inlabs.in.gov.br", status_integracao="requer_credencial",
         como_coberto="Seção 3 do DOU (avisos de licitação).",
         procedimento="Exige cadastro no INLABS da Imprensa Nacional. Conector ainda não implementado; os avisos "
                      "federais chegam pelo PNCP."),
    dict(codigo="diarios_estaduais", nome="Diários oficiais estaduais", tipo="diario_oficial",
         url_base=None, status_integracao="nao_integrado",
         como_coberto="Os editais estaduais da Lei 14.133 chegam pelo PNCP.",
         procedimento="Cada imprensa oficial tem formato próprio; integrar por estado conforme prioridade."),
    dict(codigo="espelhos_pncp", nome="Espelhos públicos do PNCP (GitHub)", tipo="espelho",
         url_base="https://raw.githubusercontent.com", status_integracao="ativo",
         como_coberto="Cópias diárias da API do PNCP feitas por projetos abertos; usadas quando o PNCP está "
                      "inacessível. Cada edital mantém o link oficial e é atualizado pelo PNCP quando ele responder.",
         procedimento="Sem credencial."),
    dict(codigo="licitacoes_e", nome="Licitações-e (Banco do Brasil)", tipo="portal_proprio",
         url_base="https://www.licitacoes-e.com.br", status_integracao="via_pncp",
         como_coberto="Editais da Lei 14.133 publicados no PNCP com link de origem do Licitações-e.",
         procedimento="Sem API pública; não raspamos o portal."),
    dict(codigo="portal_compras_publicas", nome="Portal de Compras Públicas", tipo="portal_proprio",
         url_base="https://www.portaldecompraspublicas.com.br", status_integracao="via_pncp",
         como_coberto="Via PNCP (identificado pelo link de origem e pelo prefixo no objeto).",
         procedimento="Sem API pública aberta."),
    dict(codigo="bll", nome="BLL Compras", tipo="portal_proprio", url_base="https://bllcompras.com",
         status_integracao="via_pncp", como_coberto="Via PNCP (integração BLL → PNCP).", procedimento="Sem API pública."),
    dict(codigo="licitanet", nome="Licitanet", tipo="portal_proprio", url_base="https://licitanet.com.br",
         status_integracao="via_pncp", como_coberto="Via PNCP.", procedimento="Sem API pública."),
    dict(codigo="bbmnet", nome="BBMNET", tipo="portal_proprio", url_base="https://bbmnet.com.br",
         status_integracao="via_pncp", como_coberto="Via PNCP.", procedimento="Sem API pública."),
    dict(codigo="bec_sp", nome="BEC-SP e sistemas estaduais", tipo="portal_proprio", url_base="https://www.bec.sp.gov.br",
         status_integracao="via_pncp", como_coberto="Via PNCP; SP e outros estados publicam no PNCP.",
         procedimento="Conectores diretos por estado podem ser adicionados (páginas públicas, sem login)."),
    dict(codigo="estatais_13303", nome="Estatais em portal próprio (Petronect, Caixa, BB…)", tipo="portal_proprio",
         url_base=None, status_integracao="nao_integrado",
         como_coberto="Parte publica no PNCP; o restante fica em portais com cadastro.",
         procedimento="Exige cadastro de fornecedor em cada portal; não contornamos login."),
]

# domínio do link de origem -> plataforma
PLATAFORMAS = {
    "cnetmobile.estaleiro.serpro.gov.br": "Compras.gov.br",
    "compras.gov.br": "Compras.gov.br",
    "comprasnet.gov.br": "Compras.gov.br",
    "portaldecompraspublicas.com.br": "Portal de Compras Públicas",
    "bllcompras.com": "BLL Compras",
    "bll.org.br": "BLL Compras",
    "bllcompras.org.br": "BLL Compras",
    "licitanet.com.br": "Licitanet",
    "bbmnet.com.br": "BBMNET",
    "licitacoes-e.com.br": "Licitações-e",
    "licitacoes-e2.bb.com.br": "Licitações-e",
    "bec.sp.gov.br": "BEC-SP",
    "compras.mg.gov.br": "Compras MG",
    "www1.compras.mg.gov.br": "Compras MG",
    "licitardigital.com.br": "Licitar Digital",
    "compras.rs.gov.br": "Compras RS",
    "comprasparana.pr.gov.br": "Compras Paraná",
    "peintegrado.pe.gov.br": "PE Integrado",
    "e-compras.am.gov.br": "e-Compras AM",
    "comprasnet.ba.gov.br": "Comprasnet BA",
    "siga.es.gov.br": "SIGA ES",
    "compras.rj.gov.br": "SIGA RJ",
    "procergs.rs.gov.br": "Procergs",
    "pregaobanrisul.com.br": "Pregão Banrisul",
    "comprasbr.com.br": "ComprasBR",
    "bnc.org.br": "BNC",
    "bnccompras.com": "BNC",
    "ecustomize.com.br": "eCustomize",
    "ammlicita.org.br": "AMM Licita (MG)",
    "licitamaisbrasil.com.br": "Licita Mais Brasil",
    "compras.empro.com.br": "Empro (SP)",
}
# plataformas cujos editais chegam pelo PNCP, por fonte do catálogo (para o controle de qualidade)
PLATAFORMAS_DA_FONTE = {
    "licitacoes_e": ["Licitações-e"], "portal_compras_publicas": ["Portal de Compras Públicas"],
    "bll": ["BLL Compras"], "licitanet": ["Licitanet"], "bbmnet": ["BBMNET"],
    "bec_sp": ["BEC-SP", "Compras MG", "Compras RS", "Compras Paraná", "PE Integrado", "e-Compras AM",
               "Comprasnet BA", "SIGA ES", "SIGA RJ", "Procergs"],
}
PREFIXOS = {
    "[portal de compras publicas]": "Portal de Compras Públicas",
    "[licitanet]": "Licitanet",
    "[bll]": "BLL Compras",
    "[bnc]": "BNC",
}


def plataforma_de(link_origem: str | None, objeto: str | None = None, publicador: str | None = None) -> str | None:
    from .util import normalizar

    if objeto:
        o = normalizar(objeto)[:40]
        for pref, nome in PREFIXOS.items():
            if o.startswith(normalizar(pref)):
                return nome
    if link_origem:
        host = (urlparse(link_origem).hostname or "").lower()
        for dom, nome in PLATAFORMAS.items():
            if host == dom or host.endswith("." + dom):
                return nome
        if host:
            return host.removeprefix("www.")
    if publicador:
        return publicador
    return None


def registrar_fontes(s: Session) -> None:
    for d in CATALOGO:
        f = s.query(Fonte).filter_by(codigo=d["codigo"]).one_or_none()
        if f is None:
            s.add(Fonte(**d))
        else:
            for k, v in d.items():
                setattr(f, k, v)
    s.flush()


def fonte(s: Session, codigo: str) -> Fonte:
    f = s.query(Fonte).filter_by(codigo=codigo).one_or_none()
    if f is None:
        registrar_fontes(s)
        f = s.query(Fonte).filter_by(codigo=codigo).one()
    return f
