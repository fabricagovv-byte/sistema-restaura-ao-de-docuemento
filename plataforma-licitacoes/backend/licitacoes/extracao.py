"""Extração de texto dos documentos, página a página, com a cláusula de cada trecho.

PDF: PyMuPDF. Páginas que são só imagem passam pela limpeza e OCR do módulo `restaurador`
(o sistema de restauração de documentos deste repositório), quando ele e o Tesseract estão
disponíveis. PDF danificado também é consertado por ele antes da leitura.
DOCX, XLSX, TXT/HTML e ZIP (com os arquivos de dentro) são suportados.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[3]
if str(RAIZ_REPO) not in sys.path:
    sys.path.append(str(RAIZ_REPO))

try:  # reaproveita o restaurador do repositório (OCR, PDF danificado, acentos corrompidos)
    from restaurador import imagem as _rest_img
    from restaurador.texto import corrigir_caracteres as _corrigir
    RESTAURADOR = True
except Exception:  # pragma: no cover - ambiente sem o restaurador
    _rest_img = None
    _corrigir = None
    RESTAURADOR = False

RE_CLAUSULA = re.compile(
    r"^\s*((?:cl[aá]usula\s+[\wºª]+|item\s+\d+(?:\.\d+)*|\d{1,2}(?:\.\d{1,3}){0,4})[\s.)–-]+)([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{2,120})",
    re.IGNORECASE | re.MULTILINE,
)
CARACTERES_POR_PAGINA_LOGICA = 3500


@dataclass
class Pagina:
    documento: str
    numero: int
    texto: str
    ocr: bool = False
    logica: bool = False  # True quando o formato não tem página (DOCX/TXT) e a divisão é por tamanho


def _limpar(t: str) -> str:
    if _corrigir:
        try:
            t, _ = _corrigir(t)
        except Exception:
            pass
    return re.sub(r"[ \t]+\n", "\n", t)


def _pdf(nome: str, dados: bytes, usar_ocr: bool = True) -> list[Pagina]:
    import pymupdf

    try:
        doc = pymupdf.open(stream=dados, filetype="pdf")
    except Exception:
        if not RESTAURADOR:
            raise
        from restaurador.modelos import Restauracao
        from restaurador.pdf import restaurar_pdf

        r = restaurar_pdf(dados, Restauracao(nome=nome, origem=nome, tipo="pdf"), usar_ocr=False)
        if r.arquivo:
            doc = pymupdf.open(stream=r.arquivo[1], filetype="pdf")
        else:  # estrutura destruída: usa o texto resgatado, página a página
            partes = re.split(r"\[Página \d+\]\n", r.texto)
            return [Pagina(nome, i, _limpar(t)) for i, t in enumerate([p for p in partes if p.strip()], 1)]
    paginas = []
    for i, pg in enumerate(doc, 1):
        t = pg.get_text("text") or ""
        ocr = False
        if len(t.strip()) < 20 and usar_ocr and _rest_img is not None and _rest_img.ocr_disponivel():
            from PIL import Image

            pix = pg.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            limpa, _ = _rest_img.restaurar_pagina(img)
            t = _rest_img.ocr(limpa)
            ocr = True
        paginas.append(Pagina(nome, i, _limpar(t), ocr=ocr))
    return paginas


def _logicas(nome: str, texto: str) -> list[Pagina]:
    texto = _limpar(texto)
    blocos, atual = [], []
    tam = 0
    for par in texto.split("\n"):
        atual.append(par)
        tam += len(par) + 1
        if tam >= CARACTERES_POR_PAGINA_LOGICA:
            blocos.append("\n".join(atual))
            atual, tam = [], 0
    if atual:
        blocos.append("\n".join(atual))
    return [Pagina(nome, i, b, logica=True) for i, b in enumerate(blocos or [""], 1)]


def _docx(nome: str, dados: bytes) -> list[Pagina]:
    import docx

    d = docx.Document(io.BytesIO(dados))
    partes = [p.text for p in d.paragraphs]
    for tab in d.tables:
        for linha in tab.rows:
            partes.append(" | ".join(c.text.strip() for c in linha.cells))
    return _logicas(nome, "\n".join(partes))


def _xlsx(nome: str, dados: bytes) -> list[Pagina]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
    paginas = []
    for i, ws in enumerate(wb.worksheets, 1):
        linhas = []
        for row in ws.iter_rows(values_only=True):
            if any(v is not None for v in row):
                linhas.append(" | ".join("" if v is None else str(v) for v in row))
        paginas.append(Pagina(f"{nome} [aba {ws.title}]", i, "\n".join(linhas), logica=True))
    return paginas


def _texto(nome: str, dados: bytes) -> list[Pagina]:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            t = dados.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "<html" in t[:1000].lower():
        t = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", t))
    return _logicas(nome, t)


def extrair(nome: str, dados: bytes, usar_ocr: bool = True, profundidade: int = 0) -> list[Pagina]:
    n = nome.lower()
    if dados.startswith(b"%PDF") or n.endswith(".pdf"):
        return _pdf(nome, dados, usar_ocr)
    if dados.startswith(b"PK"):
        try:
            z = zipfile.ZipFile(io.BytesIO(dados))
        except zipfile.BadZipFile:
            return []
        nomes = z.namelist()
        if "word/document.xml" in nomes:
            return _docx(nome, dados)
        if "xl/workbook.xml" in nomes:
            return _xlsx(nome, dados)
        if profundidade > 2:
            return []
        paginas = []
        for interno in nomes:
            if interno.endswith("/"):
                continue
            try:
                paginas += extrair(f"{nome}/{interno}", z.read(interno), usar_ocr, profundidade + 1)
            except Exception:
                continue
        return paginas
    if n.endswith((".txt", ".csv", ".html", ".htm", ".xml", ".md")):
        return _texto(nome, dados)
    return []


def clausulas(pagina: Pagina) -> list[tuple[int, str]]:
    """Posições e títulos das cláusulas que começam nesta página."""
    return [(m.start(), (m.group(1) + m.group(2)).strip()) for m in RE_CLAUSULA.finditer(pagina.texto)]


def clausula_em(paginas: list[Pagina], documento: str, numero: int, posicao: int) -> str | None:
    """Cláusula vigente num ponto do documento (a última que começou antes, mesmo em página anterior)."""
    docs = [p for p in paginas if p.documento == documento and p.numero <= numero]
    for p in sorted(docs, key=lambda x: x.numero, reverse=True):
        cl = [c for pos, c in clausulas(p) if p.numero < numero or pos <= posicao]
        if cl:
            return cl[-1]
    return None
