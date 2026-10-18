# Zeneke Apps

A small collection of family-oriented web apps on one shared Django backend.
One site, one sign-in, many little apps: parents sign in with Google, kids sign
in with a username and a PIN they choose themselves, and every app on the site
shares the same family accounts.

Live at **https://apps.zeneke.com** (sign-in is limited to the family).

## Apps

| App | Path | Status | What it does |
|---|---|---|---|
| **Fercoins** | `/fercoins/` | live | Parents reward (or deduct) points for chores; kids see their balance and history. |
| **Family** | `/family/` | live | Parents create kid accounts, hand out one-time setup codes, reset PINs and unlock accounts. |
| **Bingo** | `/bingo/` | planned | A simple bingo simulator. |

The Fercoins and family pages are in Spanish; the rest of the site is in English.

## How sign-in works

```
                      /accounts/login/
              +--------------+---------------+
              |                              |
     Parents: Google / GitHub        Kids: username + 4-digit PIN
     (django-allauth OAuth)          (custom backend, kid accounts only)
              |                              |
              +---------> one Django session <---------+
                     shared by every app on the site
```

- **Parents** are superusers who sign in with OAuth. Google sign-in is limited
  to a list of test users, so strangers can't create accounts.
- **Kids** don't need an email or a Google account. A parent creates the kid
  and gets a **one-time 6-digit setup code** (valid 24 hours). The kid enters it
  once and **chooses their own PIN**, which they can change later.
- PINs and setup codes are stored only as salted hashes. **Five wrong attempts
  lock the account for 15 minutes**, and every failure shows the same message,
  so the login page never reveals which usernames exist.

## Architecture

```
 browser --https--> Caddy (reverse proxy, Let's Encrypt)
                       |  X-Forwarded-Proto: https
                       v
                 127.0.0.1:8010 (loopback only)
                       |
          +------------+--------------------------------+
          | Docker container (non-root, uid 1000)       |
          |   gunicorn -> Django                        |
          |     core      home, family, kid PIN login,  |
          |               /healthz                      |
          |     fercoins  chores & points               |
          |     bingo     (placeholder)                 |
          |   WhiteNoise serves static files            |
          +------------+--------------------------------+
                       |
              named volume: /data/db.sqlite3
```

- **One Django project** (`src/app/backend/`: settings and root URLs) with one
  Django app per family app. Shared pieces, such as the kid accounts, live in
  `core` so every app can use them.
- **SQLite** is enough for one family: a single file on a Docker volume, backed
  up with SQLite's online backup.
- **Safe by default:** without `DEBUG=true` the app runs in production mode. It
  refuses to start without a real `SECRET_KEY` and `ALLOWED_HOSTS`, redirects
  plain HTTP to HTTPS, uses HTTPS-only cookies and sends HSTS.
- **Static files** are collected into the image at build time and served by
  the app itself (WhiteNoise), so no extra web server is needed.
- **Deploys** are one script on the server (`deploy.sh`). It backs up the
  database, fast-forwards to `main`, rebuilds the image and waits until
  `/healthz` reports healthy.

## Tech stack

Python 3.12, Django 6.0, django-allauth (Google/GitHub OAuth), gunicorn,
WhiteNoise, python-dotenv, SQLite, Bootstrap 5. Dependencies are managed with
[uv](https://docs.astral.sh/uv/); the app runs in Docker, behind Caddy in
production.

## Repository layout

```
.
+-- src/
|   +-- pyproject.toml, uv.lock   Python dependencies (uv)
|   +-- .env.example              local development settings template
|   +-- README.md                 developer notes and production variables
|   +-- app/
|       +-- manage.py
|       +-- backend/              Django project: settings, root URLs
|       +-- core/                 home, family management, kid PIN login, /healthz
|       +-- fercoins/             chores & points app
|       +-- bingo/                bingo app (placeholder)
|       +-- templates/, static/   shared Bootstrap layout and styles
+-- Dockerfile                    one image for dev and production
+-- docker-compose.yml            local development (runserver, live reload)
+-- docker-compose.prod.yml       production on the server (loopback port, volume)
+-- deploy.sh, backup.sh          server scripts
+-- DEPLOY.md                     server setup and operations guide
+-- openspec/                     specifications and change history
+-- LICENSE                       MIT
```

## Running it locally

You need [uv](https://docs.astral.sh/uv/) (or Docker). Then:

```
cp src/.env.example src/.env
cd src/app
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open http://localhost:8000. Without OAuth keys in `src/.env`, sign in as the
superuser at `/admin/login/`. From there, create kids at `/family/`.

With Docker instead (also needs `src/.env`):

```
docker compose up --build
```

Run the tests with:

```
cd src/app
uv run python manage.py test
```

More developer notes, including the production environment variables, are in
[src/README.md](src/README.md).

## Deployment

Production runs on a VPS behind Caddy. [DEPLOY.md](DEPLOY.md) covers the
first-time setup (DNS, the Caddy block, the secrets file, the first deploy,
Google sign-in) and day-to-day operations (deploy, logs, backups, restore,
rollback).

## How this project is developed

Changes follow a spec-driven workflow with [OpenSpec](https://github.com/Fission-AI/OpenSpec):
each feature starts as a proposal, a spec of the required behaviour, a design
and a task list, and is archived once it ships.

- `openspec/specs/` describes what the system does today: `kid-authentication`,
  `family-management`, `fercoins`, `runtime-configuration` and `deployment`.
- `openspec/changes/archive/` keeps every completed change, with its proposal,
  design and tasks.

## Roadmap

- Bingo app
- Deploys from GitHub Actions after each push to `main`
- Off-server copies of the database backups
- Moving from `apps.zeneke.com` to `zeneke.com`

## License

[MIT](LICENSE)
