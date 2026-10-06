"""Gera documentos fictícios DANIFICADOS em exemplos/ para testar o sistema.

    python gerar_exemplos.py
"""

from __future__ import annotations

import io
import random
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PASTA = Path(__file__).parent / "exemplos"

CONTRATO = [
    "CONTRATO ADMINISTRATIVO Nº 12/2026",
    "Processo SEI nº 23000.001234/2026-11",
    "Contratante: Prefeitura Municipal de Exemplópolis, CNPJ 12.345.678/0001-95.",
    "Contratada: Serviços Gerais Ltda., CNPJ 98.765.432/0001-10.",
    "CLÁUSULA PRIMEIRA - DO OBJETO. Prestação de serviços contínuos de limpeza e conservação "
    "nas unidades de saúde do município, conforme Termo de Referência.",
    "CLÁUSULA SEGUNDA - DO VALOR. O valor global é de R$ 1.250.000,00 (um milhão, duzentos e "
    "cinquenta mil reais), pagos em parcelas mensais.",
    "CLÁUSULA TERCEIRA - DA VIGÊNCIA. Vigência de 12 (doze) meses a contar da assinatura.",
    "CLÁUSULA QUARTA - DAS OBRIGAÇÕES. A contratada fornecerá mão de obra, materiais e "
    "equipamentos necessários à execução dos serviços.",
]


def _pdf(paginas: list[list[str]], titulo: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    c.setTitle(titulo)
    total = len(paginas)
    for n, linhas in enumerate(paginas, 1):
        y = 800
        for linha in linhas:
            for pedaco in textwrap.wrap(linha, 90):
                c.drawString(50, y, pedaco)
                y -= 16
        c.drawString(260, 30, f"Página {n} de {total}")
        c.showPage()
    c.save()
    return buf.getvalue()


def contrato_cortado() -> bytes:
    """PDF de 3 páginas cortado: perdeu a tabela xref, o trailer e o %%EOF (download interrompido)."""
    paginas = [CONTRATO[:3], CONTRATO[3:6], CONTRATO[6:]]
    completo = _pdf(paginas, "Contrato 12/2026")
    return completo[: completo.rfind(b"xref")]


def memorando_destruido() -> bytes:
    """PDF com catálogo, árvore de páginas e xref destruídos: só o resgate bruto recupera o texto."""
    dados = bytearray(_pdf([["MEMORANDO Nº 45/2026 - SECRETARIA DE ADMINISTRAÇÃO",
                             "Assunto: Solicitação de abertura de processo licitatório para aquisição de "
                             "material de expediente.",
                             "Encaminhamos a solicitação para as providências cabíveis."]], "Memorando"))
    for alvo in (b"/Catalog", b"/Pages", b"xref", b"trailer", b"startxref", b"/Root"):
        pos = dados.find(alvo)
        while pos != -1:
            dados[pos:pos + len(alvo)] = b"#" * len(alvo)
            pos = dados.find(alvo)
    return bytes(dados)


def oficio_docx() -> bytes:
    import docx

    documento = docx.Document()
    documento.add_heading("OFÍCIO Nº 77/2026 - GABINETE", 1)
    documento.add_paragraph("Senhor Secretário,")
    documento.add_paragraph(
        "Solicitamos informações sobre a execução do Contrato nº 12/2026, em especial quanto às medições "
        "de serviços realizadas nos meses de março e abril, para instrução do processo de pagamento."
    )
    documento.add_paragraph("Atenciosamente,")
    documento.add_paragraph("Coordenação de Controle Interno")
    buf = io.BytesIO()
    documento.save(buf)
    return buf.getvalue()


def oficio_corrompido() -> bytes:
    """DOCX cujo índice do ZIP (diretório central) foi perdido: o Word diz que o arquivo está corrompido."""
    dados = oficio_docx()
    return dados[: dados.find(b"PK\x01\x02")]


def ata_mojibake() -> bytes:
    """Texto salvo com codificação errada (acentos viram Ã§, Ã£...) e com hifenização de PDF."""
    texto = (
        "ATA DA REUNIÃO ORDINÁRIA DO CONSELHO MUNICIPAL DE SAÚDE\n\n"
        "Aos cinco dias do mês de março de dois mil e vinte e seis, reuniram-se os conse-\n"
        "lheiros para deliberar sobre a aprovação das contas do exercício anterior e a\n"
        "programação anual de saúde. Após discussão, a proposta foi aprovada por unani-\n"
        "midade.\n"
    )
    return texto.encode("utf-8").decode("latin-1").encode("utf-8")


def parecer_copias() -> tuple[bytes, bytes]:
    """Duas cópias do mesmo parecer, cada uma perdeu um pedaço diferente."""
    texto = (
        "PARECER JURÍDICO Nº 31/2026\n\n"
        "Trata-se de consulta sobre a possibilidade de prorrogação do Contrato nº 12/2026, firmado para "
        "prestação de serviços contínuos de limpeza. A Lei nº 14.133/2021 admite a prorrogação de contratos de "
        "serviços contínuos, desde que haja previsão no edital e no contrato, a autoridade competente ateste "
        "que as condições e os preços permanecem vantajosos e o contratado concorde com a prorrogação. "
        "Verifica-se nos autos que a cláusula terceira prevê a possibilidade de prorrogação e que a pesquisa "
        "de preços demonstra a vantajosidade. Ante o exposto, opina-se pela possibilidade jurídica da "
        "prorrogação, condicionada à manutenção da regularidade fiscal da contratada.\n"
        "Exemplópolis, 10 de abril de 2026.\n"
    ).encode("utf-8")
    corte_a = int(len(texto) * 0.65)
    corte_b = int(len(texto) * 0.40)
    return texto[:corte_a], texto[corte_b:]


def digitalizacao_torta() -> bytes:
    """'Foto' de um documento: inclinada, com sombra, amarelada e granulada."""
    img = Image.new("L", (1240, 900), 255)
    desenho = ImageDraw.Draw(img)
    try:
        fonte = ImageFont.truetype("DejaVuSans.ttf", 28)
    except OSError:
        fonte = ImageFont.load_default()
    linhas = ["NOTA DE EMPENHO 2026NE000123", "Credor: Serviços Gerais Ltda.", "Valor: R$ 104.166,67",
              "Contrato nº 12/2026 - parcela de março", "Fonte de recurso: 1.500.0000"]
    for i, linha in enumerate(linhas):
        desenho.text((80, 120 + i * 70), linha, fill=20, font=fonte)
    img = img.rotate(4.0, resample=Image.BICUBIC, fillcolor=255, expand=False)
    arr = np.array(img).astype(np.float32)
    gradiente = np.linspace(0.55, 1.0, arr.shape[1])[None, :]  # sombra à esquerda
    arr = arr * gradiente * 0.92 + 10
    arr += np.random.default_rng(1).normal(0, 14, arr.shape)
    cinza = np.clip(arr, 0, 255).astype(np.uint8)
    rgb = np.stack([cinza, cinza, (cinza * 0.85).astype(np.uint8)], axis=2)  # amarelado
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def relatorio_partes() -> dict[str, bytes]:
    partes = {}
    for n in (1, 3):
        partes[f"relatorio_auditoria_parte{n}de3.pdf"] = _pdf(
            [[f"RELATÓRIO DE AUDITORIA 05/2026 - PARTE {n}",
              f"Conteúdo da parte {n}: achados de auditoria sobre a execução contratual, seção {n}."]],
            f"Relatório parte {n}",
        )
    return partes


def pendrive_formatado() -> bytes:
    """Imagem de um pendrive formatado: os arquivos 'sumiram', mas os bytes continuam lá."""
    rnd = random.Random(7)
    blocos = [
        bytes(4096),
        bytes(rnd.getrandbits(8) for _ in range(3000)),
        _pdf([["MEMORANDO Nº 46/2026", "Assunto: envio da planilha de medição do Contrato nº 12/2026."]], "Memo 46"),
        bytes(2048),
        oficio_docx(),
        bytes(1024),
        digitalizacao_torta(),
        bytes(4096),
    ]
    return b"".join(blocos)


def gerar() -> None:
    PASTA.mkdir(exist_ok=True)
    arquivos = {
        "contrato_12_2026_cortado.pdf": contrato_cortado(),
        "memorando_45_2026_destruido.pdf": memorando_destruido(),
        "oficio_77_2026_corrompido.docx": oficio_corrompido(),
        "ata_conselho_saude.txt": ata_mojibake(),
        "foto_nota_empenho.jpg": digitalizacao_torta(),
        "pendrive_formatado.img": pendrive_formatado(),
    }
    a, b = parecer_copias()
    arquivos["parecer_31_2026.txt"] = a
    arquivos["parecer_31_2026 (copia).txt"] = b
    arquivos.update(relatorio_partes())
    for nome, dados in arquivos.items():
        (PASTA / nome).write_bytes(dados)
        print(f"{nome}: {len(dados)} bytes")


if __name__ == "__main__":
    gerar()
