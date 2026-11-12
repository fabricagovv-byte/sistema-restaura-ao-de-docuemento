#!/bin/sh
# Importa o último pacote do coletor (branch dados-licitacoes do GitHub). Agendar no cron do servidor a cada 6 horas:
#   17 */6 * * * cd /opt/licitacoes/plataforma-licitacoes && sh producao/atualizar-dados.sh >> producao/atualizar.log 2>&1
set -eu
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$AQUI/.." && pwd)"
PACOTE="$REPO/.pacote-licitacoes"
DC="docker compose -f $AQUI/docker-compose.yml -f $AQUI/docker-compose.producao.yml --env-file $AQUI/producao/.env"
cd "$REPO"
git fetch -q origin dados-licitacoes
git worktree remove --force "$PACOTE" 2>/dev/null || true
git worktree prune
git worktree add -q --detach "$PACOTE" FETCH_HEAD
$DC cp "$PACOTE/." api:/tmp/pacote
$DC exec -T api python -m licitacoes.cli importar-coleta /tmp/pacote
git worktree remove --force "$PACOTE"
echo "importado em $(date)"
