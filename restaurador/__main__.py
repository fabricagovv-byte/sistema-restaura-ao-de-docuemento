"""Linha de comando.

    python -m restaurador ENTRADAS... [-o pasta_saida] [--zip] [--sem-ocr] [--ia]

ENTRADAS podem ser arquivos, pastas, ZIPs ou imagens de disco (.img, .dd, .bin...).
"""

from __future__ import annotations

import argparse
import sys

from .pipeline import executar, gerar_zip, relatorio_texto, salvar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="restaurador", description="Busca e restaura documentos danificados.")
    p.add_argument("entradas", nargs="+", help="arquivos, pastas, ZIPs ou imagens de disco")
    p.add_argument("-o", "--saida", default="resultado_restauracao", help="pasta de saída")
    p.add_argument("--zip", action="store_true", help="também gera <saida>.zip")
    p.add_argument("--sem-ocr", action="store_true", help="não faz OCR das páginas digitalizadas")
    p.add_argument("--ia", action="store_true", help="revisa textos danificados/OCR com o Claude")
    a = p.parse_args(argv)

    try:
        res = executar(a.entradas, usar_ocr=not a.sem_ocr, usar_ia=a.ia, progresso=print)
    except (ValueError, FileNotFoundError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    pasta = salvar(res, a.saida)
    if a.zip:
        with open(f"{a.saida}.zip", "wb") as f:
            f.write(gerar_zip(res))
    print()
    print(relatorio_texto(res))
    print(f"Arquivos salvos em: {pasta}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
