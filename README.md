# 🩹 Sistema de Busca e Restauração de Documentos

Você entrega arquivos danificados, pastas, ZIPs ou até a **imagem de um pendrive/HD formatado**, e o sistema:

1. **Busca** todos os documentos: percorre pastas, abre ZIPs e **escava dados brutos** (imagens de disco `.img/.dd/.bin`, arquivos `.CHK` do CHKDSK, `.bak`, arquivos sem extensão) atrás das assinaturas de PDF, DOCX/XLSX/PPTX/ODT, RTF, DOC/XLS antigos, JPEG e PNG. Documentos "apagados" ou de um pendrive formatado continuam lá e são extraídos. O tipo é identificado **pelo conteúdo**, não pela extensão. Os arquivos escavados recebem nome a partir do próprio título (`memorando_no_46_2026__recuperado_de_pendrive.pdf`).
2. **Restaura** cada arquivo:
   | Tipo | O que é consertado |
   |---|---|
   | **PDF** | lixo antes do cabeçalho, download interrompido (sem xref/trailer/%%EOF), tabela xref e árvore de páginas reconstruídas (qpdf). Se a estrutura estiver destruída, faz o **resgate bruto**: descomprime cada fluxo interno (mesmo cortado), extrai o texto e as imagens e monta um PDF novo. Avisa quando o PDF declara mais páginas do que foi possível recuperar. |
   | **DOCX / XLSX / PPTX / ODT / ODS** | ZIP com índice (diretório central) perdido, partes cortadas (descompressão até o ponto do dano), XML malformado/cortado (fecha as tags), `[Content_Types].xml` e `_rels/.rels` recriados. Confere se o resultado **abre de verdade**; se não abrir, gera um documento novo com o texto. |
   | **Fotos e digitalizações** | imagem truncada aproveitada, orientação EXIF, bordas pretas do scanner, **inclinação (deskew)**, sombras/manchas/amarelado, granulado, texto desbotado. OCR em português (Tesseract) quando instalado. Páginas digitalizadas dentro de PDFs recebem o mesmo tratamento. |
   | **TXT / CSV / HTML / RTF** | codificação errada (Latin-1, CP1252, UTF-16 → UTF-8), **acentos corrompidos** (`Ã§Ã£o` → `ção`), caracteres de controle, HTML e RTF cortados (tags e chaves fechadas). |
   | **DOC / XLS antigos (OLE)** | extração do texto mesmo com a estrutura danificada. |
   | **Desconhecido** | salva os trechos de texto legíveis. |

   Em todo texto recuperado: palavras hifenizadas na quebra de linha são reunidas e linhas partidas no meio da frase viram parágrafos.
3. **Completa** os documentos:
   - **Partes** (`_parte1`, `parte 2 de 3`, `volume 2`, `_p3`...) são ordenadas e **unidas num só arquivo**, apontando a parte que falta.
   - **Cópias danificadas** do mesmo documento (backup, "cópia", "(1)", escavada de um disco, mesmo texto com outro nome) são combinadas: o texto de cada cópia é **costurado pela sobreposição**, reconstruindo o documento inteiro mesmo quando nenhuma cópia estava completa; e a melhor cópia é escolhida.
   - **O que falta**: partes ausentes, páginas puladas pela numeração "Página X de Y", folhas (`fls.`) faltando e trechos que não se encaixam.
4. **(Opcional) IA**: com `--ia`, o Claude revisa textos de OCR/danificados corrigindo **só erros evidentes de leitura** — não inventa nem completa conteúdo, marca `[ilegível]` onde não dá para ler, e o texto original fica salvo ao lado.

Cada arquivo recebe uma situação: **íntegro**, **restaurado**, **recuperado parcialmente** ou **irrecuperável**, com a lista do que foi feito e do que não foi possível.

## Como usar

```bash
pip install -r requirements.txt
# OCR (opcional, para fotos e digitalizações):  sudo apt install tesseract-ocr tesseract-ocr-por

# Interface web
streamlit run app.py

# Linha de comando
python -m restaurador ARQUIVOS_OU_PASTAS... -o resultado_restauracao --zip
```

| Opção | O que faz |
|---|---|
| `-o pasta` | pasta de saída (padrão `resultado_restauracao`) |
| `--zip` | também gera `pasta.zip` |
| `--sem-ocr` | não faz OCR |
| `--ia` | revisa textos danificados com o Claude (requer `ANTHROPIC_API_KEY`; modelo padrão `claude-opus-5-5`, troque com `RESTAURADOR_MODELO`) |

### Teste com exemplos danificados

```bash
python gerar_exemplos.py          # cria exemplos/ com PDF cortado, PDF destruído, DOCX corrompido,
                                  # texto com acentos quebrados, foto torta, cópias parciais,
                                  # relatório com parte faltando e imagem de pendrive formatado
python -m restaurador exemplos -o saida
python -m pytest -q
```

## Saída

```
saida/
  restaurados/   cada arquivo consertado (no formato original sempre que possível)
  completos/     documentos montados a partir de partes/cópias + texto completo
  texto/         texto recuperado de cada arquivo (UTF-8)
  extras/        páginas/fotos restauradas, texto revisado pela IA, versões DOCX de RTF/DOC
  RELATORIO.txt  o que foi feito e o que falta, documento por documento
  relatorio.xlsx abas Resumo, Arquivos, Documentos e O que falta
```

## Limites honestos

- O que **não está** em nenhum arquivo não pode ser recuperado: páginas que nunca foram gravadas, a parte inferior de uma imagem truncada, a parte de um ZIP sobrescrita no disco. O sistema **aponta** essas faltas em vez de inventar.
- Escavar um disco funciona quando os arquivos estão em blocos contíguos (o caso mais comum em pendrives e cartões). Arquivos fragmentados saem parciais.
- No resgate bruto de PDF, a formatação original se perde (fica o texto e as imagens). Fontes com codificação própria (CID) podem gerar texto ilegível nesse modo.
- Sem o Tesseract, fotos e digitalizações são limpas, mas o texto delas não é extraído.

## Estrutura

```
restaurador/
  deteccao.py   tipo real do arquivo pela assinatura
  busca.py      varredura de pastas/ZIPs e escavação (file carving) de dados brutos
  pdf.py        reparo estrutural, leitura tolerante e resgate bruto de PDF
  office.py     DOCX/XLSX/PPTX/ODT (ZIP + XML), RTF, DOC antigo, HTML
  imagem.py     deskew, iluminação, ruído, contraste, OCR
  texto.py      codificação, mojibake, hifenização, linhas partidas, costura de fragmentos
  completar.py  partes, cópias, páginas e partes faltando
  ia.py         revisão opcional com o Claude
  pipeline.py   orquestração, relatório (TXT/Excel) e pacote ZIP
app.py          interface web (Streamlit)
gerar_exemplos.py  gera documentos fictícios danificados
tests/          testes (python -m pytest)
```
