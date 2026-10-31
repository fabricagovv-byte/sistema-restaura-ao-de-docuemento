# Operação em produção

## Antes de abrir para usuários

1. `LIC_JWT_SEGREDO` com 32+ caracteres aleatórios (a API avisa no log se ficar o padrão).
2. Senhas próprias para PostgreSQL e MinIO no `docker-compose.yml`.
3. HTTPS na frente (Caddy, Nginx ou o balanceador da nuvem) para a API (8000) e o painel (3000).
   Restrinja `allow_origins` do CORS em `api.py` ao domínio do painel.
4. Rede de saída liberada para as fontes (ver docs/fontes.md) e para `api.anthropic.com`.
5. Primeiro usuário: `python -m licitacoes.cli criar-usuario ... --papel admin`.

## Rotinas

| Quando | O que roda | Onde ver |
|---|---|---|
| A cada 15 min | PNCP: publicados e alterados hoje; alertas | tabela `sincronizacao`, painel de qualidade |
| A cada 6 h | PNCP: todas as propostas abertas | idem |
| 06h10 | PNCP dos últimos 3 dias, conferência individual, Compras.gov, diários, espelhos, Transparência | idem |

## Monitoramento

* `GET /saude` para o health check do balanceador.
* `GET /qualidade`: fontes com falha, falhas consecutivas, último erro, editais atualizados em 24 h.
  Alarme sugerido: `falhas_consecutivas >= 3` em qualquer fonte ativa.
* Logs em formato texto no stdout (`docker compose logs -f api worker agendador`).
* Cada execução de fonte fica em `sincronizacao` (lidos, novos, atualizados, chamadas, mensagem de erro).

## Backup

```bash
docker compose exec postgres pg_dump -U licit -Fc licitacoes > backup-$(date +%F).dump   # diário
docker compose exec minio mc mirror /data /backup/arquivos                                  # documentos
```

Restauração: `pg_restore -U licit -d licitacoes --clean backup.dump`.

## Segurança e LGPD

* Senhas com PBKDF2-SHA256 (310 mil iterações); sessão JWT de 12 h; papéis admin, analista e leitor.
* `log_auditoria` registra login, sincronizações, análises, downloads de ZIP e preparo de editais.
* Os dados coletados são públicos (atos de licitação). Dados pessoais que aparecem neles (nome de
  servidor, publicador) são usados só para o fim de acompanhar contratações; não são exportados nem
  cruzados. O campo `usuarioNome` do PNCP é guardado no registro bruto e não é exibido.
* O conteúdo dos editais vai para a API da Anthropic quando alguém pede a análise. Avise os usuários.

## Custos da IA

Um edital típico (60 a 150 páginas somando edital, TR e anexos) tem de 50 mil a 150 mil tokens de entrada.
Com `claude-opus-5-5` (US$ 4 por milhão de tokens de entrada e US$ 20 por milhão de saída), cada
análise custa da ordem de US$ 0,30 a 1,00; reanálises do mesmo edital leem o texto do cache. O uso de
tokens de cada análise fica em `analise.uso_tokens`. Para baixar o custo: `LIC_IA_ESFORCO=medium` ou
`LIC_IA_MODELO=claude-sonnet-5-5`, medindo a qualidade antes.
