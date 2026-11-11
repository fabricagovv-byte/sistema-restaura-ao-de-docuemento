from __future__ import annotations

from licitacoes import analise, catalogo, coleta, db
from licitacoes.armazenamento import armazenamento, reiniciar
from licitacoes.coletor_remoto import exportar, importar
from licitacoes.config import config
from licitacoes.modelos import Documento, Item, Licitacao, Sincronizacao, agora

from .test_coleta_busca import _registro
from .test_documentos_analise import _pdf_do_edital


def test_exportar_e_importar(banco, edital_lins, tmp_path, monkeypatch):
    s = banco
    _, lic = coleta.gravar(s, _registro(), catalogo.fonte(s, "pncp"))
    s.add(Item(licitacao_id=lic.id, numero=1, descricao="Digitalização", quantidade=1000, unidade="página",
               valor_unitario=0.5, valor_total=500))
    armazenamento().salvar("documentos/x/1.pdf", _pdf_do_edital(edital_lins))
    s.add(Documento(licitacao_id=lic.id, sequencial=1, titulo="Edital PE 083-2026", tipo="edital", url="https://x/1",
                    status="baixado", caminho="documentos/x/1.pdf"))
    s.add(Sincronizacao(fonte_id=catalogo.fonte(s, "pncp").id, status="ok", lidos=1, novos=1, chamadas=3, fim=agora()))
    s.commit()
    pacote = tmp_path / "pacote"
    exportar(s, pacote, {"execucao": "123", "passos": {}})
    assert (pacote / "contratacoes.jsonl.gz").exists() and list((pacote / "textos").glob("*.json"))

    # instalação nova, sem acesso às fontes
    monkeypatch.setenv("LIC_DATABASE_URL", f"sqlite:///{tmp_path / 'outra.db'}")
    monkeypatch.setenv("LIC_ARMAZENAMENTO_DIR", str(tmp_path / "outros-arquivos"))
    config.cache_clear()
    db.reiniciar_engine()
    reiniciar()
    db.iniciar_banco()
    s2 = db.nova_sessao()
    r = importar(s2, pacote)
    assert r["novos"] == 1 and r["textos"] == 1 and "123" in r["origem"]
    lic2 = s2.query(Licitacao).one()
    assert lic2.fonte.codigo == "pncp" and lic2.itens[0].descricao == "Digitalização"
    assert catalogo.fonte(s2, "pncp").ultimo_sucesso is not None
    paginas, _ = analise.paginas_da_licitacao(lic2)
    assert len(paginas) == len(edital_lins["paginas"]) and paginas[3].numero == 4 and "2.9.4" in paginas[3].texto
    s2.close()


def test_coleta_para_no_prazo(banco):
    """Etapas longas param quando o orçamento de tempo acaba, para o pacote sair mesmo assim."""
    import time

    from licitacoes.coletor_remoto import detalhar_relevantes, listar_segmento

    class DiarioLento:
        class http:
            class stats:
                chamadas = 0

        def buscar(self, *a, **k):
            raise AssertionError("não deveria consultar depois do prazo")

    with db.sessao() as s:
        catalogo.registrar_fontes(s)
        passado = time.monotonic() - 1
        r = coleta.sincronizar_querido_diario(s, ["digitalização"], conector=DiarioLento(), ate=passado)
        assert r.status == "parcial" and "limite de tempo" in r.mensagem
        assert listar_segmento(s, 10, ate=passado)["detalhados"] == 0
        assert detalhar_relevantes(s, 10, ate=passado)["editais"] == 0


def test_disjuntor_para_com_fonte_fora_do_ar():
    from licitacoes.coletor_remoto import Disjuntor
    from licitacoes.conectores.base import FalhaTemporaria

    dj = Disjuntor(limite=3)
    fora = FalhaTemporaria("HTTP 503 persistente", 503)
    assert not dj.falhou(fora) and not dj.falhou(fora)
    assert dj.falhou(fora) and "503" in dj.motivo
    dj.nova_chance(tentativas=2)
    assert not dj.falhou(fora) and dj.falhou(fora)  # duas tentativas e para de novo
    dj.sucesso()
    assert not dj.falhou(ValueError("dado ruim")) and dj.seguidas == 0  # erro de dado não conta


def test_coleta_aproveita_pacote_anterior_e_detalha_so_os_novos(banco, tmp_path, monkeypatch):
    """Cada execução no GitHub Actions começa com banco vazio. Com o pacote anterior, os editais abertos já
    detalhados vêm prontos e o tempo vai para os que faltam; encerrados não são trazidos de volta."""
    from datetime import timedelta

    from licitacoes import coletor_remoto
    from licitacoes.coletor_remoto import importar_detalhes, listar_segmento

    s = banco
    pncp = catalogo.fonte(s, "pncp")
    _, velho = coleta.gravar(s, _registro(), pncp)
    _, fechado = coleta.gravar(s, _registro(chave="pncp:12345678000190-1-000002/2026", numero_controle_pncp="12345678000190-1-000002/2026",
                                            sequencial=2, data_encerramento=agora() + timedelta(days=5)), pncp)
    for lic in (velho, fechado):
        s.add(Item(licitacao_id=lic.id, numero=1, descricao="Digitalização de páginas", quantidade=500_000, unidade="página",
                   valor_unitario=0.4, valor_total=200_000))
    s.commit()
    anterior = tmp_path / "anterior"
    exportar(s, anterior, {"execucao": "1", "passos": {}})

    # execução seguinte: banco novo; o segundo edital encerrou e um terceiro apareceu
    monkeypatch.setenv("LIC_DATABASE_URL", f"sqlite:///{tmp_path / 'nova.db'}")
    monkeypatch.setenv("LIC_ARMAZENAMENTO_DIR", str(tmp_path / "arq2"))
    config.cache_clear()
    db.reiniciar_engine()
    reiniciar()
    db.iniciar_banco()
    s2 = db.nova_sessao()
    pncp2 = catalogo.fonte(s2, "pncp")
    coleta.gravar(s2, _registro(), pncp2)
    coleta.gravar(s2, _registro(chave="pncp:12345678000190-1-000002/2026", numero_controle_pncp="12345678000190-1-000002/2026",
                                sequencial=2, data_encerramento=agora() - timedelta(days=1)), pncp2)
    _, novo = coleta.gravar(s2, _registro(chave="pncp:12345678000190-1-000003/2026", numero_controle_pncp="12345678000190-1-000003/2026",
                                          sequencial=3, numero_compra="31/2026", valor_estimado=2_300_000.0,
                                          objeto="Digitalização e indexação de prontuários do arquivo da saúde"), pncp2)
    s2.commit()
    r = importar_detalhes(s2, anterior, so_abertas=True)
    assert r["editais"] == 1  # o encerrado ficou de fora
    assert s2.query(Licitacao).filter_by(sequencial=1).one().itens[0].quantidade == 500_000
    assert s2.query(Licitacao).filter_by(sequencial=2).one().itens == []

    detalhados = []
    monkeypatch.setattr(coletor_remoto.coleta, "detalhar", lambda sess, lic, **k: detalhados.append(lic.chave) or {"itens": 0, "documentos": 0})
    res = listar_segmento(s2, 10)
    assert detalhados == [novo.chave]  # só o que faltava
    assert res["ja_detalhados"] == 1 and res["detalhados"] == 1
    # o pacote novo sai acumulado: o detalhe aproveitado continua lá
    pacote = tmp_path / "novo"
    exportar(s2, pacote, {"execucao": "2", "passos": {}})
    import gzip
    import json
    chaves = {json.loads(x)["chave"] for x in gzip.open(pacote / "detalhes.jsonl.gz", "rt", encoding="utf-8")}
    assert velho.chave in chaves
    s2.close()
