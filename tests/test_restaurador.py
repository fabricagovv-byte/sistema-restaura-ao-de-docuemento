import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gerar_exemplos as ex  # noqa: E402
from restaurador import busca, executar, gerar_zip  # noqa: E402
from restaurador import deteccao as d  # noqa: E402
from restaurador import imagem as im  # noqa: E402
from restaurador import texto as tx  # noqa: E402
from restaurador.completar import analisar_nome, paginas_faltando  # noqa: E402
from restaurador.modelos import INTEGRO, PARCIAL, RESTAURADO  # noqa: E402


def _um(nome, dados):
    res = executar([(nome, dados)], usar_ocr=False)
    return res, res.restauracoes[0]


def test_detecta_tipo_pelo_conteudo():
    assert d.detectar_tipo(ex.oficio_docx(), "sem_extensao") == d.DOCX
    assert d.detectar_tipo(b"lixo%PDF-1.4 ...", "x.bin") == d.PDF
    assert d.detectar_tipo(ex.digitalizacao_torta(), "x.pdf") == d.JPEG


def test_pdf_cortado_recupera_todas_as_paginas():
    _, r = _um("contrato.pdf", ex.contrato_cortado())
    assert r.status == RESTAURADO
    assert r.paginas == 3
    assert "CLÁUSULA QUARTA" in r.texto
    assert r.arquivo[1].startswith(b"%PDF")


def test_pdf_destruido_resgate_bruto():
    _, r = _um("memorando.pdf", ex.memorando_destruido())
    assert r.status == PARCIAL
    assert "MEMORANDO Nº 45/2026 - SECRETARIA DE ADMINISTRAÇÃO" in r.texto
    assert "material de expediente" in r.texto


def test_docx_sem_indice_volta_a_abrir():
    import docx

    _, r = _um("oficio.docx", ex.oficio_corrompido())
    assert r.status == RESTAURADO
    documento = docx.Document(io.BytesIO(r.arquivo[1]))
    assert any("Contrato nº 12/2026" in p.text for p in documento.paragraphs)


def test_docx_cortado_no_meio_gera_documento():
    dados = ex.oficio_docx()
    _, r = _um("oficio.docx", dados[: int(len(dados) * 0.6)])
    assert r.arquivo is not None
    assert r.status in (RESTAURADO, PARCIAL)


def test_texto_mojibake_e_hifenizacao():
    _, r = _um("ata.txt", ex.ata_mojibake())
    assert "REUNIÃO ORDINÁRIA" in r.texto
    assert "conselheiros" in r.texto and "unanimidade" in r.texto


def test_utf8_cortado_no_meio_de_acento_continua_utf8():
    texto, cod = tx.decodificar("ação".encode("utf-8")[:-2] + b"")
    assert cod == "utf-8"
    assert texto.startswith("a")


def test_costura_de_copias_parciais():
    a, b = ex.parecer_copias()
    res = executar([("parecer.txt", a), ("parecer (copia).txt", b)], usar_ocr=False)
    assert len(res.documentos) == 1
    doc = res.documentos[0]
    assert doc.completo
    assert doc.texto.startswith("PARECER JURÍDICO") and "10 de abril de 2026" in doc.texto
    assert doc.texto.count("Ante o exposto") == 1


def test_partes_unidas_e_parte_faltando():
    res = executar(list(ex.relatorio_partes().items()), usar_ocr=False)
    doc = res.documentos[0]
    assert doc.tipo_juncao == "partes"
    assert any("2 (de 3)" in f for f in doc.faltando)
    assert doc.arquivo[0].endswith("_completo.pdf")
    assert "Parte 2 — NÃO ENCONTRADA" in doc.texto


def test_escava_documentos_de_imagem_de_disco():
    achados = busca.escavar(ex.pendrive_formatado(), "pendrive.img")
    assert [a.tipo for a in achados] == [d.PDF, d.DOCX, d.JPEG]
    res = executar([("pendrive.img", ex.pendrive_formatado())], usar_ocr=False)
    nomes = [r.nome for r in res.restauracoes]
    assert any(n.startswith("memorando_no_46_2026") for n in nomes)
    assert all(r.status in (INTEGRO, RESTAURADO) for r in res.restauracoes)


def test_zip_comum_e_aberto():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pasta/ata.txt", ex.ata_mojibake())
        z.writestr("pasta/oficio.docx", ex.oficio_docx())
    res = executar([("lote.zip", buf.getvalue())], usar_ocr=False)
    assert sorted(r.tipo for r in res.restauracoes) == [d.DOCX, d.TEXTO]


def test_imagem_inclinada_e_endireitada():
    img, _ = im.abrir_imagem(ex.digitalizacao_torta())
    assert abs(im.angulo_inclinacao(im.corrigir_iluminacao(im._cinza(img))) + 4.0) < 0.6


def test_imagem_truncada_e_aproveitada():
    dados = ex.digitalizacao_torta()
    _, r = _um("foto.jpg", dados[: len(dados) // 2])
    assert r.status == PARCIAL
    assert r.extras


def test_nomes_de_partes_e_copias():
    assert analisar_nome("relatorio_parte2de3.pdf") == ("relatorio", 2, 3)
    assert analisar_nome("Relatório Volume 1.pdf")[:2] == ("relatorio", 1)
    assert analisar_nome("parecer (1).txt")[0] == analisar_nome("Cópia de parecer.txt")[0] == "parecer"


def test_paginas_faltando_pela_numeracao():
    texto = "Página 1 de 5\n...\nPágina 2 de 5\n...\nPágina 5 de 5"
    assert paginas_faltando(texto) == ["páginas ausentes pela numeração 'Página X de 5': 3–4"]


def test_pacote_zip_de_saida():
    res = executar([("ata.txt", ex.ata_mojibake())], usar_ocr=False)
    with zipfile.ZipFile(io.BytesIO(gerar_zip(res))) as z:
        nomes = z.namelist()
    assert "RELATORIO.txt" in nomes and "relatorio.xlsx" in nomes
    assert "restaurados/ata.txt" in nomes


def test_arquivo_vazio_nao_quebra():
    with pytest.raises(ValueError):
        executar([], usar_ocr=False)
    _, r = _um("vazio.bin", b"\x00" * 10)
    assert r.status == "irrecuperável"
