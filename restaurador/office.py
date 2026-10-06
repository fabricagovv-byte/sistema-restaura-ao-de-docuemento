"""Restauração de documentos Office (DOCX, XLSX, PPTX, ODT, ODS), RTF, DOC antigo e HTML.

DOCX/XLSX/PPTX/ODT são pacotes ZIP com XML dentro. Quando o arquivo é cortado ou danificado,
normalmente o "índice" do ZIP (diretório central, que fica no fim) se perde e nenhum programa
abre o arquivo — mas as partes continuam lá. Aqui:
1. Lemos o ZIP entrada por entrada pelos cabeçalhos locais, ignorando o índice quebrado.
2. Descomprimimos cada parte, aproveitando até o ponto do dano.
3. Consertamos XML cortado/malformado (fechando as tags abertas).
4. Recriamos partes obrigatórias que sumiram ([Content_Types].xml, _rels/.rels).
5. Remontamos o pacote e conferimos se ele abre de verdade.
Se mesmo assim não abrir, extraímos o texto e geramos um documento novo.
"""

from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib

from lxml import etree

from . import deteccao as d
from . import texto as tx
from .modelos import IRRECUPERAVEL, PARCIAL, RESTAURADO, Restauracao

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = {
    d.DOCX: (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/><Default Extension="jpeg" ContentType="image/jpeg"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    ),
}
RELS = {
    d.DOCX: (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    ),
}


# ---------- leitura tolerante do ZIP ----------

def _descomprimir_parcial(bruto: bytes) -> tuple[bytes, bool]:
    """Inflate cru tolerante: devolve (dados, completo?)."""
    d_ = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        saida = d_.decompress(bruto) + d_.flush()
        return saida, d_.eof
    except zlib.error:
        d_ = zlib.decompressobj(-zlib.MAX_WBITS)
        saida = b""
        for i in range(0, len(bruto), 64):
            try:
                saida += d_.decompress(bruto[i:i + 64])
            except zlib.error:
                break
        return saida, False


def ler_entradas_locais(dados: bytes) -> tuple[dict[str, bytes], list[str]]:
    """Lê todas as entradas do ZIP pelos cabeçalhos locais (não depende do índice no fim)."""
    entradas: dict[str, bytes] = {}
    avisos: list[str] = []
    for m in re.finditer(b"PK\x03\x04", dados):
        p = m.start()
        if p + 30 > len(dados):
            break
        (_, _, flags, metodo, _, _, _, csize, _, nlen, elen) = struct.unpack("<IHHHHHIIIHH", dados[p:p + 30])
        nome = dados[p + 30:p + 30 + nlen].decode("utf-8" if flags & 0x800 else "cp437", "replace")
        inicio = p + 30 + nlen + elen
        if csize == 0 or flags & 0x08 or inicio + csize > len(dados):
            prox = dados.find(b"PK", inicio)
            while prox != -1 and dados[prox:prox + 4] not in (b"PK\x03\x04", b"PK\x01\x02", b"PK\x07\x08", b"PK\x05\x06"):
                prox = dados.find(b"PK", prox + 2)
            fim = len(dados) if prox == -1 else prox
        else:
            fim = inicio + csize
        bruto = dados[inicio:fim]
        if metodo == 0:
            conteudo, completo = bruto, inicio + csize <= len(dados)
        elif metodo == 8:
            conteudo, completo = _descomprimir_parcial(bruto)
        else:
            avisos.append(f"{nome}: compressão {metodo} não suportada")
            continue
        if not completo:
            avisos.append(f"{nome}: parte danificada/cortada, aproveitado o que foi possível")
        if nome and not nome.endswith("/"):
            entradas[nome] = conteudo
    return entradas, avisos


def consertar_xml(conteudo: bytes) -> tuple[bytes, bool]:
    """Faz o parse tolerante e regrava. Devolve (xml, precisou_consertar?)."""
    try:
        etree.fromstring(conteudo)
        return conteudo, False
    except etree.XMLSyntaxError:
        pass
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        raiz = etree.fromstring(conteudo, parser)
    except etree.XMLSyntaxError:
        raiz = None
    if raiz is None:
        return conteudo, True
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True), True


# ---------- extração de texto ----------

def texto_docx_xml(xml: bytes) -> str:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    raiz = etree.fromstring(xml, parser)
    if raiz is None:
        # XML destruído: pega os <w:t> por expressão regular.
        return "\n".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml.decode("utf-8", "replace")))
    paragrafos = []
    for p in raiz.iter(f"{{{NS_W}}}p"):
        paragrafos.append("".join(t.text or "" for t in p.iter(f"{{{NS_W}}}t")))
    return "\n".join(paragrafos)


def _texto_generico_xml(xml: bytes) -> str:
    raiz = etree.fromstring(xml, etree.XMLParser(recover=True, huge_tree=True))
    if raiz is None:
        return re.sub(r"<[^>]+>", " ", xml.decode("utf-8", "replace"))
    return "\n".join(t.strip() for t in raiz.itertext() if t.strip())


def texto_do_pacote(tipo: str, entradas: dict[str, bytes]) -> str:
    if tipo == d.DOCX:
        partes = [k for k in entradas if re.match(r"word/(document|header\d*|footer\d*|footnotes)\.xml$", k)]
        partes.sort(key=lambda k: (k != "word/document.xml", k))
        return "\n\n".join(texto_docx_xml(entradas[k]) for k in partes)
    if tipo == d.XLSX:
        compartilhadas = []
        if "xl/sharedStrings.xml" in entradas:
            raiz = etree.fromstring(entradas["xl/sharedStrings.xml"], etree.XMLParser(recover=True, huge_tree=True))
            if raiz is not None:
                compartilhadas = ["".join(si.itertext()) for si in raiz if si.tag.endswith("si")]
        linhas = []
        for k in sorted(x for x in entradas if x.startswith("xl/worksheets/")):
            linhas.append(f"[{k.rsplit('/', 1)[-1]}]")
            raiz = etree.fromstring(entradas[k], etree.XMLParser(recover=True, huge_tree=True))
            if raiz is None:
                continue
            for row in raiz.iter("{*}row"):
                valores = []
                for c in row.iter("{*}c"):
                    v = c.find("{*}v")
                    texto_inline = "".join(c.find("{*}is").itertext()) if c.find("{*}is") is not None else None
                    valor = texto_inline if texto_inline is not None else (v.text if v is not None else "")
                    if c.get("t") == "s" and valor and valor.isdigit() and int(valor) < len(compartilhadas):
                        valor = compartilhadas[int(valor)]
                    valores.append(valor or "")
                linhas.append("\t".join(valores))
        return "\n".join(linhas)
    if tipo == d.PPTX:
        slides = sorted((k for k in entradas if re.match(r"ppt/slides/slide\d+\.xml$", k)),
                        key=lambda k: int(re.search(r"(\d+)", k.rsplit("/", 1)[-1]).group(1)))
        return "\n\n".join(f"[Slide {i + 1}]\n" + _texto_generico_xml(entradas[k]) for i, k in enumerate(slides))
    if tipo in (d.ODT, d.ODS) and "content.xml" in entradas:
        return _texto_generico_xml(entradas["content.xml"])
    return "\n".join(_texto_generico_xml(v) for k, v in entradas.items() if k.endswith(".xml"))


# ---------- validação ----------

def _abre(tipo: str, dados: bytes) -> bool:
    try:
        if tipo == d.DOCX:
            import docx

            docx.Document(io.BytesIO(dados))
        elif tipo == d.XLSX:
            import openpyxl

            openpyxl.load_workbook(io.BytesIO(dados), read_only=True).close()
        else:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                if z.testzip() is not None:
                    return False
        return True
    except Exception:
        return False


def _remontar(entradas: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if "mimetype" in entradas:  # ODF exige mimetype primeiro e sem compressão
            z.writestr("mimetype", entradas["mimetype"], compress_type=zipfile.ZIP_STORED)
        for nome, conteudo in entradas.items():
            if nome != "mimetype":
                z.writestr(nome, conteudo)
    return buf.getvalue()


def docx_de_texto(texto: str) -> bytes:
    import docx

    documento = docx.Document()
    for paragrafo in texto.split("\n"):
        documento.add_paragraph(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", paragrafo))
    buf = io.BytesIO()
    documento.save(buf)
    return buf.getvalue()


def _sem_ext(nome: str) -> str:
    return re.sub(r"\.[^.]+$", "", nome)


def restaurar_pacote(dados: bytes, r: Restauracao) -> Restauracao:
    tipo = r.tipo
    ext = d.EXTENSAO.get(tipo, ".zip")

    # 1) Íntegro?
    if _abre(tipo, dados):
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                entradas = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
        except Exception:
            entradas, _ = ler_entradas_locais(dados)
        r.texto = texto_do_pacote(tipo, entradas)
        r.arquivo = (_sem_ext(r.nome) + ext, dados)
        return r

    # 2) Leitura pelos cabeçalhos locais.
    inicio = dados.find(b"PK\x03\x04")
    if inicio > 0:
        r.feito.append(f"{inicio} bytes de lixo antes do início do pacote removidos")
    entradas, avisos = ler_entradas_locais(dados[max(inicio, 0):])
    r.problemas += avisos
    if not entradas:
        r.piorar(IRRECUPERAVEL)
        r.problemas.append("nenhuma parte interna do documento pôde ser lida")
        return r
    r.feito.append(f"índice do pacote ignorado; {len(entradas)} parte(s) internas lidas uma a uma")

    consertados = []
    for nome in list(entradas):
        if nome.endswith((".xml", ".rels")):
            novo, mudou = consertar_xml(entradas[nome])
            if mudou:
                entradas[nome] = novo
                consertados.append(nome)
    if consertados:
        r.feito.append(f"XML cortado/malformado consertado em: {', '.join(consertados[:6])}" + ("..." if len(consertados) > 6 else ""))

    if tipo in CONTENT_TYPES:
        if "[Content_Types].xml" not in entradas:
            entradas["[Content_Types].xml"] = CONTENT_TYPES[tipo].encode()
            r.feito.append("[Content_Types].xml ausente recriado")
        if "_rels/.rels" not in entradas:
            entradas["_rels/.rels"] = RELS[tipo].encode()
            r.feito.append("_rels/.rels ausente recriado")

    texto = texto_do_pacote(tipo, entradas)
    r.texto = texto
    remontado = _remontar(entradas)
    if _abre(tipo, remontado):
        r.arquivo = (_sem_ext(r.nome) + ext, remontado)
        r.piorar(PARCIAL if avisos else RESTAURADO)
        r.feito.append("pacote remontado e validado: o documento volta a abrir")
        return r

    # 3) Último recurso: documento novo só com o texto.
    if texto.strip():
        r.piorar(PARCIAL)
        r.problemas.append("estrutura irrecuperável: formatação perdida, gerado documento novo com o texto")
        if tipo == d.DOCX:
            r.arquivo = (_sem_ext(r.nome) + "_texto_recuperado.docx", docx_de_texto(texto))
        else:
            r.arquivo = (_sem_ext(r.nome) + "_texto_recuperado.txt", texto.encode("utf-8"))
    else:
        r.piorar(IRRECUPERAVEL)
        r.problemas.append("nenhum texto recuperado")
    return r


# ---------- RTF, DOC antigo, HTML ----------

def rtf_para_texto(rtf: str) -> str:
    rtf = re.sub(r"\{\\\*[^{}]*\}", "", rtf)
    rtf = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)(?:[^{}]|\{[^{}]*\})*\}", "", rtf)
    rtf = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252"), rtf)
    rtf = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), rtf)
    rtf = re.sub(r"\\(par|line)\b ?", "\n", rtf)
    rtf = re.sub(r"\\tab\b ?", "\t", rtf)
    rtf = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", rtf)
    rtf = rtf.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    return re.sub(r"[{}]", "", rtf)


def restaurar_rtf(dados: bytes, r: Restauracao) -> Restauracao:
    texto_bruto, _ = tx.decodificar(dados)
    abertas = texto_bruto.count("{") - texto_bruto.count("\\{") - (texto_bruto.count("}") - texto_bruto.count("\\}"))
    if abertas > 0:
        texto_bruto += "}" * abertas
        r.feito.append(f"{abertas} chave(s) de fechamento ausentes adicionadas (arquivo cortado)")
        r.piorar(RESTAURADO)
    r.texto = rtf_para_texto(texto_bruto)
    r.arquivo = (_sem_ext(r.nome) + ".rtf", texto_bruto.encode("cp1252", "replace"))
    r.extras.append((_sem_ext(r.nome) + "_texto.docx", docx_de_texto(tx.restaurar_texto(r.texto)[0])))
    return r


def texto_ole(dados: bytes) -> str:
    """Extrai texto de .doc/.xls antigos (formato OLE) procurando sequências legíveis em UTF-16 e CP1252."""
    utf16 = re.findall(rb"(?:[\x20-\x7e\xa0-\xff]\x00|\r\x00|\n\x00|\t\x00){12,}", dados)
    trechos = [t.decode("utf-16-le", "ignore") for t in utf16]
    if sum(map(len, trechos)) < 200:
        trechos += [t.decode("cp1252", "ignore") for t in re.findall(rb"[\x20-\x7e\xa0-\xff\r\n\t]{20,}", dados)]
    limpos = [t for t in trechos if tx.qualidade_texto(t) > 0.6 and not re.fullmatch(r"[\W\d_ ]+", t)]
    return "\n".join(limpos).replace("\r", "\n")


def restaurar_ole(dados: bytes, r: Restauracao) -> Restauracao:
    try:
        import olefile
    except ImportError:
        olefile = None
    if olefile is not None:
        try:
            olefile.OleFileIO(io.BytesIO(dados)).close()
            r.arquivo = (r.nome, dados)
        except Exception:
            r.problemas.append("estrutura OLE danificada: o arquivo original não abre")
    r.texto = texto_ole(dados)
    if r.arquivo is None:
        r.piorar(PARCIAL if r.texto.strip() else IRRECUPERAVEL)
    if r.texto.strip():
        r.feito.append("texto do documento Word/Excel antigo (.doc/.xls) extraído")
        r.extras.append((_sem_ext(r.nome) + "_texto.docx", docx_de_texto(tx.restaurar_texto(r.texto)[0])))
    return r


def restaurar_html(dados: bytes, r: Restauracao) -> Restauracao:
    import lxml.html

    texto, codificacao = tx.decodificar(dados)
    texto, feito = tx.corrigir_caracteres(texto)
    r.feito += feito
    arvore = lxml.html.fromstring(texto) if texto.strip() else None
    if arvore is None:
        r.piorar(IRRECUPERAVEL)
        return r
    for lixo in arvore.xpath("//script|//style"):
        lixo.drop_tree()
    html_ok = lxml.html.tostring(arvore, encoding="unicode", doctype="<!DOCTYPE html>")
    if "</html>" not in texto.lower():
        r.feito.append("HTML cortado: tags abertas foram fechadas")
        r.piorar(RESTAURADO)
    if feito:
        r.piorar(RESTAURADO)
    r.texto = "\n".join(t.strip() for t in arvore.itertext() if t.strip())
    r.arquivo = (_sem_ext(r.nome) + ".html", html_ok.encode("utf-8"))
    return r
