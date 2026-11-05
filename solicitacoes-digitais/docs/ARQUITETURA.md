# Arquitetura proposta — Sistema de Solicitações Digitais

## Visão geral

```
Navegador (frontend estático, dias 5-7)
        │  HTTPS, JSON, token Bearer
        ▼
API /api/v1  (FastAPI)  ── log estruturado com X-Correlation-ID
   ├── seguranca   senhas PBKDF2, tokens assinados, perfis e permissões
   ├── modelos     usuários, solicitações, histórico, auditoria, anexos
   ├── fluxo       máquina de estados da tramitação (dia 2)
   ├── auditoria   eventos imutáveis com correlação
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
