# Plataforma Nacional de Licitações 5.0

Descobre, coleta, organiza, analisa e monitora licitações públicas do Brasil. Backend em Python
(FastAPI, PostgreSQL, Celery/Redis), frontend em Next.js e análise de editais com o Claude.

O que está pronto e foi testado nesta entrega:

| Módulo | Situação |
|---|---|
| Conector PNCP (publicação, atualização, propostas abertas, consulta individual, itens, arquivos) | Pronto; testado com respostas reais gravadas; acesso ao vivo bloqueado nesta sessão |
| Conector Compras.gov.br (Dados Abertos, Lei 14.133 e legado 8.666) | Pronto; não validado ao vivo |
| Conector Querido Diário (diários oficiais municipais) | Pronto; não validado ao vivo |
| Conector Portal da Transparência | Pronto; exige chave gratuita |
| Lista de municípios do IBGE (API ou cópia pública) | Funcionando: 5.571 municípios carregados |
| Espelhos públicos do PNCP (GitHub) | **Funcionando ao vivo: 18.779 editais reais importados** |
| Identificação da plataforma de disputa (Compras.gov, BLL, Portal de Compras Públicas, Licitanet, BNC…) | Funcionando nos dados reais |
| Banco PostgreSQL com histórico, duplicatas e republicações | Funcionando |
| Busca com filtros e expansão por significado (18 categorias de TI, 8 de gestão documental, 7 de engenharia) | Funcionando; 40–150 ms em 18,8 mil editais |
| Download de anexos e ZIP completo com manifesto | Pronto; testado com servidor simulado |
| Extração de texto com página e cláusula (PDF, DOCX, XLSX, ZIP, OCR) | Funcionando |
| Análise com IA, com citação conferida no texto | Pronta; testada com cliente simulado (sem chave da API nesta sessão) |
| Precificação, planilha Excel com fórmulas e PDF | Funcionando |
| Alertas sem duplicidade (painel, e-mail, WhatsApp Business, webhook) | Funcionando; e-mail e WhatsApp dependem de credenciais |
| Agenda a cada 15 min (Celery beat) | Funcionando com Redis local |
| Painel, mapa por UF e município, controle de qualidade e cobertura comprovada | Funcionando |
| Autenticação JWT com papéis e log de auditoria | Funcionando |
| Testes automatizados | 30 passando em PostgreSQL e SQLite; 4 testes ao vivo prontos (precisam de rede) |

O que ficou de fora ou depende de você está em [docs/fontes.md](docs/fontes.md#o-que-falta).

## Instalar com Docker (produção)

```bash
cd plataforma-licitacoes
cp .env.example .env          # defina LIC_JWT_SEGREDO e, se quiser IA, ANTHROPIC_API_KEY
docker compose up -d --build
docker compose exec api python -m licitacoes.cli criar-usuario voce@empresa.com "Seu Nome" "senha" --papel admin
docker compose exec api python -m licitacoes.cli sync ibge
docker compose exec api python -m licitacoes.cli sync pncp-propostas      # carga inicial: editais abertos
```

* Painel: http://localhost:3000 · API: http://localhost:8000/docs · Arquivos (MinIO): http://localhost:9001
* O agendador (Celery beat) roda o monitoramento a cada 15 minutos, as propostas abertas a cada 6 horas
  e a rotina diária às 06h10 (PNCP dos últimos 3 dias, conferência individual, Compras.gov, diários, espelhos).
* OpenSearch é opcional: `docker compose --profile busca up -d` e `LIC_OPENSEARCH_URL=http://opensearch:9200`.

## Instalar sem Docker (desenvolvimento)

```bash
cd plataforma-licitacoes/backend
pip install -r requirements.txt
export LIC_DATABASE_URL=postgresql+psycopg://usuario:senha@localhost/licitacoes   # ou deixe SQLite
python -m licitacoes.cli init-db
python -m licitacoes.cli criar-usuario admin@empresa.com Admin senha --papel admin
python -m licitacoes.cli sync espelhos          # dados reais mesmo sem acesso ao PNCP
python -m licitacoes.cli sync ibge
uvicorn licitacoes.api:app --reload --port 8000

cd ../frontend
npm install && npm run dev                       # http://localhost:3000
```

Testes: `cd backend && pytest -q` (SQLite) ou `LIC_TESTE_PG=postgresql+psycopg://... pytest -q`.
Testes contra as fontes reais: `LIC_TESTES_AO_VIVO=1 pytest tests/test_ao_vivo.py -v`.

## Linha de comando

| Comando | O que faz |
|---|---|
| `sync pncp --dias 3 [--modalidades 6,4] [--ufs SP,MG]` | Publicados e alterados no PNCP no período |
| `sync pncp-propostas` | Todas as contratações com propostas abertas |
| `sync conferir` | Consulta um a um os editais que vencem em 3 dias (prorrogações e exclusões) |
| `sync comprasgov` / `sync querido-diario --termos "digitalização,GED"` / `sync transparencia` | Outras fontes |
| `sync espelhos` | Importa as cópias públicas do PNCP |
| `sync ibge` | Lista de municípios (base da cobertura comprovada) |
| `preparar ID [--sem-ia]` | Itens, documentos, download e análise de um edital |
| `zip ID arquivo.zip` | Pacote com todos os documentos públicos |
| `alertas` · `painel` · `qualidade` · `reclassificar` | Rotinas avulsas |
| `agendador` | Ciclo de monitoramento sem Celery (um processo) |

## Documentação

* [docs/arquitetura.md](docs/arquitetura.md) — módulos, banco, fluxo de dados e decisões
* [docs/fontes.md](docs/fontes.md) — cada fonte: como funciona, situação, impedimentos e o que fazer
* [docs/operacao.md](docs/operacao.md) — produção, segurança, backup, LGPD, monitoramento e custos de IA
