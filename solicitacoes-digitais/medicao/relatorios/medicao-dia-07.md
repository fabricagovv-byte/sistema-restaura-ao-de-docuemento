# Medição do dia 7 — OS-001/2026

Gerado em 2026-11-14T08:52:55-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D7-A | M-03 Desenvolvimento frontend | Frontend: painel gerencial, acessibilidade e responsividade | 75 | 75 | 75 | 0 | 0 | 2026-11-14T08:45:45-03:00 | 2026-11-14T08:52:55-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/web/app.js` (8443afa51e42…)<br>`solicitacoes/web/app.css` (a1ed4609a2f8…)<br>`tests/navegador/acessibilidade.js` (5440dcfff2de…)<br>`tests/test_e2e_navegador.py` (a6be2fd9d409…)<br>`tests/servidor_local.py` (4630117dd6b3…)<br>`medicao/evidencias/navegador-dia07.txt` (4fb55bc26693…) |
| D7-B | M-01 Análise de negócios e processos | Especificação dos indicadores e relatórios gerenciais | 20 | 20 | 0 | 0 | 0 | 2026-11-14T08:50:32-03:00 | 2026-11-14T08:52:55-03:00 | DECLARADA | `docs/INDICADORES.md` (57747e3eb876…) |
| **Total do dia** | | | **95** | **95** | **75** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 664 · verificadas tecnicamente 554 · homologadas 0 · saldo planejado 446 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia07.txt` (SHA-256 b1fb85a1a8a6460bced7d83554db446adbf0eb56919537a5a8cf3909951f2b54), 2026-11-14T08:52:55-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `2b214973176c0fc4a72efc550d6adb4e7104ce74`.
* Observação: tela Painel do gestor (filtros, 6 indicadores, 4 tabelas com barras, quadro de prazo, exportação CSV); acessibilidade verificada com axe-core em 11 telas x 2 larguras (22), sem violação grave ou crítica e sem rolagem lateral; uma violação real encontrada e corrigida (tabela rolável sem foco por teclado)
* Commit de referência na conclusão: `2b214973176c0fc4a72efc550d6adb4e7104ce74`.
* Observação: 15 indicadores especificados (definição, fórmula, campo da API e teste que prova), regras comuns (universo, período em Brasília, atendida x cancelada, finalização pela última entrada no estado final), relatório CSV e 4 relatórios propostos; implementados na API e na tela; validação com o contratante pendente (pergunta 6 da entrevista)
