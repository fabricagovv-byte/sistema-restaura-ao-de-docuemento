"""Linha de comando. Ex.: python -m licitacoes.cli sync pncp --dias 1"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import alertas, analise, catalogo, coleta, documentos, painel, tarefas
from .auth import criar_usuario
from .db import iniciar_banco, sessao
from .modelos import Licitacao
from .taxonomia import PADRAO, categorias_ativas, classificar


def _imprimir(x) -> None:
    print(json.dumps(x, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="licitacoes")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="cria tabelas e registra as fontes")
    u = sub.add_parser("criar-usuario")
    u.add_argument("email"), u.add_argument("nome"), u.add_argument("senha")
    u.add_argument("--papel", default="analista", choices=["admin", "analista", "leitor"])
    sy = sub.add_parser("sync", help="sincroniza uma fonte")
    sy.add_argument("fonte", choices=["pncp", "pncp-propostas", "comprasgov", "querido-diario", "transparencia",
                                      "espelhos", "ibge", "conferir"])
    sy.add_argument("--dias", type=int, default=1)
    sy.add_argument("--modalidades", default=None, help="ex.: 6,4,8")
    sy.add_argument("--ufs", default=None, help="ex.: SP,MG")
    sy.add_argument("--termos", default=None, help="para querido-diario; padrão: categorias prioritárias")
    pr = sub.add_parser("preparar", help="itens, documentos, download e análise de um edital")
    pr.add_argument("id", type=int), pr.add_argument("--sem-ia", action="store_true")
    an = sub.add_parser("analisar"); an.add_argument("id", type=int)
    z = sub.add_parser("zip"); z.add_argument("id", type=int); z.add_argument("saida")
    sub.add_parser("alertas")
    sub.add_parser("painel")
    sub.add_parser("qualidade")
    sub.add_parser("reclassificar", help="reaplica as categorias a todos os editais")
    sub.add_parser("agendador", help="ciclo de monitoramento sem Celery")
    co = sub.add_parser("coletar", help="coleta completa e exporta um pacote (para rodar no GitHub Actions)")
    co.add_argument("saida"), co.add_argument("--top", type=int, default=40), co.add_argument("--rapido", action="store_true")
    co.add_argument("--dias", type=int, default=3)
    co.add_argument("--listar", type=int, default=2500, help="editais de TI/gestão documental com itens e documentos listados")
    co.add_argument("--minutos", type=float, default=None, help="orçamento de tempo; as etapas longas param no prazo")
    co.add_argument("--anterior", default=None, help="pacote da execução anterior: aproveita itens e documentos dos editais ainda abertos")
    im = sub.add_parser("importar-coleta", help="importa o pacote gerado por `coletar`")
    im.add_argument("pasta")
    sub.add_parser("servidor", help="sobe a API em :8000")
    a = p.parse_args(argv)

    if a.cmd == "servidor":
        import uvicorn

        uvicorn.run("licitacoes.api:app", host="0.0.0.0", port=8000)
        return 0
    iniciar_banco()
    with sessao() as s:
        catalogo.registrar_fontes(s)
        if a.cmd == "init-db":
            print("banco pronto")
        elif a.cmd == "criar-usuario":
            criar_usuario(s, a.email, a.nome, a.senha, a.papel)
            print("usuário criado")
        elif a.cmd == "sync":
            mods = [int(x) for x in a.modalidades.split(",")] if a.modalidades else None
            ufs = a.ufs.split(",") if a.ufs else None
            if a.fonte == "pncp":
                r = coleta.sincronizar_pncp(s, modo="diario", dias=a.dias, modalidades=mods, ufs=ufs)
            elif a.fonte == "pncp-propostas":
                r = coleta.sincronizar_pncp(s, modo="propostas", ufs=ufs)
            elif a.fonte == "comprasgov":
                r = coleta.sincronizar_comprasgov(s, dias=a.dias, modalidades=mods)
            elif a.fonte == "querido-diario":
                termos = a.termos.split(",") if a.termos else [c.nome for c in PADRAO if c.segmento == "gestao_documental"]
                r = coleta.sincronizar_querido_diario(s, termos, dias=a.dias)
            elif a.fonte == "transparencia":
                r = coleta.sincronizar_transparencia(s, dias=a.dias)
            elif a.fonte == "espelhos":
                for x in coleta.sincronizar_espelhos(s):
                    _imprimir({"status": x.status, "lidos": x.lidos, "novos": x.novos, "atualizados": x.atualizados,
                               "parametros": x.parametros, "mensagem": x.mensagem})
                return 0
            elif a.fonte == "ibge":
                try:
                    print("municípios carregados:", coleta.carregar_municipios(s))
                except Exception as e:
                    print(f"IBGE inacessível ({e}); usando os códigos IBGE dos próprios editais")
                    print("municípios adicionados:", coleta.municipios_dos_editais(s))
                return 0
            else:
                _imprimir(coleta.conferir_individual(s))
                return 0
            _imprimir({"status": r.status, "lidos": r.lidos, "novos": r.novos, "atualizados": r.atualizados,
                       "chamadas": r.chamadas, "mensagem": r.mensagem})
        elif a.cmd == "preparar":
            _imprimir(tarefas.preparar_edital(a.id, not a.sem_ia))
        elif a.cmd == "analisar":
            an_ = analise.analisar(s, s.get(Licitacao, a.id))
            _imprimir({"status": an_.status, "erro": an_.erro, "verificacao": an_.verificacao})
        elif a.cmd == "zip":
            dados, man = documentos.gerar_zip(s.get(Licitacao, a.id))
            open(a.saida, "wb").write(dados)
            print(f"{a.saida}: {len(man['documentos'])} documentos listados")
        elif a.cmd == "alertas":
            _imprimir(alertas.avaliar(s))
        elif a.cmd == "painel":
            _imprimir(painel.painel(s))
        elif a.cmd == "qualidade":
            _imprimir(painel.qualidade(s))
        elif a.cmd == "reclassificar":
            cats = categorias_ativas(s)
            n = 0
            for lic in s.query(Licitacao).yield_per(500):
                coleta.classificar_licitacao(s, lic, cats)
                lic.aderencia = coleta.calcular_aderencia(lic)
                n += 1
            print("reclassificados:", n)
        elif a.cmd == "coletar":
            from .coletor_remoto import coletar, exportar

            r = coletar(s, dias=a.dias, detalhar_top=a.top, listar=a.listar, rapido=a.rapido, minutos=a.minutos, anterior=a.anterior)
            _imprimir(exportar(s, a.saida, r))
        elif a.cmd == "importar-coleta":
            from .coletor_remoto import importar

            _imprimir(importar(s, a.pasta))
        elif a.cmd == "agendador":
            tarefas.agendador_simples()
    return 0


if __name__ == "__main__":
    sys.exit(main())
