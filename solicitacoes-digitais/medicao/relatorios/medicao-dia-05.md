# Medição do dia 5 — OS-001/2026

Gerado em 2026-11-12T08:52:59-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D5-A | M-03 Desenvolvimento frontend | Frontend: login, perfis, lista e cadastro de solicitações, estados de erro e carregamento | 75 | 75 | 75 | 0 | 0 | 2026-11-12T08:43:10-03:00 | 2026-11-12T08:52:32-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/web/index.html` (ce6c6d892382…)<br>`solicitacoes/web/app.js` (72242ecc6564…)<br>`solicitacoes/web/app.css` (fd0f2888c47c…)<br>`solicitacoes/api.py` (6d4c44d7c446…)<br>`tests/test_web.py` (41bc14a3c0f7…)<br>`tests/navegador/verificacao-dia05.js` (67fc30f76f99…)<br>`medicao/evidencias/navegador-dia05.txt` (83cd0c969c69…) |
| D5-B | M-01 Análise de negócios e processos | Validação dos requisitos com as respostas da entrevista e critérios de aceite detalhados | 26 | 12 | 0 | 0 | 0 | 2026-11-12T08:50:25-03:00 | 2026-11-12T08:52:32-03:00 | DECLARADA | `docs/CRITERIOS_ACEITE.md` (4eb1a43f7892…) |
| **Total do dia** | | | **101** | **87** | **75** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 470 · verificadas tecnicamente 380 · homologadas 0 · saldo planejado 620 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia05.txt` (SHA-256 6533f6f872068c9e5a4f22ba5a299cd9f5adf370dfd209169a2dd4274a74570a), 2026-11-12T08:52:32-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `fdb46b3eaf5e8ba141ad493544d70e10eec2cf36`.
* Observação: frontend: entrar, recuperar acesso, nova senha pelo link, lista com filtros e paginação, cadastro, detalhe e usuários (admin); menu por perfil; estados de carregamento, vazio e erro (401, 403, 422 por campo, sem rede); CSP sem inline; verificado no navegador em 1280 e 390 px
* Commit de referência na conclusão: `fdb46b3eaf5e8ba141ad493544d70e10eec2cf36`.
* Observação: PARCIAL: 27 critérios de aceite detalhados (dado/quando/então) para REQ-001 a REQ-008, ligados a 56 testes existentes; a validação com as respostas da entrevista NÃO foi feita porque as respostas não chegaram (perguntas 1 a 10 de PENDENCIAS_ENTREVISTA.md). Declaradas 6 de 13 UST base; o restante depende do contratante
