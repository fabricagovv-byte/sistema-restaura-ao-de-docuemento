"""Camada opcional de IA (Claude) para revisar texto danificado (OCR ruim, trechos corrompidos).

Só é usada quando há credencial da Anthropic configurada (ex.: ANTHROPIC_API_KEY).
Regra central: a IA NÃO inventa conteúdo. Ela só corrige erros evidentes de leitura
(letras trocadas pelo OCR, palavras partidas, acentos perdidos) e marca o que está ilegível.
O texto original continua salvo ao lado do revisado, para conferência.
"""

from __future__ import annotations

import os

MODELO = os.environ.get("RESTAURADOR_MODELO", "claude-opus-5-5")
TAMANHO_BLOCO = 60_000  # caracteres por chamada

SISTEMA = (
    "Você revisa textos de documentos brasileiros recuperados de arquivos danificados ou digitalizados (OCR). "
    "Responda sempre em português do Brasil."
)

INSTRUCOES = (
    "Revise o trecho abaixo, extraído de um documento danificado/digitalizado.\n"
    "Corrija SOMENTE erros evidentes de leitura: letras trocadas pelo OCR (ex.: 'rn'→'m', '0'→'o' dentro de "
    "palavras, 'l'→'1' em números), palavras partidas ou grudadas, acentos e cedilhas perdidos ou corrompidos, "
    "quebras de linha no meio da frase.\n"
    "NÃO invente, resuma, complete nem reescreva conteúdo. Nomes, números, valores, datas e CPFs/CNPJs só "
    "mudam se o erro for inequívoco. Onde o texto estiver ilegível, escreva [ilegível] em vez de adivinhar.\n"
    "Mantenha a ordem, os títulos, as listas e as tabelas. Devolva apenas o texto revisado, sem comentários."
)


def ia_disponivel() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))


def _blocos(texto: str) -> list[str]:
    blocos, atual = [], ""
    for paragrafo in texto.split("\n\n"):
        if atual and len(atual) + len(paragrafo) > TAMANHO_BLOCO:
            blocos.append(atual)
            atual = ""
        atual = f"{atual}\n\n{paragrafo}" if atual else paragrafo
    if atual:
        blocos.append(atual)
    return blocos


def _chamar(cliente, mensagem: str) -> str:
    with cliente.beta.messages.stream(
        model=MODELO,
        max_tokens=64000,
        system=SISTEMA,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": mensagem}],
    ) as stream:
        resposta = stream.get_final_message()
    if resposta.stop_reason == "refusal":
        raise RuntimeError("A IA recusou a solicitação.")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("Resposta da IA cortada (limite de tokens).")
    return "".join(b.text for b in resposta.content if b.type == "text")


def revisar_texto(nome: str, texto: str) -> str:
    """Revisa o texto em blocos e devolve a versão corrigida."""
    import anthropic

    cliente = anthropic.Anthropic()
    revisados = []
    for i, bloco in enumerate(_blocos(texto), 1):
        mensagem = f"{INSTRUCOES}\n\nDocumento: {nome} (trecho {i})\n<texto>\n{bloco}\n</texto>"
        revisados.append(_chamar(cliente, mensagem).strip())
    return "\n\n".join(revisados) + "\n"
