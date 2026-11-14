# Especificação dos indicadores e relatórios gerenciais — OS-001/2026 (entrega D7-B, REQ-004)

Situação em 14/11/2026: **especificação proposta**, implementada na API (`GET /api/v1/painel/indicadores`,
`GET /api/v1/painel/exportacao.csv`) e na tela **Painel** do gestor. Os indicadores que o gestor do contratante já usa
(pergunta 6 de `PENDENCIAS_ENTREVISTA.md`) ainda não foram informados; tudo aqui é **premissa** até a validação.

## 1. Regras comuns

| Regra | Definição |
|---|---|
| Universo | Solicitações gravadas no banco. Por padrão, **sem as arquivadas** (`arquivadas=excluir`); `incluir` soma as arquivadas e `somente` mostra só elas. |
| Período | `de` e `ate` são dias do calendário de **Brasília**, inclusivos, aplicados à **data de abertura** (`criado_em`). O banco guarda UTC. |
| Filtros | Situação, categoria, responsável (ou "sem responsável"), prioridade e arquivadas. Os mesmos filtros valem para os indicadores e para o CSV. |
| Aberta | Situação diferente de concluída, indeferida e cancelada. |
| Atendida | Concluída ou indeferida. A cancelada pelo solicitante **não** entra no indicador de prazo (não foi atendida nem recusada pelo órgão). |
| Momento da finalização | Data e hora da **última** entrada no estado final atual, lida no histórico. Uma solicitação reaberta e concluída de novo conta uma vez, pela última conclusão. |
| Prazo | `prazo_em` = abertura + prazo da categoria em dias corridos. Ao trocar a categoria, o prazo é recalculado. |
| Conciliação | Toda contagem precisa bater com a listagem da API e com as linhas do CSV, com os mesmos filtros. |
| Acesso | Só o perfil **gestor** (`painel:ver`, `painel:exportar`). |

## 2. Indicadores

| # | Indicador | Fórmula | Campo na API | Prova automática |
|---|---|---|---|---|
| I-01 | Total de solicitações | quantidade no universo filtrado | `total` | `test_indicadores_conciliam_com_os_registros_e_com_o_csv` |
| I-02 | Em aberto | quantidade com situação aberta | `abertas` | idem |
| I-03 | Por situação | quantidade por situação, as 7 sempre presentes (zero quando não houver) | `por_status` | idem |
| I-04 | Por prioridade | quantidade por prioridade (baixa, normal, alta, urgente) | `por_prioridade` | idem |
| I-05 | Por categoria | total e em aberto por categoria, do maior para o menor | `por_categoria` | idem |
| I-06 | Por responsável | total, em aberto e atrasadas por responsável; "Sem responsável" primeiro | `por_responsavel` | idem |
| I-07 | Abertas no prazo | abertas com `prazo_em` ≥ agora | `prazo.abertas_no_prazo` | `test_indicadores_de_prazo_e_tempo_medio` |
| I-08 | Abertas atrasadas | abertas com `prazo_em` < agora | `prazo.abertas_atrasadas` | idem |
| I-09 | Vencem em 48 horas | abertas com agora ≤ `prazo_em` < agora + 48 h | `prazo.vencem_em_48h` | idem |
| I-10 | Atendidas no prazo | atendidas com finalização ≤ `prazo_em` | `prazo.atendidas_no_prazo` | idem e `test_reaberta_e_concluida_de_novo_conta_uma_vez_pela_ultima_conclusao` |
| I-11 | Atendidas com atraso | atendidas com finalização > `prazo_em` | `prazo.atendidas_com_atraso` | idem |
| I-12 | % atendidas no prazo | I-10 ÷ (I-10 + I-11) × 100, uma casa decimal; vazio quando não houver atendida | `prazo.percentual_atendidas_no_prazo` | `test_indicadores_de_prazo_e_tempo_medio`, `test_painel_vazio` |
| I-13 | Canceladas | quantidade cancelada pelo solicitante | `prazo.canceladas` | `test_indicadores_de_prazo_e_tempo_medio` |
| I-14 | Sem prazo | quantidade sem `prazo_em` (dados antigos ou importados) | `prazo.sem_prazo` | idem |
| I-15 | Tempo médio até concluir | média, em horas, de (finalização − abertura) das **concluídas** | `tempo_medio_conclusao_horas` | idem |

Na tela, o tempo médio aparece em horas até 48 h e em dias acima disso. Cada tabela mostra o número escrito e uma
barra apenas visual, para leitura por leitor de tela e impressão.

## 3. Relatório exportado (CSV)

| Item | Especificação |
|---|---|
| Rota | `GET /api/v1/painel/exportacao.csv` com os mesmos filtros do painel |
| Formato | UTF-8 com BOM, separador `;`, quebra de linha CRLF (abre direto no Excel em português) |
| Colunas | `protocolo; titulo; categoria; status; prioridade; solicitante_id; responsavel; criado_em; prazo_em; finalizada_em; situacao_prazo; arquivada` |
| Datas | `dd/mm/aaaa hh:mm`, horário de Brasília |
| `situacao_prazo` | `no_prazo`, `atrasada`, `atendida_no_prazo`, `atendida_com_atraso`, `cancelada` ou `sem_prazo` (mesmas regras de I-07 a I-14) |
| Dados pessoais | Sem descrição e sem nome do solicitante (só o identificador). Nome do responsável (servidor do órgão) sai. **Confirmar com o encarregado de dados** (pergunta 10). |
| Segurança | Célula que começa com `=`, `+`, `-`, `@`, tabulação ou retorno ganha apóstrofo (planilha não executa fórmula vinda do usuário) |
| Limite | 50 mil linhas por arquivo; acima disso a API pede para restringir o período |
| Auditoria | Cada exportação gera evento `exportar` com filtros, quantidade de linhas, SHA-256 do arquivo e correlação |
| Provas | `test_csv_formato_minimizacao_e_auditoria`, `test_csv_neutraliza_formula_em_texto_do_usuario`, `test_exportacao_respeita_o_limite` |

## 4. Relatórios propostos para validar na entrevista (não implementados)

| Relatório | Para quê | Depende de |
|---|---|---|
| Mensal de atendimento por categoria (PDF) | Prestação de contas à direção | Pergunta 6 (formato usado hoje) |
| Produtividade por responsável (volume, prazo, tempo médio) | Gestão da equipe | Pergunta 6 e política de RH do órgão |
| Solicitações paradas há mais de N dias sem movimento | Cobrança de pendências | Valor de N pelo contratante |
| Série histórica semanal de abertas × atendidas | Ver tendência | Pergunta 6 |

## 5. Para validar com o contratante

1. Estes indicadores atendem? Faltam recortes (unidade, canal de entrada, bairro)?
2. O prazo deve ser em dias corridos (atual) ou úteis, com feriados de qual calendário?
3. Cancelada pelo solicitante fica mesmo fora do % no prazo?
4. O gestor pode exportar o nome do solicitante?
5. Quais dos relatórios da seção 4 entram e em que formato?
