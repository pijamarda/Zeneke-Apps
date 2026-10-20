# Steps followed for uv setup

uv run django-admin startproject backend .

## Run locally

From `src/app`:

```
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Copy `src/.env.example` to `src/.env` first. It is loaded automatically (also
by docker-compose) and sets `DEBUG=true`. Without it the app starts in
production mode and refuses to run without a real `SECRET_KEY` and `ALLOWED_HOSTS`.

### Signing in

- **Parents** (superusers) sign in with Google/GitHub. When the OAuth keys are
  not set (typical locally), sign in at `/admin/login/` with the superuser you
  created; the session also works for the rest of the site.
- **Kids** are created by a parent at `/family/`, which shows a one-time
  6-digit setup code (valid 24h). The kid enters their username + that code on
  `/accounts/login/` and chooses their own 4-digit PIN. Parents can reset a PIN
  or unlock an account (5 wrong PINs lock it for 15 minutes) from `/family/`.

### Bingo

Bingo pages (`/bingo/`) are public: no sign-in is needed to create or join a
room. The browser that creates a room is its host; players are remembered by
their browser session. To try a game alone, open the host screen in one window
and join from one or more private windows (each one is a different player).

Rooms are deleted after a period without activity, and the number of rooms and
players is capped. The limits are Django settings in `backend/settings.py`:

| Setting | Default | Meaning |
|---|---|---|
| `BINGO_ROOM_IDLE_HOURS` | `12` | hours without activity before a room expires |
| `BINGO_MAX_ROOMS` | `50` | rooms that can exist at the same time |
| `BINGO_MAX_PLAYERS` | `30` | players per room |

## Production environment

Deploying to the VPS (Caddy, `deploy.sh`, backups): see [DEPLOY.md](../DEPLOY.md).

Production mode is the default (anything but `DEBUG=true`). The app expects a
proxy in front (Caddy, Fly.io, ...) that terminates HTTPS and sends
`X-Forwarded-Proto`; plain HTTP is redirected to HTTPS. Static files are
collected into the image at build time and served by the app itself.

| Variable | Required | Meaning |
|---|---|---|
| `SECRET_KEY` | yes | 50+ random characters; startup fails without it |
| `ALLOWED_HOSTS` | yes | site domain(s), comma-separated, e.g. `zeneke.example.com` |
| `DATA_DIR` | recommended | directory for `db.sqlite3`, on a persistent volume (default: `src/app/`) |
| `SECURE_HSTS_SECONDS` | no | HSTS duration, default `3600`; raise once HTTPS is stable |
| `CSRF_TRUSTED_ORIGINS` | no | defaults to `https://<each allowed host>` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | for Google sign-in | add `https://<domain>/accounts/google/login/callback/` to the OAuth client |

Generate a key with:

```
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Do not expose the container port (8000) publicly; only the proxy should reach it.

## Django specific commands

### Start the server
uv run manage.py runserver

### Run the tests
uv run manage.py test

### Add an application
uv run manage.py startapp bingo
