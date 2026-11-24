"""Busca diária no PNCP com proposta aberta, em formato WhatsApp. Dois temas:
  documental — digitalização, indexação e gestão documental (padrão)
  ust        — contratações de TI com UST (unidade de serviço técnico), com destaque para UST em sistemas prontos

Uso (com o pacote pncp-cli instalado e o backend no PYTHONPATH):
    PYTHONPATH=plataforma-licitacoes/backend python plataforma-licitacoes/busca-diaria/busca_diaria.py SAIDA_DIR [documental|ust]

Gera em SAIDA_DIR: AAAA-MM-DD.txt (texto para WhatsApp), AAAA-MM-DD.json (dados), ultima.txt e ultima.json.
Se SAIDA_DIR já tiver um ultima.json, marca como 🆕 as licitações que não estavam na busca anterior.

Regras: só dados do PNCP (nada inventado); só proposta aberta (prazo futuro e situação "Divulgada");
informação ausente sai como NÃO LOCALIZADO; republicações iguais (mesmo órgão, valor e objeto) aparecem uma vez.
"""
import json, math, os, re, subprocess, sys, unicodedata, concurrent.futures as cf
from datetime import datetime, timedelta, timezone

from licitacoes.taxonomia import classificar, natureza, tipo_volume, volumes_no_texto

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "."
TEMA = sys.argv[2] if len(sys.argv) > 2 else "documental"
assert TEMA in ("documental", "ust"), TEMA
LIMITE = int(os.environ.get("BUSCA_LIMITE", "600"))  # registros por termo
AGORA = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)  # Brasília (datas do PNCP vêm sem fuso)

TERMOS = [
    "digitalizacao de documentos", "digitalizacao", "digitalizacao de processos", "digitalizacao de prontuarios", "digitalizacao de acervo",
    "indexacao", "indexacao de documentos", "gestao documental", "gestao arquivistica", "gestao de documentos", "tratamento documental",
    "tratamento arquivistico", "organizacao de arquivos", "organizacao de acervo", "organizacao de documentos", "higienizacao documental",
    "restauracao de documentos", "gerenciamento eletronico de documentos", "GED", "OCR", "classificacao documental", "acervo documental",
    "massa documental", "preservacao digital", "repositorio arquivistico", "guarda de documentos", "custodia de documentos", "guarda externa",
    "microfilmagem", "conversao digital", "captura de documentos", "escaneamento", "avaliacao documental", "tabela de temporalidade",
    "eliminacao de documentos", "arquivistica", "arquivo",
]
# UST: universo de TIC inteiro (a UST costuma estar só nos itens ou no edital, não no objeto)
TERMOS_UST = [
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
    # 20/11 — UST dentro de manutenção/sustentação/suporte e contratos de valor fixo mensal
    "UST manutencao", "UST sustentacao", "UST suporte", "UST desenvolvimento", "unidade de servico tecnico manutencao",
    "servicos tecnicos especializados de tecnologia da informacao", "manutencao e suporte de sistemas", "suporte e manutencao de software",
    "manutencao de sistemas", "sustentacao", "manutencao evolutiva e corretiva", "atendimento N1 N2", "operacao de infraestrutura de TI",
    "valor fixo mensal", "valor mensal", "mensalidade", "pagamento mensal", "servico mensal", "locacao de sistema", "licenca mensal",
    "locacao de software", "cessao de uso de software", "software como servico",
    # 21/11 — TIC, desenvolvimento, manutenção, sustentação e EAD
    "desenvolvimento de aplicativo", "desenvolvimento de portal", "manutencao de software", "manutencao de sistemas informatizados",
    "suporte e manutencao de sistemas", "sustentacao de software", "sustentacao de sistemas de informacao", "evolucao de sistemas",
    "EAD", "ensino a distancia", "cursos online", "capacitacao online", "plataforma de cursos", "moodle", "LMS",
    "trilhas de aprendizagem", "universidade corporativa", "conteudo educacional digital", "educacao digital", "TIC",
]
UST_RX = re.compile(r"\bust\b|\bust'?s\b|unidades? de servicos? (tecnic|tecnolog)|banco de ust")
# UST em sistema pronto: licença/locação/SaaS/sistema integrado (a UST paga implantação, customização e suporte)
PRONTO_RX = re.compile(r"licen[cs]|locacao|cessao|saas|software como servi|subscri|sistemas? integrad|plataforma|solucao (integrada|tecnol)|"
                       r"sistemas? de gestao|software de gestao|\berp\b|sistemas? informatizad")
FORA_UST_RX = re.compile(r"obra de|pavimenta|construcao de|reforma de|alimentacao|merenda|combustivel|veiculos?\b|medicament|"
                         r"material hospitalar|uniforme|limpeza urbana|coleta de lixo")
if TEMA == "ust":
    TERMOS = TERMOS_UST
DOC_CATS = {"digitalizacao", "indexacao", "ged", "ocr", "triagem", "guarda", "higienizacao", "restauracao"}
DOC_RX = re.compile(r"digitaliz|escanea|indexa|gestao documental|gestao arquivist|gestao de documentos|tratamento (documental|arquivist)|"
                    r"arquivist|\bged\b|gerenciamento eletronico de doc|microfilm|custodia de (documentos|acervo)|guarda (de|externa).{0,40}(document|acervo|caixa|processo)|"
                    r"massa documental|acervo (documental|arquivist|fisico)|conversao digital|temporalidade|preservacao digital|"
                    r"repositorio arquivist|organizacao (de|do) (acervo|arquivo|documento)|higieniza.{0,30}(document|acervo)|"
                    r"restaura.{0,30}(document|acervo|livro)|\bocr\b")
FORA_RX = re.compile(r"raios?.?x|materiais? de expediente|suprimentos|manutencao (preventiva |corretiva )?de equipamentos|radiolog|odontolog|intraora|mamograf|tomograf|digitalizador de imagens? (radio|medic)|"
                     r"aquisicao de (scanner|scanners|impressora|equipamento|computador|notebook)|acervo bibliografico|aquisicao de livros|"
                     r"livros didaticos|obra de|engenharia civil|pavimenta|construcao de|reforma de|leiloeiro|arquivo deslizante|"
                     r"arquivos? de aco|mobiliario|estante|armario|digitalizacao de (sinal|tv|radio)|tv digital|radio digital|"
                     r"camaras? (frigorific|fria)|alimentacao|merenda|combustivel|veiculo")
IMPRESSAO_RX = re.compile(r"impressao|impress[aã]o|copia|reprografia|multifuncion|copiadora|outsourcing de impress")
GESTAO_RX = re.compile(r"gestao documental|gestao arquivist|acervo|indexa|arquivist|guarda (externa|gerenciada|de documentos)|\bged\b|"
                       r"gerenciamento eletronico de documentos|tratamento documental")
# o serviço principal é documental (vale em qualquer parte do objeto)
DOC_FORTE_RX = re.compile(r"digitalizacao,? (e )?(de |do |da |dos |das )?(documento|acervo|processo|prontuario|arquivo|livro|jornai|microfilm|"
                          r"plantas|mapas|fichas|imagens de documentos)|servicos? (tecnicos? )?de digitalizacao|preparacao e digitalizacao|"
                          r"(servicos?|empresa especializada|solucao integrada) (\w+ ){0,3}(em|de) (gestao documental|gestao arquivist|tratamento (documental|arquivist))|"
                          r"servicos arquivist|tratamento (documental|arquivist)|guarda (externa|gerenciada)|guarda (e|de) (consulta a )?documentos|"
                          r"custodia de (documentos|acervo)|microfilm|indexacao (de|do|da|dos|das) (acervo|documento|processo)|massa documental|"
                          r"organizacao,? (\w+ ){0,3}(de|do|da) (acervo|arquivo|documentos)|higienizacao (\w+ ){0,2}(documental|de documentos|de acervo)|"
                          r"restauracao de (documentos|acervo|livros)")
# sistema de GED / gestão eletrônica de documentos (vale se estiver no começo do objeto, onde fica o objeto principal)
GED_RX = re.compile(r"gestao eletronica de documentos|gerenciamento eletronico de documentos|\bged\b|desmaterializacao|arquivo digital|"
                    r"gestao de documentacao|arquivologia|digitalizacao e indexacao|gestao documental")
# fora do tema mesmo citando documento (o termo aparece de passagem)
FORA2_RX = re.compile(r"materiais? de expediente|suprimentos|producao cultural|frota|catadores|captacao de recursos|\bbim\b|issqn|"
                      r"equipamentos de informatica|desktop|servicos graficos|etiqueta|gestao da qualidade|gestao escolar|"
                      r"manutencao de equipamentos|monitoramento, captura|videomonitoramento|engenharia")


def eh_documental(texto):
    n = norm(texto)
    if FORA_RX.search(n):
        return False
    if IMPRESSAO_RX.search(n) and not GESTAO_RX.search(n):
        return False  # impressão/cópia com "digitalização" do equipamento
    if DOC_FORTE_RX.search(n) or (GED_RX.search(n[:350]) and not FORA2_RX.search(n)):
        return True
    return bool(DOC_RX.search(n[:180])) and not FORA2_RX.search(n)


def eh_tema(texto, e=None):
    """Triagem: documental pelo objeto; UST = TI e (UST nos itens ou citada no objeto/informação complementar)."""
    if TEMA == "documental":
        return eh_documental(texto)
    n = norm(texto)
    if FORA_UST_RX.search(n):
        return False
    if e is None:  # antes dos itens: qualquer objeto de TI ou que cite UST
        return bool(UST_RX.search(n) or classificar(texto))
    v = e.get("vol") or {}
    return bool(v.get("ust") or v.get("ust_texto") or e.get("ust_doc") or UST_RX.search(norm(f"{texto} {e.get('info') or ''}")))


UST_QTD_RX = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d{2,7})\s*(?:\([^)]{0,60}\)\s*)?(?:ust'?s?\b|unidades? de servicos? tecnic)")


def pdfs_do_arquivo(bruto):
    """PDFs de um arquivo baixado: o próprio PDF ou os PDFs de dentro de um .zip (lidos em memória, com limite de tamanho)."""
    if bruto.startswith(b"%PDF"):
        return [bruto]
    if bruto.startswith(b"PK"):
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(bruto)) as z:
            nomes = [i for i in z.infolist() if i.filename.lower().endswith(".pdf") and i.file_size < 40_000_000]
            nomes.sort(key=lambda i: 0 if re.search(r"edital|termo|\btr\b|referencia|anexo i\b", norm(i.filename)) else 1)
            return [z.read(i) for i in nomes[:5]]
    return []


def texto_pdf(pdf):
    try:
        return subprocess.run(["pdftotext", "-q", "-", "-"], input=pdf, capture_output=True, timeout=120).stdout.decode("utf-8", "ignore")
    except FileNotFoundError:
        import io
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(pdf)).pages[:150])


def ust_no_documento(e):
    """Lê o edital e o TR (PDF) e procura UST: marca a citação e a maior quantidade plausível."""
    alvo = [a for a in e.get("arquivos") or [] if re.search(r"edital|termo de referencia|\btr\b|projeto basico|anexo",
                                                          norm(f"{a.get('tipo')} {a.get('titulo')}"))][:3]
    for a in alvo:
        try:
            bruto = subprocess.run(["curl", "-sL", "--max-time", "120", "--max-filesize", "60000000", a["url"]], capture_output=True, timeout=150).stdout
            txt = "\n".join(texto_pdf(p) for p in pdfs_do_arquivo(bruto))
        except Exception:  # noqa: BLE001
            continue
        n = norm(txt)
        if UST_RX.search(n):
            qs = []
            for m in UST_QTD_RX.finditer(n):
                ctx = n[max(0, m.start() - 80):m.start()]
                if re.search(r"atestad|comprova|minimo de|capacidade tecnica|habilitac|\bano\b|\bart\.|\blei\b|r\$", ctx):
                    continue
                q = float(m.group(1).replace(".", ""))
                if 10 <= q <= 2_000_000:
                    qs.append(q)
            e["ust_doc"] = {"arquivo": a["url"], "quantidade": max(qs) if qs else None}
            return


def norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def pncp(*args, timeout=180):
    r = subprocess.run(["pncp", *args, "-q", "--retries", "4"], capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout) if r.stdout.strip() else None


def buscar(termo):
    try:
        r = subprocess.run(["pncp", "search", termo, "--tipo", "edital", "--status", "recebendo_proposta", "--all", "--limit", str(LIMITE),
                            "--ndjson", "-q", "--pausa", "0.3"], capture_output=True, text=True, timeout=900)
        return termo, [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
    except Exception as e:  # noqa: BLE001
        print(f"erro na busca '{termo}': {e}", file=sys.stderr)
        return termo, []


# ------------------------------------------------------------------ 1. busca por palavra-chave
editais, por_termo = {}, {}
with cf.ThreadPoolExecutor(4) as ex:
    for termo, linhas in ex.map(buscar, TERMOS):
        por_termo[termo] = len(linhas)
        for d in linhas:
            c = d.get("numero_controle_pncp")
            if c:
                e = editais.setdefault(c, {k: d.get(k) for k in ("numero_controle_pncp", "description", "orgao_cnpj", "orgao_nome", "unidade_nome",
                                                                 "municipio_nome", "uf", "numero_sequencial", "ano", "esfera_nome")} | {"termos": []})
                e["termos"].append(termo)
print(f"{len(editais)} editais únicos em {len(TERMOS)} termos", file=sys.stderr)

# ------------------------------------------------------------------ 2. triagem pelo objeto
cand = []
for e in editais.values():
    obj = e.get("description") or ""
    n = norm(obj)
    cats = {c["codigo"] for c in classificar(obj)} & DOC_CATS
    if not eh_tema(obj) or natureza(obj) == "material":
        continue
    e["cats"] = sorted(cats)
    cand.append(e)
print(f"{len(cand)} após triagem pelo objeto", file=sys.stderr)


# ------------------------------------------------------------------ 3. detalhe oficial, itens e arquivos
def detalhar(e):
    cnpj, ano, seq = e["orgao_cnpj"], str(e["ano"]), str(e["numero_sequencial"])
    try:
        d = pncp("contratacao", cnpj, ano, seq)
    except Exception as ex:  # noqa: BLE001
        e["erro"] = str(ex)[:200]
        return e
    if not d:
        e["erro"] = "sem detalhe"
        return e
    e.update(valor=d.get("valorTotalEstimado"), sigiloso=d.get("orcamentoSigilosoDescricao"), numero=d.get("numeroCompra"),
             processo=d.get("processo"), modalidade=d.get("modalidadeNome"), srp=d.get("srp"), abertura=d.get("dataAberturaProposta"),
             encerramento=d.get("dataEncerramentoProposta"), situacao=d.get("situacaoCompraNome"), objeto=d.get("objetoCompra"),
             info=d.get("informacaoComplementar"), link_origem=d.get("linkSistemaOrigem"),
             link_pncp=f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{int(seq)}")
    if not (e.get("encerramento") and datetime.fromisoformat(e["encerramento"]) > AGORA and (e.get("situacao") or "").startswith("Divulgada")):
        return e
    try:
        itens = pncp("itens", cnpj, ano, seq, timeout=300) or []
    except Exception:  # noqa: BLE001
        itens = []
    vol, mensal, meses = {}, 0.0, []
    for it in itens:
        q, u, desc = float(it.get("quantidade") or 0), norm(it.get("unidadeMedida")), norm(it.get("descricao"))
        if str(it.get("materialOuServicoNome") or "").lower().startswith("m"):
            continue
        k = tipo_volume(it.get("unidadeMedida"), it.get("descricao"), it.get("quantidade"), it.get("valorUnitarioEstimado"))
        if k in ("ust", "pf") and TEMA == "ust":
            vol[k] = vol.get(k, 0) + q
        elif k in ("pagina", "registro", "hora"):
            vol[k] = vol.get(k, 0) + q
        elif "metro linear" in u or (u.strip() in {"ml", "m", "metro", "metros"} and re.search(r"arquiv|document|acervo|metro linear", desc)):
            vol["metro_linear"] = vol.get("metro_linear", 0) + q
        elif re.search(r"\bcaixa", u) and re.search(r"arquiv|document|acervo|guarda|custodia|processo", desc):
            vol["caixa"] = vol.get("caixa", 0) + q
        elif k == "mes" and q >= 2 and it.get("valorUnitarioEstimado"):
            mensal += float(it["valorUnitarioEstimado"])
            meses.append(q)
    e["n_itens"] = len(itens)
    e["vol"] = {k: round(v) for k, v in vol.items() if v}
    for k, v in volumes_no_texto(f"{e.get('objeto') or ''} {e.get('info') or ''}", documental=(TEMA == "documental")).items():
        if k == "pagina" and not e["vol"].get("pagina"):
            e["vol"]["pagina_texto"] = round(v)
        elif k == "ust" and TEMA == "ust" and not e["vol"].get("ust"):
            e["vol"]["ust_texto"] = round(v)
    if mensal and meses:
        m = max(set(meses), key=meses.count)
        if e.get("valor") and mensal * m > 1.2 * e["valor"]:
            mensal = e["valor"] / m
        e["mensal"], e["meses"] = round(mensal, 2), int(m)
    try:
        arqs = pncp("arquivos", cnpj, ano, seq) or []
    except Exception:  # noqa: BLE001
        arqs = []
    e["arquivos"] = [{"titulo": a.get("titulo"), "tipo": a.get("tipoDocumentoNome"), "url": a.get("url") or a.get("uri")}
                     for a in arqs if a.get("statusAtivo", True) is not False]
    if TEMA == "ust" and not (e["vol"].get("ust") or e["vol"].get("ust_texto")) and ((e.get("valor") or 0) >= 300_000 or not e.get("valor")):
        ust_no_documento(e)
        if e.get("ust_doc") and e["ust_doc"].get("quantidade"):
            e["vol"]["ust_doc"] = round(e["ust_doc"]["quantidade"])
    return e


with cf.ThreadPoolExecutor(5) as ex:
    cand = list(ex.map(detalhar, cand))
abertos = [e for e in cand if e.get("encerramento") and datetime.fromisoformat(e["encerramento"]) > AGORA
           and (e.get("situacao") or "").startswith("Divulgada") and eh_tema(e.get("objeto") or e.get("description"), e)]
print(f"{len(abertos)} com proposta aberta", file=sys.stderr)

# republicações iguais aparecem uma vez (fica a mais recente pelo sequencial)
uniq = {}
for e in sorted(abertos, key=lambda x: int(x["numero_sequencial"])):
    uniq[(e["orgao_cnpj"], e.get("valor"), re.sub(r"[^a-z0-9]", "", norm(e.get("objeto")))[:60])] = e
abertos = list(uniq.values())


# ------------------------------------------------------------------ 4. nota 0–100
def nota(e):
    v = e.get("valor") or 0
    pv = 30 if v >= 1e7 else 26 if v >= 5e6 else 22 if v >= 1e6 else 16 if v >= 5e5 else 10 if v >= 1e5 else 6 if v > 0 else 12
    n = norm(e.get("objeto"))
    if TEMA == "ust":
        u = (e.get("vol") or {}).get("ust") or (e.get("vol") or {}).get("ust_texto") or (e.get("vol") or {}).get("ust_doc") or 0
        pc = 30 if u >= 10000 else 26 if u >= 1000 else 22 if u > 0 else 12
    else:
        pc = 30 if re.search(r"digitaliz|indexa", n) else 24 if re.search(r"gestao documental|arquivist|\bged\b|tratamento documental", n) else 16
    pq = 15 if e.get("vol") else 5
    dias = (datetime.fromisoformat(e["encerramento"]) - AGORA).total_seconds() / 86400
    pp = 15 if dias >= 7 else 10 if dias >= 3 else 5
    mod = norm(e.get("modalidade"))
    pm = 10 if "pregao" in mod else 8 if "concorrencia" in mod else 4
    e["dias"] = dias
    return pv + pc + pq + pp + pm


for e in abertos:
    e["nota"] = nota(e)

anterior = set()
ult = os.path.join(SAIDA, "ultima.json")
if os.path.exists(ult):
    try:
        anterior = {x["numero_controle_pncp"] for x in json.load(open(ult))["licitacoes"]}
    except Exception:  # noqa: BLE001
        anterior = set()
for e in abertos:
    e["nova"] = bool(anterior) and e["numero_controle_pncp"] not in anterior


# ------------------------------------------------------------------ 5. texto WhatsApp
def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(v):
    return f"{v:,.0f}".replace(",", ".")


def dt(s):
    return datetime.fromisoformat(s).strftime("%d/%m/%Y %H:%M") if s else "NÃO LOCALIZADO"


ROT = {"pagina": "páginas/imagens", "pagina_texto": "páginas (citadas no objeto)", "metro_linear": "metros lineares", "caixa": "caixas",
       "registro": "registros", "hora": "horas técnicas", "ust": "UST", "ust_texto": "UST (citadas no objeto)", "ust_doc": "UST (lidas no edital/TR — conferir)", "pf": "pontos de função"}


def arq(e, rx):
    for a in e.get("arquivos") or []:
        if re.search(rx, norm(f"{a.get('tipo')} {a.get('titulo')}")):
            return a["url"]
    return None


def valor_txt(e):
    v = e.get("valor")
    return brl(v) if v else ("SIGILOSO" if "sigil" in norm(e.get("sigiloso")) and "sem sigilo" not in norm(e.get("sigiloso")) else "NÃO LOCALIZADO")


def bloco(i, e):
    valor = valor_txt(e)
    vol = " · ".join(f"{num(q)} {ROT.get(k, k)}" for k, q in (e.get("vol") or {}).items()) or "NÃO LOCALIZADO nos itens"
    if e.get("ust_doc") and not e["ust_doc"].get("quantidade"):
        vol += " · UST citada no edital/TR (quantidade NÃO LOCALIZADA)"
    ed = arq(e, r"edital")
    tr = arq(e, r"termo de referencia|\btr\b|projeto basico|estudo tecnico")
    d = e["dias"]
    prazo = f"{int(d)} dias" if d >= 1 else f"{int(d * 24)} horas"
    linhas = [f"*{i}. 🏛️ {(e.get('orgao_nome') or '').strip()}*{' 🆕' if e.get('nova') else ''}",
              f"📍 {e.get('municipio_nome') or 'NÃO LOCALIZADO'}/{e.get('uf') or '-'}",
              f"📑 {e.get('modalidade') or 'NÃO LOCALIZADO'} nº {e.get('numero') or 'NÃO LOCALIZADO'}" + (f" · Processo {e['processo']}" if e.get("processo") else "")
              + (" · SRP" if e.get("srp") else ""),
              f"📋 {' '.join((e.get('objeto') or '').split())[:260]}",
              f"💰 {valor}",
              f"📦 {vol}"]
    if e.get("mensal"):
        linhas.append(f"💵 {brl(e['mensal'])}/mês × {e['meses']} meses")
    linhas += [f"📅 Abertura das propostas: {dt(e.get('abertura'))}",
               f"⏳ Propostas até: {dt(e.get('encerramento'))} (faltam {prazo})",
               f"⭐ Nota {e['nota']}/100",
               f"🔗 {e['link_pncp']}",
               f"📥 Edital: {ed or 'NÃO LOCALIZADO no PNCP'}",
               f"📥 TR: {tr or 'NÃO LOCALIZADO no PNCP (ver anexos do edital)'}"]
    return "\n".join(linhas)


competitivas = [e for e in abertos if re.search(r"pregao|concorrencia|leilao|dialogo", norm(e.get("modalidade")))]
outras = [e for e in abertos if e not in competitivas]
competitivas.sort(key=lambda e: (-e["nota"], -(e.get("valor") or 0)))
outras.sort(key=lambda e: (-(e.get("valor") or 0)))
novas = [e for e in competitivas + outras if e.get("nova")]
urgentes = sorted([e for e in abertos if e["dias"] < 3], key=lambda e: e["encerramento"])
soma = sum(e.get("valor") or 0 for e in abertos if (e.get("valor") or 0) < 1e9)

TITULO = {"documental": "📂 BUSCA DIÁRIA — DIGITALIZAÇÃO, INDEXAÇÃO E GESTÃO DOCUMENTAL",
          "ust": "🧮 BUSCA DIÁRIA — UST (UNIDADE DE SERVIÇO TÉCNICO)"}[TEMA]
txt = [f"*{TITULO}*",
       f"Fonte: PNCP (pncp.gov.br), verificado em {AGORA.strftime('%d/%m/%Y %H:%M')} (Brasília).",
       f"{len(TERMOS)} palavras-chave · {num(len(editais))} editais examinados · *{len(abertos)} com proposta aberta* · soma estimada {brl(soma)}",
       f"🆕 Novas desde a busca anterior: {len(novas) if anterior else 'primeira busca'} · ⏳ Encerram em até 3 dias: {len(urgentes)}",
       "Valores = estimativa oficial do órgão no PNCP. Só licitações com prazo de proposta aberto. Confira sempre o edital."]
if anterior and novas:
    txt += ["", f"*🆕 NOVAS ({len(novas)})*"] + [f"• {(e.get('orgao_nome') or '').strip()} ({e.get('uf')}) — "
                                                 f"valor {valor_txt(e)} — até {dt(e['encerramento'])[:10]} — {e['link_pncp']}"
                                                 for e in novas]
if urgentes:
    txt += ["", f"*⏳ ENCERRAM EM ATÉ 3 DIAS ({len(urgentes)})*"] + [f"• {dt(e['encerramento'])} — {(e.get('orgao_nome') or '').strip()} ({e.get('uf')}) — "
                                                                   f"valor {valor_txt(e)} — {e['link_pncp']}"
                                                                   for e in urgentes]
if TEMA == "ust":
    prontos = [e for e in competitivas if PRONTO_RX.search(norm(e.get("objeto")))]
    grupos = [("⭐ UST EM SISTEMAS PRONTOS (licença, locação, SaaS, sistema integrado)", prontos),
              ("🧮 OUTRAS COM UST (manutenção, sustentação, suporte, desenvolvimento)", [e for e in competitivas if e not in prontos])]
else:
    grupos = [("⭐ PREGÕES E CONCORRÊNCIAS, POR NOTA", competitivas)]
for titulo, lista in grupos:
    if lista:
        txt += ["", f"*{titulo} ({len(lista)})*", ""]
        txt += [bloco(i, e) + "\n" for i, e in enumerate(lista, 1)]
if outras:
    txt += [f"*📎 DISPENSAS, CREDENCIAMENTOS E OUTRAS ({len(outras)})*", ""]
    txt += [bloco(i, e) + "\n" for i, e in enumerate(outras, 1)]
txt.append("Critério da nota (0–100): valor 30 · " + ("quantidade de UST 30" if TEMA == "ust" else "aderência ao tema 30")
           + " · quantidades informadas 15 · prazo 15 · modalidade 10.")

os.makedirs(SAIDA, exist_ok=True)
dia = AGORA.strftime("%Y-%m-%d")
texto = "\n".join(txt) + "\n"
dados = {"verificado_em": AGORA.isoformat(timespec="minutes"), "termos": por_termo, "examinados": len(editais), "triados": len(cand),
         "abertas": len(abertos), "soma_estimada": soma, "novas": len(novas), "urgentes": len(urgentes),
         "licitacoes": [{k: v for k, v in e.items() if k != "description"} for e in competitivas + outras]}
for nome, conteudo in ((f"{dia}.txt", texto), ("ultima.txt", texto)):
    open(os.path.join(SAIDA, nome), "w").write(conteudo)
for nome in (f"{dia}.json", "ultima.json"):
    json.dump(dados, open(os.path.join(SAIDA, nome), "w"), ensure_ascii=False, indent=1)
print(f"ok: {len(abertos)} abertas ({len(novas)} novas, {len(urgentes)} urgentes) -> {SAIDA}")
