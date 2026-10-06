"""Restauração de PDF.

Ordem de tentativas, da mais fiel para a mais agressiva:
1. Remove lixo antes do cabeçalho / depois do último %%EOF.
2. Reconstrói a tabela xref, o trailer e a árvore de páginas com o qpdf (pikepdf).
3. Leitura tolerante com pypdf e regravação página a página (descarta só as páginas quebradas).
4. Resgate bruto: varre todos os objetos do arquivo, descomprime os fluxos (mesmo cortados),
   extrai o texto dos comandos de desenho e as imagens JPEG, e monta um PDF novo com o que sobrou.

Páginas sem texto (digitalizadas) são renderizadas, limpas (deskew, contraste, manchas)
e passam por OCR quando o Tesseract está instalado.
"""

from __future__ import annotations

import io
import re
import zlib

from . import imagem as im
from . import texto as tx
from .modelos import IRRECUPERAVEL, PARCIAL, RESTAURADO, Restauracao


def _aparar(dados: bytes, r: Restauracao) -> bytes:
    inicio = dados.find(b"%PDF-")
    if inicio > 0:
        r.feito.append(f"{inicio} bytes de lixo antes do cabeçalho %PDF removidos")
        dados = dados[inicio:]
    if b"%%EOF" not in dados[-2048:]:
        r.problemas.append("arquivo sem marca de fim (%%EOF): provavelmente cortado/incompleto")
    return dados


def _contagem_declarada(dados: bytes) -> int | None:
    contagens = [int(m) for m in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", dados)]
    contagens += [int(m) for m in re.findall(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", dados)]
    return max(contagens) if contagens else None


def _via_pikepdf(dados: bytes, r: Restauracao) -> bytes | None:
    import pikepdf

    try:
        with pikepdf.open(io.BytesIO(dados), attempt_recovery=True) as pdf:
            avisos = pdf.get_warnings()
            n = len(pdf.pages)
            if n == 0:
                return None
            saida = io.BytesIO()
            pdf.remove_unreferenced_resources()
            pdf.save(saida, fix_metadata_version=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
            if avisos:
                r.feito.append(f"estrutura interna reconstruída (xref/trailer) — {len(avisos)} defeito(s) corrigido(s)")
                r.status = RESTAURADO
            return saida.getvalue()
    except Exception as erro:
        mensagem = re.sub(r"^.*?object at 0x[0-9a-f]+>:\s*", "", str(erro))
        r.problemas.append(f"reparo estrutural (qpdf) falhou: {mensagem[:150]}")
        return None


def _via_pypdf(dados: bytes, r: Restauracao) -> bytes | None:
    from pypdf import PdfReader, PdfWriter

    try:
        leitor = PdfReader(io.BytesIO(dados), strict=False)
        paginas = list(leitor.pages)
    except Exception as erro:
        r.problemas.append(f"leitura tolerante (pypdf) falhou: {str(erro)[:150]}")
        return None
    escritor = PdfWriter()
    perdidas = 0
    for pagina in paginas:
        try:
            pagina.extract_text()
            escritor.add_page(pagina)
        except Exception:
            perdidas += 1
    if not escritor.pages:
        return None
    if perdidas:
        r.problemas.append(f"{perdidas} página(s) danificada(s) descartada(s)")
    r.feito.append("documento regravado página a página (leitura tolerante)")
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


# ---------- resgate bruto ----------

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)(?=endobj|\d+\s+\d+\s+obj\b|$)", re.S)


def _descomprimir(bruto: bytes) -> bytes:
    """Descomprime FlateDecode tolerando fluxo cortado (devolve o que deu para ler)."""
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        d = zlib.decompressobj(wbits)
        try:
            return d.decompress(bruto) + d.flush()
        except zlib.error:
            # Descomprime em pedaços para aproveitar até o ponto do dano.
            d = zlib.decompressobj(wbits)
            saida = b""
            for i in range(0, len(bruto), 256):
                try:
                    saida += d.decompress(bruto[i:i + 256])
                except zlib.error:
                    break
            if saida:
                return saida
    return b""


def _fluxos(dados: bytes):
    for m in _OBJ.finditer(dados):
        corpo = m.group(3)
        s = corpo.find(b"stream")
        if s == -1:
            continue
        dicionario = corpo[:s]
        conteudo = corpo[s + 6:].lstrip(b"\r\n")
        fim = conteudo.rfind(b"endstream")
        if fim != -1:
            conteudo = conteudo[:fim]
        if b"/FlateDecode" in dicionario:
            conteudo = _descomprimir(conteudo)
        yield dicionario, conteudo


def _literal_pdf(s: bytes) -> str:
    saida = bytearray()
    i = 0
    escapes = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
    while i < len(s):
        c = s[i]
        if c == 0x5C and i + 1 < len(s):
            n = s[i + 1]
            if n in escapes:
                saida.append(escapes[n])
                i += 2
            elif 0x30 <= n <= 0x37:
                octal = re.match(rb"[0-7]{1,3}", s[i + 1:i + 4]).group()
                saida.append(int(octal, 8) & 0xFF)
                i += 1 + len(octal)
            elif n in (10, 13):
                i += 2
            else:
                saida.append(n)
                i += 2
        else:
            saida.append(c)
            i += 1
    bruto = bytes(saida)
    if bruto.startswith(b"\xfe\xff"):
        return bruto[2:].decode("utf-16-be", "replace")
    return bruto.decode("cp1252", "replace")


# Strings vêm primeiro na alternância para que operadores dentro do texto ("SECRETARIA" contém "ET")
# não sejam confundidos com comandos.
_TOKENS_TEXTO = re.compile(
    rb"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|(?<![A-Za-z*])(?:T\*|Td|TD|Tm|ET|BT|'|\")(?![A-Za-z*])", re.S
)


def texto_de_fluxo(conteudo: bytes) -> str:
    if not re.search(rb"(?<![A-Za-z])BT(?![A-Za-z])", conteudo):
        return ""
    partes: list[str] = []
    for bloco in [conteudo]:
        for tok in _TOKENS_TEXTO.finditer(bloco):
            t = tok.group()
            if t.startswith(b"("):
                partes.append(_literal_pdf(t[1:-1]))
            elif t.startswith(b"<"):
                hexa = re.sub(rb"\s", b"", t[1:-1])
                try:
                    b = bytes.fromhex(hexa.decode() + ("0" if len(hexa) % 2 else ""))
                    partes.append(b.decode("utf-16-be", "replace") if len(b) % 2 == 0 and b[:1] == b"\x00" else b.decode("cp1252", "replace"))
                except ValueError:
                    pass
            elif t in (b"T*", b"Td", b"TD", b"'", b'"', b"ET"):
                partes.append("\n")
            elif t == b"Tm":
                partes.append(" ")
    texto = "\n".join(linha.strip() for linha in "".join(partes).split("\n"))
    return re.sub(r"\n{2,}", "\n", texto).strip()


def resgatar(dados: bytes) -> tuple[list[str], list[bytes]]:
    """Extrai textos (um por fluxo de conteúdo) e imagens JPEG de um PDF destruído."""
    textos: list[str] = []
    imagens: list[bytes] = []
    for dicionario, conteudo in _fluxos(dados):
        if b"/DCTDecode" in dicionario and conteudo.startswith(b"\xff\xd8"):
            imagens.append(conteudo)
            continue
        t = texto_de_fluxo(conteudo)
        if t.strip():
            textos.append(t)
    return textos, imagens


def montar_pdf_texto(paginas_texto: list[str], imagens: list[bytes] | None = None, titulo: str = "") -> bytes:
    """Monta um PDF novo e legível com o texto (e imagens) recuperados."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=titulo or "Documento restaurado")
    estilo = getSampleStyleSheet()
    corpo = []
    for i, pagina in enumerate(paginas_texto):
        if i:
            corpo.append(PageBreak())
        for paragrafo in re.split(r"\n\s*\n", pagina):
            if paragrafo.strip():
                corpo.append(Paragraph(escape(paragrafo.strip()).replace("\n", "<br/>"), estilo["Normal"]))
                corpo.append(Spacer(1, 6))
    for jpg in imagens or []:
        try:
            leitor = ImageReader(io.BytesIO(jpg))
            w, h = leitor.getSize()
            escala = min(450 / w, 650 / h, 1)
            corpo += [PageBreak(), RLImage(io.BytesIO(jpg), width=w * escala, height=h * escala)]
        except Exception:
            continue
    if not corpo:
        corpo.append(Paragraph("(nenhum conteúdo recuperável)", estilo["Normal"]))
    doc.build(corpo)
    return buf.getvalue()


# ---------- páginas ----------

def _textos_e_digitalizadas(pdf_bytes: bytes, r: Restauracao, usar_ocr: bool) -> list[str]:
    import pypdfium2 as pdfium

    textos: list[str] = []
    try:
        doc = pdfium.PdfDocument(pdf_bytes)
    except Exception as erro:
        r.problemas.append(f"não foi possível renderizar o PDF: {erro}")
        return textos
    restauradas = []
    for i in range(len(doc)):
        try:
            pagina = doc[i]
            t = pagina.get_textpage().get_text_range()
        except Exception:
            r.problemas.append(f"página {i + 1}: conteúdo ilegível")
            textos.append("")
            continue
        if len(t.strip()) < 20:
            # Página digitalizada (só imagem): limpa e tenta OCR.
            try:
                img = pagina.render(scale=2).to_pil()
                limpa, _ = im.restaurar_pagina(img)
                restauradas.append(limpa)
                if usar_ocr and im.ocr_disponivel():
                    t = im.ocr(limpa)
                    r.feito.append(f"página {i + 1}: texto reconhecido por OCR")
            except Exception as erro:
                r.problemas.append(f"página {i + 1}: falha ao tratar imagem ({erro})")
        textos.append(t)
    if restauradas:
        buf = io.BytesIO()
        restauradas[0].save(buf, format="PDF", save_all=True, append_images=restauradas[1:], resolution=150)
        r.extras.append((_sem_ext(r.nome) + "_paginas_digitalizadas_restauradas.pdf", buf.getvalue()))
        r.feito.append(f"{len(restauradas)} página(s) digitalizada(s) limpa(s): inclinação, manchas e contraste")
        if not (usar_ocr and im.ocr_disponivel()):
            r.problemas.append(
                f"{len(restauradas)} página(s) são imagem: instale o Tesseract (tesseract-ocr-por) para extrair o texto"
            )
    return textos


def _sem_ext(nome: str) -> str:
    return re.sub(r"\.[^.]+$", "", nome)


def restaurar_pdf(dados: bytes, r: Restauracao, usar_ocr: bool = True) -> Restauracao:
    dados = _aparar(dados, r)
    esperadas = _contagem_declarada(dados)

    pdf = _via_pikepdf(dados, r) or _via_pypdf(dados, r)
    if pdf:
        if r.problemas and r.status != PARCIAL:
            r.piorar(RESTAURADO)
        textos = _textos_e_digitalizadas(pdf, r, usar_ocr)
        r.paginas = len(textos)
        r.texto = "\n\n".join(f"[Página {i + 1}]\n{t.strip()}" for i, t in enumerate(textos))
        r.arquivo = (_sem_ext(r.nome) + ".pdf", pdf)
    else:
        textos, imagens = resgatar(dados)
        if not textos and not imagens:
            r.piorar(IRRECUPERAVEL)
            r.problemas.append("nenhum texto ou imagem pôde ser extraído do PDF")
            return r
        textos = [tx.restaurar_texto(t)[0] for t in textos]
        r.feito.append(
            f"resgate bruto: {len(textos)} bloco(s) de texto e {len(imagens)} imagem(ns) extraídos dos fluxos internos"
        )
        r.texto = "\n\n".join(f"[Bloco {i + 1}]\n{t.strip()}" for i, t in enumerate(textos))
        r.arquivo = (_sem_ext(r.nome) + "_resgatado.pdf", montar_pdf_texto(textos, imagens, r.nome))
        r.paginas = len(textos)
        r.piorar(PARCIAL)
        r.problemas.append("layout original perdido: o PDF foi remontado só com texto e imagens resgatados")

    if esperadas and r.paginas is not None and r.paginas < esperadas:
        r.paginas_esperadas = esperadas
        r.problemas.append(f"o documento declara {esperadas} páginas mas só {r.paginas} foram recuperadas")
        r.piorar(PARCIAL)
    return r
