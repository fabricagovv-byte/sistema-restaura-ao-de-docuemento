"""Análise automática do edital com o Claude, com citação verificável de cada informação.

Fluxo:
1. Dados estruturados do PNCP (órgão, número, modalidade, objeto, valor, datas, itens) entram como
   informação OFICIAL, com a fonte "PNCP — dados estruturados".
2. O texto dos documentos baixados vai para o Claude, página a página e identificado; ele devolve
   um JSON (saída estruturada) em que cada campo traz natureza (oficial, cálculo, estimativa da IA,
   não encontrado) e citações com documento, página, cláusula e o trecho literal.
3. Cada citação é conferida no texto extraído: o trecho precisa existir naquela página. Citação que não
   confere fica marcada como não verificada (nunca é apresentada como confirmada).
4. Totais por item são recalculados (quantidade × valor unitário) e marcados como cálculo próprio.
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from .armazenamento import armazenamento
from .config import config
from .extracao import Pagina, clausula_em, extrair
from .modelos import Analise, Licitacao
from .util import normalizar

log = logging.getLogger("licitacoes.analise")

CAMPOS = [
    ("orgao", "Órgão contratante"), ("numero", "Número da licitação"), ("modalidade", "Modalidade"),
    ("objeto", "Objeto"), ("valor_estimado", "Valor estimado"), ("data_abertura", "Data de abertura"),
    ("prazo_propostas", "Prazo para propostas"), ("itens_lotes", "Quantidade de itens e lotes"),
    ("prazo_contratual", "Prazo contratual"), ("local_execucao", "Local de execução"),
    ("equipe_minima", "Equipe mínima exigida"), ("qualificacao_tecnica", "Qualificação técnica"),
    ("atestados", "Atestados de capacidade técnica"), ("certificacoes", "Certificações"),
    ("exigencias_juridicas_fiscais", "Exigências jurídicas e fiscais"), ("garantias", "Garantias contratuais"),
    ("criterio_julgamento", "Critério de julgamento"),
]
CHAVES = [c for c, _ in CAMPOS]
NATUREZAS = ["oficial", "calculo", "estimativa_ia", "nao_encontrado"]

_CITACAO = {
    "type": "object",
    "properties": {
        "documento": {"type": "string"}, "pagina": {"type": "integer"},
        "clausula": {"type": "string"}, "trecho": {"type": "string"},
    },
    "required": ["documento", "pagina", "clausula", "trecho"], "additionalProperties": False,
}
_LISTA_ANALITICA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "descricao": {"type": "string"},
            "gravidade": {"type": "string", "enum": ["baixa", "media", "alta"]},
            "natureza": {"type": "string", "enum": NATUREZAS},
            "base": {"type": "string"},
            "citacoes": {"type": "array", "items": _CITACAO},
        },
        "required": ["descricao", "gravidade", "natureza", "base", "citacoes"], "additionalProperties": False,
    },
}
ESQUEMA = {
    "type": "object",
    "properties": {
        "campos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "campo": {"type": "string", "enum": CHAVES},
                    "valor": {"type": "string"},
                    "natureza": {"type": "string", "enum": NATUREZAS},
                    "citacoes": {"type": "array", "items": _CITACAO},
                    "observacao": {"type": "string"},
                },
                "required": ["campo", "valor", "natureza", "citacoes", "observacao"], "additionalProperties": False,
            },
        },
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lote": {"type": "string"}, "numero": {"type": "string"}, "descricao": {"type": "string"},
                    "quantidade": {"type": "string"}, "unidade": {"type": "string"},
                    "valor_unitario": {"type": "string"}, "valor_total": {"type": "string"},
                    "citacoes": {"type": "array", "items": _CITACAO},
                },
                "required": ["lote", "numero", "descricao", "quantidade", "unidade", "valor_unitario",
                             "valor_total", "citacoes"],
                "additionalProperties": False,
            },
        },
        "riscos": _LISTA_ANALITICA,
        "custos_operacionais": _LISTA_ANALITICA,
        "oportunidades": _LISTA_ANALITICA,
        "documentos_citados_nao_enviados": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["campos", "itens", "riscos", "custos_operacionais", "oportunidades",
                 "documentos_citados_nao_enviados"],
    "additionalProperties": False,
}

SISTEMA = """Você é analista de licitações públicas brasileiras (Lei 14.133/2021) e lê editais para uma empresa \
que decide se participa. Você recebe o texto dos documentos de UMA licitação, separado por documento e página.

Regras:
- Use somente o que está nos documentos. Se a informação não aparece, use natureza "nao_encontrado", valor "" \
e nenhuma citação. Não complete com conhecimento geral nem com o que "costuma" constar em editais.
- Cada citação traz o nome do documento e o número da página exatamente como aparecem no cabeçalho \
"=== DOCUMENTO: ... | PÁGINA n ===", a cláusula ou item (ex.: "8.2.1" ou "Cláusula Sétima"; "" se não houver) e \
um trecho copiado literalmente da página, de 20 a 300 caracteres, sem reescrever. O trecho será conferido.
- natureza: "oficial" quando o valor é dito pelo documento; "calculo" quando você somou ou multiplicou \
números do documento (diga a conta em observacao); "estimativa_ia" para avaliações suas (riscos, custos, \
oportunidades), sempre com a base em "base".
- Em itens, liste cada item ou lote com os números como estão no documento (quantidade, unidade, valor \
unitário e total estimados). Se o documento não traz o valor, deixe "".
- riscos: o que pode dar errado na execução ou na habilitação (prazos curtos, penalidades, exigências \
difíceis, cláusulas ambíguas). custos_operacionais: custos que a empresa terá e o edital deixa implícitos \
(equipe, deslocamento, garantias, licenças, equipamentos). oportunidades: o que favorece participar \
(margem, cota ME/EPP, registro de preços com adesão, exigências acessíveis).
- documentos_citados_nao_enviados: anexos mencionados no texto que não estão entre os documentos recebidos.
Responda em português."""

PALAVRAS_RELEVANTES = [
    "habilitacao", "qualificacao tecnica", "atestado", "capacidade tecnica", "garantia", "vigencia", "prazo",
    "equipe", "profissional", "criterio de julgamento", "menor preco", "tecnica e preco", "valor estimado", "item",
    "lote", "local", "certificacao", "iso", "penalidade", "multa", "pagamento", "regularidade fiscal", "balanco",
    "patrimonio liquido", "visita tecnica", "amostra", "prova de conceito", "subcontratacao", "consorcio",
]


def paginas_da_licitacao(lic: Licitacao, usar_ocr: bool = True) -> tuple[list[Pagina], list[str]]:
    paginas: list[Pagina] = []
    avisos = []
    for d in lic.documentos:
        if d.status != "baixado" or not d.caminho:
            avisos.append(f"{d.titulo}: não analisado ({d.status})")
            continue
        try:
            ps = extrair(f"{d.titulo}{'.' + d.caminho.rsplit('.', 1)[-1] if '.' in d.caminho else ''}",
                         armazenamento().ler(d.caminho), usar_ocr)
        except Exception as e:  # documento ilegível não derruba a análise inteira
            avisos.append(f"{d.titulo}: falha na leitura ({type(e).__name__})")
            continue
        if not ps:
            avisos.append(f"{d.titulo}: formato sem texto extraível")
        d.paginas = len(ps)
        paginas += ps
    return paginas, avisos


def montar_contexto(paginas: list[Pagina], limite: int) -> tuple[str, list[str]]:
    blocos = [(p, f"=== DOCUMENTO: {p.documento} | PÁGINA {p.numero} ===\n{p.texto.strip()}\n") for p in paginas]
    total = sum(len(b) for _, b in blocos)
    omitidas: list[str] = []
    if total > limite:
        def pontos(p: Pagina) -> int:
            n = normalizar(p.texto)
            return sum(n.count(t) for t in PALAVRAS_RELEVANTES) + (50 if p.numero <= 3 else 0)
        ordem = sorted(blocos, key=lambda b: -pontos(b[0]))
        escolhidos, usado = set(), 0
        for p, b in ordem:
            if usado + len(b) > limite:
                omitidas.append(f"{p.documento} p.{p.numero}")
                continue
            escolhidos.add(id(b))
            usado += len(b)
        blocos = [(p, b) for p, b in blocos if id(b) in escolhidos]
    return "\n".join(b for _, b in blocos), omitidas


def _norm_trecho(t: str) -> str:
    return re.sub(r"\s+", " ", normalizar(t)).strip(" .;:")


def verificar_citacao(c: dict, paginas: list[Pagina]) -> dict:
    alvo = [p for p in paginas if p.documento == c.get("documento") and p.numero == c.get("pagina")]
    if not alvo:
        alvo = [p for p in paginas if normalizar(p.documento) == normalizar(c.get("documento", ""))
                and p.numero == c.get("pagina")]
    res = dict(c)
    if not alvo:
        res.update(verificada=False, motivo="documento ou página não existe no material analisado")
        return res
    pagina = alvo[0]
    trecho = _norm_trecho(c.get("trecho", ""))
    texto = _norm_trecho(pagina.texto)
    if len(trecho) < 8:
        res.update(verificada=False, motivo="trecho curto demais para conferir")
        return res
    pos = texto.find(trecho)
    if pos >= 0:
        res.update(verificada=True, semelhanca=1.0)
    else:
        melhor = 0.0
        janela = len(trecho)
        passo = max(1, janela // 4)
        for i in range(0, max(1, len(texto) - janela + 1), passo):
            r = SequenceMatcher(None, trecho, texto[i:i + janela]).ratio()
            if r > melhor:
                melhor, pos = r, i
        res.update(verificada=melhor >= 0.88, semelhanca=round(melhor, 3))
        if melhor < 0.88:
            res["motivo"] = "trecho não encontrado na página indicada"
    if not c.get("clausula"):
        bruto = pagina.texto.lower().find(c.get("trecho", "")[:30].lower())
        res["clausula_detectada"] = clausula_em(paginas, pagina.documento, pagina.numero, max(0, bruto))
    return res


def _campos_oficiais(lic: Licitacao) -> dict:
    fonte = [{"documento": "PNCP — dados estruturados da contratação", "pagina": 0, "clausula": "",
              "trecho": lic.link_pncp or lic.link_origem or "", "verificada": True}]

    def f(valor, nat="oficial"):
        return {"valor": valor, "natureza": nat if valor not in (None, "") else "nao_encontrado",
                "citacoes": fonte if valor not in (None, "") else [], "observacao": "", "origem": "fonte_estruturada"}

    v = f"R$ {float(lic.valor_estimado):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if lic.valor_estimado else ""
    obs_v = "Orçamento sigiloso ou não informado ao PNCP" if not lic.valor_estimado else ""
    campos = {
        "orgao": f(" — ".join(x for x in [lic.orgao_nome, lic.unidade_nome] if x)),
        "numero": f(" / ".join(x for x in [lic.numero_compra and f"nº {lic.numero_compra}", lic.processo and f"processo {lic.processo}"] if x)),
        "modalidade": f(lic.modalidade or ""),
        "objeto": f(lic.objeto),
        "valor_estimado": {**f(v), "observacao": obs_v},
        "data_abertura": f(lic.data_abertura.strftime("%d/%m/%Y %H:%M") if lic.data_abertura else ""),
        "prazo_propostas": f(lic.data_encerramento.strftime("%d/%m/%Y %H:%M") if lic.data_encerramento else ""),
    }
    if lic.itens:
        lotes = {(i.bruto or {}).get("numeroGrupo") for i in lic.itens} - {None}
        campos["itens_lotes"] = f(f"{len(lic.itens)} itens" + (f" em {len(lotes)} lotes" if lotes else ""))
    return campos


def _itens_oficiais(lic: Licitacao) -> list[dict]:
    saida = []
    for i in sorted(lic.itens, key=lambda x: x.numero):
        q = float(i.quantidade) if i.quantidade is not None else None
        u = float(i.valor_unitario) if i.valor_unitario is not None else None
        t = float(i.valor_total) if i.valor_total is not None else None
        calc = round(q * u, 2) if q is not None and u is not None else None
        saida.append({
            "numero": str(i.numero), "descricao": i.descricao, "quantidade": q, "unidade": i.unidade,
            "valor_unitario": u, "valor_total": t, "natureza": "oficial", "origem": "PNCP — itens da contratação",
            "calculo": {"valor_total_calculado": calc, "natureza": "calculo",
                        "confere": None if calc is None or t is None else abs(calc - t) < max(0.05, 0.001 * t)},
        })
    return saida


def chamar_claude(contexto: str, lic: Licitacao, cliente=None) -> tuple[dict, dict, str]:
    """Devolve (relatorio_json, uso, stop_reason). Lança exceção se a API falhar."""
    import anthropic

    cfg = config()
    cli = cliente or anthropic.Anthropic()
    instrucao = (
        f"Licitação: {lic.orgao_nome or ''} — nº {lic.numero_compra or ''} — {lic.modalidade or ''}.\n"
        f"Objeto informado: {lic.objeto}\n\nPreencha o relatório com todos os campos listados no esquema."
    )
    pedido = dict(
        model=cfg.ia_modelo,
        max_tokens=cfg.ia_max_tokens_saida,
        system=SISTEMA,
        output_config={"effort": cfg.ia_esforco, "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": contexto, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": instrucao},
        ]}],
    )
    # Fallback do servidor: se o modelo recusar por política, a API repete com o modelo indicado pela própria Anthropic.
    with cli.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **pedido) as st:
        msg = st.get_final_message()
    uso = {"entrada": msg.usage.input_tokens, "saida": msg.usage.output_tokens,
           "cache_leitura": getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
           "cache_escrita": getattr(msg.usage, "cache_creation_input_tokens", 0) or 0, "modelo": msg.model}
    if msg.stop_reason == "refusal":
        return {}, uso, "refusal"
    texto = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return {}, uso, msg.stop_reason or "json_invalido"
    return dados, uso, msg.stop_reason or "end_turn"


def analisar(s: Session, lic: Licitacao, cliente=None, usar_ocr: bool = True) -> Analise:
    cfg = config()
    paginas, avisos = paginas_da_licitacao(lic, usar_ocr)
    relatorio = {
        "campos": {k: {"rotulo": r, **_campos_oficiais(lic).get(k, {"valor": "", "natureza": "nao_encontrado",
                                                                     "citacoes": [], "observacao": ""})}
                   for k, r in CAMPOS},
        "itens_oficiais": _itens_oficiais(lic),
        "itens_documento": [], "riscos": [], "custos_operacionais": [], "oportunidades": [],
        "documentos_analisados": sorted({p.documento for p in paginas}),
        "paginas_analisadas": len(paginas), "avisos": avisos, "paginas_nao_enviadas": [],
        "legenda": {"oficial": "dito pela fonte oficial", "calculo": "conta feita pela plataforma ou pela IA",
                    "estimativa_ia": "avaliação da IA, não consta do edital", "nao_encontrado": "não localizado"},
    }
    an = Analise(licitacao_id=lic.id, modelo=cfg.ia_modelo, status="parcial", relatorio=relatorio)
    if not paginas:
        an.status = "parcial"
        an.erro = "nenhum documento com texto disponível; relatório só com dados estruturados da fonte"
    else:
        contexto, omitidas = montar_contexto(paginas, cfg.ia_max_caracteres_contexto)
        relatorio["paginas_nao_enviadas"] = omitidas
        try:
            dados, uso, parada = chamar_claude(contexto, lic, cliente)
            an.uso_tokens = uso
        except Exception as e:
            an.status = "ia_indisponivel"
            an.erro = f"{type(e).__name__}: {str(e)[:500]}"
            dados, parada = {}, "erro"
        if parada == "refusal":
            an.status, an.erro = "recusada", "o modelo recusou a análise"
        elif dados:
            verif = {"total": 0, "verificadas": 0, "nao_verificadas": []}

            def conferir(cits):
                saida = []
                for c in cits or []:
                    v = verificar_citacao(c, paginas)
                    verif["total"] += 1
                    verif["verificadas"] += bool(v.get("verificada"))
                    if not v.get("verificada"):
                        verif["nao_verificadas"].append({k: v.get(k) for k in ("documento", "pagina", "trecho", "motivo")})
                    saida.append(v)
                return saida

            for c in dados.get("campos", []):
                k = c.get("campo")
                if k not in relatorio["campos"]:
                    continue
                atual = relatorio["campos"][k]
                cits = conferir(c.get("citacoes"))
                if atual.get("origem") == "fonte_estruturada" and atual["natureza"] != "nao_encontrado":
                    atual["citacoes_documentos"] = cits
                    if c.get("valor") and normalizar(c["valor"]) != normalizar(str(atual["valor"])):
                        atual["valor_nos_documentos"] = c["valor"]
                else:
                    relatorio["campos"][k] = {"rotulo": atual["rotulo"], "valor": c.get("valor", ""),
                                              "natureza": c.get("natureza", "nao_encontrado"), "citacoes": cits,
                                              "observacao": c.get("observacao", ""), "origem": "ia_documentos"}
            for it in dados.get("itens", []):
                it["citacoes"] = conferir(it.get("citacoes"))
                relatorio["itens_documento"].append(it)
            for chave in ("riscos", "custos_operacionais", "oportunidades"):
                for x in dados.get(chave, []):
                    x["citacoes"] = conferir(x.get("citacoes"))
                    relatorio[chave].append(x)
            relatorio["documentos_citados_nao_enviados"] = dados.get("documentos_citados_nao_enviados", [])
            an.verificacao = verif
            an.status = "concluida" if parada == "end_turn" else "parcial"
            if parada not in ("end_turn",):
                an.erro = f"resposta interrompida ({parada})"
        elif an.status == "parcial":
            an.status = "erro"
            an.erro = an.erro or f"resposta sem JSON ({parada})"
    an.relatorio = relatorio
    s.add(an)
    s.commit()
    return an


def classificar_objetos_ia(objetos: list[str], codigos: list[str], cliente=None) -> list[list[str]]:
    """Classifica objetos que a taxonomia não reconheceu. Opcional (custa tokens)."""
    import anthropic

    cli = cliente or anthropic.Anthropic()
    esquema = {"type": "object", "properties": {"classificacoes": {"type": "array", "items": {
        "type": "object", "properties": {"indice": {"type": "integer"},
                                         "categorias": {"type": "array", "items": {"type": "string", "enum": codigos}}},
        "required": ["indice", "categorias"], "additionalProperties": False}}},
        "required": ["classificacoes"], "additionalProperties": False}
    lista = "\n".join(f"{i}. {o[:600]}" for i, o in enumerate(objetos))
    msg = cli.messages.create(
        model=config().ia_modelo, max_tokens=8000, output_config={"effort": "low", "format": {"type": "json_schema", "schema": esquema}},
        messages=[{"role": "user", "content": "Classifique cada objeto de licitação nas categorias que se aplicam "
                   "(lista vazia se nenhuma). Considere o serviço contratado, não palavras soltas.\n\n" + lista}],
    )
    texto = next((b.text for b in msg.content if b.type == "text"), "{}")
    dados = json.loads(texto)
    saida = [[] for _ in objetos]
    for c in dados.get("classificacoes", []):
        if 0 <= c["indice"] < len(objetos):
            saida[c["indice"]] = c["categorias"]
    return saida
