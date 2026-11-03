#!/usr/bin/env bash
# ProSync — backup diario do Postgres
#
# Gera um dump comprimido em ./backups/ e apaga os arquivos com mais de 7 dias.
# Uso:  ./scripts/backup.sh
# Cron: 0 3 * * * /home/SEU-USUARIO/prosync-completo/scripts/backup.sh >> /home/SEU-USUARIO/backup.log 2>&1

set -euo pipefail

# Vai para a raiz do projeto (onde esta o docker-compose.prod.yml),
# independentemente de onde o script foi chamado.
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"
DESTINO="backups"
RETENCAO_DIAS=7
ARQUIVO="${DESTINO}/prosync-$(date +%Y%m%d-%H%M%S).sql.gz"

mkdir -p "$DESTINO"

# Le POSTGRES_USER / POSTGRES_DB do .env (sem imprimir senha).
POSTGRES_USER=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2-)
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2-)
POSTGRES_USER=${POSTGRES_USER:-prosync}
POSTGRES_DB=${POSTGRES_DB:-prosync}

# pg_dump roda DENTRO do container do banco; PGPASSWORD vem do proprio ambiente dele.
if $COMPOSE exec -T db \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
    | gzip > "$ARQUIVO"; then

    TAMANHO=$(du -h "$ARQUIVO" | cut -f1)
    echo "[$(date '+%F %T')] OK ${ARQUIVO} (${TAMANHO})"
else
    echo "[$(date '+%F %T')] FALHA no backup" >&2
    rm -f "$ARQUIVO"
    exit 1
fi

# Remove dumps antigos.
find "$DESTINO" -name 'prosync-*.sql.gz' -mtime +"$RETENCAO_DIAS" -delete
