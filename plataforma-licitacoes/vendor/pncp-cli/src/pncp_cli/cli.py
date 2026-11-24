"""Parser argparse e ponto de entrada."""

import argparse
import datetime
import re
import sys

from .client import CONFIG, PncpError, _EXIT, _HOUVE_REQUISICAO
from .constants import STATUS, TIPOS_BUSCA, VERSAO
from .commands.busca import cmd_search, cmd_filtros
from .commands.consulta import (cmd_consulta_contratacoes,
    cmd_consulta_propostas, cmd_consulta_atas, cmd_consulta_contratos,
    cmd_consulta_cobranca, cmd_consulta_pca)
from .commands.compra import (cmd_contratacao, cmd_itens,
    cmd_resultados, cmd_arquivos, cmd_historico, cmd_controle)
from .commands.ata import cmd_ata
from .commands.contrato import cmd_contrato
from .commands.orgao import cmd_orgao
from .commands.pca import cmd_pca
from .commands.dominio import cmd_dominio
from .commands.skill import cmd_skill

def _tipo_data(s):
    """Valida YYYY-MM-DD como data de calendário."""
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"data inválida: {s!r} (use YYYY-MM-DD)")
    return s


def _tipo_positivo(s):
    """Inteiro >= 1."""
    try:
        v = int(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"esperado um inteiro: {s!r}")
    if v < 1:
        raise argparse.ArgumentTypeError(f"esperado um inteiro >= 1: {s!r}")
    return v


def _tipo_pausa(s):
    """Segundos (float >= 0) entre requisições."""
    try:
        v = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"esperado um número de segundos: {s!r}")
    if v < 0:
        raise argparse.ArgumentTypeError(f"pausa não pode ser negativa: {s!r}")
    return v


def _tipo_cnpj(s):
    """Aceita CNPJ com ou sem pontuação; normaliza para os 14 dígitos."""
    digitos = re.sub(r"\D", "", s)
    if len(digitos) != 14:
        raise argparse.ArgumentTypeError(
            f"CNPJ inválido: {s!r} (precisa de 14 dígitos)")
    return digitos


def build_parser():
    p = argparse.ArgumentParser(
        prog="pncp",
        description="CLI para as APIs públicas do Portal Nacional de Contratações Públicas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
exemplos:
  pncp search "notebook" --tipo edital --status recebendo_proposta --uf SP --table
  pncp search "hospitalar" --tipo edital --modalidade 6 --all --limit 500 --ndjson > editais.ndjson
  pncp filtros --tipo edital --faceta modalidades
  pncp consulta contratacoes --de 2026-07-01 --ate 2026-07-15 --modalidade 6 --all --ndjson
  pncp consulta contratacoes --de 2026-07-14 --ate 2026-07-15 --modalidade all --por atualizacao
  pncp consulta contratos --de 2026-07-01 --ate 2026-07-15 --all
  pncp contratacao 07424905000138 2026 212
  pncp itens --controle 07424905000138-1-000212/2026
  pncp arquivos 07424905000138 2026 212 --baixar ./docs
  pncp controle 07424905000138-1-000212/2026 --detalhe

Dica: use a BUSCA (/search) para descoberta textual/facetada; use CONSULTA
(/consulta) para coleta em massa por período — a busca limita paginação a ~10k.
""")
    p.add_argument("--version", action="version", version=f"pncp-cli {VERSAO}")

    fmt = argparse.ArgumentParser(add_help=False)
    g = fmt.add_argument_group("saída")
    ex = g.add_mutually_exclusive_group()
    ex.add_argument("--output", choices=["json", "ndjson", "table"],
                    help="formato de saída (padrão: json)")
    ex.add_argument("--ndjson", action="store_true",
                    help="atalho para --output ndjson (streaming em coletas)")
    ex.add_argument("--table", action="store_true",
                    help="atalho para --output table")
    gg = fmt.add_argument_group("globais")
    gg.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS,
                    help="silencia o progresso no stderr (avisos ⚠ continuam)")
    gg.add_argument("--timeout", type=_tipo_positivo, default=argparse.SUPPRESS, metavar="S",
                    help="timeout por requisição em segundos (padrão 60)")
    gg.add_argument("--retries", type=_tipo_positivo, default=argparse.SUPPRESS, metavar="N",
                    help="tentativas por requisição (padrão 5)")
    gg.add_argument("--pausa", type=_tipo_pausa, default=argparse.SUPPRESS, metavar="SEG",
                    help="pacing preventivo: segundos entre requisições (padrão 0)")

    # filtros/enriquecimento locais (etapa opcional pós-consulta — ver filtros.py)
    filt = argparse.ArgumentParser(add_help=False)
    gf = filt.add_argument_group("filtro local")
    gf.add_argument("--incluir", action="append", metavar="TERMO",
                    help="mantém registros que casam o termo (token ou frase; "
                         "sem acentos/caixa; repetível)")
    gf.add_argument("--excluir", action="append", metavar="TERMO",
                    help="descarta registros que casam o termo (repetível)")
    gf.add_argument("--match", choices=["any", "all"], default="any",
                    help="--incluir exige QUALQUER termo (any, padrão) ou TODOS (all)")
    gf.add_argument("--link", action="store_true",
                    help="adiciona _link_pncp (URL oficial do portal) a cada registro")

    # flags comuns da API /consulta (paginada por envelope data/totalPaginas)
    pag = argparse.ArgumentParser(add_help=False)
    gp = pag.add_argument_group("paginação")
    gp.add_argument("--tam", type=int, default=50, help="tamanho de página (10-50)")
    gp.add_argument("--all", action="store_true", help="pagina até esgotar")
    gp.add_argument("--limit", type=_tipo_positivo, help="teto de registros")
    gp.add_argument("--desde-pagina", dest="desde_pagina", type=_tipo_positivo, metavar="N",
                    help="retoma a coleta a partir da página N (após saída parcial)")

    sub = p.add_subparsers(dest="cmd", required=True)

    # search
    s = sub.add_parser("search", parents=[fmt, filt], help="busca textual/facetada (/api/search)")
    s.add_argument("termo", nargs="?", help="palavra-chave (opcional)")
    s.add_argument("--tipo", choices=TIPOS_BUSCA, default="edital")
    s.add_argument("--status", choices=STATUS, default="todos")
    s.add_argument("--uf", help="UFs separadas por vírgula, ex: SP,RJ")
    s.add_argument("--modalidade", help="IDs de modalidade, ex: 6,8 (ver `pncp filtros`)")
    s.add_argument("--orgao", help="IDs de órgão separados por vírgula")
    s.add_argument("--municipio", help="IDs de município separados por vírgula")
    s.add_argument("--esfera", help="F=Federal,E=Estadual,M=Municipal (vírgula)")
    s.add_argument("--poder", help="E=Executivo,L=Legislativo,J=Judiciário (vírgula)")
    s.add_argument("--ordenacao", default="-data", help="-data (mais recentes) ou data")
    s.add_argument("--pagina", type=int, default=1)
    s.add_argument("--tam", type=int, default=10, help="itens por página")
    s.add_argument("--all", action="store_true", help="pagina automaticamente (até ~10k)")
    s.add_argument("--limit", type=int, help="teto de registros com --all")
    s.set_defaults(func=cmd_search)

    # filtros
    f = sub.add_parser("filtros", parents=[fmt], help="facetas/tabelas de IDs (/api/search/filters)")
    f.add_argument("--tipo", choices=TIPOS_BUSCA, default="edital")
    f.add_argument("--faceta", help="modalidades|orgaos|ufs|municipios|esferas|poderes|...")
    f.set_defaults(func=cmd_filtros)

    # consulta (grupo)
    c = sub.add_parser("consulta", help="coleta em massa por data (API oficial /consulta/v1)")
    csub = c.add_subparsers(dest="csub", required=True)

    cc = csub.add_parser("contratacoes", parents=[fmt, pag, filt], help="editais/contratações por período")
    cc.add_argument("--de", required=True, type=_tipo_data, help="data inicial YYYY-MM-DD")
    cc.add_argument("--ate", required=True, type=_tipo_data, help="data final YYYY-MM-DD")
    cc.add_argument("--modalidade", default="6",
                    help="ID da modalidade (obrigatório na API) ou 'all' p/ varrer todas")
    cc.add_argument("--por", choices=["publicacao", "atualizacao"], default="publicacao")
    cc.add_argument("--uf", help="sigla da UF")
    cc.add_argument("--municipio", help="código IBGE do município")
    cc.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    cc.add_argument("--unidade", help="código da unidade administrativa")
    cc.add_argument("--modo-disputa", dest="modo_disputa", type=int,
                    help="código do modo de disputa (ver `pncp dominio modos-disputas`)")
    cc.add_argument("--checkpoint", metavar="ARQ",
                    help="grava progresso em ARQ após cada página; rodar de novo "
                         "com o mesmo ARQ retoma de onde parou (apagado ao concluir)")
    cc.set_defaults(func=cmd_consulta_contratacoes)

    cp = csub.add_parser("propostas", parents=[fmt, pag], help="contratações com propostas em aberto")
    cp.add_argument("--ate", required=True, type=_tipo_data, help="data final da recepção YYYY-MM-DD")
    cp.add_argument("--modalidade", help="ID da modalidade (opcional)")
    cp.add_argument("--uf", help="sigla da UF (opcional)")
    cp.add_argument("--municipio", help="código IBGE do município")
    cp.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    cp.add_argument("--unidade", help="código da unidade administrativa")
    cp.set_defaults(func=cmd_consulta_propostas)

    ca = csub.add_parser("atas", parents=[fmt, pag], help="atas de registro de preço por período")
    ca.add_argument("--de", required=True, type=_tipo_data)
    ca.add_argument("--ate", required=True, type=_tipo_data)
    ca.add_argument("--por", choices=["vigencia", "atualizacao"], default="vigencia",
                    help="vigencia (padrão) ou atualizacao")
    ca.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    ca.add_argument("--unidade", help="código da unidade administrativa")
    ca.set_defaults(func=cmd_consulta_atas)

    ct = csub.add_parser("contratos", parents=[fmt, pag], help="contratos por período")
    ct.add_argument("--de", required=True, type=_tipo_data)
    ct.add_argument("--ate", required=True, type=_tipo_data)
    ct.add_argument("--por", choices=["publicacao", "atualizacao"], default="publicacao",
                    help="publicacao (padrão) ou atualizacao")
    ct.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    ct.add_argument("--unidade", help="código da unidade administrativa")
    ct.set_defaults(func=cmd_consulta_contratos)

    cb = csub.add_parser("cobranca", parents=[fmt, pag],
                         help="instrumentos de cobrança incluídos no período")
    cb.add_argument("--de", required=True, type=_tipo_data)
    cb.add_argument("--ate", required=True, type=_tipo_data)
    cb.add_argument("--tipo", type=int,
                    help="tipo (ver `pncp dominio tipos-instrumentos-cobranca`)")
    cb.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    cb.set_defaults(func=cmd_consulta_cobranca)

    cpca = csub.add_parser("pca", parents=[fmt, pag],
                           help="Plano de Contratações Anual (3 modos)")
    cpca.add_argument("--ano", type=int, help="ano do PCA")
    cpca.add_argument("--classificacao",
                      help="código da classificação superior do catálogo")
    cpca.add_argument("--usuario", type=int,
                      help="modo usuário: id do sistema publicador")
    cpca.add_argument("--por", choices=["padrao", "atualizacao"], default="padrao",
                      help="atualizacao: itens de PCA alterados em --de/--ate")
    cpca.add_argument("--de", type=_tipo_data, help="data inicial (só --por atualizacao)")
    cpca.add_argument("--ate", type=_tipo_data, help="data final (só --por atualizacao)")
    cpca.add_argument("--cnpj", type=_tipo_cnpj, help="CNPJ do órgão")
    cpca.add_argument("--unidade", help="código da unidade administrativa")
    cpca.set_defaults(func=cmd_consulta_pca)

    # detalhe / sub-recursos
    def add_alvo(sp):
        sp.add_argument("cnpj", nargs="?", type=_tipo_cnpj, help="CNPJ do órgão (14 dígitos)")
        sp.add_argument("ano", nargs="?", type=int)
        sp.add_argument("seq", nargs="?", type=int, help="sequencial da compra")
        sp.add_argument("--controle", help="nº de controle PNCP (alternativa a CNPJ ANO SEQ)")

    d = sub.add_parser("contratacao", parents=[fmt], help="detalhe de uma contratação")
    add_alvo(d); d.set_defaults(func=cmd_contratacao)

    it = sub.add_parser("itens", parents=[fmt], help="itens de uma contratação (pagina tudo)")
    add_alvo(it)
    it.add_argument("--tam", type=int, default=100,
                    help="itens por página ao paginar (padrão 100; a API entrega 10 se omitido)")
    it.add_argument("--limit", type=int, help="teto de itens retornados")
    it.set_defaults(func=cmd_itens)

    ar = sub.add_parser("arquivos", parents=[fmt], help="arquivos/documentos de uma contratação")
    add_alvo(ar)
    ar.add_argument("--baixar", metavar="DIR", help="baixa os arquivos para o diretório")
    ar.set_defaults(func=cmd_arquivos)

    hi = sub.add_parser("historico", parents=[fmt], help="histórico de manutenção")
    add_alvo(hi); hi.set_defaults(func=cmd_historico)

    ct2 = sub.add_parser("controle", parents=[fmt], help="decompõe um nº de controle PNCP")
    ct2.add_argument("numero", help="ex: 07424905000138-1-000212/2026")
    ct2.add_argument("--detalhe", action="store_true", help="também busca o detalhe")
    ct2.set_defaults(func=cmd_controle)

    # resultados (fornecedor vencedor por item)
    rs = sub.add_parser("resultados", parents=[fmt],
                        help="resultados de itens: fornecedor vencedor, valores homologados")
    add_alvo(rs)
    rs.add_argument("--item", type=int, help="só o item N (padrão: todos com resultado)")
    rs.set_defaults(func=cmd_resultados)

    # órgão
    og = sub.add_parser("orgao", parents=[fmt], help="dados de um órgão/entidade")
    og.add_argument("cnpj", nargs="?", type=_tipo_cnpj, help="CNPJ do órgão (14 dígitos)")
    og.add_argument("--id", type=int, help="busca por id interno (orgao_id do search)")
    og.add_argument("--buscar", metavar="TEXTO", help="busca por razão social")
    og.add_argument("--unidades", action="store_true", help="lista as unidades do órgão")
    og.add_argument("--limit", type=int, help="teto de registros com --buscar")
    og.set_defaults(func=cmd_orgao)

    # ata (de uma compra)
    at = sub.add_parser("ata", parents=[fmt],
                        help="atas de registro de preço de uma contratação")
    at.add_argument("asub", choices=["listar", "detalhe", "arquivos", "partes",
                                     "contratos", "historico"],
                    help="subcomando")
    add_alvo(at)
    at.add_argument("--seq-ata", dest="seq_ata", type=int,
                    help="sequencial da ata (obrigatório exceto em 'listar')")
    at.add_argument("--baixar", metavar="DIR", help="(arquivos) baixa para o diretório")
    at.set_defaults(func=cmd_ata)

    # contrato
    co = sub.add_parser("contrato", parents=[fmt], help="contratos e seus sub-recursos")
    co.add_argument("csub", choices=["detalhe", "arquivos", "termos", "empenhos",
                                     "historico", "cobranca", "da-compra"],
                    help="subcomando ('da-compra': contratos nascidos de uma contratação)")
    add_alvo(co)
    co.add_argument("--seq-termo", dest="seq_termo", type=int,
                    help="(termos) arquivos do termo aditivo N")
    co.add_argument("--baixar", metavar="DIR", help="(arquivos/termos) baixa para o diretório")
    co.set_defaults(func=cmd_contrato)

    # pca (plano anual de contratações de um órgão)
    pc = sub.add_parser("pca", parents=[fmt],
                        help="Plano de Contratações Anual de um órgão")
    pc.add_argument("psub", choices=["consolidado", "itens", "valores", "planos", "csv"],
                    help="subcomando")
    pc.add_argument("cnpj", type=_tipo_cnpj, help="CNPJ do órgão (14 dígitos)")
    pc.add_argument("ano", type=int, help="ano do PCA")
    pc.add_argument("--seq", type=int, help="sequencial do plano (ver 'pca planos')")
    pc.add_argument("--uasg", help="(planos) código da unidade")
    pc.add_argument("--categoria", type=int, help="(itens) filtra por categoria")
    pc.add_argument("--limit", type=int, help="(itens) teto de registros")
    pc.add_argument("--unidades", action="store_true",
                    help="(consolidado) detalha por unidade")
    pc.add_argument("--saida", metavar="ARQ", help="(csv) arquivo de destino")
    pc.set_defaults(func=cmd_pca)

    # skill de Claude Code
    sk = sub.add_parser("skill", parents=[fmt],
                        help="instala a skill de Claude Code embutida no pacote")
    sk.add_argument("ssub", choices=["instalar", "caminho"],
                    help="instalar: copia para o diretório de skills; "
                         "caminho: mostra origem e destino")
    sk.add_argument("--dir", help="diretório de destino "
                                  "(padrão: ~/.claude/skills/pncp)")
    sk.set_defaults(func=cmd_skill)

    # tabelas de domínio
    dm = sub.add_parser("dominio", parents=[fmt],
                        help="tabelas de domínio (modalidades, amparos legais…)")
    dm.add_argument("tabela", nargs="?", help="nome da tabela (vazio = listar opções)")
    dm.set_defaults(func=cmd_dominio)

    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    _EXIT["code"] = 0  # idempotente para uso como biblioteca (processo reusado)
    _HOUVE_REQUISICAO["v"] = False  # cada invocação tem sua "primeira requisição"
    CONFIG["quiet"] = getattr(args, "quiet", False)
    CONFIG["timeout"] = getattr(args, "timeout", 60)
    CONFIG["retries"] = getattr(args, "retries", 5)
    CONFIG["pausa"] = getattr(args, "pausa", 0.0)
    try:
        args.func(args)
    except PncpError as e:
        sys.stderr.write(f"erro: {e}\n")
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
    sys.exit(_EXIT["code"])
