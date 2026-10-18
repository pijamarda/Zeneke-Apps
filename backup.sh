#!/usr/bin/env bash
# Online backup of the production SQLite database into backups/.
# Safe while the app is running. Used by deploy.sh and suitable for cron.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod)
KEEP="${BACKUP_KEEP:-14}"
TMP=/data/.backup-tmp.sqlite3

log() { echo "[backup] $*"; }

mkdir -p backups

# Overlapping runs (cron + a deploy) queue up instead of racing for the same
# file names and temp file. Released when the script exits.
exec 8>backups/.backup.lock
flock -w 300 8 || { log "ERROR: another backup has been running for 5 minutes" >&2; exit 1; }

container="$("${COMPOSE[@]}" ps --all --quiet web 2>/dev/null || true)"
if [ -z "$container" ]; then
    log "app has never been started; nothing to back up yet"
    exit 0
fi

target="backups/db-$(date +%Y%m%d-%H%M%S).sqlite3"
while [ -e "$target" ]; do  # never overwrite a backup taken in the same second
    sleep 1
    target="backups/db-$(date +%Y%m%d-%H%M%S).sqlite3"
done

state="$(docker inspect -f '{{.State.Status}}' "$container")"
source_path=/data/db.sqlite3

# Running (even while starting up): SQLite online backup stays consistent while
# the app writes. Otherwise (stopped, crash loop) nothing serves writes, so a
# plain file copy is consistent; docker cp works on containers in any state.
if [ "$state" = "running" ] && "${COMPOSE[@]}" exec -T web python -c "
import sqlite3
src = sqlite3.connect('/data/db.sqlite3')
dst = sqlite3.connect('$TMP')
src.backup(dst)
dst.close()
src.close()
" 2>/dev/null; then
    source_path="$TMP"
else
    log "app is $state; copying the database file directly"
fi

if ! "${COMPOSE[@]}" cp "web:$source_path" "$target" >/dev/null 2>&1; then
    if [ "$source_path" = /data/db.sqlite3 ]; then
        log "no database file yet; nothing to back up"
        exit 0
    fi
    log "ERROR: could not copy the backup out of the container" >&2
    exit 1
fi
[ "$source_path" = "$TMP" ] && "${COMPOSE[@]}" exec -T web rm -f "$TMP"
log "wrote $target"

# Keep only the newest $KEEP backups (names sort chronologically).
mapfile -t old < <(find backups -maxdepth 1 -name 'db-*.sqlite3' | sort -r | tail -n +"$((KEEP + 1))")
if [ "${#old[@]}" -gt 0 ]; then
    rm -f -- "${old[@]}"
    log "removed ${#old[@]} old backup(s), keeping $KEEP"
fi
