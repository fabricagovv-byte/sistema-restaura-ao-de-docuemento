"""Pesquisa nacional ao vivo no PNCP (pncp-cli): editais com proposta aberta para as palavras-chave do roteiro."""
import json, subprocess, sys, concurrent.futures as cf

TERMOS = [
    # A — desenvolvimento
    "fabrica de software", "desenvolvimento de sistemas", "desenvolvimento de software", "desenvolvimento sob demanda",
    "desenvolvimento e manutencao de sistemas", "metodos ageis", "engenharia de software", "sistemas corporativos", "java",
    ".net", "desenvolvimento web", "aplicativos moveis", "servicos de programacao", "modernizacao de sistemas", "transformacao digital",
    # B — medição
    "UST", "unidade de servico tecnico", "unidade de servico tecnologico", "ponto de funcao", "pontos de funcao",
    "analise de pontos de funcao", "HST", "hora de servico tecnico", "horas tecnicas", "homem-hora", "catalogo de servicos de TI",
    "banco de horas", "servicos tecnicos sob demanda",
    # C — sustentação
    "sustentacao de sistemas", "manutencao evolutiva", "manutencao corretiva de sistemas", "manutencao adaptativa",
    "suporte tecnico especializado", "servicos continuados de TIC", "operacao assistida", "sustentacao de aplicacoes",
    "outsourcing de desenvolvimento", "servicos gerenciados de TI", "devops", "service desk",
    # D — documental
    "digitalizacao de documentos", "gestao documental", "tratamento documental", "indexacao", "organizacao de arquivos",
    "higienizacao documental", "restauracao de documentos", "gerenciamento eletronico de documentos", "GED", "OCR",
    "classificacao documental", "acervo", "preservacao digital", "guarda de documentos", "microfilmagem",
    # E — tecnologia avançada
    "inteligencia artificial", "automacao de processos", "RPA", "integracao de sistemas", "seguranca da informacao",
    "governanca de TI", "ciencia de dados", "engenharia de dados", "banco de dados", "computacao em nuvem",
    "infraestrutura de TIC", "business intelligence", "big data",
    # F — educação e sistemas
    "educacao a distancia", "plataforma educacional", "ambiente virtual de aprendizagem", "sistema de gestao publica",
    "sistema de gestao em saude", "tecnologia da informacao",
]


def buscar(termo):
    try:
        r = subprocess.run(["pncp", "search", termo, "--tipo", "edital", "--status", "recebendo_proposta", "--all", "--limit", "600",
                            "--ndjson", "-q", "--pausa", "0.3"], capture_output=True, text=True, timeout=900)
        linhas = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        return termo, linhas, r.returncode
    except Exception as e:  # noqa: BLE001
        return termo, [], f"erro {e}"


saida = {}
por_termo = {}
with cf.ThreadPoolExecutor(4) as ex:
    for termo, linhas, rc in ex.map(buscar, TERMOS):
        por_termo[termo] = (len(linhas), rc)
        for d in linhas:
            c = d.get("numero_controle_pncp")
            if not c:
                continue
            e = saida.setdefault(c, {k: d.get(k) for k in ("numero_controle_pncp", "title", "description", "orgao_cnpj", "orgao_nome",
                                                            "unidade_nome", "municipio_nome", "uf", "modalidade_licitacao_nome",
                                                            "data_publicacao_pncp", "data_inicio_vigencia", "data_fim_vigencia",
                                                            "item_url", "esfera_nome", "numero_sequencial", "ano")} | {"termos": []})
            e["termos"].append(termo)
        print(f"{termo}: {len(linhas)} (rc {rc})", file=sys.stderr, flush=True)
json.dump({"por_termo": por_termo, "editais": list(saida.values())}, open(sys.argv[1], "w"), ensure_ascii=False)
print("únicos:", len(saida))
