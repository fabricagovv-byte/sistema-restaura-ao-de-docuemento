# Medição do dia 2 — OS-001/2026

Gerado em 2026-11-05T12:04:25-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D2-A | M-02 Desenvolvimento backend | Cadastro de solicitações (CRUD, arquivamento, validações), tramitação com transições válidas, atribuição e auditoria | 66 | 66 | 66 | 0 | 0 | 2026-11-05T12:00:02-03:00 | 2026-11-05T12:03:40-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/rotas_solicitacoes.py` (6a996379a965…)<br>`solicitacoes/fluxo.py` (1dca17c2f4b1…)<br>`solicitacoes/modelos.py` (05aa6d385819…)<br>`solicitacoes/migracoes.py` (b41d26f559ff…)<br>`tests/test_fluxo.py` (e5015f57261d…)<br>`tests/test_solicitacoes.py` (90874bbeb53e…)<br>`tests/test_categorias.py` (d76f23fccb4a…) |
| D2-B | M-01 Análise de negócios e processos | Modelagem do processo de tramitação: estados, regras, prazos e papéis | 34 | 28 | 0 | 0 | 0 | 2026-11-05T12:03:40-03:00 | 2026-11-05T12:04:25-03:00 | DECLARADA | `docs/PROCESSO_TRAMITACAO.md` (34207a0e3ac7…)<br>`docs/MATRIZ_REQUISITOS.md` (5c363c8a33b7…) |
| **Total do dia** | | | **100** | **94** | **66** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 183 · verificadas tecnicamente 105 · homologadas 0 · saldo planejado 895 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia02.txt` (SHA-256 0737feb6e98d6f473d9c8d18601b7d8f32122b6ffd8a57774696b275fc32cd8f), 2026-11-05T12:04:01-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `039a0b89df2caa515c349816818f75aa098f69ac`.
* Commit de referência na conclusão: `039a0b89df2caa515c349816818f75aa098f69ac`.
* Observação: Processo modelado a partir do código; 3 UST base ficam para a validação dos prazos e da pausa do prazo na entrevista.
