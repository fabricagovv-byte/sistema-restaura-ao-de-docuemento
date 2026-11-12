#!/bin/sh
# Backup do PostgreSQL: um na subida do serviço e depois todo dia às 03:00 (hora do servidor); guarda 14 dias.
# Restaurar: gunzip -c producao/backups/licitacoes-AAAAMMDD.sql.gz | docker compose exec -T postgres psql -U licit licitacoes
set -eu
fazer() {
  arq="/backups/licitacoes-$(date +%Y%m%d).sql.gz"
  if pg_dump -h postgres -U licit licitacoes | gzip > "$arq.tmp"; then mv "$arq.tmp" "$arq"; echo "backup ok: $arq"
  else echo "backup FALHOU em $(date)"; fi
  find /backups -name 'licitacoes-*.sql.gz' -mtime +14 -exec rm -f {} \;
}
sleep 20
fazer
while true; do
  if [ "$(date +%H%M)" = "0300" ]; then fazer; sleep 61; fi
  sleep 30
done
