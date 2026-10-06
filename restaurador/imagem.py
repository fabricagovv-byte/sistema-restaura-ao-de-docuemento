"""Restauração de imagens e páginas digitalizadas.

- Abre imagens truncadas/corrompidas (aproveita o que foi gravado).
- Corrige orientação (EXIF), inclinação (deskew), sombra/iluminação desigual, manchas e ruído,
  contraste desbotado (documento amarelado/apagado) e recorta bordas pretas de scanner.
- Faz OCR (Tesseract, português) quando disponível.
"""

from __future__ import annotations

import io
import shutil

import cv2
import numpy as np
from PIL import Image, ImageFile, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True


def abrir_imagem(dados: bytes) -> tuple[Image.Image | None, list[str]]:
    feito: list[str] = []
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except Exception as erro:
        recuperada = _abrir_com_opencv(dados)
        if recuperada is None:
            return None, [f"imagem ilegível: {erro}"]
        img = recuperada
        feito.append("imagem lida por decodificador alternativo (arquivo corrompido)")
    else:
        if _parece_truncada(dados, img.format):
            feito.append("imagem truncada: parte inferior perdida foi preenchida (não há como recuperá-la)")
    try:
        if img.getexif().get(0x0112, 1) != 1:
            img = ImageOps.exif_transpose(img)
            feito.append("orientação corrigida pelo EXIF")
    except Exception:
        pass
    return img, feito


def _abrir_com_opencv(dados: bytes) -> Image.Image | None:
    arr = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def _parece_truncada(dados: bytes, formato: str | None) -> bool:
    if formato == "JPEG":
        return not dados.rstrip(b"\x00").endswith(b"\xff\xd9")
    if formato == "PNG":
        return b"IEND" not in dados[-64:]
    return False


def _cinza(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("L"))


def corrigir_iluminacao(cinza: np.ndarray) -> np.ndarray:
    """Remove sombras e manchas amplas dividindo pela iluminação de fundo estimada."""
    tamanho = max(31, (min(cinza.shape) // 20) | 1)
    fundo = cv2.medianBlur(cv2.dilate(cinza, np.ones((7, 7), np.uint8)), tamanho)
    return cv2.divide(cinza, fundo, scale=255)


def angulo_inclinacao(cinza: np.ndarray) -> float:
    """Estima a inclinação do texto (graus) pela projeção horizontal: testa ângulos e escolhe o
    que deixa as linhas de texto mais nítidas."""
    pequeno = cinza
    escala = 1000 / max(cinza.shape)
    if escala < 1:
        pequeno = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    tinta = (pequeno < 128).astype(np.uint8)
    if tinta.sum() < 50:
        return 0.0
    h, w = tinta.shape
    centro = (w / 2, h / 2)

    def nitidez(angulo: float) -> float:
        m = cv2.getRotationMatrix2D(centro, angulo, 1.0)
        girada = cv2.warpAffine(tinta, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        perfil = girada.sum(axis=1).astype(np.float64)
        return float(np.sum(np.diff(perfil) ** 2))

    melhor = max(np.arange(-15, 15.01, 1.0), key=nitidez)
    fino = max(np.arange(melhor - 1, melhor + 1.01, 0.1), key=nitidez)
    return round(float(fino), 2)


def girar(cinza: np.ndarray, angulo: float) -> np.ndarray:
    h, w = cinza.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, 1.0)
    cos, sen = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sen + w * cos), int(h * cos + w * sen)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(cinza, m, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=255)


def esticar_niveis(cinza: np.ndarray) -> np.ndarray:
    """Leva o tom do papel para branco e o da tinta para preto (níveis), sem amplificar o granulado."""
    tinta = float(np.percentile(cinza, 0.5))
    papel = float(np.percentile(cinza, 60))
    if papel - tinta < 10:
        return cinza
    esticada = (cinza.astype(np.float32) - tinta) * (255.0 / (papel - tinta))
    return np.clip(esticada, 0, 255).astype(np.uint8)


def recortar_bordas_pretas(cinza: np.ndarray) -> np.ndarray:
    _, mascara = cv2.threshold(cinza, 40, 255, cv2.THRESH_BINARY)
    linhas = np.where(mascara.mean(axis=1) > 128)[0]
    colunas = np.where(mascara.mean(axis=0) > 128)[0]
    if len(linhas) < cinza.shape[0] * 0.5 or len(colunas) < cinza.shape[1] * 0.5:
        return cinza
    return cinza[linhas[0]:linhas[-1] + 1, colunas[0]:colunas[-1] + 1]


def restaurar_pagina(img: Image.Image, binarizar: bool = False) -> tuple[Image.Image, list[str]]:
    """Pipeline de restauração de uma página digitalizada/fotografada."""
    feito: list[str] = []
    cinza = _cinza(img)

    recortada = recortar_bordas_pretas(cinza)
    if recortada.shape != cinza.shape:
        feito.append("bordas pretas do scanner removidas")
    cinza = recortada

    cinza = corrigir_iluminacao(cinza)
    feito.append("sombras, manchas e amarelado removidos (iluminação uniformizada)")

    cinza = cv2.fastNlMeansDenoising(cinza, None, h=12, templateWindowSize=7, searchWindowSize=21)
    feito.append("ruído/granulado reduzido")

    angulo = angulo_inclinacao(cinza)
    if abs(angulo) >= 0.3:
        cinza = girar(cinza, angulo)
        feito.append(f"inclinação corrigida ({angulo:+.1f}°)")

    cinza = esticar_niveis(cinza)
    feito.append("contraste do texto apagado/desbotado reforçado (fundo branco, tinta escura)")

    if binarizar:
        cinza = cv2.adaptiveThreshold(cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        feito.append("página convertida para preto e branco nítido")
    return Image.fromarray(cinza), feito


def ocr_disponivel() -> bool:
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def ocr(img: Image.Image) -> str:
    import pytesseract

    idiomas = pytesseract.get_languages(config="")
    lang = "por" if "por" in idiomas else "eng"
    return pytesseract.image_to_string(img, lang=lang, config="--psm 3")


def imagem_para_bytes(img: Image.Image, formato: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=formato)
    return buf.getvalue()
