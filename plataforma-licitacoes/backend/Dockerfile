FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por qpdf \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY plataforma-licitacoes/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# o módulo de restauração/OCR do repositório é reaproveitado na extração de editais
COPY restaurador /restaurador_pkg/restaurador
ENV PYTHONPATH=/restaurador_pkg
COPY plataforma-licitacoes/backend/licitacoes ./licitacoes
COPY plataforma-licitacoes/backend/tests ./tests
EXPOSE 8000
CMD ["uvicorn", "licitacoes.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
