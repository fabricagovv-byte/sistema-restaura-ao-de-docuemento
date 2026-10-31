# Fontes de dados

A Lei 14.133/2021 (arts. 54 e 174) obriga todos os entes a publicar seus editais no PNCP, inclusive
os que disputam em plataformas privadas (BLL, Portal de Compras Públicas, Licitanet, BNC, BBMNET,
Licitações-e). Por isso o PNCP é a espinha dorsal, e as outras fontes cobrem o que ele não tem:
contratações antigas (Lei 8.666), avisos que só saem em diário oficial e dados complementares.

## Situação de cada fonte

| Fonte | Conector | Situação | Impedimento | O que fazer |
|---|---|---|---|---|
| PNCP — API de consulta e integração | `conectores/pncp.py` | Pronto e testado com respostas reais gravadas | Rede desta sessão bloqueia `pncp.gov.br` (HTTP 403 do proxy) | Liberar `pncp.gov.br` na rede do servidor |
| Compras.gov.br — Dados Abertos | `conectores/outras.py` | Pronto, nomes de campo do Swagger público | Não validado ao vivo (rede bloqueada) | Liberar `dadosabertos.compras.gov.br` e rodar `LIC_TESTES_AO_VIVO=1 pytest tests/test_ao_vivo.py` |
| Portal da Transparência (CGU) | `conectores/outras.py` | Pronto | Exige chave | Cadastrar e-mail em portaldatransparencia.gov.br/api-de-dados/cadastrar-email; definir `LIC_TRANSPARENCIA_CHAVE` e `LIC_TRANSPARENCIA_ORGAOS` (códigos SIAFI) |
| Querido Diário (diários municipais) | `conectores/outras.py` | Pronto | Rede bloqueada nesta sessão | Liberar `queridodiario.ok.org.br` (o endereço antigo `api.queridodiario.ok.org.br` recusa TLS) |
| IBGE (municípios) | `conectores/outras.py` | **Funcionando** pela cópia pública (MIT) quando a API do IBGE não responde | API do IBGE bloqueada aqui | Liberar `servicodados.ibge.gov.br` (opcional) |
| Espelhos do PNCP no GitHub | `conectores/outras.py` | **Funcionando ao vivo** | Cobrem sobretudo SP, MG, PR e RJ (é o recorte de quem mantém) | Usar como contingência; o PNCP direto cobre o país todo |
| Diário Oficial da União (INLABS) | — | Não implementado | Exige cadastro no INLABS | Avisos federais já chegam pelo PNCP; implementar se precisar do DOU em si |
| Diários oficiais estaduais | — | Não implementado | Cada imprensa oficial tem um formato | Integrar por estado, conforme prioridade |
| Licitações-e, Portal de Compras Públicas, BLL, Licitanet, BBMNET, BEC-SP, Compras MG, SIGA RJ… | via PNCP | **Funcionando via PNCP**: a plataforma é identificada pelo link de origem | Sem API pública aberta; não raspamos portais com login | Nada; o painel de qualidade mostra quantos editais vieram de cada plataforma |
| Estatais em portal próprio (Petronect, Caixa, BB) — Lei 13.303 | — | Não integrado | Exigem cadastro de fornecedor | Cadastrar a empresa em cada portal; integrar o que tiver API |

Não contornamos CAPTCHA, login nem bloqueio. Um 401/403 vira `AcessoNegado`, e o documento fica
marcado como "requer autenticação" no ZIP e no painel.

## Coletor remoto

Quando o servidor da plataforma não alcança as fontes (como o ambiente onde ela foi construída), o
workflow `coletor-licitacoes.yml` faz a coleta no GitHub Actions e publica um pacote no branch
`dados-licitacoes`; `cli importar-coleta` traz tudo para o banco local, mantendo a fonte original de
cada edital, as execuções de cada fonte (para o painel de qualidade) e o texto dos documentos com o
número de página original (para a análise com IA). Repositório público: os minutos do Actions são
gratuitos e os dados publicados são públicos (atos oficiais).

## Comportamento do PNCP (medido em chamadas reais, out/2026)

Registrado pelo projeto público [Radar-PNCP](https://github.com/victor-ozores/Radar-PNCP) (MIT) e
confirmado nos dados gravados:

* Sem autenticação. Datas em `AAAAMMDD`; ISO devolve 422.
* `codigoModalidadeContratacao` é obrigatório em `/publicacao` e `/atualizacao`.
* `tamanhoPagina` de 10 a 50. Sem registros: 204 sem corpo.
* Excesso de chamadas: 429 com corpo HTML e sem `Retry-After`. 4 s entre chamadas evita o bloqueio;
  o cliente espera 30, 60 e 120 s se ele vier.
* Edital excluído: 410 na consulta individual, e some das listagens sem aviso. A conferência diária
  marca como excluído.
* Prorrogações são frequentes e a listagem demora horas para refletir. Por isso a rotina lê
  `/contratacoes/atualizacao` e confere individualmente os editais que vencem em até 3 dias.
* Valor não informado chega como 0; tratamos como "sem valor divulgado" (inclui orçamento sigiloso, art. 24).
* O mesmo edital às vezes é publicado duas vezes (cerca de 3%); as republicações são ligadas ao original.

Volume de referência (16/10/2026, Brasil): ~1.600 pregões eletrônicos e ~250 concorrências eletrônicas
publicados num dia. A 4 s por chamada e 50 por página, o ciclo de 15 min do dia corrente leva poucos
minutos; a carga de propostas abertas leva cerca de 1 hora.

## Precisão da classificação (medida nos 18.779 editais reais)

A primeira versão da busca por "fábrica de software" trazia "esquadrias" (o termo "squad"), e
"digitalização" trazia locação de impressoras multifuncionais. Ajustes feitos e cobertos por teste:

* termos curtos casam só palavra inteira (`" squad "`, `" ust "`, `" bim "`, `" etl "`);
* termos de exclusão por categoria (ex.: "outsourcing de impressão" tira um edital de "digitalização");
* termos ambíguos ("manutenção do sistema", "migração de dados", "processamento de dados") só contam
  com uma palavra de contexto (software, sistema informatizado, banco de dados…).

Resultado: "digitalização" foi de 27 para 6 editais abertos, todos de gestão documental; "fábrica de
software" de 20 para 2 relevantes. Categorias novas e termos podem ser cadastrados pela API
(`POST /categorias`) sem mexer no código; `cli reclassificar` reaplica a todos.

## Cobertura comprovada

O painel de qualidade calcula: municípios com ao menos um edital coletado nos últimos 90 dias ÷
municípios da lista do IBGE. Com os espelhos públicos: **1.683 de 5.571 municípios (30,2%)**, concentrados
em MG (692 de 853), PR (378 de 399), SP (500 de 645) e RJ (80 de 92). Esse número só sobe para o país
inteiro com o acesso direto ao PNCP. A plataforma não declara cobertura que não consegue medir.

## O que falta

* Liberar a rede para `pncp.gov.br`, `dadosabertos.compras.gov.br`, `queridodiario.ok.org.br` e
  `servicodados.ibge.gov.br` e rodar os testes ao vivo.
* `ANTHROPIC_API_KEY` para a análise com IA (testada com cliente simulado).
* Credenciais de SMTP e do WhatsApp Business (Cloud API da Meta, com template aprovado) para os alertas.
* Conectores do DOU (INLABS) e de diários estaduais.
* Os caminhos de OpenSearch, pgvector (embeddings) e S3/MinIO estão escritos, mas não foram executados
  aqui (sem esses serviços nesta sessão); o docker-compose sobe todos eles.
* Notificação push nativa (Web Push/FCM): hoje sai por webhook, que serve para ntfy, OneSignal ou FCM.
