"""Etapa 2: triagem pelo objeto (taxonomia da plataforma), detalhe oficial (valor, datas, links), itens e arquivos."""
import json, re, subprocess, sys, concurrent.futures as cf
from datetime import datetime, timezone, timedelta
from licitacoes.taxonomia import classificar, natureza, tipo_volume, volumes_no_texto, texto_busca

ENTRADA, SAIDA, UST_DB = sys.argv[1:4]
AGORA = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)  # horário de Brasília (as datas do PNCP vêm sem fuso)
FOCO = {"desenvolvimento", "fabrica_software", "manutencao_software", "sustentacao", "sistemas_gestao", "dados", "ia", "integracao",
        "cloud", "servidores", "seguranca", "suporte", "infra_ti", "consultoria_ti", "digitalizacao", "indexacao", "ged", "ocr",
        "triagem", "guarda", "higienizacao", "restauracao", "ead", "ti_mensal"}
MEDIDA = {"UST", "unidade de servico tecnico", "unidade de servico tecnologico", "ponto de funcao", "pontos de funcao",
          "analise de pontos de funcao", "HST", "hora de servico tecnico", "horas tecnicas", "homem-hora", "catalogo de servicos de TI",
          "banco de horas", "servicos tecnicos sob demanda"}
CTX = re.compile(r"\b(ti|tic)\b|tecnologia|software|sistema|digitaliz|document|dados|informatica|nuvem|aplicac")


def pncp(*args, timeout=120):
    r = subprocess.run(["pncp", *args, "-q", "--retries", "4"], capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout) if r.stdout.strip() else None


ed = json.load(open(ENTRADA))["editais"]
cand = []
for e in ed:
    obj = e.get("description") or ""
    cats = {c["codigo"] for c in classificar(obj)}
    medida = bool(set(e["termos"]) & MEDIDA) and CTX.search(texto_busca(obj))
    if (cats & FOCO or medida) and natureza(obj) != "material":
        e["cats"] = sorted(cats & FOCO)
        cand.append(e)
print("editais únicos:", len(ed), "| após triagem pelo objeto:", len(cand), file=sys.stderr)

db = {x["link"].rstrip("/").split("/editais/")[-1]: x for x in json.load(open(UST_DB)) if x.get("link") and "/editais/" in x["link"]}


def detalhar(e):
    cnpj, ano, seq = e["orgao_cnpj"], e["ano"], e["numero_sequencial"]
    try:
        d = pncp("contratacao", cnpj, str(ano), str(seq))
    except Exception as ex:  # noqa: BLE001
        e["erro"] = str(ex)[:200]
        return e
    if not d:
        e["erro"] = "sem detalhe"
        return e
    e.update(valor=d.get("valorTotalEstimado"), sigiloso=d.get("orcamentoSigilosoDescricao"), numero=d.get("numeroCompra"),
             processo=d.get("processo"), modalidade=d.get("modalidadeNome"), disputa=d.get("modoDisputaNome"), srp=d.get("srp"),
             abertura=d.get("dataAberturaProposta"), encerramento=d.get("dataEncerramentoProposta"), situacao=d.get("situacaoCompraNome"),
             objeto=d.get("objetoCompra"), info=d.get("informacaoComplementar"), link_origem=d.get("linkSistemaOrigem"),
             link_processo=d.get("linkProcessoEletronico"), atualizado=d.get("dataAtualizacaoGlobal"),
             link_pncp=f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{int(seq)}",
             plataforma=(d.get("usuarioNome") or ""))
    return e


with cf.ThreadPoolExecutor(5) as ex:
    cand = list(ex.map(detalhar, cand))
abertos = [e for e in cand if e.get("encerramento") and datetime.fromisoformat(e["encerramento"]) > AGORA
           and (e.get("situacao") or "").startswith("Divulgada")]
print("com detalhe:", sum(1 for e in cand if "valor" in e), "| prazo ainda aberto e situação divulgada:", len(abertos), file=sys.stderr)


def aprofundar(e):
    """Itens (quantidades de UST/PF/HST/páginas) e arquivos (edital, TR) para os de maior valor ou com medida."""
    cnpj, ano, seq = e["orgao_cnpj"], str(e["ano"]), str(e["numero_sequencial"])
    try:
        itens = pncp("itens", cnpj, ano, seq, timeout=240) or []
    except Exception:  # noqa: BLE001
        itens = []
    vol, linhas = {}, []
    for it in itens:
        k = tipo_volume(it.get("unidadeMedida"), it.get("descricao"), it.get("quantidade"), it.get("valorUnitarioEstimado"))
        if k and not str(it.get("materialOuServicoNome") or "").lower().startswith("m"):
            vol[k] = vol.get(k, 0) + float(it.get("quantidade") or 0)
            linhas.append(f"item {it.get('numeroItem')}: {float(it.get('quantidade') or 0):,.0f} {it.get('unidadeMedida')} — "
                          f"{' '.join((it.get('descricao') or '').split())[:90]}".replace(",", "."))
    e["n_itens"] = len(itens)
    e["vol_itens"] = {k: round(v) for k, v in vol.items()}
    e["linhas_volume"] = linhas[:6]
    vt = volumes_no_texto(f"{e.get('objeto') or ''} {e.get('info') or ''}")
    e["vol_objeto"] = {k: round(v) for k, v in vt.items()}
    x = db.get(f"{cnpj}/{ano}/{int(seq)}")
    e["vol_documentos"] = (x or {}).get("vol") or {}
    try:
        arqs = pncp("arquivos", cnpj, ano, seq) or []
    except Exception:  # noqa: BLE001
        arqs = []
    e["arquivos"] = [{"titulo": a.get("titulo"), "tipo": a.get("tipoDocumentoNome"), "url": a.get("url") or a.get("uri")}
                     for a in arqs if a.get("statusAtivo", True) is not False]
    return e


fundo = [e for e in abertos if (e.get("valor") or 0) >= 1_000_000 or set(e["termos"]) & MEDIDA or e.get("sigiloso", "").startswith("Compra sigil")]
with cf.ThreadPoolExecutor(5) as ex:
    fundo = list(ex.map(aprofundar, fundo))
ids = {e["numero_controle_pncp"] for e in fundo}
json.dump({"verificado_em": AGORA.isoformat(timespec="minutes"), "examinados": len(ed), "triados": len(cand),
           "abertos": [e for e in abertos if e["numero_controle_pncp"] not in ids] + fundo}, open(SAIDA, "w"), ensure_ascii=False)
print("aprofundados (itens e arquivos):", len(fundo), file=sys.stderr)
