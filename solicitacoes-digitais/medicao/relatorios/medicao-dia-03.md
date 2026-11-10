# Medição do dia 3 — OS-001/2026

Gerado em 2026-11-10T08:48:27-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D3-A | M-02 Desenvolvimento backend | Anexos com verificação de tipo e tamanho, recuperação de conta, log estruturado com correlação | 60 | 60 | 60 | 0 | 0 | 2026-11-10T08:42:45-03:00 | 2026-11-10T08:45:47-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/rotas_anexos.py` (f75b29c5671f…)<br>`solicitacoes/rotas_conta.py` (58111bd087c3…)<br>`solicitacoes/migracoes.py` (598686b9448b…)<br>`solicitacoes/modelos.py` (9ab31d538e26…)<br>`tests/test_anexos.py` (2fef2c9ae7f0…)<br>`tests/test_recuperacao.py` (017d0d16d5f3…)<br>`tests/test_migracoes.py` (87ccfb12bce2…) |
| D3-B | M-04 Testes de sistemas | Testes unitários e de integração do backend com relatório de cobertura | 40 | 40 | 40 | 0 | 0 | 2026-11-10T08:45:47-03:00 | 2026-11-10T08:48:11-03:00 | VERIFICADA_TECNICAMENTE | `tests/test_cobertura_regras.py` (695a01a502f2…)<br>`tests/test_anexos.py` (2fef2c9ae7f0…)<br>`tests/test_recuperacao.py` (017d0d16d5f3…)<br>`medicao/evidencias/cobertura-dia03.txt` (1c7ea36658c7…)<br>`medicao/evidencias/testes-dia03.txt` (a873aa13a053…) |
| **Total do dia** | | | **100** | **100** | **100** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 283 · verificadas tecnicamente 205 · homologadas 0 · saldo planejado 795 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia03.txt` (SHA-256 a873aa13a05384e8ceeee7a96130b6508e089389e61484ae67a37e55b53c5fe6), 2026-11-10T08:47:57-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `0010bb9f01a745837d27e3f2a9328d0b8c930924`.
* Observação: O log estruturado com correlação, previsto nesta entrega, foi entregue no dia 1 sem contagem e é contado aqui conforme o plano. O envio real do e-mail de recuperação depende da integração SMTP (dia 8); até lá a mensagem fica na caixa de saída.
* Verificação técnica: `medicao/evidencias/testes-dia03.txt` (SHA-256 a873aa13a05384e8ceeee7a96130b6508e089389e61484ae67a37e55b53c5fe6), 2026-11-10T08:48:11-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `2b4717008a2585cd0d04d65fff7582886ff92c58`.
* Observação: Cobertura de linhas e desvios do backend de 90% para 98% (64 testes).
