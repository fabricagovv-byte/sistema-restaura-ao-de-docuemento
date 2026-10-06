"""Interface web: suba os arquivos danificados e baixe tudo restaurado.

Executar:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from restaurador import executar, gerar_excel, gerar_zip
from restaurador.ia import ia_disponivel
from restaurador.imagem import ocr_disponivel

st.set_page_config(page_title="Restauração de Documentos", page_icon="🩹", layout="wide")
st.title("🩹 Busca e Restauração de Documentos")
st.caption(
    "Suba documentos danificados (PDF, Word, Excel, RTF, TXT, HTML, fotos e digitalizações), pastas compactadas "
    "em ZIP ou imagens de disco/pendrive (.img, .dd, .bin, .chk). O sistema procura os documentos, conserta o que "
    "estiver quebrado, junta partes e cópias e mostra o que ainda falta."
)

with st.sidebar:
    st.header("Configurações")
    usar_ocr = st.toggle(
        "OCR em páginas digitalizadas", value=ocr_disponivel(), disabled=not ocr_disponivel(),
        help="Requer o Tesseract instalado (pacote tesseract-ocr-por).",
    )
    if not ocr_disponivel():
        st.info("OCR desativado: instale o Tesseract para ler texto de fotos e digitalizações.")
    tem_ia = ia_disponivel()
    usar_ia = st.toggle(
        "Revisar textos danificados com IA (Claude)", value=False, disabled=not tem_ia,
        help="Corrige erros de leitura do OCR sem inventar conteúdo. Requer ANTHROPIC_API_KEY.",
    )
    if not tem_ia:
        st.info("IA desativada: defina ANTHROPIC_API_KEY para habilitar.")

arquivos = st.file_uploader("Arquivos (qualquer formato)", accept_multiple_files=True)

if arquivos and st.button("▶️ Buscar e restaurar", type="primary"):
    with st.status("Trabalhando...", expanded=True) as status:
        try:
            resultado = executar(
                [(a.name, a.getvalue()) for a in arquivos], usar_ocr=usar_ocr, usar_ia=usar_ia, progresso=st.write
            )
        except ValueError as erro:
            status.update(label=str(erro), state="error")
            st.stop()
        status.update(label="Concluído", state="complete", expanded=False)
    st.session_state["resultado"] = resultado

res = st.session_state.get("resultado")
if res:
    resumo = res.resumo()
    c = st.columns(6)
    c[0].metric("Arquivos encontrados", resumo["arquivos_encontrados"])
    c[1].metric("Escavados de dados brutos", resumo["escavados_de_dados_brutos"])
    c[2].metric("Íntegros", resumo["integros"])
    c[3].metric("Restaurados", resumo["restaurados"])
    c[4].metric("Parciais", resumo["recuperados_parcialmente"])
    c[5].metric("Irrecuperáveis", resumo["irrecuperaveis"])
    for aviso in res.avisos:
        st.warning(aviso)

    b1, b2 = st.columns(2)
    b1.download_button("⬇️ Baixar tudo restaurado (ZIP)", data=gerar_zip(res), file_name="documentos_restaurados.zip",
                       type="primary")
    b2.download_button("⬇️ Baixar relatório (Excel)", data=gerar_excel(res), file_name="relatorio_restauracao.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    aba_docs, aba_arqs, aba_falta = st.tabs(["📚 Documentos", "🗂️ Arquivos", "⚠️ O que falta"])
    with aba_docs:
        for doc in res.documentos:
            icone = "✅" if doc.completo else "⚠️"
            with st.expander(f"{icone} {doc.nome} — {doc.tipo_juncao} ({len(doc.membros)} arquivo(s))"):
                for o in doc.observacoes:
                    st.write(f"• {o}")
                for f in doc.faltando:
                    st.error(f"Falta: {f}")
                if doc.arquivo:
                    st.download_button(f"Baixar {doc.arquivo[0]}", data=doc.arquivo[1], file_name=doc.arquivo[0],
                                       key=f"doc-{id(doc)}")
                if doc.texto.strip():
                    st.text_area("Texto recuperado", doc.texto, height=250, key=f"txt-{id(doc)}")
    with aba_arqs:
        for r in res.restauracoes:
            with st.expander(f"{r.nome} — {r.status}"):
                st.caption(f"Origem: {r.origem} · tipo: {r.tipo} · encontrado como: {r.como_encontrado}")
                for f in r.feito:
                    st.write(f"✔️ {f}")
                for p in r.problemas:
                    st.write(f"✖️ {p}")
                for nome, dados in r.extras:
                    if nome.endswith(".png"):
                        st.image(dados, caption=nome)
                    st.download_button(f"Baixar {nome}", data=dados, file_name=nome, key=f"x-{id(r)}-{nome}")
    with aba_falta:
        faltas = [{"documento": d.nome, "falta": f} for d in res.documentos for f in d.faltando]
        st.dataframe(pd.DataFrame(faltas, columns=["documento", "falta"]), use_container_width=True)
