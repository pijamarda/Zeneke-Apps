# Design

## Context

- The production settings already exist (`openspec/specs/runtime-configuration`): production by default, `DATA_DIR`, proxy header, HTTPS redirect, WhiteNoise, static files collected at image build.
- The `Dockerfile` installs the venv at `/opt/venv`, runs as root, has no `HEALTHCHECK`, and its `CMD` runs gunicorn on `0.0.0.0:8000` with 2 workers. `entrypoint.sh` runs `migrate`, then `exec`s the command.
- The dev `docker-compose.yml` (project `zeneke-apps`, service `web`) bind-mounts `./src`, runs as `${UID:-1000}`, and uses `runserver`.
- The server: an existing VPS with Caddy installed on the host (systemd, `/etc/caddy/Caddyfile`) in front of other backends; Docker Compose v2; the repo already cloned and pullable. Domain `apps.zeneke.com`, DNS on Netlify.
- `.gitignore` and `.dockerignore` already exclude `.env.*` (except `.env.example`), so `.env.prod` is covered.

Requirements are in `specs/deployment/spec.md` and the modified `specs/runtime-configuration/spec.md`; see `proposal.md` for the motivation.

## Goals / Non-Goals

**Goals:**
- One image for dev and production; production differs only through its compose file and environment.
- `deploy.sh` that is safe to run by hand and, unchanged, from CI over SSH.

**Non-Goals:**
- Zero-downtime deploys. A single container on SQLite means a few seconds of downtime while it is replaced.
- Managing Caddy, DNS or the OS from this repo. We ship a snippet and documentation only.
- Building images in CI or a registry. The VPS builds from its checkout.

## Decisions

### 1. Health check as the first middleware
Add `core.middleware.HealthCheckMiddleware` at the **top** of `MIDDLEWARE`. When `request.path == '/healthz'` it returns `HttpResponse('ok', content_type='text/plain')` straight away. Otherwise it passes the request on.
- Being first means it answers before `SecurityMiddleware` (HTTPS redirect) and before anything calls `request.get_host()` (the `ALLOWED_HOSTS` check that would return 400 for `127.0.0.1:8000`).
- It never touches the database or sessions, so a probe can't be slowed down or broken by them.
- *Alternative:* a normal view plus `SECURE_REDIRECT_EXEMPT`. Rejected: it would still fail the `ALLOWED_HOSTS` check for the probe's `Host` header, and adding `127.0.0.1` to `ALLOWED_HOSTS` would widen what the whole site accepts.

### 2. Non-root image with an owned `/data`
In the `Dockerfile`: `useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin zeneke`, then `mkdir /data && chown zeneke:zeneke /data`, and `USER zeneke` as the last step before `ENTRYPOINT`. `collectstatic` keeps running as root before the switch; the files are world-readable, which is all gunicorn needs.
- A Docker **named volume** copies the ownership of the image's `/data` the first time it's created, so the volume starts out owned by uid 1000. That means no root step and no `chown` or `setpriv` at startup.
- Dev keeps working: dev compose already runs as uid 1000, and `DATA_DIR` is unset there, so the database stays in the bind-mounted `src/app/`.
- `HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"`. It uses Python because the slim image has no `curl`. It lives in the `Dockerfile`, so the image is self-describing; in dev it simply probes runserver.

### 3. `docker-compose.prod.yml`
```
name: zeneke-prod
services:
  web:
    build: .
    restart: unless-stopped
    env_file: [.env.prod]
    environment:
      DATA_DIR: /data
    ports:
      - "127.0.0.1:${ZENEKE_PORT:-8010}:8000"
    volumes:
      - zeneke-data:/data
volumes:
  zeneke-data:
```
- **`name: zeneke-prod`** keeps it apart from the dev project (`zeneke-apps`). Running both on one machine never replaces the other's container or volume.
- **`DATA_DIR` is set in the compose file**, not in `.env.prod`, so it can't be forgotten.
- **No bind mount of the source:** the image is what runs.
- **`ZENEKE_PORT`** comes from `.env.prod`. `deploy.sh` passes `--env-file .env.prod` so compose can substitute it.
- The gunicorn `CMD` from the `Dockerfile` is used as is: 2 workers, which fits SQLite and a small VPS.

### 4. `.env.prod` and its template
`.env.prod.example` is committed and lists `SECRET_KEY` (with the generation command), `ALLOWED_HOSTS=apps.zeneke.com`, `ZENEKE_PORT=8010`, the Google and GitHub keys, and the optional `SECURE_HSTS_SECONDS`. The real `.env.prod` lives only on the server with mode `600`. `deploy.sh` enforces that.

### 5. `backup.sh`
1. `cd` to the script's directory, `mkdir -p backups`, then take `backups/.backup.lock` with `flock -w 300`, so overlapping runs (cron plus a deploy) queue up instead of racing for the same file name and temporary file.
2. If project `zeneke-prod` has **no** `web` container at all (`ps --all`): print "nothing to back up yet" and exit 0.
3. Pick the target `backups/db-$(date +%Y%m%d-%H%M%S).sqlite3`. If that name already exists, wait a second and take a new timestamp, so a backup is never overwritten (for example a cron backup and a deploy in the same second).
4. **Container running** (even while its health check is still "starting"): `docker compose ... exec -T web python -c "<sqlite3 online backup of /data/db.sqlite3 to /data/.backup-tmp.sqlite3>"`. It uses `sqlite3.Connection.backup()` from Python's standard library, so it's consistent while the app keeps writing, and no `sqlite3` binary is needed on the host. Then `docker compose ... cp` the temporary file out and remove it inside the container.
5. **Container not running** (stopped, or in a restart loop after a failed deploy), or the `exec` fails: nothing is serving writes, so `docker compose ... cp web:/data/db.sqlite3` copies the file directly; `docker cp` works on containers in any state. If there is no database file yet, print "nothing to back up" and exit 0.
   - This was found during implementation. Treating a restart-looping container as "not running" made the recovery deploy after a failure either crash at the backup step (`exec` refused while restarting) or skip a database holding real data.
6. Retention: delete all but the newest `${BACKUP_KEEP:-14}` `backups/db-*.sqlite3`.

`backups/` is gitignored and excluded from the Docker build context. A cron line for daily backups is documented, not installed.

### 6. `deploy.sh`
Bash with `set -euo pipefail`, `cd "$(dirname "$0")"`, and the compose command fixed as `docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod`:
1. **Lock:** `exec 9>.deploy.lock; flock -n 9`, or fail with "deploy already running". The lock is released automatically when the script exits.
2. **Preflight (changes nothing):** `.env.prod` exists, and `stat -c %a` shows no group or other bits; `docker compose up --help` mentions `--wait`; the branch is `main`; `git status --porcelain` is empty.
3. **Code:** `git fetch origin main`, then `git merge --ff-only origin/main`. It fails if the branches have diverged.
4. **Backup:** `./backup.sh`.
5. **Start:** `up -d --build --wait --wait-timeout ${DEPLOY_TIMEOUT:-120}`. On failure, print `logs --tail 80 web` and exit 1.
6. **Cleanup:** `docker image prune -f`, which removes only dangling images, so other apps on the VPS are unaffected.
7. **Report:** `Deployed <short sha> <subject>`.

Every message is prefixed `[deploy]` and nothing reads stdin, so the output is readable both in a terminal and in CI logs.

### 7. Future GitHub Actions (documented, not built)
A workflow on push to `main` runs the tests, then `ssh deploy@vps` with a dedicated key stored as a GitHub secret. On the VPS, that key's `authorized_keys` line is restricted:
`command="/path/to/zeneke-apps/deploy.sh",no-port-forwarding,no-agent-forwarding,no-pty ssh-ed25519 ...`
A leaked key could then only run a deploy of `main`. `deploy.sh` needs no changes for this.

### 8. Testing approach
- **Health middleware:** Django tests (status, body, plain HTTP in production with `override_settings`, an unknown host, a database failure simulated by patching the connection, other paths still redirected).
- **Image:** build it, `docker run` it, check `id -u` = 1000 and that the health status becomes `healthy`.
- **Scripts:** run against a **scratch clone** whose `origin` is a local bare repository (a copy of this repo), on a spare port, so the real checkout and dev containers are never touched. This covers: first deploy, deploy after a new commit, a failing deploy (bad `SECRET_KEY`), each preflight refusal, a concurrent run, data surviving a redeploy, backups and retention.

## Risks / Trade-offs

- [A few seconds of downtime on each deploy] → acceptable for a family app; deploys are quick.
- [Building on the VPS uses its CPU and memory for about a minute] → the image is small; `docker image prune -f` keeps the disk tidy. A registry can come with CI later.
- [Backups live on the same server] → enough against bad deploys and mistakes, not against losing the server. Copying them elsewhere is documented as a next step.
- [The port `8010` may already be taken on the VPS] → configurable through `ZENEKE_PORT`; the docs say to check with `ss -ltn`.
- [The Caddy block is applied by hand] → the docs give the exact block and the `caddy validate` / `systemctl reload caddy` commands, so a typo can't take down the other sites.
- [The named volume isn't visible as a plain folder] → `backup.sh` is the supported way to get a copy; restore is documented as stop, `docker compose cp` the file in, start.

## Migration Plan

1. Merge to `main`. Dev is unchanged apart from the image now defaulting to uid 1000, which dev compose already uses.
2. On the VPS, the first time:
   - the DNS `A` record
   - the Caddy block, then validate and reload
   - `.env.prod` with `chmod 600`
   - `./deploy.sh`
   - create the first parent with `createsuperuser` through `docker compose exec`
   - the Google redirect URI
   - check the site works
3. Rollback: revert the commit on `main` and run `./deploy.sh`. If needed, restore `db.sqlite3` from `backups/`.
