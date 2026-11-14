# Matriz de requisitos — Sistema de Solicitações Digitais (OS-001/2026)

Base: Termo de Referência (minuta DG-CONT-001, 04/11/2026), seções 1 a 7; Ordem de Serviço OS-001/2026.
Situação: **proposta técnica**. Critérios de aceite detalhados por requisito: `docs/CRITERIOS_ACEITE.md` (dia 5, pendentes de validação). Papéis, dados e regras precisam ser confirmados na entrevista obrigatória
(`docs/PENDENCIAS_ENTREVISTA.md`). O que depende dessa confirmação está marcado como *premissa*.

## Papéis

| Papel | Pode | Não pode |
|---|---|---|
| Solicitante | Abrir solicitação, anexar arquivos, acompanhar as próprias, responder pedidos de complemento, cancelar enquanto não atribuída | Ver solicitações de outros, mudar status, ver auditoria |
| Operador | Triar, assumir, atender, pedir complemento, concluir ou indeferir solicitações da sua fila | Gerir usuários, ver auditoria completa, reabrir arquivadas |
| Gestor | Tudo do operador em qualquer fila, atribuir a operadores, reabrir, ver painel, exportar, ver auditoria | Gerir usuários e parâmetros do sistema |
| Administrador | Gerir usuários, perfis, categorias e parâmetros; ver auditoria | Alterar o conteúdo de uma solicitação de terceiro sem registro de auditoria |

## Requisitos funcionais

| ID | Requisito | Critério de aceite (TR seção 3) | Prioridade | Entrega da OS |
|---|---|---|---|---|
| REQ-001 | Controle de acesso: autenticação por e-mail e senha, sessão com expiração, perfis e autorização por recurso; recuperação de conta | Login, logout e expiração funcionam; cada rota recusa perfil sem permissão (teste automatizado por perfil × rota) | Alta | E-02, E-03 |
| REQ-002 | Persistência de solicitações: criar, listar, ver, editar, arquivar; validações de campos; anexos com limite de tipo e tamanho | Criar, listar, editar e arquivar com persistência confirmada após reinício; validações recusam dado inválido com mensagem | Alta | E-02, E-03 |
| REQ-003 | Fluxo de tramitação: status, atribuição, regras de transição, prazo por categoria e histórico | Só transições válidas são aceitas; transição inválida é bloqueada com erro claro; histórico registra cada passo | Alta | E-02, E-03 |
| REQ-004 | Consulta gerencial: filtros, contagens por status, categoria, operador e prazo; exportação CSV | Indicadores batem com os registros persistidos (teste de conciliação) | Média | E-02, E-03 |
| REQ-005 | Auditoria: log de alterações com evento, ator, data/hora, recurso, valores anteriores e novos, identificador de correlação | Toda alteração gera evento consultável por identificador; evento não pode ser editado pela API | Alta | E-02 |
| REQ-006 | API documentada e versionada (`/api/v1`), contrato OpenAPI; integrações autorizadas (notificação por e-mail, webhook) | Documentação acessível; teste ponta a ponta com serviço real ou de homologação controlada | Média | E-04 |
| REQ-007 | Infraestrutura: instalação reproduzível, configuração por ambiente, logs estruturados, pipeline de CI | Instalação limpa a partir do repositório; pipeline executa testes e registra resultado | Média | E-05 |
| REQ-008 | Backup e restauração com RTO e RPO definidos formalmente | Restauração de exercício a partir de backup em ambiente limpo, com registro de tempo | Média | E-05 |

## Requisitos não funcionais (TR seção 4)

| ID | Requisito | Como será atendido | Como será verificado |
|---|---|---|---|
| RNF-01 | Identificação e autorização de todas as operações | Dependência de autenticação em todas as rotas, matriz perfil × ação centralizada | Teste por perfil para cada rota protegida |
| RNF-02 | Proteção contra injeção, falha de autenticação, exposição de dados e dependências vulneráveis | ORM com parâmetros; senhas com PBKDF2-SHA256 (600 mil iterações) e sal; token assinado com expiração; respostas sem hash de senha; verificação de dependências no CI | Testes de autorização e de entrada maliciosa; `pip-audit` no pipeline (dia 10) |
| RNF-03 | Log estruturado com correlação | Cabeçalho `X-Correlation-ID` recebido ou gerado, gravado no log e na auditoria | Teste que segue um ID da requisição até o evento |
| RNF-04 | Backup testado, RTO e RPO formais | Rotina de backup do banco e procedimento de restauração (dia 9) | Restauração cronometrada em ambiente limpo |
| RNF-05 | Contrato de API versionado | Prefixo `/api/v1`, OpenAPI gerado e publicado em `/api/v1/openapi.json`, salvo em `docs/api/openapi-v1.json` (dia 4) | `tests/test_contrato.py`: salvo = gerado e detecção de mudança incompatível |
| RNF-06 | Arquitetura modular, migrações idempotentes, configuração por ambiente | Pacote em módulos; migrações numeradas com controle de versão no banco; variáveis `SD_*` | Teste que aplica migrações duas vezes sem erro |
| RNF-07 | Testes unitários, de integração e ponta a ponta do fluxo crítico | pytest + cliente HTTP; ponta a ponta no Chromium (`tests/test_e2e_navegador.py`, dia 6) | Log de execução anexado à medição |
| RNF-08 | Evidência com versão, commit, tempo e status de testes | `medicao/registro.py` grava início/fim reais, hash dos artefatos e commit | Relatório diário em `medicao/relatorios/` |
| RNF-09 | Acessibilidade razoável e estados de erro/carregamento | Rótulos, erros por campo com `aria-describedby`, `aria-busy`, `aria-live`, pular para o conteúdo, tabelas responsivas e focáveis, movimento reduzido | `tests/navegador/acessibilidade.js` (axe-core, WCAG 2.0/2.1 A e AA): 22 verificações sem violação grave ou crítica e sem rolagem lateral (dia 7) |

## Escopo excluído até aprovação (TR seção 5)

Integração com bases governamentais, gov.br, sistemas de produção de terceiros, infraestrutura pública e dados de cidadãos.
O desenvolvimento usa apenas dados fictícios gerados pelos testes.

## Rastreabilidade

| ID | OS | Artefato | Teste | Status |
|---|---|---|---|---|
| REQ-001 | OS-001 | `solicitacoes/seguranca.py`, `solicitacoes/dependencias.py`, telas de entrar e recuperar acesso em `solicitacoes/web/` (dia 5) | `tests/test_autenticacao.py`, `tests/test_permissoes.py`, `tests/test_web.py` | Implementado (inclui recuperação de conta: `solicitacoes/rotas_conta.py`, `tests/test_recuperacao.py`; telas verificadas no navegador, `medicao/evidencias/navegador-dia05.txt`) |
| REQ-002 | OS-001 | `solicitacoes/rotas_solicitacoes.py`, `solicitacoes/modelos.py`, telas de lista, cadastro e detalhe (dia 5) | `tests/test_solicitacoes.py`, `tests/test_categorias.py`, `tests/test_web.py` | Implementado (inclui anexos: `solicitacoes/rotas_anexos.py`, `tests/test_anexos.py`; tela de anexos verificada no navegador no dia 6) |
| REQ-003 | OS-001 | `solicitacoes/fluxo.py`, `docs/PROCESSO_TRAMITACAO.md`, telas de tramitação e histórico (dia 6) | `tests/test_fluxo.py`, `tests/test_e2e_navegador.py` | Implementado (fluxo crítico verificado no navegador) |
| REQ-004 | OS-001 | `solicitacoes/rotas_painel.py`, tela Painel (dia 7), `docs/INDICADORES.md` | `tests/test_painel.py` (conciliação com a listagem e com o CSV), `tests/test_e2e_navegador.py` | Implementado (indicadores definitivos dependem da pergunta 6 da entrevista) |
| REQ-005 | OS-001 | `solicitacoes/auditoria.py`, histórico de tramitação, telas de auditoria (dia 6) | `tests/test_auditoria.py`, `tests/test_fluxo.py`, `tests/test_e2e_navegador.py` | Implementado |
| REQ-006 | OS-001 | `solicitacoes/contrato.py`, `docs/api/openapi-v1.json` (dia 4); integrações (dias 8 a 10) | `tests/test_contrato.py`; testes de integração (dia 8) | Em execução (contrato versionado pronto; integrações planejadas) |
| REQ-007 | OS-001 | `solicitacoes/config.py`, `solicitacoes/migracoes.py` (dia 1), CI (dia 8) | `tests/test_migracoes.py` | Em execução |
| REQ-008 | OS-001 | backup e restauração (dia 9) | restauração cronometrada | Planejado |
