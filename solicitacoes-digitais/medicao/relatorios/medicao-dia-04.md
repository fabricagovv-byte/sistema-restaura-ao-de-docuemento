# Medição do dia 4 — OS-001/2026

Gerado em 2026-11-11T16:43:16-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D4-A | M-02 Desenvolvimento backend | Painel gerencial (filtros, contagens, exportação CSV) e contrato de API versionado e documentado | 60 | 60 | 60 | 0 | 0 | 2026-11-11T16:35:07-03:00 | 2026-11-11T16:42:48-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/rotas_painel.py` (2c93b98db97e…)<br>`solicitacoes/contrato.py` (d4f59eefba22…)<br>`docs/api/openapi-v1.json` (f22de4c66890…)<br>`solicitacoes/migracoes.py` (31f1eba3d9be…)<br>`solicitacoes/seguranca.py` (1b1de470046f…)<br>`solicitacoes/api.py` (2b0d5d95cffb…) |
| D4-B | M-04 Testes de sistemas | Testes do painel, da exportação e do contrato da API | 40 | 40 | 40 | 0 | 0 | 2026-11-11T16:38:05-03:00 | 2026-11-11T16:42:48-03:00 | VERIFICADA_TECNICAMENTE | `tests/test_painel.py` (e1f592740f7d…)<br>`tests/test_contrato.py` (8c949c4ae006…)<br>`tests/test_permissoes.py` (ab61daea8057…)<br>`medicao/evidencias/testes-dia04.txt` (31d22e767080…)<br>`medicao/evidencias/cobertura-dia04.txt` (a8cb091a5ffc…) |
| **Total do dia** | | | **100** | **100** | **100** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 383 · verificadas tecnicamente 305 · homologadas 0 · saldo planejado 695 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia04.txt` (SHA-256 31d22e767080addfcc82944788acd36015c9009102907affea8b4d8391d76995), 2026-11-11T16:42:48-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `a213f3daa2fafcf03530384594a7b83a6ceed507`.
* Observação: painel com indicadores por status, prioridade, categoria, responsável e prazo; exportação CSV auditada; contrato OpenAPI v1 salvo e verificável; migração v4 (índices)
* Verificação técnica: `medicao/evidencias/testes-dia04.txt` (SHA-256 31d22e767080addfcc82944788acd36015c9009102907affea8b4d8391d76995), 2026-11-11T16:42:48-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `a213f3daa2fafcf03530384594a7b83a6ceed507`.
* Observação: 23 testes novos (painel 14, contrato 7, matriz perfil x rota 2); 87 aprovados no SQLite e no PostgreSQL; cobertura 99%
