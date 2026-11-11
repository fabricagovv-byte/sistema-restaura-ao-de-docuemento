# Entrevista obrigatória e pendências formais

O pacote exige entrevista e aprovação antes de produção faturável. Até as respostas chegarem, a execução segue com
as premissas abaixo, registradas como tal. Nada aqui foi inventado como fato.

## Formalização (bloqueia homologação e faturamento)

| # | Pendência | Situação |
|---|---|---|
| F-01 | Contrato DG-CONT-001 assinado pelas partes | Minuta não assinada |
| F-02 | OS-001 aprovada ("Autoriza-se a produção desta OS? SIM"), com data e hora de início | Pendente |
| F-03 | Catálogo de serviços, UST base e fatores aceitos por escrito | Proposta da OS (base 390, ajustadas 1.000) |
| F-04 | Preço por UST, regras de reajuste e tributos | Não informado |
| F-05 | Responsável pela homologação e revisor independente da contratante | Não indicado |
| F-06 | Equipe humana: 7 nomes propostos e 3 vagas; CPF protegido | Nenhuma hora humana registrada; produção atual é de agente de IA |
| F-07 | Prazo: o pedido original (04/11/2026, 18h) já passou; ritmo proposto de 100 UST ajustadas por dia em 10 dias | Precisa de aceite |

## Perguntas de negócio (afetam requisitos)

1. Quem é o contratante e qual o público dos solicitantes (cidadãos, servidores, empresas)?
2. Quais categorias de solicitação existem e qual o prazo de atendimento de cada uma?
3. O solicitante precisa de login próprio ou pode abrir solicitação só com e-mail e número de protocolo?
4. Quais estados e transições a organização já usa? O fluxo proposto em `ARQUITETURA.md` serve?
5. Que anexos são aceitos (tipos, tamanho máximo, quantidade) e por quanto tempo devem ser guardados?
6. Quais indicadores o gestor acompanha hoje e em que formato exporta?
7. Integrações autorizadas: servidor de e-mail, sistema de protocolo, gov.br? Com quais credenciais e ambientes de homologação?
8. Onde o sistema vai rodar (nuvem, data center próprio) e quem opera?
9. RTO e RPO desejados para backup e restauração?
10. Política de segurança e LGPD: encarregado de dados, retenção, bases legais?

## Premissas adotadas até a entrevista

* Quatro papéis do TR (administrador, operador, gestor, solicitante), com login para todos.
* Fluxo de estados de `ARQUITETURA.md`.
* Anexos: PDF, PNG, JPEG e DOCX até 10 MB cada (dia 3).
* Painel (dia 4): indicadores por status, prioridade, categoria, responsável e prazo, só para o gestor; prazo do atendimento
  medido até a conclusão ou o indeferimento (cancelamento pelo solicitante fica fora do percentual). Responde em parte a
  pergunta 6: falta confirmar os indicadores que o gestor já usa e se precisa de outros recortes (unidade, canal).
* Exportação CSV (dia 4): separador ponto e vírgula, UTF-8 com BOM, até 50 mil linhas, **sem a descrição e sem o nome do
  solicitante** (só o identificador), por minimização de dados pessoais. Confirmar com o encarregado de dados (pergunta 10)
  se o gestor pode exportar o nome.
* Execução em contêiner com PostgreSQL; desenvolvimento e testes com SQLite.
* Nenhuma integração externa real sem credenciais e autorização formal; testes com servidores locais de homologação.
