"""Busca de documentos: varre pastas, arquivos compactados e dados brutos atrás de documentos.

- Pastas são percorridas recursivamente.
- ZIPs comuns (não Office) são abertos e seu conteúdo entra na busca.
- Imagens de disco, dumps, arquivos .CHK/.bak/sem extensão ou qualquer arquivo que não seja um
  documento reconhecível são "escavados" (file carving): procuramos as assinaturas de PDF, Office,
  RTF, OLE (doc/xls antigos), JPEG e PNG dentro dos bytes e extraímos cada documento encontrado,
  mesmo que esteja cortado — a restauração cuida do resto.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import deteccao as d

TAMANHO_MINIMO = 64  # bytes; fragmentos menores não valem a extração
EXTENSOES_BRUTAS = {".img", ".dd", ".raw", ".bin", ".chk", ".dat", ".dmp", ".iso", ".vhd", ".tmp", ".bak", ".001"}


@dataclass
class Encontrado:
    nome: str
    dados: bytes
    origem: str  # arquivo de onde veio
    como: str = "arquivo"  # arquivo | dentro de zip | escavado
    deslocamento: int | None = None
    tipo: str = ""
    observacoes: list[str] = field(default_factory=list)
    copias_identicas: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.tipo:
            self.tipo = d.detectar_tipo(self.dados, self.nome)

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.dados).hexdigest()


ASSINATURAS = [
    (b"%PDF-", d.PDF),
    (b"PK\x03\x04", d.ZIP),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", d.DOC_OLE),
    (b"{\\rtf", d.RTF),
    (b"\xff\xd8\xff", d.JPEG),
    (b"\x89PNG\r\n\x1a\n", d.PNG),
]
_PADRAO = re.compile(b"|".join(re.escape(a) for a, _ in ASSINATURAS))
_TIPO_DA_ASSINATURA = {a: t for a, t in ASSINATURAS}


def _fim_pdf(dados: bytes, inicio: int, limite: int) -> int:
    trecho = dados[inicio:limite]
    ultimo = trecho.rfind(b"%%EOF")
    if ultimo == -1:
        return limite  # cortado: leva tudo até o próximo achado
    fim = ultimo + 5
    while fim < len(trecho) and trecho[fim:fim + 1] in (b"\r", b"\n"):
        fim += 1
    return inicio + fim


def _fim_zip(dados: bytes, inicio: int) -> int:
    """Fim do ZIP = registro EOCD + comentário. Sem EOCD, vai até a última entrada local plausível."""
    pos = dados.find(b"PK\x05\x06", inicio)
    if pos != -1 and pos + 22 <= len(dados):
        comentario = int.from_bytes(dados[pos + 20:pos + 22], "little")
        return min(pos + 22 + comentario, len(dados))
    # Sem diretório central: avança enquanto houver entradas PK encadeadas.
    fim = inicio
    for m in re.finditer(b"PK\x03\x04|PK\x01\x02", dados[inicio:]):
        fim = inicio + m.start()
    return _fim_ate_lixo(dados, fim)


def _fim_ate_lixo(dados: bytes, desde: int) -> int:
    # Para quando encontra um longo trecho de zeros (área vazia do disco).
    pos = dados.find(b"\x00" * 512, desde)
    return len(dados) if pos == -1 else pos


def _fim_jpeg(dados: bytes, inicio: int, limite: int) -> int:
    pos = dados.rfind(b"\xff\xd9", inicio, limite)
    return limite if pos == -1 else pos + 2


def _fim_png(dados: bytes, inicio: int, limite: int) -> int:
    pos = dados.find(b"IEND", inicio, limite)
    return limite if pos == -1 else min(pos + 8, len(dados))


def _fim_rtf(dados: bytes, inicio: int, limite: int) -> int:
    nivel = 0
    i = inicio
    while i < limite:
        c = dados[i]
        if c == 0x5C:  # barra invertida: pula o caractere escapado
            i += 2
            continue
        if c == 0x7B:
            nivel += 1
        elif c == 0x7D:
            nivel -= 1
            if nivel == 0:
                return i + 1
        i += 1
    return limite


def escavar(dados: bytes, origem: str) -> list[Encontrado]:
    """Procura documentos embutidos em dados brutos (file carving)."""
    achados: list[Encontrado] = []
    inicios = [(m.start(), _TIPO_DA_ASSINATURA[m.group()]) for m in _PADRAO.finditer(dados)]
    pos_minima = 0
    for indice, (inicio, tipo) in enumerate(inicios):
        if inicio < pos_minima:
            continue  # está dentro de um documento já extraído (ex.: JPEG dentro de PDF/DOCX)
        limite = next((s for s, _ in inicios[indice + 1:] if s >= inicio + 1 and not _interno(tipo, dados, s)), len(dados))
        limite = min(limite, _fim_ate_lixo(dados, inicio))
        if tipo == d.PDF:
            fim = _fim_pdf(dados, inicio, max(limite, _proximo_de_outro_pdf(dados, inicio)))
        elif tipo == d.ZIP:
            fim = _fim_zip(dados, inicio)
        elif tipo == d.JPEG:
            fim = _fim_jpeg(dados, inicio, limite)
        elif tipo == d.PNG:
            fim = _fim_png(dados, inicio, limite)
        elif tipo == d.RTF:
            fim = _fim_rtf(dados, inicio, len(dados))
        else:
            fim = limite
        bloco = dados[inicio:fim]
        if len(bloco) < TAMANHO_MINIMO:
            continue
        tipo_real = d.detectar_tipo(bloco)
        nome = f"{Path(origem).stem}_escavado_{len(achados) + 1:03d}_off{inicio}{d.EXTENSAO.get(tipo_real, '.bin')}"
        achados.append(Encontrado(nome, bloco, origem, "escavado", inicio, tipo_real))
        pos_minima = fim
    return achados


def _interno(tipo_atual: str, dados: bytes, pos: int) -> bool:
    """Assinaturas que normalmente aparecem DENTRO de outro documento e não iniciam um novo."""
    if tipo_atual == d.ZIP and dados.startswith(b"PK\x03\x04", pos):
        return True  # próxima entrada do mesmo ZIP
    if tipo_atual == d.PDF and (dados.startswith(b"\xff\xd8\xff", pos) or dados.startswith(b"\x89PNG", pos)):
        return True  # imagem embutida no PDF
    return False


def _proximo_de_outro_pdf(dados: bytes, inicio: int) -> int:
    pos = dados.find(b"%PDF-", inicio + 5)
    return len(dados) if pos == -1 else pos


def _deve_escavar(item: Encontrado) -> bool:
    ext = Path(item.nome).suffix.lower()
    if ext in EXTENSOES_BRUTAS or item.tipo == d.DESCONHECIDO:
        return True
    if item.tipo == d.TEXTO:
        return False
    # Documento com lixo antes do cabeçalho ou vários documentos colados num só arquivo.
    return item.tipo == d.PDF and item.dados.count(b"%PDF-") > 1


def _abrir_zip(item: Encontrado) -> list[Encontrado] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(item.dados)) as z:
            saida = []
            for info in z.infolist():
                if info.is_dir():
                    continue
                try:
                    conteudo = z.read(info)
                except Exception as erro:
                    item.observacoes.append(f"{info.filename}: não foi possível extrair ({erro})")
                    continue
                saida.append(Encontrado(Path(info.filename).name, conteudo, f"{item.nome}/{info.filename}", "dentro de zip"))
            return saida
    except zipfile.BadZipFile:
        return None


def expandir(item: Encontrado, profundidade: int = 0) -> list[Encontrado]:
    """Abre ZIPs e escava dados brutos, recursivamente."""
    if profundidade > 3:
        return [item]
    if item.tipo == d.ZIP:
        internos = _abrir_zip(item)
        if internos is not None:
            return [x for i in internos for x in expandir(i, profundidade + 1)]
        # ZIP corrompido: será restaurado como arquivo.
        return [item]
    if _deve_escavar(item):
        achados = escavar(item.dados, item.nome)
        if achados and not (len(achados) == 1 and achados[0].dados == item.dados):
            for a in achados:
                a.origem = item.origem if item.origem != item.nome else item.nome
            return [x for a in achados for x in expandir(a, profundidade + 1)] or [item]
    return [item]


def coletar(entradas: list[str | Path | tuple[str, bytes]]) -> list[Encontrado]:
    """Recebe caminhos (arquivos/pastas) ou pares (nome, bytes) e devolve todos os documentos encontrados,
    sem duplicatas exatas."""
    brutos: list[Encontrado] = []
    for entrada in entradas:
        if isinstance(entrada, tuple):
            nome, dados = entrada
            brutos.append(Encontrado(nome, dados, nome))
            continue
        caminho = Path(entrada)
        if caminho.is_dir():
            for raiz, _, arquivos in os.walk(caminho):
                for arq in sorted(arquivos):
                    p = Path(raiz) / arq
                    brutos.append(Encontrado(arq, p.read_bytes(), str(p)))
        elif caminho.is_file():
            brutos.append(Encontrado(caminho.name, caminho.read_bytes(), str(caminho)))
        else:
            raise FileNotFoundError(f"Não encontrado: {caminho}")

    vistos: dict[str, Encontrado] = {}
    saida: list[Encontrado] = []
    for item in brutos:
        for achado in expandir(item):
            if achado.hash in vistos:
                onde = achado.origem if achado.como != "escavado" else f"{achado.origem} (posição {achado.deslocamento})"
                vistos[achado.hash].copias_identicas.append(onde)
                continue
            vistos[achado.hash] = achado
            saida.append(achado)
    return saida
