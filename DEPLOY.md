# Deploying Zeneke to the VPS

Zeneke runs on the VPS as one Docker container behind the Caddy that is
already installed on the host:

```
internet --443--> Caddy (host) --> 127.0.0.1:8010 --> container (gunicorn, uid 1000)
                  apps.zeneke.com                       volume zeneke-prod_zeneke-data:/data
```

Everything routine is one script: `./deploy.sh`.

Commands marked **(server)** run on the VPS in the repo checkout; the rest are
optional local checks. All commands work in fish and bash.

## First-time setup

### 1. Check the server (server)

```
systemctl status caddy        # Caddy runs on the host
caddy version
docker compose version        # Compose v2 with "up --wait"
ss -ltn | grep 8010           # no output = port 8010 is free (else pick another ZENEKE_PORT)
```

### 2. DNS (Netlify)

In Netlify DNS for `zeneke.com`, add an `A` record `apps` pointing to the VPS
public IPv4 (and an `AAAA` record if the VPS has IPv6). Check with:

```
dig +short apps.zeneke.com
```

### 3. Caddy (server)

Add to `/etc/caddy/Caddyfile` (use the port from `.env.prod` if you changed it):

```
apps.zeneke.com {
    reverse_proxy 127.0.0.1:8010
}
```

Validate before reloading, so a typo can't affect the other sites:

```
caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy gets the Let's Encrypt certificate once DNS resolves to the VPS.

### 4. Secrets (server)

```
cp .env.prod.example .env.prod
chmod 600 .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # paste as SECRET_KEY
nano .env.prod                                                   # SECRET_KEY, Google keys
```

`.env.prod` is gitignored and must stay `600`; `deploy.sh` refuses otherwise.

### 5. First deploy (server)

```
./deploy.sh
```

It ends with `[deploy] deployed <commit>`. Check:

```
curl -s http://127.0.0.1:8010/healthz          # ok
curl -sI https://apps.zeneke.com/ | head -1      # HTTP/2 200
```

### 6. First parent (server)

```
docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod \
    exec web python manage.py createsuperuser
```

This local superuser can sign in at `https://apps.zeneke.com/admin/login/`.

### 7. Google sign-in

In Google Cloud (project `zeneke-apps`):

- **Clients → zeneke-web → Authorized redirect URIs**: add
  `https://apps.zeneke.com/accounts/google/login/callback/` (keep the localhost ones for dev).
- **Branding → Authorized domains**: add `zeneke.com` if asked.
- **Audience**: keep Testing mode; test users are the only accounts that can sign in.

Then sign in with Google once on `https://apps.zeneke.com/accounts/login/` and
make that account a parent: in `/admin/` (as the superuser from step 6) open the
user and tick **Superuser status** and **Staff status**.

### 8. Daily backups (server)

`crontab -e` and add (adjust the path):

```
30 3 * * * /home/<user>/zeneke-apps/backup.sh >> /home/<user>/zeneke-apps/backups/cron.log 2>&1
```

## Operations

| Task | Command (server) |
|---|---|
| Deploy latest `main` | `./deploy.sh` |
| Logs | `docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod logs -f web` |
| Backup now | `./backup.sh` (keeps 14; `BACKUP_KEEP=30 ./backup.sh` to keep more) |
| Status | `docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod ps` |

`deploy.sh` refuses to run when `.env.prod` is missing or not `600`, the
checkout is not on a clean `main`, `main` can't fast-forward, or another deploy
is running. It always backs up before rebuilding, and fails with the app's logs
if it isn't healthy within 120s (`DEPLOY_TIMEOUT=300 ./deploy.sh` for longer).

### Rollback

Revert the bad commit on `main` (locally: `git revert <sha> && git push`), then
`./deploy.sh` on the server.

### Restore a backup (server)

```
docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod stop web
docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod cp backups/db-YYYYmmdd-HHMMSS.sqlite3 web:/data/db.sqlite3
docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod run --rm --no-deps --user root --entrypoint chown web zeneke:zeneke /data/db.sqlite3
docker compose -p zeneke-prod -f docker-compose.prod.yml --env-file .env.prod start web
```

The `chown` makes sure the app (uid 1000) can write the restored file,
whatever user ran the copy.

### Raising HSTS

Once HTTPS has been stable for a while, set `SECURE_HSTS_SECONDS=31536000` in
`.env.prod` and run `./deploy.sh`.

## Troubleshooting

### `failed to fetch oauth token ... denied` while pulling `ghcr.io/astral-sh/uv`

The build pulls a public image from ghcr.io. If `~/.docker/config.json` on the
server still holds an old or expired ghcr.io login, Docker sends it anyway and
ghcr.io refuses. Check that nothing on the server needs a private ghcr.io image,
then remove the stale login once (server):

```
find ~ -maxdepth 3 \( -name 'docker-compose*.yml' -o -name 'Dockerfile' \) -exec grep -l 'ghcr.io' {} + 2>/dev/null
docker logout ghcr.io
./deploy.sh
```

If you do need that login for another project, log in again with a valid token
(`docker login ghcr.io`) instead of logging out.

### `deploy.sh` refuses with "uncommitted changes in the checkout"

The server checkout must only ever be updated by `deploy.sh`. Run
`git status --short` to see what changed; undo it with `git checkout -- <file>`,
or commit the change on your dev machine and push it.

## Later: deploy from GitHub Actions

`deploy.sh` needs no changes. Give CI its own SSH key, stored as a GitHub
secret, and restrict it on the VPS in `~/.ssh/authorized_keys` so it can only
deploy:

```
command="/home/<user>/zeneke-apps/deploy.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA... zeneke-ci
```

The workflow then runs the tests and `ssh <user>@<vps>` after each push to `main`.
