# Medição do dia 6 — OS-001/2026

Gerado em 2026-11-13T08:49:35-03:00. **Situação contratual:** DG-CONT-001 (minuta não assinada); OS PROPOSTA — PENDENTE DE ACEITE E AUTORIZAÇÃO DE PRODUÇÃO. Nenhuma UST abaixo está homologada nem é faturável: a homologação é ato do contratante.

Executor de todas as tarefas: Claude (agente de IA da Anthropic) — execução automatizada, sem horas humanas. Horas humanas comprovadas: **0**.

| Tarefa | Serviço (catálogo proposto) | Entrega | Planejada | Declarada | Verificada | Glosada | Homologada | Início real | Fim real | Situação | Evidências (SHA-256) |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| D6-A | M-03 Desenvolvimento frontend | Frontend: tramitação, histórico, anexos e auditoria | 75 | 75 | 75 | 0 | 0 | 2026-11-13T08:43:34-03:00 | 2026-11-13T08:49:17-03:00 | VERIFICADA_TECNICAMENTE | `solicitacoes/web/app.js` (b95e222bb755…)<br>`solicitacoes/web/app.css` (fd3d0393b032…)<br>`tests/test_web.py` (c6c6a8c04d76…)<br>`medicao/evidencias/navegador-dia06.txt` (fe2673045c9c…) |
| D6-B | M-04 Testes de sistemas | Teste ponta a ponta do fluxo crítico no navegador | 24 | 24 | 24 | 0 | 0 | 2026-11-13T08:46:11-03:00 | 2026-11-13T08:49:17-03:00 | VERIFICADA_TECNICAMENTE | `tests/test_e2e_navegador.py` (68ee55a46d3f…)<br>`tests/navegador/e2e_fluxo_critico.js` (f828a9de67a9…)<br>`medicao/evidencias/navegador-dia06.txt` (fe2673045c9c…)<br>`medicao/evidencias/testes-dia06.txt` (81361b54e8a9…) |
| **Total do dia** | | | **99** | **99** | **99** | **0** | **0** | | | | |

**Acumulado da OS:** declaradas 569 · verificadas tecnicamente 479 · homologadas 0 · saldo planejado 521 de 1000 UST ajustadas.

* Verificação técnica: `medicao/evidencias/testes-dia06.txt` (SHA-256 81361b54e8a927857c1e480d220af3a9297d27793d84f930875edb29542071b3), 2026-11-13T08:49:17-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `be1fadfa832b3a4be4290273c74689b597b7048a`.
* Observação: detalhe com tramitação (só ações permitidas ao perfil), atribuição (gestor) e assumir (operador), arquivar/desarquivar, anexos (enviar, baixar, remover), linha do tempo do histórico, auditoria da solicitação e tela de auditoria com filtros; exercitado pelo teste ponta a ponta do dia
* Verificação técnica: `medicao/evidencias/testes-dia06.txt` (SHA-256 81361b54e8a927857c1e480d220af3a9297d27793d84f930875edb29542071b3), 2026-11-13T08:49:17-03:00. Revisor independente: PENDENTE — indicar pessoa da contratante.
* Commit de referência na conclusão: `be1fadfa832b3a4be4290273c74689b597b7048a`.
* Observação: fluxo crítico no Chromium com 3 perfis e 19 verificações (abertura com anexo, triagem, atribuição, atendimento, complemento com recusa sem comentário, resposta, conclusão, download, arquivamento, histórico e auditoria); roda dentro do pytest; o roteiro foi começado durante a D6-A e a D6-B foi iniciada no registro logo depois
