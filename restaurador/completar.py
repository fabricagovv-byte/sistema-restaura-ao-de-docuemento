"""Completar documentos: junta partes, combina cópias danificadas e aponta o que ainda falta.

- Partes: "relatorio_parte1.pdf" + "relatorio_parte2.pdf", "volume 2", "_p3", "2de5"... são
  ordenadas e unidas num só arquivo.
- Versões/cópias: o mesmo documento em vários arquivos (backup, "cópia", "(1)", escavado de um
  disco, versão anterior). Cada cópia pode ter perdido um pedaço diferente; os textos são
  costurados pela sobreposição para reconstruir o documento inteiro, e a melhor cópia é escolhida.
- Faltas: partes que não apareceram (tem a 1 e a 3, falta a 2), "Página X de Y" e folhas
  (fls.) puladas.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field

from . import texto as tx
from .modelos import ORDEM_STATUS, Restauracao

_PARTE = re.compile(
    r"(?:[_\-\s.]|^)(?:parte|part|pt|vol(?:ume)?|p|anexo|cap(?:itulo)?)[_\-\s.]*(\d{1,3})(?:\s*de\s*(\d{1,3}))?(?=$|[_\-\s.])"
    r"|(?:[_\-\s.])(\d{1,3})\s*de\s*(\d{1,3})(?=$|[_\-\s.])",
    re.I,
)
_RUIDO = re.compile(
    r"(\(\d+\)|\bc[oó]pia(?: de)?\b|\bcopy( of)?\b|\bbackup\b|\bbak\b|\bold\b|\bantigo\b|\bfinal\b|\brestaurado\b"
    r"|\bv\d+\b|\bversao\s*\d+\b|_escavado_\d+_off\d+|~\$|\brecuperado\b|\bcorrompido\b|\bdanificado\b)",
    re.I,
)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def analisar_nome(nome: str) -> tuple[str, int | None, int | None]:
    """Devolve (chave do documento, número da parte, total de partes)."""
    base = _sem_acento(re.sub(r"\.[A-Za-z0-9]{2,5}$", "", nome)).lower()
    parte = total = None
    m = None
    for m in _PARTE.finditer(base):
        pass  # usa a última ocorrência ("contrato 12 parte 2")
    if m:
        parte = int(m.group(1) or m.group(3))
        total = int(m.group(2) or m.group(4)) if (m.group(2) or m.group(4)) else None
        base = base[: m.start()] + base[m.end():]
    base = _RUIDO.sub(" ", base)
    chave = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return chave, parte, total


def _shingles(texto: str, n: int = 6) -> set[int]:
    palavras = re.findall(r"\w+", texto.lower())
    return {hash(" ".join(palavras[i:i + n])) for i in range(max(len(palavras) - n + 1, 0))}


def _sobreposicao(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass
class DocumentoCompleto:
    nome: str
    membros: list[Restauracao]
    tipo_juncao: str  # único | partes | versões | partes e versões
    arquivo: tuple[str, bytes] | None = None
    texto: str = ""
    faltando: list[str] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return not self.faltando and all(m.status != "irrecuperável" for m in self.membros)


def _melhor(versoes: list[Restauracao]) -> Restauracao:
    return min(versoes, key=lambda r: (ORDEM_STATUS[r.status], -(r.paginas or 0), -len(r.texto), -r.qualidade))


def paginas_faltando(texto: str) -> list[str]:
    """Procura numeração 'Página X de Y' / 'fls. N' e aponta as que não aparecem."""
    faltas: list[str] = []
    pags = [(int(a), int(b)) for a, b in re.findall(r"p[áa]g(?:ina)?\.?\s*(\d{1,4})\s*(?:de|/)\s*(\d{1,4})", texto, re.I)]
    if pags:
        total = max(b for _, b in pags)
        vistas = {a for a, _ in pags}
        ausentes = sorted(set(range(1, total + 1)) - vistas)
        if ausentes and len(vistas) >= 2:
            faltas.append(f"páginas ausentes pela numeração 'Página X de {total}': {_faixas(ausentes)}")
    folhas = sorted({int(n) for n in re.findall(r"\bfls?\.?\s*(\d{1,5})\b", texto, re.I)})
    if len(folhas) >= 3:
        ausentes = sorted(set(range(folhas[0], folhas[-1] + 1)) - set(folhas))
        if ausentes and len(ausentes) <= (folhas[-1] - folhas[0]) // 2:
            faltas.append(f"folhas (fls.) puladas: {_faixas(ausentes)}")
    return faltas


def _faixas(nums: list[int]) -> str:
    faixas, inicio, ant = [], None, None
    for n in nums + [None]:
        if inicio is None:
            inicio = ant = n
        elif n is not None and n == ant + 1:
            ant = n
        else:
            faixas.append(str(inicio) if inicio == ant else f"{inicio}–{ant}")
            inicio = ant = n
    return ", ".join(faixas[:30]) + ("..." if len(faixas) > 30 else "")


def _juntar_pdfs(pdfs: list[bytes]) -> bytes | None:
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    try:
        for p in pdfs:
            for pagina in PdfReader(io.BytesIO(p), strict=False).pages:
                escritor.add_page(pagina)
        buf = io.BytesIO()
        escritor.write(buf)
        return buf.getvalue()
    except Exception:
        return None


def agrupar(restauracoes: list[Restauracao], limiar_conteudo: float = 0.6) -> list[list[Restauracao]]:
    """Agrupa por nome (mesma chave) e por conteúdo (cópias com texto muito parecido)."""
    pai = list(range(len(restauracoes)))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    def unir(a, b):
        pai[raiz(a)] = raiz(b)

    # Arquivos escavados têm nome artificial: só se agrupam pelo conteúdo.
    chaves = ["" if r.como_encontrado == "escavado" else analisar_nome(r.nome)[0] for r in restauracoes]
    por_chave: dict[str, int] = {}
    for i, c in enumerate(chaves):
        if c in por_chave and c:
            unir(i, por_chave[c])
        por_chave.setdefault(c, i)

    sh = [_shingles(r.texto) for r in restauracoes]
    for i in range(len(restauracoes)):
        for j in range(i + 1, len(restauracoes)):
            if raiz(i) != raiz(j) and len(sh[i]) >= 5 and len(sh[j]) >= 5 and _sobreposicao(sh[i], sh[j]) >= limiar_conteudo:
                unir(i, j)

    grupos: dict[int, list[Restauracao]] = {}
    for i, r in enumerate(restauracoes):
        grupos.setdefault(raiz(i), []).append(r)
    return list(grupos.values())


def completar(grupo: list[Restauracao]) -> DocumentoCompleto:
    nomes = [analisar_nome(r.nome) for r in grupo]
    # Nome do documento: o mais "limpo" entre os membros que não foram escavados.
    candidatos = [r.nome for r in grupo if r.como_encontrado != "escavado"] or [grupo[0].nome]
    nome_doc = min(candidatos, key=len)
    chave_nome, _, _ = analisar_nome(nome_doc)

    partes: dict[int, list[Restauracao]] = {}
    sem_parte: list[Restauracao] = []
    totais = set()
    for r, (_, parte, total) in zip(grupo, nomes):
        if total:
            totais.add(total)
        if parte is None:
            sem_parte.append(r)
        else:
            partes.setdefault(parte, []).append(r)

    if len(grupo) == 1:
        r = grupo[0]
        doc = DocumentoCompleto(r.nome, grupo, "único", r.arquivo, r.texto)
        doc.faltando += paginas_faltando(r.texto)
        if r.paginas_esperadas and r.paginas is not None and r.paginas < r.paginas_esperadas:
            doc.faltando.append(f"{r.paginas_esperadas - r.paginas} página(s) não recuperada(s) do arquivo")
        _, parte, total = nomes[0]
        if parte is not None and (total or 0) > 1:
            doc.faltando.append(f"só a parte {parte} de {total} foi encontrada")
        return doc

    doc = DocumentoCompleto(chave_nome or nome_doc, grupo, "versões")

    if partes:
        doc.tipo_juncao = "partes e versões" if any(len(v) > 1 for v in partes.values()) else "partes"
        # Versões sem número de parte entram como cópia da parte que mais se parece com elas.
        for r in sem_parte:
            alvo = max(partes, key=lambda k: _sobreposicao(_shingles(r.texto), _shingles(_melhor(partes[k]).texto)))
            if _sobreposicao(_shingles(r.texto), _shingles(_melhor(partes[alvo]).texto)) >= 0.5:
                partes[alvo].append(r)
            else:
                doc.observacoes.append(f"'{r.nome}' parece ser o documento inteiro ou outra parte sem número")
        ordem = sorted(partes)
        total = max(totais) if totais else ordem[-1]
        ausentes = sorted(set(range(1, total + 1)) - set(ordem))
        if ausentes:
            doc.faltando.append(f"parte(s) não encontrada(s): {_faixas(ausentes)} (de {total})")
        escolhidas = []
        textos = []
        for k in sorted(set(ordem) | set(ausentes)):
            if k not in partes:
                textos.append(f"===== Parte {k} — NÃO ENCONTRADA =====")
                continue
            versoes = partes[k]
            melhor = _melhor(versoes)
            escolhidas.append(melhor)
            texto_parte = tx.costurar_fragmentos([v.texto for v in versoes]) if len(versoes) > 1 else melhor.texto
            textos.append(f"===== Parte {k} =====\n{texto_parte}")
            if len(versoes) > 1:
                doc.observacoes.append(f"parte {k}: {len(versoes)} cópias combinadas; melhor arquivo: {melhor.nome}")
        doc.texto = "\n\n".join(textos)
        arquivos = [e.arquivo for e in escolhidas if e.arquivo]
        if arquivos and all(a[0].lower().endswith(".pdf") for a in arquivos):
            unido = _juntar_pdfs([a[1] for a in arquivos])
            if unido:
                doc.arquivo = (f"{chave_nome or 'documento'}_completo.pdf", unido)
                doc.observacoes.append(f"{len(arquivos)} partes unidas num único PDF, na ordem")
        if doc.arquivo is None:
            from .office import docx_de_texto

            doc.arquivo = (f"{chave_nome or 'documento'}_completo.docx", docx_de_texto(doc.texto))
    else:
        # Só cópias do mesmo documento.
        versoes = sem_parte + [r for v in partes.values() for r in v]
        melhor = _melhor(versoes)
        combinado = tx.costurar_fragmentos([v.texto for v in versoes])
        doc.texto = combinado
        if melhor.arquivo:
            ext = re.search(r"(\.[^.]+)?$", melhor.arquivo[0]).group()
            doc.arquivo = (f"{chave_nome or 'documento'}{ext}", melhor.arquivo[1])
        doc.observacoes.append(f"{len(versoes)} cópias do mesmo documento; melhor arquivo: {melhor.nome}")
        if len(combinado.strip()) > len(melhor.texto.strip()) * 1.05:
            from .office import docx_de_texto

            doc.observacoes.append(
                "nenhuma cópia estava inteira: o texto completo foi reconstruído juntando os trechos de cada cópia"
            )
            doc.arquivo = (f"{chave_nome or 'documento'}_texto_completo_reconstruido.docx", docx_de_texto(combinado))
    doc.faltando += paginas_faltando(doc.texto)
    if "[--- trecho sem ligação" in doc.texto:
        doc.faltando.append("há trechos que não se encaixam: pode faltar o pedaço que os liga")
    return doc
