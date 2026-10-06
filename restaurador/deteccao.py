"""Identificação do tipo real de um arquivo pelo conteúdo (assinatura), não pela extensão.

Arquivos danificados ou recuperados de backups costumam vir com extensão errada,
sem extensão ou com nomes genéricos (FILE0001.CHK, arquivo.bak). Aqui olhamos os bytes.
"""

from __future__ import annotations

import io
import re
import zipfile

# Tipos lógicos usados pelo restante do sistema.
PDF, DOCX, XLSX, PPTX, ODT, ODS, ZIP, DOC_OLE, RTF, JPEG, PNG, TIFF, BMP, GIF, HTML, TEXTO, DESCONHECIDO = (
    "pdf", "docx", "xlsx", "pptx", "odt", "ods", "zip", "doc", "rtf", "jpeg", "png", "tiff", "bmp", "gif",
    "html", "texto", "desconhecido",
)

IMAGENS = {JPEG, PNG, TIFF, BMP, GIF}
OFFICE_ZIP = {DOCX, XLSX, PPTX, ODT, ODS}

EXTENSAO = {
    PDF: ".pdf", DOCX: ".docx", XLSX: ".xlsx", PPTX: ".pptx", ODT: ".odt", ODS: ".ods", ZIP: ".zip",
    DOC_OLE: ".doc", RTF: ".rtf", JPEG: ".jpg", PNG: ".png", TIFF: ".tif", BMP: ".bmp", GIF: ".gif",
    HTML: ".html", TEXTO: ".txt", DESCONHECIDO: ".bin",
}

_EXT_PARA_TIPO = {
    ".pdf": PDF, ".docx": DOCX, ".docm": DOCX, ".xlsx": XLSX, ".xlsm": XLSX, ".pptx": PPTX, ".odt": ODT,
    ".ods": ODS, ".zip": ZIP, ".doc": DOC_OLE, ".xls": DOC_OLE, ".rtf": RTF, ".jpg": JPEG, ".jpeg": JPEG,
    ".png": PNG, ".tif": TIFF, ".tiff": TIFF, ".bmp": BMP, ".gif": GIF, ".html": HTML, ".htm": HTML,
    ".txt": TEXTO, ".md": TEXTO, ".csv": TEXTO, ".xml": TEXTO, ".json": TEXTO,
}


def tipo_pela_extensao(nome: str) -> str:
    m = re.search(r"(\.[A-Za-z0-9]{2,5})$", nome.lower())
    return _EXT_PARA_TIPO.get(m.group(1), DESCONHECIDO) if m else DESCONHECIDO


def _tipo_zip(dados: bytes) -> str:
    """Distingue DOCX/XLSX/PPTX/ODT/ODS dentro de um ZIP, mesmo com o diretório central quebrado."""
    nomes = ""
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nomes = " ".join(z.namelist())
            if "mimetype" in z.namelist():
                mime = z.read("mimetype").decode("ascii", "ignore")
                if "spreadsheet" in mime:
                    return ODS
                if "text" in mime:
                    return ODT
    except Exception:
        # Diretório central perdido: procura nomes nas entradas locais.
        nomes = dados[:200_000].decode("latin-1", "ignore")
    if "word/" in nomes:
        return DOCX
    if "xl/" in nomes:
        return XLSX
    if "ppt/" in nomes:
        return PPTX
    if "opendocument.spreadsheet" in nomes:
        return ODS
    if "opendocument.text" in nomes:
        return ODT
    return ZIP


def detectar_tipo(dados: bytes, nome: str = "") -> str:
    cabeca = dados[:2048]
    if b"%PDF-" in cabeca[:1024]:
        return PDF
    if cabeca.startswith(b"PK\x03\x04") or cabeca.startswith(b"PK\x05\x06"):
        return _tipo_zip(dados)
    if cabeca.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return DOC_OLE
    if cabeca.lstrip().startswith(b"{\\rtf"):
        return RTF
    if cabeca.startswith(b"\xff\xd8\xff"):
        return JPEG
    if cabeca.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if cabeca[:4] in (b"II*\x00", b"MM\x00*"):
        return TIFF
    if cabeca.startswith(b"BM"):
        return BMP
    if cabeca[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    baixo = cabeca.lower()
    if b"<html" in baixo or b"<!doctype html" in baixo:
        return HTML
    if cabeca and _parece_texto(cabeca):
        return TEXTO
    # Cabeçalho destruído: confia na extensão como último recurso.
    return tipo_pela_extensao(nome)


def _parece_texto(amostra: bytes) -> bool:
    if b"\x00" in amostra and amostra.count(b"\x00") > len(amostra) * 0.05:
        # UTF-16 tem muitos zeros mas é texto.
        return amostra[:2] in (b"\xff\xfe", b"\xfe\xff")
    imprimiveis = sum(1 for b in amostra if b in (9, 10, 13) or 32 <= b)
    return imprimiveis / max(len(amostra), 1) > 0.9
