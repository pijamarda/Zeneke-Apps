# Proposal

## Why

Zeneke is production-ready in its settings (`runtime-configuration`), but there is no way to run it on the server yet. The target is the existing VPS, which already hosts other backends behind Caddy installed on the host, at `https://apps.zeneke.com`. Today the image runs as root, keeps no data across redeploys, has no health check (and production mode would redirect or reject one), and deploying would mean remembering a sequence of commands. A deploy should be one script, safe to run by hand now and from GitHub Actions later.

## What Changes

- A **`/healthz` endpoint** answers `200 ok` over plain HTTP with any `Host` header, without touching the database, so Docker can probe the container. **This modifies `runtime-configuration`:** health checks become the one exception to the HTTPS redirect.
- The **image runs as a non-root user** (`zeneke`, uid 1000). It owns `/data`, the database location in production, and declares a Docker `HEALTHCHECK`.
- A **`docker-compose.prod.yml`** runs the app under its own compose project. It publishes only on `127.0.0.1:${ZENEKE_PORT:-8010}`, so only Caddy on the host can reach it. It keeps the database in a named volume, restarts automatically, and reads secrets from a `.env.prod` on the server, documented by a committed `.env.prod.example`.
- A **`deploy.sh`**: one command, no prompts, meaningful exit codes. It takes a lock, runs preflight checks, fast-forwards to `origin/main`, backs up the database, builds and starts the container, waits until it is healthy, cleans up and reports the deployed commit. On failure it exits non-zero and shows the container's logs.
- A **`backup.sh`** takes an online SQLite backup into dated files under `backups/`, keeps the most recent 14 by default, and works from `deploy.sh` and from cron.
- **Deployment docs**: a step-by-step first-time setup on the VPS (Netlify DNS record, Caddyfile block, `.env.prod`, first deploy, creating the first parent, the Google redirect URI) and routine operations (deploy, backup, restore, rollback).

## Capabilities

### New Capabilities
- `deployment`: how Zeneke is run and operated in production: health checks, non-root runtime, persistent data, loopback-only exposure, the deploy and backup scripts, and their failure behaviour.

### Modified Capabilities
- `runtime-configuration`: the requirement "Plain HTTP is redirected in production" gains an exception for the health-check endpoint.

## Impact

- **Code**: a small health-check middleware in `core`, placed first in `MIDDLEWARE` in `backend/settings.py`, with tests.
- **Docker**: the `Dockerfile` gains a `zeneke` user, `/data`, `HEALTHCHECK` and `USER`. New `docker-compose.prod.yml` and `.env.prod.example`. The dev `docker-compose.yml` keeps working; it already runs as uid 1000.
- **Scripts**: new `deploy.sh` and `backup.sh` at the repo root; `backups/` and the deploy lock file are gitignored and excluded from the Docker build context.
- **Docs**: a new `DEPLOY.md`.
- **Server (manual, by you)**: an `A` record for `apps.zeneke.com` in Netlify, a block in `/etc/caddy/Caddyfile`, `.env.prod`, and the Google OAuth redirect URI for the domain.
- **Out of scope**: the GitHub Actions workflow (the design records the intended restricted-key setup), moving to `zeneke.com`, restricting GitHub OAuth sign-up, off-server backup copies.
