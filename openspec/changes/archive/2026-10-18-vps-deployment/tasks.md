# Tasks

Run Django commands from `src/app` with `uv run python manage.py ...`. Script tests run in a scratch clone (see design.md, decision 8), never in the real checkout.

## 1. Health check endpoint

- [x] 1.1 Add `core/middleware.py` with `HealthCheckMiddleware` (exact path `/healthz`, returns `text/plain` `ok`, no database or session access) and put it first in `MIDDLEWARE` in `backend/settings.py`. Verify `manage.py check` passes and `curl http://127.0.0.1:8000/healthz` on runserver prints `ok`.
- [x] 1.2 Add tests in `core/tests.py`: 200 `ok` in dev; with production security settings over plain HTTP, `/healthz` returns 200 (not 301) while `/` and `/healthz/extra` return 301; `Host: 127.0.0.1:8000` outside `ALLOWED_HOSTS` still gets 200; with the database connection patched to fail, it still returns 200. Verify `manage.py test` passes.

## 2. Non-root image with health check

- [x] 2.1 In the `Dockerfile`: create user `zeneke` (uid 1000, no shell), create `/data` owned by it, add the `HEALTHCHECK` from design.md decision 2, and end with `USER zeneke` (after `collectstatic`). Verify that `docker build` succeeds, that `docker run` with production values shows uid 1000 for the gunicorn processes (`docker exec ... ps` or `/proc/1/status`), and that `docker inspect` health becomes `healthy`.
- [x] 2.2 Verify the dev setup still works with the new image: in a scratch copy, `docker compose up --build` serves `/`, the CSS and `/healthz` on `http://localhost`, and its container reports `healthy`.

## 3. Production compose and secrets template

- [x] 3.1 Add `docker-compose.prod.yml` as in design.md decision 3, `.env.prod.example` (decision 4), and add `backups/` and `.deploy.lock` to `.gitignore` and `.dockerignore`. Verify `docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod.example config` resolves, shows `127.0.0.1:8010:8000`, the `zeneke-data` volume, `DATA_DIR=/data` and `restart: unless-stopped`, and that `git check-ignore .env.prod backups/x .deploy.lock` lists all three.

## 4. Backup script

- [x] 4.1 Add an executable `backup.sh` following design.md decision 5. Verify in the scratch clone: with no running container it prints "nothing to back up" and exits 0; with the app running and a kid created, it writes `backups/db-<timestamp>.sqlite3`, which opens with Python `sqlite3` and contains the kid; with 14 existing backups (dummy files with older names) a run leaves 14, the newest included and the oldest removed; `BACKUP_KEEP=3` leaves 3.

## 5. Deploy script

- [x] 5.1 Add an executable `deploy.sh` following design.md decision 6. Verify in the scratch clone (origin = a local bare copy of this repo, `.env.prod` with a spare `ZENEKE_PORT`): a first deploy exits 0, prints the commit, and `/healthz` and `/` (with `X-Forwarded-Proto: https`) answer; after pushing a new commit to the bare origin, a deploy moves to it and the kid created earlier still exists; a deploy with an invalid `SECRET_KEY` exits non-zero, prints the container logs, and a pre-deploy backup exists.
- [x] 5.2 Verify the refusals in the scratch clone, each exiting non-zero before building or pulling: missing `.env.prod`; `.env.prod` with mode `644`; an uncommitted change to a tracked file; a checkout on another branch; a second `deploy.sh` started while the first holds the lock.

## 6. Documentation

- [x] 6.1 Write `DEPLOY.md`:
  - **First-time setup:**
    - check Caddy (`systemctl status caddy`, `caddy version`)
    - check the port is free (`ss -ltn | grep 8010`)
    - the Netlify `A` (and `AAAA` if any) record for `apps`
    - the Caddyfile block `apps.zeneke.com { reverse_proxy 127.0.0.1:8010 }`, then `caddy validate --config /etc/caddy/Caddyfile` and `sudo systemctl reload caddy`
    - `cp .env.prod.example .env.prod`, `chmod 600`, then fill it in
    - `./deploy.sh`
    - create the first parent with `createsuperuser` through `docker compose -p zeneke-prod ... exec web`
    - Google: add the redirect URI `https://apps.zeneke.com/accounts/google/login/callback/` and the authorized domain `zeneke.com`, then promote the Google account to parent
  - **Operations:** deploy, logs, daily backups (cron line), restore, rollback, raising `SECURE_HSTS_SECONDS` once stable.
  - **Future CI:** the restricted `authorized_keys` line.

  Link it from `src/README.md`. Verify every command in it has been run in the scratch tests or is marked as server-only.

## 7. Integration check

- [x] 7.1 Run the full test suite and `makemigrations --check`, and run `shellcheck` on both scripts (via `docker run --rm -v "$PWD:/mnt" koalaman/shellcheck:stable` if shellcheck isn't installed) with no warnings. Re-run the scratch-clone sequence end to end once: first deploy, create a kid, backup, new commit, redeploy (kid still present), failing deploy. Remove the scratch containers, volumes and images afterwards.

## 8. Rollout on the VPS (you, on the server; guided)

- [x] 8.1 Follow `DEPLOY.md` first-time setup on the VPS up to and including the first `./deploy.sh`. Verify `https://apps.zeneke.com/healthz` returns `ok` and `https://apps.zeneke.com/` loads with its CSS and a valid certificate.
- [x] 8.2 Finish the setup: Google redirect URI and authorized domain, the first parent, a test kid, the daily backup cron line. Verify Google sign-in works on `https://apps.zeneke.com`, a kid can sign in with a PIN, and `./backup.sh` writes a file in `backups/`.

## Workflow follow-up

- Archive the change after the rollout is verified.
- Follow-up changes to propose: the GitHub Actions deploy (tests, then SSH with the restricted key), off-server backup copies, the move from `apps.zeneke.com` to `zeneke.com`, restricting GitHub OAuth sign-up.
