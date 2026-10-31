"""Documentos do edital: classificação, download e o pacote ZIP com tudo o que é público.

Nada é inventado: o ZIP leva só arquivos baixados da fonte, mais um manifesto que lista o que
foi baixado, o que está indisponível, o que exige login e quais tipos esperados não foram publicados.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
import zipfile
from datetime import datetime

from sqlalchemy.orm import Session

from .armazenamento import armazenamento
from .conectores.base import AcessoNegado, ClienteHttp, ErroFonte
from .modelos import Documento, Licitacao, agora
from .util import normalizar, slug

TIPOS = [
    ("retificacao", ["retificacao", "retificado", "errata", "adendo", "aditamento ao edital"]),
    ("esclarecimento", ["esclarecimento", "pedido de esclarecimento", "resposta a questionamento"]),
    ("impugnacao", ["impugnacao", "recurso administrativo", "contrarrazoes"]),
    ("estudo_tecnico_preliminar", ["estudo tecnico preliminar", " etp "]),
    ("termo_referencia", ["termo de referencia", " tr "]),
    ("projeto_executivo", ["projeto executivo", "projetos executivos"]),
    ("projeto_basico", ["projeto basico"]),
    ("planilha_orcamentaria", ["planilha orcamentaria", "planilha de custos", "orcamento estimado", "mapa de cotacao",
                               "planilha de precos", "composicao de custos", "bdi"]),
    ("modelo_proposta", ["modelo de proposta", "proposta comercial", "modelo da proposta"]),
    ("minuta_contrato", ["minuta do contrato", "minuta de contrato", "minuta contratual", "minuta da ata",
                         "ata de registro de precos"]),
    ("edital", ["edital", "aviso de licitacao", "aviso de contratacao"]),
    ("anexo", ["anexo"]),
]
ESPERADOS = ["edital", "termo_referencia", "estudo_tecnico_preliminar", "projeto_basico", "projeto_executivo",
             "planilha_orcamentaria", "modelo_proposta", "minuta_contrato", "anexo", "retificacao",
             "esclarecimento", "impugnacao"]
NOMES = {
    "edital": "Edital", "termo_referencia": "Termo de Referência", "estudo_tecnico_preliminar": "Estudo Técnico Preliminar",
    "projeto_basico": "Projeto Básico", "projeto_executivo": "Projetos Executivos",
    "planilha_orcamentaria": "Planilhas orçamentárias", "modelo_proposta": "Modelo de proposta",
    "minuta_contrato": "Minuta contratual", "anexo": "Anexos", "retificacao": "Retificações",
    "esclarecimento": "Esclarecimentos", "impugnacao": "Impugnações e respostas", "outro": "Outros",
}
MAPA_PNCP = {
    "edital": "edital", "aviso de contratacao direta": "edital", "termo de referencia": "termo_referencia",
    "estudo tecnico preliminar": "estudo_tecnico_preliminar", "minuta do contrato": "minuta_contrato",
    "minuta da ata de registro de precos": "minuta_contrato", "projeto basico": "projeto_basico",
}


def classificar_documento(titulo: str | None, tipo_fonte: str | None = None) -> str:
    n = " " + normalizar(f"{titulo or ''}") + " "
    for tipo, termos in TIPOS[:4]:  # retificação/esclarecimento/impugnação/ETP vencem o tipo informado
        if any(t in n for t in termos):
            return tipo
    tf = normalizar(tipo_fonte or "")
    if tf in MAPA_PNCP:
        return MAPA_PNCP[tf]
    for tipo, termos in TIPOS[4:]:
        if any(t in n for t in termos):
            return tipo
    return "outro"


def _extensao(mime: str | None, url: str | None, conteudo: bytes, disposicao: str | None) -> str:
    if disposicao:
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposicao)
        if m and "." in m.group(1):
            return "." + m.group(1).rsplit(".", 1)[-1].lower()[:6]
    if conteudo.startswith(b"%PDF"):
        return ".pdf"
    if conteudo.startswith(b"PK"):
        return ".zip" if not mime or "zip" in mime else (mimetypes.guess_extension(mime) or ".zip")
    if mime:
        ext = mimetypes.guess_extension(mime.split(";")[0].strip())
        if ext:
            return ext
    return ".bin"


def baixar_documento(s: Session, doc: Documento, http: ClienteHttp | None = None) -> Documento:
    if not doc.url:
        doc.status, doc.erro = "indisponivel", "a fonte não informa link para o arquivo"
        return doc
    http = http or ClienteHttp(intervalo_minimo_s=1.0, timeout_s=180, cabecalhos={"Accept": "*/*"})
    try:
        r = http.requisitar("GET", doc.url)
    except AcessoNegado as e:
        doc.status, doc.erro = "requer_autenticacao", str(e)
        return doc
    except ErroFonte as e:
        doc.status = "indisponivel" if e.status in (404, 410) else "erro"
        doc.erro = str(e)
        return doc
    if r is None or not r.content:
        doc.status, doc.erro = "indisponivel", "a fonte respondeu sem conteúdo"
        return doc
    conteudo = r.content
    if b"<html" in conteudo[:500].lower() and ("login" in r.text[:5000].lower() or "captcha" in r.text[:5000].lower()):
        doc.status, doc.erro = "requer_autenticacao", "a fonte devolveu página de login/CAPTCHA"
        return doc
    mime = r.headers.get("content-type")
    ext = _extensao(mime, doc.url, conteudo, r.headers.get("content-disposition"))
    lic = doc.licitacao
    chave = f"documentos/{slug(lic.chave, 120)}/{doc.sequencial or doc.id:03d}-{slug(doc.titulo, 60)}{ext}"
    armazenamento().salvar(chave, conteudo, mime)
    doc.caminho, doc.tamanho, doc.mime = chave, len(conteudo), mime
    doc.sha256 = hashlib.sha256(conteudo).hexdigest()
    doc.status, doc.erro, doc.baixado_em = "baixado", None, agora()
    return doc


def baixar_todos(s: Session, lic: Licitacao, http: ClienteHttp | None = None) -> dict:
    res: dict[str, int] = {}
    for doc in lic.documentos:
        if doc.status == "baixado" and doc.caminho and armazenamento().existe(doc.caminho):
            res["ja_baixado"] = res.get("ja_baixado", 0) + 1
            continue
        baixar_documento(s, doc, http)
        res[doc.status] = res.get(doc.status, 0) + 1
    s.commit()
    return res


def checklist(lic: Licitacao) -> list[dict]:
    presentes: dict[str, list[Documento]] = {}
    for d in lic.documentos:
        presentes.setdefault(d.tipo, []).append(d)
    saida = []
    for tipo in ESPERADOS:
        docs = presentes.get(tipo, [])
        saida.append({
            "tipo": tipo, "nome": NOMES[tipo], "publicado": bool(docs),
            "baixados": sum(d.status == "baixado" for d in docs),
            "observacao": None if docs else "não publicado na fonte (ou publicado dentro de outro arquivo)",
        })
    return saida


def gerar_zip(lic: Licitacao) -> tuple[bytes, dict]:
    buf = io.BytesIO()
    manifesto = {
        "licitacao": {"chave": lic.chave, "orgao": lic.orgao_nome, "numero": lic.numero_compra,
                      "objeto": lic.objeto, "link_pncp": lic.link_pncp, "link_origem": lic.link_origem},
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "documentos": [], "checklist": checklist(lic),
        "aviso": "Este pacote contém somente arquivos baixados da fonte oficial. Nenhum anexo foi criado.",
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        usados: set[str] = set()
        for d in sorted(lic.documentos, key=lambda x: (x.sequencial or 0, x.titulo)):
            item = {"titulo": d.titulo, "tipo": NOMES.get(d.tipo, d.tipo), "status": d.status, "url": d.url,
                    "sha256": d.sha256, "erro": d.erro}
            if d.status == "baixado" and d.caminho:
                nome = f"{d.sequencial or 0:02d}-{slug(d.titulo, 70)}{'.' + d.caminho.rsplit('.', 1)[-1] if '.' in d.caminho else ''}"
                while nome in usados:
                    nome = "_" + nome
                usados.add(nome)
                z.writestr(nome, armazenamento().ler(d.caminho))
                item["arquivo"] = nome
            manifesto["documentos"].append(item)
        z.writestr("manifesto.json", json.dumps(manifesto, ensure_ascii=False, indent=2, default=str))
        faltas = [x for x in manifesto["documentos"] if x["status"] != "baixado"]
        leia = [f"Licitação: {lic.orgao_nome} — {lic.numero_compra or ''}", f"Objeto: {lic.objeto}",
                f"Fonte oficial: {lic.link_pncp or lic.link_origem}", "",
                f"Arquivos incluídos: {len(usados)}", f"Arquivos não incluídos: {len(faltas)}"]
        for x in faltas:
            leia.append(f"  - {x['titulo']}: {x['status']} {('(' + x['erro'] + ')') if x['erro'] else ''}")
        leia += ["", "Tipos de documento não publicados na fonte:"]
        leia += [f"  - {c['nome']}" for c in manifesto["checklist"] if not c["publicado"]]
        z.writestr("LEIA-ME.txt", "\n".join(leia))
    return buf.getvalue(), manifesto
