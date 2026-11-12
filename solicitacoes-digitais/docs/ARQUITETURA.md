# Arquitetura proposta — Sistema de Solicitações Digitais

## Visão geral

```
Navegador (frontend estático em solicitacoes/web, servido pela própria API; dias 5-7)
        │  HTTPS, JSON, token Bearer
        ▼
API /api/v1  (FastAPI)  ── log estruturado com X-Correlation-ID
   ├── seguranca   senhas PBKDF2, tokens assinados, perfis e permissões
   ├── modelos     usuários, solicitações, histórico, auditoria, anexos
   ├── fluxo       máquina de estados da tramitação (dia 2)
   ├── auditoria   eventos imutáveis com correlação
   ├── painel      indicadores gerenciais e exportação CSV auditada (dia 4)
   ├── contrato    OpenAPI v1 salvo em docs/api e verificado nos testes (dia 4)
   └── migracoes   versões numeradas e idempotentes
        │  SQLAlchemy 2
        ▼
Banco: PostgreSQL em produção; SQLite para desenvolvimento e testes
Arquivos anexos: diretório configurável (dia 3), depois armazenamento de objetos se o contratante quiser
```

## Decisões

| Tema | Decisão | Motivo |
|---|---|---|
| Linguagem e framework | Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic 2 | Contrato OpenAPI gerado do código, validação declarativa, ecossistema maduro |
| Banco | PostgreSQL (produção) e SQLite (testes) pela mesma camada | Testes rápidos sem servidor e produção robusta |
| Migrações | Lista numerada no código com tabela `versao_esquema`; cada passo verifica se já foi aplicado | Requisito RNF-06 (idempotência) sem ferramenta externa |
| Senhas | PBKDF2-HMAC-SHA256, 600 mil iterações, sal de 16 bytes, comparação em tempo constante | Biblioteca padrão; recomendação atual de iterações |
| Sessão | Token JWT HS256 com expiração (padrão 60 min) e `jti`; logout grava o `jti` numa lista de revogação | Sem estado no servidor, com revogação explícita |
| Autorização | Matriz central perfil → permissões; cada rota declara a permissão exigida | Teste automático perfil × rota |
| Auditoria | Tabela só de inclusão; a API não expõe alteração nem exclusão | REQ-005 |
| Configuração | Variáveis `SD_*` (banco, segredo, expiração, ambiente); segredo obrigatório fora de desenvolvimento | Separação por ambiente (TR seção 4) |
| Correlação | Middleware lê ou gera `X-Correlation-ID`, devolve na resposta e grava no log e na auditoria | RNF-03 |
| Contrato da API | OpenAPI gerado do código, salvo em `docs/api/openapi-v1.json` e servido em `/api/v1/openapi.json`; teste compara salvo e gerado e aponta mudança incompatível | RNF-05; clientes sabem quando a API muda |
| Exportação | CSV com BOM e `;`, células com fórmula neutralizadas, sem dados pessoais além do identificador, cada exportação auditada com SHA-256 | Abre certo no Excel em português; evita injeção em planilha; LGPD |
| Frontend | HTML, CSS e JavaScript sem etapa de build, servidos pela API na raiz; DOM montado só com `textContent`; token no `sessionStorage` | Instalação simples, CSP restritiva sem `unsafe-inline`, menos superfície para XSS |
| Cabeçalhos das telas | `Content-Security-Policy` só com o próprio servidor, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` | Impede script de terceiros, clickjacking e vazamento do link de redefinição |
| Dados | Só dados fictícios até aprovação formal; nada de CPF real | TR seção 5 e LGPD |

## Estados da solicitação (detalhados no dia 2)

`recebida → em_triagem → em_atendimento ⇄ aguardando_solicitante → concluida` e as saídas `indeferida`, `cancelada`;
qualquer estado final pode ser `arquivada` pelo gestor; `reaberta` volta para `em_triagem`.

## Estrutura do repositório

```
solicitacoes-digitais/
  solicitacoes/   código da aplicação
  tests/          testes automatizados
  docs/           requisitos, arquitetura, pendências
  medicao/        plano da OS, registro de execução, evidências e relatórios diários
```
