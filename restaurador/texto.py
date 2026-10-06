"""Restauração de texto: codificação, caracteres corrompidos, quebras de linha e hifenização.

Tudo aqui é conservador: corrige o que é mecanicamente certo (acentos quebrados por
codificação errada, palavras hifenizadas na quebra de linha, linhas partidas no meio da frase)
e nunca inventa conteúdo.
"""

from __future__ import annotations

import re
import unicodedata

import ftfy
from charset_normalizer import from_bytes


def decodificar(dados: bytes) -> tuple[str, str]:
    """Descobre a codificação (UTF-8, Latin-1, CP1252, UTF-16...) e devolve (texto, codificação)."""
    if dados.startswith(b"\xef\xbb\xbf"):
        return dados[3:].decode("utf-8", "replace"), "utf-8-sig"
    if dados[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return dados.decode("utf-16", "replace"), "utf-16"
    try:
        return dados.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # UTF-8 com poucos bytes danificados (ex.: arquivo cortado no meio de um caractere acentuado)
        # continua sendo UTF-8: não vale trocar a codificação do arquivo inteiro por causa disso.
        tolerante = dados.decode("utf-8", "replace")
        if tolerante.count("\ufffd") <= max(2, len(dados) // 1000):
            return tolerante.rstrip("\ufffd"), "utf-8"
    melhor = from_bytes(dados).best()
    if melhor is not None and melhor.encoding:
        return str(melhor), melhor.encoding
    return dados.decode("cp1252", "replace"), "cp1252"


_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f￾￿]")
_HIFEN_QUEBRA = re.compile(r"(\w)[-­]\n[ \t]*([a-záéíóúâêôãõçà]\w*)")
_FIM_DE_FRASE = re.compile(r"[.!?:;)\]\"'»”]\s*$")


def corrigir_caracteres(texto: str) -> tuple[str, list[str]]:
    feito: list[str] = []
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    corrigido = ftfy.fix_text(texto, normalization="NFC", uncurl_quotes=False, fix_line_breaks=False)
    if corrigido != texto:
        feito.append("acentos/caracteres corrompidos por codificação errada corrigidos (mojibake)")
    sem_controle = _CONTROLE.sub("", corrigido)
    if sem_controle != corrigido:
        feito.append("caracteres de controle/lixo binário removidos")
    sem_controle = sem_controle.replace("�", "�")
    return unicodedata.normalize("NFC", sem_controle), feito


def juntar_hifenizacao(texto: str) -> str:
    return _HIFEN_QUEBRA.sub(r"\1\2", texto)


def juntar_linhas_partidas(texto: str) -> str:
    """Reúne linhas quebradas no meio da frase (típico de PDF e OCR), preservando parágrafos,
    listas, títulos e tabelas."""
    linhas = texto.split("\n")
    saida: list[str] = []
    for linha in linhas:
        atual = linha.rstrip()
        if (
            saida
            and saida[-1].strip()
            and atual.strip()
            and not _FIM_DE_FRASE.search(saida[-1])
            and not _inicio_de_bloco(atual)
            and not _parece_tabela(saida[-1])
            and atual.lstrip()[:1].islower()
        ):
            saida[-1] = saida[-1].rstrip() + " " + atual.lstrip()
        else:
            saida.append(atual)
    return "\n".join(saida)


def _inicio_de_bloco(linha: str) -> bool:
    s = linha.lstrip()
    return bool(re.match(r"([-•*–]|\d+[.)]|[a-z][)]|[IVXLC]+[.-]\s|art\.|§|cl[áa]usula)", s, re.I))


def _parece_tabela(linha: str) -> bool:
    return linha.count("|") >= 2 or linha.count("\t") >= 2 or bool(re.search(r"\S {3,}\S", linha))


def normalizar_espacos(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{4,}", "\n\n\n", texto)
    return texto.strip() + "\n" if texto.strip() else ""


def restaurar_texto(texto: str) -> tuple[str, list[str]]:
    """Aplica todas as correções seguras e devolve (texto, lista do que foi feito)."""
    texto, feito = corrigir_caracteres(texto)
    base = normalizar_espacos(texto)
    hifen = juntar_hifenizacao(base)
    if hifen != base:
        feito.append("palavras hifenizadas na quebra de linha reunidas")
    juntas = juntar_linhas_partidas(hifen)
    if juntas != hifen:
        feito.append("linhas partidas no meio da frase reunidas em parágrafos")
    return normalizar_espacos(juntas), feito


def qualidade_texto(texto: str) -> float:
    """0 a 1: fração de 'palavras' que parecem palavras reais (letras, sem lixo). Usado para
    escolher a melhor versão de um documento e para decidir se vale tentar OCR/IA."""
    palavras = re.findall(r"\S+", texto)
    if not palavras:
        return 0.0
    boas = sum(1 for p in palavras if re.fullmatch(r"[\wÀ-ÿ.,;:!?()\"'/%$ºª°§-]+", p) and not re.search(r"(.)\1{4,}", p))
    return round(boas / len(palavras), 3)


def costurar_fragmentos(fragmentos: list[str], minimo: int = 40) -> str:
    """Junta pedaços de texto do mesmo documento que se sobrepõem (ex.: duas cópias parciais,
    uma com o começo e outra com o fim), eliminando a parte repetida."""
    restantes = [f.strip() for f in fragmentos if f and f.strip()]
    if not restantes:
        return ""
    resultado = max(restantes, key=len)
    restantes.remove(resultado)
    mudou = True
    while restantes and mudou:
        mudou = False
        for frag in list(restantes):
            if frag in resultado:
                restantes.remove(frag)
                mudou = True
                continue
            juntado = _juntar_por_sobreposicao(resultado, frag, minimo)
            if juntado:
                resultado = juntado
                restantes.remove(frag)
                mudou = True
    # O que não se encaixou entra no fim, sinalizado.
    for frag in restantes:
        resultado += "\n\n[--- trecho sem ligação clara com o restante ---]\n\n" + frag
    return resultado


def _juntar_por_sobreposicao(a: str, b: str, minimo: int) -> str | None:
    for primeiro, segundo in ((a, b), (b, a)):
        # Fim de `primeiro` igual ao começo de `segundo`: procura o começo de `segundo` em `primeiro`.
        ancora = segundo[:minimo]
        if len(ancora) < minimo:
            continue
        pos = primeiro.find(ancora)
        while pos != -1:
            cauda = primeiro[pos:]
            if segundo.startswith(cauda):
                return primeiro + segundo[len(cauda):]
            pos = primeiro.find(ancora, pos + 1)
    return None
