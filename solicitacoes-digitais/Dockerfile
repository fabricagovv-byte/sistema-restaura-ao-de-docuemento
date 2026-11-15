# syntax=docker/dockerfile:1
# Imagem da API de Solicitações Digitais (OS-001, entrega D8-A).
# Uma imagem para os dois papéis: API (padrão) e envio de e-mails (`python -m solicitacoes enviar-mensagens --continuo`).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    SD_ANEXOS_DIR=/dados/anexos

WORKDIR /app
COPY requirements.txt .
# Rede com inspeção de HTTPS (comum em órgão público): passe a cadeia de certificados da rede só na construção,
# sem gravá-la na imagem:  docker build --secret id=ca,src=/caminho/ca-da-rede.crt .
RUN --mount=type=secret,id=ca,required=false \
    if [ -s /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; pip install -r requirements.txt

COPY solicitacoes ./solicitacoes
COPY docs/api ./docs/api

# usuário sem privilégio; anexos num volume próprio
RUN useradd --system --uid 10001 --home /app sd && mkdir -p /dados/anexos && chown -R sd /dados
USER sd

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/saude', timeout=4).status == 200 else 1)"

# aplica as migrações pendentes (idempotentes) e sobe a API
CMD ["sh", "-c", "python -m solicitacoes migrar && exec python -m solicitacoes servidor --host 0.0.0.0 --porta 8000"]
