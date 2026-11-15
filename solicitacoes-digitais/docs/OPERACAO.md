# Requisitos de operação: RTO, RPO e rotina de backup — OS-001/2026 (entrega D8-C, REQ-007 e REQ-008)

Situação em 15/11/2026: **proposta da equipe, não validada.** RTO e RPO são decisão do contratante (pergunta 9 de
`PENDENCIAS_ENTREVISTA.md`). Os números abaixo são o ponto de partida sugerido para um sistema de solicitações de
porte municipal; a restauração cronometrada do dia 9 vai medir se a rotina cumpre o que está proposto.

## 1. Definições

* **RPO** (ponto de recuperação): quanto dado, no máximo, pode ser perdido — o intervalo entre o último backup
  utilizável e a falha.
* **RTO** (tempo de recuperação): em quanto tempo o sistema volta a atender depois da falha, contado do acionamento da
  equipe até a API responder `/api/v1/saude` com os dados restaurados.

## 2. Proposta

| Cenário | RPO proposto | RTO proposto | Como |
|---|---|---|---|
| Perda do servidor (banco e anexos) | **24 horas** no nível básico; **15 minutos** no nível recomendado | **4 horas** em horário de expediente | básico: cópia diária; recomendado: cópia diária + arquivamento contínuo do WAL do PostgreSQL |
| Erro humano (exclusão, alteração indevida) | o mesmo do nível adotado | 4 horas | restauração em ambiente separado e cópia do que se perdeu; a API não exclui solicitações (REQ-002) e a auditoria guarda antes/depois |
| Queda só da API | 0 (dados intactos) | 15 minutos | reiniciar o contêiner; a subida reaplica migrações idempotentes |
| Queda do servidor de e-mail | 0 (mensagens ficam na caixa de saída) | não afeta o atendimento | novas tentativas em 1, 5, 15 e 60 minutos (D8-B) |

## 3. O que precisa de backup

| Item | Onde | Como | Observação |
|---|---|---|---|
| Banco PostgreSQL | volume `banco` | `pg_dump --format=custom` diário (e WAL contínuo no nível recomendado) | contém solicitações, histórico, auditoria, usuários (hash de senha) e caixa de saída |
| Anexos | volume `anexos` | cópia diária dos arquivos (são imutáveis: nome único e SHA-256 conferido no download) | o banco guarda o hash; a restauração confere arquivo a arquivo |
| Configuração | `.env` do ambiente | guardado fora do servidor, em cofre de segredos | sem ele não se decifram as sessões (SD_SEGREDO) nem se acessa o banco |
| Imagem | registro de imagens | versão marcada (`SD_VERSAO_IMAGEM`) | reconstrução também possível a partir do repositório |

## 4. Rotina proposta

1. **Diária, 02:00 (Brasília):** `pg_dump` + cópia dos anexos para armazenamento **em outro local** (outra máquina ou
   nuvem do órgão), cifrado.
2. **Retenção:** 7 diárias, 4 semanais, 12 mensais (ajustar à tabela de temporalidade e à LGPD — pergunta 10).
3. **Conferência automática** depois de cada cópia: tamanho maior que zero, `pg_restore --list` lê o arquivo e a contagem
   de anexos bate com a tabela `anexo`; falha gera alerta.
4. **Exercício de restauração mensal** em ambiente limpo, cronometrado, com registro do tempo e do ponto restaurado
   (o primeiro é a entrega do dia 9).
5. **Monitoramento:** `/api/v1/saude` a cada minuto; o serviço `mensagens` sai com código 1 quando o SMTP não responde
   no modo de execução única, para o monitoramento acusar.

## 5. Comandos de referência (compose deste repositório)

```bash
# cópia do banco
docker compose exec -T banco pg_dump -U sd -d solicitacoes --format=custom > backup-$(date +%F).dump
# cópia dos anexos
docker run --rm -v solicitacoes_anexos:/dados:ro -v "$PWD":/destino alpine tar czf /destino/anexos-$(date +%F).tgz -C /dados .
# restauração (ambiente limpo)
docker compose up -d banco
docker compose exec -T banco pg_restore -U sd -d solicitacoes --clean --if-exists < backup-AAAA-MM-DD.dump
```

O script automatizado com conferência e a medição real de RTO e RPO são a entrega do dia 9 (REQ-008).

## 6. Para o contratante decidir

1. Qual RPO é aceitável: 24 horas (mais simples) ou 15 minutos (exige arquivamento de WAL e armazenamento contínuo)?
2. Qual RTO, e em que horário a equipe é acionada (só expediente ou 24×7)?
3. Onde guardar as cópias (fora do servidor principal) e por quanto tempo?
4. Quem executa e confere o exercício mensal de restauração?
