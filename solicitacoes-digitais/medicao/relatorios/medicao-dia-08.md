# Medição do dia 8 — OS-001/2026

Gerado em 2026-11-15T08:59:41-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D8-A | M-05 Implantação DevOps | Contêineres, pipeline de CI e configuração por ambiente | 60 | 60 | 60 | 0 | 0 | 2026-11-15T08:43:17-03:00 | 2026-11-15T08:59:41-03:00 | VERIFICADA_TECNICAMENTE | `Dockerfile` (bb987755ad9f…)<br>`docker-compose.yml` (2086eb48abeb…)<br>`.env.exemplo` (e79fc3562d64…)<br>`docs/IMPLANTACAO.md` (69f4d00bff8c…)<br>`tests/test_implantacao.py` (b54d71e85f87…)<br>`tests/homologacao_conteineres.py` (1f16550831d4…)<br>`medicao/evidencias/implantacao-dia08.txt` (5a9d11737da6…)<br>`medicao/evidencias/ci-dia08.txt` (54750261be4f…) |
| D8-B | M-06 Integrações | Integração de notificações por e-mail (SMTP configurável) com teste em servidor de homologação local | 30 | 30 | 30 | 0 | 0 | 2026-11-15T08:43:17-03:00 | 2026-11-15T08:59:37-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/notificacoes.py` (4a2b7fe40777…)<br>`solicitacoes/rotas_mensagens.py` (dd83c957bad7…)<br>`solicitacoes/migracoes.py` (05086f6662bc…)<br>`tests/smtp_local.py` (d861ecf1cfba…)<br>`tests/test_notificacoes.py` (2e318cafffe5…)<br>`medicao/evidencias/implantacao-dia08.txt` (5a9d11737da6…) |
| D8-C | M-01 Análise de negócios e processos | Requisitos de operação: RTO, RPO e rotina de backup propostos | 10 | 10 | 0 | 0 | 0 | 2026-11-15T08:43:17-03:00 | 2026-11-15T08:59:37-03:00 | DECLARADA | `docs/OPERACAO.md` (b3510a48e18a…) |
| **Total do dia** | | | **100** | **100** | **90** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 764 · verificadas tecnicamente 644 · homologadas 0 · saldo planejado 356 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia08.txt` (SHA-256 68436d64840e0d76811f738aa39fa1b18b46ea85932d9b8f032862d2e8f0ee0b), 2026-11-15T08:59:41-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `cf12f7ccdb5fdf1ef358d1d95b4f8a75017cf8b5`.
* Verificação técnica: `medicao/evidencias/testes-dia08.txt` (SHA-256 68436d64840e0d76811f738aa39fa1b18b46ea85932d9b8f032862d2e8f0ee0b), 2026-11-15T08:59:41-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `cf12f7ccdb5fdf1ef358d1d95b4f8a75017cf8b5`.
* Commit de referência na conclusão: `cf12f7ccdb5fdf1ef358d1d95b4f8a75017cf8b5`.
* Observação: Proposta de RTO, RPO e rotina para decisão do contratante (pergunta 9); não validada
