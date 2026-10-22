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
| Deploy a specific commit on `main` | `./deploy.sh <full-commit-hash>` (never moves back to an older commit) |
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

### A CI deploy fails with "another deploy is already running"

A manual `./deploy.sh` was running at the same time. Wait for it to finish,
then use **Re-run jobs** on the failed run.

### `deploy.sh` refuses with "uncommitted changes in the checkout"

The server checkout must only ever be updated by `deploy.sh`. Run
`git status --short` to see what changed; undo it with `git checkout -- <file>`,
or commit the change on your dev machine and push it.

## Automatic deploys

Every push to `main` runs the tests on GitHub Actions and, if they pass,
deploys **that exact commit** (`.github/workflows/deploy.yml`). Pull requests
run the tests only. The runner joins your tailnet for the length of the job
and SSHs to the VPS's tailnet address, so public SSH can stay IP-filtered.
Its key can only run `deploy.sh`.

```
push to main --> test job --pass--> deploy job --tailnet, ssh--> VPS: deploy.sh <commit>
```

### One-time setup

**1. Tailscale policy** (admin console, Access controls). Let `tag:ci` reach
only the VPS's SSH port (`22`, or `2222` if you use Tailscale SSH, see below).
Adapt the VPS name or tag to your policy:

```
"tagOwners": { "tag:ci": ["autogroup:admin"] },
"grants": [
  { "src": ["tag:ci"], "dst": ["<vps-tailnet-name-or-tag>"], "ip": ["tcp:22"] }
]
```

If your policy still has the default allow-all rule, narrow it so it doesn't
cover `tag:ci`. CI must reach plain sshd, not Tailscale SSH: Tailscale SSH
ignores `authorized_keys`, so the restriction below wouldn't apply. Don't give
`tag:ci` any entry in the policy's `ssh` section.

**If Tailscale SSH is on for the VPS** (`tailscale up --ssh`), it takes over port
22 on the tailnet address, and CI fails with "tailnet policy does not permit
you to SSH to this node". Keep it for your own logins, and have sshd also
listen on port 2222 for CI (server):

```
sudo nano /etc/ssh/sshd_config      # next to any "Port" line, or at the top: Port 22 and Port 2222
sudo sshd -t                         # no output = config is valid
sudo systemctl daemon-reload
systemctl is-active ssh.socket       # "active": sudo systemctl restart ssh.socket
                                     # otherwise: sudo systemctl restart ssh
ss -ltn | grep 2222                  # sshd is listening
```

Keep `Port 22` as well, so normal SSH keeps working. Don't open 2222 in the
Oracle security list or the host firewall: CI reaches it over the tailnet only.
Grant `tcp:2222` instead of `tcp:22` in the policy above, use `-p 2222` in step 5,
and set `DEPLOY_PORT` in step 6.

**2. Tailscale OAuth client** (Settings, OAuth clients): scope **Auth keys:
write**, tag `tag:ci`. Keep the client ID and secret for step 6.

**3. CI key** (dev machine):

```
ssh-keygen -t ed25519 -N "" -C zeneke-ci -f zeneke-ci
```

**4. Restrict the key (server).** Append this line, on one line, with the
public key from `zeneke-ci.pub` and your checkout path, to
`~/.ssh/authorized_keys` of the user who owns the checkout:

```
command="/home/<user>/zeneke-apps/deploy.sh --ssh",from="100.64.0.0/10,fd7a:115c:a1e0::/48",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty,no-user-rc ssh-ed25519 AAAA... zeneke-ci
```

Whatever the client asks to run, sshd runs `deploy.sh --ssh`, which only
accepts a full commit hash on `origin/main`. The `from=` part makes the key
work only from tailnet addresses.

**5. Host key (server).** Collect the line CI will trust, and check that its
fingerprint matches the server's own. `tailscale ip -4` shows the tailnet IP:

```
ssh-keyscan -t ed25519 <vps-tailnet-ip>
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

With port 2222, run `ssh-keyscan -p 2222 -t ed25519 <vps-tailnet-ip>`; its line
starts with `[<vps-tailnet-ip>]:2222`, which is what CI needs. Don't scan port 22
while Tailscale SSH is on: that returns Tailscale's key, not sshd's.

**6. GitHub** (repo Settings, Environments): create an environment named
`production`, set **Deployment branches** to `main` only, and add these secrets:

| Secret | Value |
|---|---|
| `TS_OAUTH_CLIENT_ID` | from step 2 |
| `TS_OAUTH_SECRET` | from step 2 |
| `DEPLOY_SSH_KEY` | contents of `zeneke-ci` (the private key) |
| `DEPLOY_KNOWN_HOSTS` | the `ssh-keyscan` line from step 5 |
| `DEPLOY_HOST` | the VPS's tailnet IP, the same one used in step 5 |
| `DEPLOY_USER` | the user from step 4 |

With sshd on port 2222, also add a **variable** (Variables tab of the same
environment) `DEPLOY_PORT` = `2222`. Without it CI uses port 22.

Then delete the local `zeneke-ci` private key.

**7. Unattended fetch (server).** `deploy.sh` runs `git fetch` with no agent and
no terminal. In the checkout, `git remote -v` should show the HTTPS URL, and
this must succeed without a prompt:

```
env -u SSH_AUTH_SOCK git fetch origin main
```

### Day to day

- **Deploy:** push or merge to `main`. Follow it in the repo's Actions tab.
- **Redeploy the current `main`:** Actions, **Test and deploy**, **Run workflow** on `main`.
- **A failed run:** open the **deploy** job. The `[deploy]` lines are the
  script's output, and when the app didn't become healthy they end with its
  logs. Fix forward or revert on `main`; either push deploys again.
- **Switch it off:** Actions, **Test and deploy**, **Disable workflow**. Or
  remove the `zeneke-ci` line from `authorized_keys`. Manual `./deploy.sh`
  keeps working either way.
