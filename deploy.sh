#!/usr/bin/env bash
# Deploy the latest origin/main on this server. Non-interactive: safe to run by
# hand or from CI over SSH. Exits non-zero on any failure.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod)
TIMEOUT="${DEPLOY_TIMEOUT:-120}"

log() { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }

# 1. One deploy at a time; the lock is released when the script exits.
exec 9>.deploy.lock
flock -n 9 || fail "another deploy is already running"

# 2. Preflight: nothing below changes anything until these pass.
[ -f .env.prod ] || fail ".env.prod not found; create it from .env.prod.example (cp .env.prod.example .env.prod && chmod 600 .env.prod)"
mode="$(stat -c %a .env.prod)"
[ "${mode: -2}" = "00" ] || fail ".env.prod is readable by other users (mode $mode); run: chmod 600 .env.prod"
docker compose up --help 2>/dev/null | grep -q -- '--wait' || fail "docker compose is too old (needs 'up --wait'); update Docker Compose v2"
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || fail "checkout is on '$branch', not 'main'"
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "uncommitted changes in the checkout; the server must not be edited by hand"

# 3. Code: fast-forward only.
log "fetching origin/main"
git fetch --quiet origin main
git merge --ff-only --quiet origin/main || fail "main cannot be fast-forwarded to origin/main"

# 4. Backup before anything is rebuilt.
./backup.sh

# 5. Build, start and wait until healthy.
log "building and starting (waiting up to ${TIMEOUT}s for healthy)"
if ! "${COMPOSE[@]}" up -d --build --wait --wait-timeout "$TIMEOUT"; then
    echo "[deploy] recent logs:" >&2
    "${COMPOSE[@]}" logs --tail 80 web >&2 || true
    fail "app did not become healthy"
fi

# 6. Remove dangling images only (other apps on the server are untouched).
docker image prune -f >/dev/null

# 7. Report.
log "deployed $(git log -1 --format='%h %s')"
