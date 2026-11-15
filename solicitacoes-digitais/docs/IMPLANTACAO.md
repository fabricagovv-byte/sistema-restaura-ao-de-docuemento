# Implantação, configuração por ambiente e CI — OS-001/2026 (entrega D8-A, REQ-007)

Situação em 15/11/2026: **contêineres, configuração por ambiente e pipeline de CI implementados e testados nesta
máquina** (PostgreSQL 16, API e serviço de e-mail em Docker, caixa de e-mail de homologação local). O ambiente real de
produção do contratante ainda não foi informado (pergunta 8 de `PENDENCIAS_ENTREVISTA.md`).

## 1. Peças

| Arquivo | Para quê |
|---|---|
| `Dockerfile` | Imagem única (Python 3.12 slim, usuário sem privilégio `sd`, verificação de saúde em `/api/v1/saude`). Na subida aplica as migrações pendentes (idempotentes) e inicia a API. |
| `docker-compose.yml` | Serviços `banco` (PostgreSQL 16), `api`, `mensagens` (envio contínuo da caixa de saída) e, só no perfil `homologacao`, `mailpit` (caixa de e-mail local). Volumes `banco` e `anexos`. |
| `.env.exemplo` | Todas as variáveis `SD_*` lidas pelo código, com o valor padrão e o que significam. O teste `test_toda_variavel_lida_pelo_codigo_esta_no_env_de_exemplo` falha se alguém criar variável nova sem documentar. |
| `.github/workflows/solicitacoes-ci.yml` | CI: testes no SQLite e no PostgreSQL, conferência do contrato OpenAPI, construção da imagem e teste de fumaça com o compose. |
| `tests/homologacao_conteineres.py` | Roteiro de homologação contra os contêineres de verdade (login, cadastro, solicitação, tramitação e e-mail entregue). |

## 2. Configuração por ambiente

| Variável | desenvolvimento | teste | homologacao | producao |
|---|---|---|---|---|
| `SD_SEGREDO` | opcional (valor fixo de desenvolvimento) | opcional | **obrigatório, 32+ caracteres** | **obrigatório, 32+ caracteres** |
| `SD_BANCO_URL` | SQLite local | SQLite temporário ou `SD_TESTE_PG` | PostgreSQL (compose) ou SQLite | **PostgreSQL obrigatório** |
| `SD_SMTP_*` | opcional | servidor SMTP local dos testes | Mailpit (`mailpit:1025`, sem cifra) | servidor do órgão com `starttls` ou `ssl` (sem cifra só em `localhost`) |
| `SD_PBKDF2_ITERACOES` | 600 mil | 1.000 (só para acelerar testes) | 600 mil | 600 mil |
| `SD_URL_PUBLICA` | `http://127.0.0.1:8000` | idem | endereço de homologação | endereço público HTTPS |

As regras em negrito estão no código (`solicitacoes/config.py`): o serviço **não sobe** se forem violadas, e cada uma
tem teste (`test_producao_exige_segredo_forte`, `test_configuracao_de_email_e_de_producao_validada`).

Um arquivo por ambiente: `SD_ENV_ARQUIVO=/etc/sd/homologacao.env docker compose --env-file /etc/sd/homologacao.env up -d`.

## 3. Subir

```bash
cp .env.exemplo .env            # preencha SD_SEGREDO, POSTGRES_PASSWORD, SD_URL_PUBLICA e o SMTP
docker compose up -d --build --wait
docker compose exec api python -m solicitacoes criar-admin admin@orgao.gov.br "Nome do administrador"
```

A API fica em `127.0.0.1:8000`: publique-a por um proxy com HTTPS (Caddy, Nginx ou o balanceador do órgão).
Rede com inspeção de HTTPS: `docker build --secret id=ca,src=/caminho/ca-da-rede.crt .` (o certificado só é usado na
construção, não fica na imagem).

## 4. Pipeline de CI

A cada push ou pull request que altera `solicitacoes-digitais/`:

1. **testes (sqlite)** e **testes (postgresql)**, em paralelo: instala as dependências, confere que o contrato OpenAPI
   salvo é o gerado pelo código e roda a suíte inteira (`pytest -v`), a segunda com um PostgreSQL 16 de serviço;
2. **imagem** (só se os testes passarem): constrói a imagem, sobe `banco` e `api` com o compose em modo produção
   (segredo e senha gerados na hora), confere `/api/v1/saude`, confere que rota protegida responde 401 e reaplica as
   migrações; mostra os registros se falhar e sempre derruba tudo com `down -v`.

Os testes de navegador (Playwright) são pulados na CI enquanto o Node com Playwright não estiver instalado no runner;
rodam nesta máquina e o resultado vai para `medicao/evidencias/`.

## 5. O que foi verificado nesta máquina (15/11/2026)

Registro completo em `medicao/evidencias/implantacao-dia08.txt`:

* imagem construída; compose de homologação com os 4 serviços saudáveis;
* administrador criado pela linha de comando dentro do contêiner; roteiro de homologação com 13 verificações aprovadas,
  inclusive o aviso de tramitação entregue na caixa local em 4 segundos;
* dados preservados depois de reiniciar o banco e a API;
* **achado e corrigido:** com o banco parado, o serviço de envio caía (erro de conexão) e só voltava porque o Docker o
  reiniciava; agora registra o erro e tenta na rodada seguinte. Conferido parando e voltando o banco: zero reinícios do
  contêiner. Teste de regressão: `test_servico_continuo_sobrevive_a_banco_fora_do_ar`.

## 6. Pendências

* Onde vai rodar e quem opera (pergunta 8) — define proxy HTTPS, domínio e registro de logs centralizado.
* Servidor de e-mail do órgão, remetente e credenciais (pergunta 7) — até lá, só a caixa local de homologação.
* Primeira execução da CI no GitHub: o resultado entra no relatório quando o job terminar.
