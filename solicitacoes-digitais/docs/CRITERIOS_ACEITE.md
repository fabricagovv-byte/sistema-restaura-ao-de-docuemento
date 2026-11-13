# Critérios de aceite detalhados — OS-001/2026 (entrega D5-B)

Situação em 12/11/2026: **critérios detalhados prontos; validação com o contratante PENDENTE.**
As respostas da entrevista (`docs/PENDENCIAS_ENTREVISTA.md`, perguntas 1 a 10) ainda não chegaram. Por isso cada critério
abaixo está marcado como **Premissa** (definido pela equipe a partir do TR) até ser confirmado ou corrigido pelo contratante.
Nada aqui foi validado por pessoa do contratante.

Formato: *Dado* (situação) · *Quando* (ação) · *Então* (resultado esperado). A coluna **Prova** aponta o teste automático
que já verifica o critério hoje; "—" quando ainda não há teste (planejado para o dia indicado).

## REQ-001 — Controle de acesso e recuperação de conta

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 001.1 | Dado um usuário ativo, quando entra com e-mail e senha corretos, então recebe sessão com validade (padrão 60 min) e vê a tela inicial do seu perfil | `test_login_eu_e_logout`; navegador dia 5 | 3 |
| 001.2 | Quando a senha está errada, o e-mail não existe ou o usuário está inativo, então a resposta é a mesma ("e-mail ou senha incorretos") e o evento fica na auditoria | `test_login_recusa_senha_errada_email_inexistente_e_inativo`, `test_login_recusado_fica_auditado` | — |
| 001.3 | Dado um token expirado, adulterado, revogado (logout) ou de antes da troca de senha, quando usado, então a API responde 401 e o frontend volta ao login com aviso | `test_token_expirado_adulterado_ou_ausente`, `test_fluxo_completo_troca_senha_e_encerra_sessoes`; navegador dia 5 | — |
| 001.4 | Para cada rota protegida e cada perfil, só os perfis da matriz de `MATRIZ_REQUISITOS.md` são atendidos; os outros recebem 403; sem token, 401 | `test_cada_perfil_so_acessa_o_que_pode`, `test_matriz_de_permissoes`, `test_todas_as_rotas_sao_versionadas_e_protegidas` | 1, 3 |
| 001.5 | A senha tem ao menos 10 caracteres com maiúsculas, minúsculas e números; é guardada com PBKDF2-SHA256 e sal | `test_politica_de_senha`, `test_hash_de_senha_tem_sal_e_confere` | 10 |
| 001.6 | O pedido de recuperação responde igual para e-mail cadastrado ou não; o link vale 30 minutos, é de uso único, no máximo 3 por hora; a troca encerra todas as sessões | `test_resposta_igual_para_email_inexistente_e_sem_mensagem`, `test_token_expirado_e_limite_de_pedidos`, `test_novo_link_invalida_os_anteriores_depois_da_troca` | 7 (envio real do e-mail: dia 8) |
| 001.7 | Usuário desativado perde a sessão na próxima requisição | `test_usuario_desativado_perde_a_sessao` | — |

## REQ-002 — Persistência de solicitações e anexos

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 002.1 | Quando o solicitante abre uma solicitação válida, então ela recebe protocolo `AAAA` + 6 dígitos, situação "recebida", prazo pela categoria e primeiro registro no histórico | `test_cria_com_protocolo_prazo_e_historico`; navegador dia 5 | 2 |
| 002.2 | Título com menos de 5 caracteres, descrição com menos de 10, categoria inexistente ou inativa e prioridade fora da lista são recusados com mensagem por campo | `test_validacoes_de_cadastro`; navegador dia 5 (mensagens em português no formulário) | 2 |
| 002.3 | O dono edita só enquanto "recebida"; o gestor até a finalização; trocar a categoria recalcula o prazo | `test_edicao_pelo_dono_so_enquanto_recebida`, `test_troca_de_categoria_recalcula_prazo_e_recusa_inativa` | 4 |
| 002.4 | Solicitação nunca é excluída; finalizada pode ser arquivada pelo gestor e deixa de tramitar | `test_nao_ha_exclusao`, `test_arquivamento_so_de_finalizadas_e_bloqueia_tramitacao` | 10 (retenção) |
| 002.5 | Lista com filtros (situação, categoria, responsável, prioridade, busca, atraso) e paginação mostra a cada perfil só o que ele pode ver | `test_filtros_busca_paginacao_e_atraso`, `test_visibilidade_por_perfil`; navegador dia 5 | 1 |
| 002.6 | Anexos: PDF, PNG, JPEG e DOCX verificados pelo conteúdo; até 10 MB e 20 por solicitação; SHA-256 conferido no download; remoção lógica por quem enviou ou pelo gestor | `test_tipo_pelo_conteudo_e_nao_pela_extensao`, `test_recusa_tipo_tamanho_vazio_e_quem_nao_pode`, `test_limite_de_anexos_por_solicitacao`, `test_arquivo_alterado_no_disco_nao_e_entregue`, `test_remocao_so_por_quem_enviou_ou_gestor` | 5 |
| 002.7 | Os dados persistem após reiniciar o serviço (PostgreSQL) | suíte inteira no PostgreSQL (`testes-diaNN.txt`); reinício cronometrado no dia 9 | 8 |

## REQ-003 — Fluxo de tramitação

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 003.1 | Só as transições de `PROCESSO_TRAMITACAO.md` são aceitas; qualquer outra é recusada (409) dizendo para onde é possível ir | `test_transicoes_invalidas_sao_bloqueadas_com_motivo`, `test_toda_transicao_declarada_tem_perfil_e_estados_validos` | 4 |
| 003.2 | Iniciar atendimento exige responsável; operador só atua no que é dele e só assume para si; gestor atribui | `test_somente_responsavel_atende_e_operador_so_assume_para_si`, `test_atribuicao_em_finalizada_e_por_perfil_sem_poder` | 4 |
| 003.3 | Indeferir, concluir, pedir complemento, cancelar e reabrir exigem comentário | `test_regras_de_fluxo_isoladas`, `test_cancelamento_pelo_solicitante_e_reabertura_pelo_gestor` | 4 |
| 003.4 | Cada passo grava histórico (quem, quando, de, para, comentário) e auditoria | `test_fluxo_completo_com_historico_e_auditoria` | — |
| 003.5 | Telas de tramitação e histórico no navegador | `test_fluxo_critico_no_navegador` (dia 6) | 4 |

## REQ-004 — Consulta gerencial

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 004.1 | As contagens por situação, categoria, responsável e prioridade batem com a listagem e com as linhas do CSV, com os mesmos filtros | `test_indicadores_conciliam_com_os_registros_e_com_o_csv`, `test_filtros_valem_igual_para_painel_e_csv` | 6 |
| 004.2 | Indicadores de prazo: abertas no prazo, atrasadas, vencendo em 48 h, atendidas no prazo e com atraso pela última conclusão; tempo médio de conclusão | `test_indicadores_de_prazo_e_tempo_medio`, `test_reaberta_e_concluida_de_novo_conta_uma_vez_pela_ultima_conclusao` | 6 |
| 004.3 | Período filtrado em dias do calendário de Brasília | `test_periodo_usa_o_dia_de_brasilia` | — |
| 004.4 | CSV abre no Excel em português, não executa fórmula vinda de texto do usuário, não leva descrição nem nome do solicitante, e cada exportação fica auditada | `test_csv_formato_minimizacao_e_auditoria`, `test_csv_neutraliza_formula_em_texto_do_usuario`, `test_exportacao_respeita_o_limite` | 6, 10 |
| 004.5 | Só o gestor vê o painel e exporta | `test_so_o_gestor_ve_e_exporta` | 1 |
| 004.6 | Painel no navegador | — (dia 7) | 6 |

## REQ-005 — Auditoria

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 005.1 | Toda alteração gera evento com ação, ator, data/hora, recurso, antes, depois e correlação, sem senha nem token | `test_alteracoes_geram_eventos_com_ator_correlacao_e_sem_senha` | 10 |
| 005.2 | A API não altera nem apaga eventos | `test_auditoria_nao_tem_rota_de_alteracao` | — |
| 005.3 | O identificador de correlação recebido (ou gerado) volta na resposta e aparece no evento | `test_correlacao_gerada_quando_ausente_e_saneada` | — |

## REQ-006 — API documentada e integrações

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 006.1 | Contrato OpenAPI em `/api/v1/openapi.json`, igual ao salvo em `docs/api/openapi-v1.json`; mudança incompatível é apontada | `test_contrato_salvo_e_o_gerado_pelo_codigo`, `test_detecta_mudancas_incompativeis`, `test_documentacao_publicada_na_versao` | — |
| 006.2 | O frontend só usa rotas que existem no contrato | `test_frontend_so_chama_rotas_do_contrato` | — |
| 006.3 | E-mail e webhook testados ponta a ponta com servidor de homologação controlado | — (dia 8) | 7 |

## REQ-007 e REQ-008 — Infraestrutura, backup e restauração

| # | Critério | Prova | Depende da pergunta |
|---|---|---|---|
| 007.1 | Migrações numeradas e idempotentes; banco antigo sobe de versão sem perder dados | `test_migracoes_sao_idempotentes`, `test_v3_atualiza_banco_criado_antes_da_coluna_de_sessao` | — |
| 007.2 | Fora de desenvolvimento, o serviço não sobe sem segredo forte | `test_producao_exige_segredo_forte` | 8 |
| 007.3 | Telas servidas com CSP sem código embutido, sem montagem de HTML a partir de texto | `test_telas_servidas_com_politica_de_seguranca`, `test_html_sem_script_ou_estilo_embutido`, `test_codigo_do_frontend_nao_monta_html_a_partir_de_texto` | 10 |
| 007.4 | Instalação limpa e pipeline de CI executando os testes | — (dia 8) | 8 |
| 008.1 | Restauração a partir do backup em ambiente limpo, cronometrada, dentro do RTO e RPO acordados | — (dia 9) | 9 |

## O que falta para validar (bloqueio desta entrega)

1. Respostas das perguntas 1 a 10 da entrevista.
2. Leitura deste documento por responsável do contratante, marcando cada critério como **aceito**, **ajustar** (com o texto
   novo) ou **fora do escopo**.
3. Indicação de quem homologa (pendência F-05).

Com isso a equipe atualiza os critérios, os testes que dependem deles e a matriz em até um dia útil.
