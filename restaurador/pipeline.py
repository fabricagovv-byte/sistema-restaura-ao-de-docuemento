"""Orquestração: busca → restaura cada arquivo → completa documentos → relatório e pacote de saída."""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

from . import deteccao as d
from . import imagem as im
from . import office, pdf
from . import texto as tx
from .busca import Encontrado, coletar
from .completar import DocumentoCompleto, agrupar, completar
from .modelos import INTEGRO, IRRECUPERAVEL, PARCIAL, RESTAURADO, Restauracao


@dataclass
class Resultado:
    encontrados: list[Encontrado]
    restauracoes: list[Restauracao]
    documentos: list[DocumentoCompleto]
    avisos: list[str] = field(default_factory=list)

    def resumo(self) -> dict:
        status = Counter(r.status for r in self.restauracoes)
        return {
            "arquivos_encontrados": len(self.encontrados),
            "escavados_de_dados_brutos": sum(1 for e in self.encontrados if e.como == "escavado"),
            "integros": status.get(INTEGRO, 0),
            "restaurados": status.get(RESTAURADO, 0),
            "recuperados_parcialmente": status.get(PARCIAL, 0),
            "irrecuperaveis": status.get(IRRECUPERAVEL, 0),
            "documentos": len(self.documentos),
            "documentos_completos": sum(1 for doc in self.documentos if doc.completo),
            "documentos_com_falta": sum(1 for doc in self.documentos if not doc.completo),
        }


def _sem_ext(nome: str) -> str:
    return re.sub(r"\.[^.]+$", "", nome)


def _restaurar_imagem(dados: bytes, r: Restauracao, usar_ocr: bool) -> Restauracao:
    img, feito = im.abrir_imagem(dados)
    r.feito += [f for f in feito if not f.startswith("imagem truncada")]
    r.problemas += [f for f in feito if f.startswith("imagem truncada")]
    if img is None:
        r.piorar(IRRECUPERAVEL)
        r.problemas += feito
        return r
    if any(f.startswith("imagem truncada") for f in feito):
        r.piorar(PARCIAL)
    elif feito:
        r.piorar(RESTAURADO)
    r.arquivo = (_sem_ext(r.nome) + ".png", im.imagem_para_bytes(img.convert("RGB")))
    limpa, passos = im.restaurar_pagina(img)
    r.extras.append((_sem_ext(r.nome) + "_restaurada.png", im.imagem_para_bytes(limpa)))
    r.feito += passos
    if r.status == INTEGRO:
        r.status = RESTAURADO
    if usar_ocr and im.ocr_disponivel():
        r.texto = im.ocr(limpa)
        r.feito.append("texto reconhecido por OCR")
    elif usar_ocr:
        r.problemas.append("OCR indisponível: instale o Tesseract (tesseract-ocr-por) para extrair o texto")
    return r


def _restaurar_texto_puro(dados: bytes, r: Restauracao) -> Restauracao:
    texto, codificacao = tx.decodificar(dados)
    corrigido, feito = tx.corrigir_caracteres(texto)
    if codificacao not in ("utf-8", "ascii"):
        feito.insert(0, f"codificação {codificacao} convertida para UTF-8")
    if feito:
        r.feito += feito
        r.piorar(RESTAURADO)
    if "\x00" in texto or "�" in texto:
        r.problemas.append("havia bytes ilegíveis no meio do texto (marcados com �)")
        r.piorar(PARCIAL)
    r.texto = corrigido
    ext = Path(r.nome).suffix.lower() if Path(r.nome).suffix.lower() in (".txt", ".csv", ".md", ".xml", ".json") else ".txt"
    r.arquivo = (_sem_ext(r.nome) + ext, corrigido.encode("utf-8"))
    return r


def _restaurar_desconhecido(dados: bytes, r: Restauracao) -> Restauracao:
    trechos = [t.decode("cp1252", "ignore") for t in re.findall(rb"[\x20-\x7e\xa0-\xff\r\n\t]{20,}", dados)]
    trechos += [t.decode("utf-16-le", "ignore") for t in re.findall(rb"(?:[\x20-\x7e\xa0-\xff]\x00){20,}", dados)]
    legiveis = [t for t in trechos if tx.qualidade_texto(t) > 0.7]
    if not legiveis:
        r.piorar(IRRECUPERAVEL)
        r.problemas.append("formato não reconhecido e nenhum texto legível encontrado")
        return r
    r.texto = "\n".join(legiveis)
    r.piorar(PARCIAL)
    r.problemas.append("formato não reconhecido: apenas os trechos de texto legíveis foram salvos")
    r.arquivo = (_sem_ext(r.nome) + "_texto_legivel.txt", r.texto.encode("utf-8"))
    return r


def _nome_pelo_conteudo(texto: str, encontrado: Encontrado) -> str:
    """Arquivos escavados não têm nome: usa o título (primeira linha com conteúdo) do próprio texto."""
    import unicodedata

    for linha in texto.splitlines():
        linha = re.sub(r"^\[(Página|Bloco) \d+\]$", "", linha.strip())
        if len(re.findall(r"[A-Za-zÀ-ÿ]", linha)) >= 4:
            base = unicodedata.normalize("NFKD", linha).encode("ascii", "ignore").decode().lower()
            base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")[:60].rstrip("_")
            return f"{base}__recuperado_de_{Path(encontrado.origem).stem}{Path(encontrado.nome).suffix}"
    return encontrado.nome


def restaurar(encontrado: Encontrado, usar_ocr: bool = True) -> Restauracao:
    r = Restauracao(encontrado.nome, encontrado.origem, encontrado.tipo, como_encontrado=encontrado.como)
    r.problemas += encontrado.observacoes
    tipo = encontrado.tipo
    dados = encontrado.dados
    try:
        if tipo == d.PDF:
            pdf.restaurar_pdf(dados, r, usar_ocr)
        elif tipo in d.OFFICE_ZIP or tipo == d.ZIP:
            office.restaurar_pacote(dados, r)
        elif tipo == d.DOC_OLE:
            office.restaurar_ole(dados, r)
        elif tipo == d.RTF:
            office.restaurar_rtf(dados, r)
        elif tipo == d.HTML:
            office.restaurar_html(dados, r)
        elif tipo in d.IMAGENS:
            _restaurar_imagem(dados, r, usar_ocr)
        elif tipo == d.TEXTO:
            _restaurar_texto_puro(dados, r)
        else:
            _restaurar_desconhecido(dados, r)
    except Exception as erro:  # nenhum arquivo derruba o processamento dos demais
        r.problemas.append(f"erro inesperado: {type(erro).__name__}: {erro}")
        if r.arquivo is None:
            _restaurar_desconhecido(dados, r)

    if r.texto:
        r.texto, passos = tx.restaurar_texto(r.texto)
        r.feito += [f"texto: {p}" for p in passos if p not in r.feito]
    r.qualidade = tx.qualidade_texto(r.texto)
    if r.texto and r.qualidade < 0.75:
        r.problemas.append(f"texto com muitos caracteres estranhos (qualidade {r.qualidade:.0%}): revise ou use a IA")
    if encontrado.como == "escavado" and r.texto.strip():
        r.nome = _nome_pelo_conteudo(r.texto, encontrado)
        if r.arquivo:
            r.arquivo = (_sem_ext(r.nome) + Path(r.arquivo[0]).suffix, r.arquivo[1])
    for onde in encontrado.copias_identicas:
        r.feito.append(f"cópia idêntica também encontrada em '{onde}'")
    if encontrado.como == "escavado":
        r.feito.insert(0, f"encontrado dentro de '{Path(encontrado.origem).name}' na posição {encontrado.deslocamento}")
    return r


def executar(
    entradas: list,
    usar_ocr: bool = True,
    usar_ia: bool = False,
    progresso: Callable[[str], None] | None = None,
) -> Resultado:
    log = progresso or (lambda _m: None)
    log("🔎 Buscando documentos (pastas, ZIPs e dados brutos)...")
    encontrados = coletar(entradas)
    if not encontrados:
        raise ValueError("Nenhum arquivo encontrado nas entradas.")
    escavados = sum(1 for e in encontrados if e.como == "escavado")
    log(f"   {len(encontrados)} arquivo(s) encontrado(s)" + (f", {escavados} escavado(s) de dados brutos" if escavados else ""))

    restauracoes = []
    for e in encontrados:
        log(f"🛠️ Restaurando {e.nome} ({e.tipo})...")
        restauracoes.append(restaurar(e, usar_ocr))

    avisos: list[str] = []
    if usar_ia:
        from . import ia

        if not ia.ia_disponivel():
            avisos.append("IA pedida, mas ANTHROPIC_API_KEY não está configurada: revisão por IA ignorada")
        else:
            for r in restauracoes:
                precisa = r.texto.strip() and (r.qualidade < 0.9 or any("OCR" in f for f in r.feito))
                if not precisa:
                    continue
                log(f"🤖 Revisando texto de {r.nome} com IA...")
                try:
                    revisado = ia.revisar_texto(r.nome, r.texto)
                except Exception as erro:
                    r.problemas.append(f"revisão por IA falhou: {erro}")
                    continue
                r.extras.append((_sem_ext(r.nome) + "_texto_revisado_ia.txt", revisado.encode("utf-8")))
                r.feito.append("texto revisado pela IA (erros de leitura corrigidos; original mantido ao lado)")

    log("🧩 Juntando partes e cópias de cada documento...")
    documentos = [completar(g) for g in agrupar(restauracoes)]
    documentos.sort(key=lambda doc: doc.nome.lower())
    log("✅ Concluído")
    return Resultado(encontrados, restauracoes, documentos, avisos)


# ---------- saídas ----------

def _tabelas(res: Resultado) -> dict[str, pd.DataFrame]:
    arquivos = pd.DataFrame([
        {
            "arquivo": r.nome,
            "origem": r.origem,
            "como foi encontrado": r.como_encontrado,
            "tipo": r.tipo,
            "situação": r.status,
            "páginas": r.paginas,
            "páginas declaradas": r.paginas_esperadas,
            "qualidade do texto": r.qualidade,
            "caracteres de texto": len(r.texto),
            "o que foi feito": "\n".join(r.feito),
            "problemas / o que não deu": "\n".join(r.problemas),
            "arquivo restaurado": r.arquivo[0] if r.arquivo else "",
        }
        for r in res.restauracoes
    ])
    docs = pd.DataFrame([
        {
            "documento": doc.nome,
            "junção": doc.tipo_juncao,
            "arquivos": "\n".join(m.nome for m in doc.membros),
            "completo?": "SIM" if doc.completo else "NÃO",
            "o que falta": "\n".join(doc.faltando),
            "observações": "\n".join(doc.observacoes),
            "arquivo final": doc.arquivo[0] if doc.arquivo else "",
        }
        for doc in res.documentos
    ])
    faltas = pd.DataFrame(
        [{"documento": doc.nome, "falta": f} for doc in res.documentos for f in doc.faltando]
        + [{"documento": r.nome, "falta": p} for r in res.restauracoes for p in r.problemas],
        columns=["documento", "falta"],
    )
    resumo = pd.DataFrame(list(res.resumo().items()), columns=["indicador", "valor"])
    return {"Resumo": resumo, "Arquivos": arquivos, "Documentos": docs, "O que falta": faltas}


def gerar_excel(res: Resultado) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as escritor:
        for nome, df in _tabelas(res).items():
            df.to_excel(escritor, sheet_name=nome, index=False)
            planilha = escritor.sheets[nome]
            for coluna in planilha.columns:
                largura = max((len(str(c.value or "").split("\n")[0]) for c in coluna), default=10)
                planilha.column_dimensions[coluna[0].column_letter].width = min(max(largura + 2, 12), 70)
    return buf.getvalue()


def relatorio_texto(res: Resultado) -> str:
    linhas = ["RELATÓRIO DE BUSCA E RESTAURAÇÃO DE DOCUMENTOS", "=" * 48, ""]
    for k, v in res.resumo().items():
        linhas.append(f"{k.replace('_', ' ')}: {v}")
    for aviso in res.avisos:
        linhas.append(f"AVISO: {aviso}")
    linhas += ["", "DOCUMENTOS", "-" * 48]
    for doc in res.documentos:
        linhas.append(f"\n■ {doc.nome}  [{doc.tipo_juncao}]  {'COMPLETO' if doc.completo else 'INCOMPLETO'}")
        if doc.arquivo:
            linhas.append(f"  arquivo final: {doc.arquivo[0]}")
        for m in doc.membros:
            linhas.append(f"  - {m.nome}: {m.status}")
            for f in m.feito:
                linhas.append(f"      ✔ {f}")
            for p in m.problemas:
                linhas.append(f"      ✖ {p}")
        for o in doc.observacoes:
            linhas.append(f"  • {o}")
        for f in doc.faltando:
            linhas.append(f"  ⚠ FALTA: {f}")
    return "\n".join(linhas) + "\n"


def _arquivos_saida(res: Resultado) -> list[tuple[str, bytes]]:
    usados: set[str] = set()

    def unico(caminho: str) -> str:
        base, ext = re.match(r"(.*?)(\.[^./]*)?$", caminho).groups()
        ext = ext or ""
        candidato, n = caminho, 2
        while candidato in usados:
            candidato = f"{base}_{n}{ext}"
            n += 1
        usados.add(candidato)
        return candidato

    saida = []
    for r in res.restauracoes:
        if r.arquivo:
            saida.append((unico(f"restaurados/{r.arquivo[0]}"), r.arquivo[1]))
        for nome, dados in r.extras:
            saida.append((unico(f"extras/{nome}"), dados))
        if r.texto.strip():
            saida.append((unico(f"texto/{_sem_ext(r.nome)}.txt"), r.texto.encode("utf-8")))
    for doc in res.documentos:
        if len(doc.membros) > 1:
            if doc.arquivo:
                saida.append((unico(f"completos/{doc.arquivo[0]}"), doc.arquivo[1]))
            if doc.texto.strip():
                saida.append((unico(f"completos/{doc.nome}_texto_completo.txt"), doc.texto.encode("utf-8")))
    saida.append(("RELATORIO.txt", relatorio_texto(res).encode("utf-8")))
    saida.append(("relatorio.xlsx", gerar_excel(res)))
    return saida


def gerar_zip(res: Resultado) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in _arquivos_saida(res):
            z.writestr(nome, dados)
    return buf.getvalue()


def salvar(res: Resultado, pasta: str | Path) -> Path:
    pasta = Path(pasta)
    for nome, dados in _arquivos_saida(res):
        destino = pasta / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
    return pasta
