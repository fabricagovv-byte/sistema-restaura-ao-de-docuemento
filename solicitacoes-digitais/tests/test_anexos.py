import hashlib
import io
import zipfile
from pathlib import Path

from solicitacoes.rotas_anexos import tipo_pelo_conteudo

from .apoio import cenario, nova, tramitar

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def enviar(c, h, sid, nome, dados, tipo="application/octet-stream"):
    return c.post(f"/api/v1/solicitacoes/{sid}/anexos", files={"arquivo": (nome, dados, tipo)}, headers=h)


def test_tipo_pelo_conteudo_e_nao_pela_extensao():
    assert tipo_pelo_conteudo(PDF) == "pdf" and tipo_pelo_conteudo(PNG) == "png"
    assert tipo_pelo_conteudo(b"\xff\xd8\xff\xe0JFIF") == "jpg" and tipo_pelo_conteudo(docx()) == "docx"
    zip_comum = io.BytesIO()
    with zipfile.ZipFile(zip_comum, "w") as z:
        z.writestr("virus.exe", "MZ")
    assert tipo_pelo_conteudo(zip_comum.getvalue()) is None
    assert tipo_pelo_conteudo(b"MZ\x90\x00 executavel") is None and tipo_pelo_conteudo(b"<html><script>") is None


def test_envio_lista_baixa_e_remove_com_historico_e_auditoria(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    r = enviar(c, h["solicitante"], sid, "../../etc/comprovante de residência.pdf", PDF, "image/png")
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["nome"] == "comprovante de residência.pdf" and a["tipo"] == "application/pdf"  # tipo real, nome sem caminho
    assert a["sha256"] == hashlib.sha256(PDF).hexdigest() and a["tamanho"] == len(PDF)
    assert [x["id"] for x in c.get(f"/api/v1/solicitacoes/{sid}/anexos", headers=h["gestor"]).json()] == [a["id"]]
    d = c.get(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["gestor"])
    assert d.status_code == 200 and d.content == PDF and "attachment" in d.headers["content-disposition"]
    assert d.headers["x-content-type-options"] == "nosniff"
    assert c.get(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["solicitante2"]).status_code == 404
    assert c.delete(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["solicitante"]).status_code == 204
    assert c.get(f"/api/v1/solicitacoes/{sid}/anexos", headers=h["solicitante"]).json() == []
    hist = [x["comentario"] for x in c.get(f"/api/v1/solicitacoes/{sid}/historico", headers=h["solicitante"]).json() if x["evento"] == "anexo"]
    assert hist == ["anexado: comprovante de residência.pdf", "removido: comprovante de residência.pdf"]
    ev = [e["acao"] for e in c.get("/api/v1/auditoria", params={"recurso": "solicitacao", "recurso_id": str(sid)}, headers=h["gestor"]).json()]
    assert "anexar" in ev and "remover_anexo" in ev


def test_recusa_tipo_tamanho_vazio_e_quem_nao_pode(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    assert enviar(c, h["solicitante"], sid, "programa.pdf", b"MZ\x90\x00 executavel").status_code == 415
    assert enviar(c, h["solicitante"], sid, "grande.pdf", b"%PDF-" + b"0" * (1024 * 1024 + 10)).status_code == 413
    assert enviar(c, h["solicitante"], sid, "vazio.pdf", b"").status_code == 422
    assert enviar(c, h["solicitante2"], sid, "x.pdf", PDF).status_code == 404       # não vê
    assert enviar(c, h["operador"], sid, "x.pdf", PDF).status_code == 409           # não é o responsável
    assert enviar(c, h["solicitante"], sid, "foto.png", PNG).status_code == 201
    assert enviar(c, h["gestor"], sid, "parecer.docx", docx()).status_code == 201
    tramitar(c, h["gestor"], sid, "em_triagem")
    tramitar(c, h["gestor"], sid, "indeferida", "Fora da competência")
    assert enviar(c, h["solicitante"], sid, "depois.pdf", PDF).status_code == 409   # finalizada


def test_remocao_so_por_quem_enviou_ou_gestor(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    c.post(f"/api/v1/solicitacoes/{sid}/atribuir", json={"responsavel_id": ids["operador"]}, headers=h["gestor"])
    a = enviar(c, h["solicitante"], sid, "doc.pdf", PDF).json()
    assert c.delete(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["operador"]).status_code == 403
    assert c.delete(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["gestor"]).status_code == 204
    assert c.delete(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["gestor"]).status_code == 404


def test_arquivo_alterado_no_disco_nao_e_entregue(app_cliente):
    c = app_cliente
    ids, h, cat = cenario(c)
    sid = nova(c, h["solicitante"], cat)["id"]
    a = enviar(c, h["solicitante"], sid, "doc.pdf", PDF).json()
    from solicitacoes.banco import sessao
    from solicitacoes.modelos import Anexo

    with sessao() as s:
        Path(s.get(Anexo, a["id"]).caminho).write_bytes(b"%PDF- adulterado")
    assert c.get(f"/api/v1/solicitacoes/{sid}/anexos/{a['id']}", headers=h["gestor"]).status_code == 500
