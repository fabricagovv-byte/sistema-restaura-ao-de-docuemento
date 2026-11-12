"""Configuração da plataforma, lida de variáveis de ambiente com prefixo LIC_ (ou de um .env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIC_", env_file=".env", extra="ignore")

    # Banco e filas
    database_url: str = "sqlite:///./licitacoes.db"
    redis_url: str = "redis://localhost:6379/0"
    execucao: str = "local"  # "local" roda as tarefas na hora; "celery" manda para a fila

    # Armazenamento de documentos: pasta local ou S3 compatível (MinIO, AWS, R2)
    armazenamento_dir: str = "./armazenamento"
    s3_bucket: str | None = None
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_regiao: str = "us-east-1"

    # Busca textual opcional em OpenSearch (sem ele a busca usa o PostgreSQL)
    opensearch_url: str | None = None
    opensearch_indice: str = "licitacoes"

    # Busca semântica opcional (pgvector + sentence-transformers)
    embeddings_modelo: str | None = None  # ex.: "paraphrase-multilingual-MiniLM-L12-v2"

    # IA
    ia_modelo: str = "claude-opus-5-5"
    ia_esforco: str = "high"
    ia_max_tokens_saida: int = 64000
    ia_max_caracteres_contexto: int = 1_200_000  # acima disso, seleciona páginas e registra as omitidas

    # PNCP (limites medidos em chamadas reais: 4 s entre chamadas evita o 429)
    pncp_intervalo_s: float = 4.0
    # rodadas extras por página do PNCP depois das tentativas do cliente HTTP (segundos entre elas; vazio = nenhuma)
    pncp_esperas_pagina: str = "30,60,120"
    pncp_tamanho_pagina: int = 50
    pncp_modalidades: str = "6,4,8,7,5,12,9,1,3,2,10,11,13"
    pncp_dias_proposta: int = 180

    # Portal da Transparência (exige chave gratuita: portaldatransparencia.gov.br/api-de-dados/cadastrar-email)
    transparencia_chave: str | None = None
    transparencia_orgaos: str = ""  # códigos SIAFI separados por vírgula

    # Categorias que pesam na aderência (perfil da empresa)
    categorias_prioritarias: str = (
        "digitalizacao,indexacao,ged,triagem,guarda,higienizacao,restauracao,ocr,"
        "desenvolvimento,fabrica_software,manutencao_software,sustentacao,dados,ia,remun_fixo_mensal,remun_ust,remun_pf,ti_mensal,tecnologia,ead,pesquisa,pd_inovacao"
    )

    # Monitoramento
    intervalo_monitoramento_min: int = 15
    horas_prazo_proximo: int = 72
    valor_alto: float = 5_000_000.0

    # Ambiente: "desenvolvimento" ou "producao". Em produção o segredo padrão é recusado.
    ambiente: str = "desenvolvimento"
    # Origens que o navegador pode usar para chamar a API (vírgula). Em produção, só o domínio do site.
    cors_origens: str = "*"

    # Autenticação
    jwt_segredo: str = "troque-este-segredo-em-producao-0000000000"
    jwt_horas: int = 12
    auth_obrigatoria: bool = True

    # Canais de alerta
    smtp_host: str | None = None
    smtp_porta: int = 587
    smtp_usuario: str | None = None
    smtp_senha: str | None = None
    smtp_remetente: str | None = None
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_template: str | None = None  # nome do template aprovado na Meta
    whatsapp_versao_api: str = "v21.0"

    user_agent: str = "PlataformaLicitacoes/5.0 (monitoramento de editais publicos)"

    @property
    def origens(self) -> list[str]:
        return [x.strip() for x in self.cors_origens.split(",") if x.strip()] or ["*"]

    def conferir_producao(self) -> list[str]:
        """Problemas que impedem subir em produção (lista vazia = pode subir)."""
        if self.ambiente != "producao":
            return []
        erros = []
        if self.jwt_segredo.startswith("troque-este-segredo") or len(self.jwt_segredo) < 32:
            erros.append("LIC_JWT_SEGREDO precisa de um segredo próprio com 32 caracteres ou mais")
        if "*" in self.origens:
            erros.append("LIC_CORS_ORIGENS precisa listar o domínio do site (ex.: https://licitacoes.suaempresa.com.br)")
        if not self.auth_obrigatoria:
            erros.append("LIC_AUTH_OBRIGATORIA não pode ser falso em produção")
        if self.database_url.startswith("sqlite"):
            erros.append("LIC_DATABASE_URL deve apontar para o PostgreSQL em produção")
        return erros

    @property
    def prioritarias(self) -> list[str]:
        return [x.strip() for x in self.categorias_prioritarias.split(",") if x.strip()]

    @property
    def modalidades_pncp(self) -> list[int]:
        return [int(x) for x in self.pncp_modalidades.split(",") if x.strip()]


@lru_cache
def config() -> Configuracao:
    return Configuracao()
