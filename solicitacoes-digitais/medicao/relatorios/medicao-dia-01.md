# Medição do dia 1 — OS-001/2026

Gerado em 2026-11-05T11:54:13-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D1-A | M-01 Análise de negócios e processos | E-01: matriz de requisitos, arquitetura e pendências de entrevista | 60 | 50 | 0 | 0 | 0 | 2026-11-05T11:49:29-03:00 | 2026-11-05T11:50:24-03:00 | DECLARADA | `docs/MATRIZ_REQUISITOS.md` (b298e6594431…)<br>`docs/ARQUITETURA.md` (c4551f7c94aa…)<br>`docs/PENDENCIAS_ENTREVISTA.md` (8a9e8902a90a…) |
| D1-B | M-02 Desenvolvimento backend | Banco com migrações idempotentes, configuração por ambiente, autenticação, perfis e autorização | 39 | 39 | 39 | 0 | 0 | 2026-11-05T11:50:24-03:00 | 2026-11-05T11:53:49-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/api.py` (f196bf3b4614…)<br>`solicitacoes/seguranca.py` (07107f60ec54…)<br>`solicitacoes/migracoes.py` (855274cc053a…)<br>`solicitacoes/modelos.py` (f29e74b543c8…)<br>`solicitacoes/auditoria.py` (c525fba7c2b0…)<br>`solicitacoes/config.py` (965c975d2932…)<br>`medicao/evidencias/execucao-servidor-dia01.txt` (de14ae4b4e8e…) |
| **Total do dia** | | | **99** | **89** | **39** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 89 · verificadas tecnicamente 39 · homologadas 0 · saldo planejado 961 de 1000 UST ajustadas.

* Commit de referência na conclusão: `df796a1e864f869cb5795920a48937e78831fede`.
* Observação: Matriz, arquitetura e pendências entregues; 5 UST base ficam para depois da entrevista obrigatória, que ainda não ocorreu. Entrega documental: a verificação técnica exige revisão por pessoa da contratante (testes de código não a verificam).
* Verificação técnica: `medicao/evidencias/testes-dia01.txt` (SHA-256 fafa5bbe6d5d94fdc71ceea34efb1b98e7906e87c9159284f24aa224bb20f604), 2026-11-05T11:53:49-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `b0cb84fe331f707f87335abeb361d8e5ddfe3490`.
* Observação: Também entregue antes do previsto: auditoria com correlação e log estruturado (previstos para os dias 2 e 3), sem contagem adicional.
