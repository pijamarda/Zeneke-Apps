# Proposal

## Why

Zeneke is about to be deployed to a VPS or Fly.io, but in production mode today it is broken and unsafe. With `DEBUG=false` under gunicorn, `/static/css/style.css` returns 404, so the site loses its styling. `DEBUG` defaults to on and `SECRET_KEY` falls back to a key committed in the repo, so one missing environment variable makes it run in public debug mode. Behind the host's HTTPS proxy Django thinks requests are plain `http`, which breaks the Google OAuth callback and form submissions. Session and CSRF cookies are not marked HTTPS-only (`manage.py check --deploy` reports 5 warnings). The SQLite file lives inside the image, so every redeploy wipes all data.

## What Changes

- **BREAKING (dev)**: settings default to **production mode**. `DEBUG` is off unless set to `true`. Local runs keep working because a `src/.env` file is now loaded automatically; already-set environment variables always win over the file.
- Production mode **refuses to start** without a secure `SECRET_KEY` or a non-empty `ALLOWED_HOSTS`, with a clear error message.
- The app **serves its own static files** in production. They are collected at image build time, so the CSS works on any host without proxy configuration.
- **HTTPS behind a proxy**: production trusts the proxy's `X-Forwarded-Proto` header, redirects plain HTTP to HTTPS, marks session and CSRF cookies HTTPS-only, and sends HSTS (1 hour by default, configurable). OAuth callback URLs are built as `https://`.
- `CSRF_TRUSTED_ORIGINS` is **derived from `ALLOWED_HOSTS`** (`https://<host>`), with an explicit override.
- A **`DATA_DIR`** setting decides where the SQLite database lives, so a host volume can hold it. The default stays as today.
- `src/.env.example` documents the new variables, and `src/README.md` describes the production environment.

## Capabilities

### New Capabilities
- `runtime-configuration`: How the application picks up its configuration from the environment, and what it guarantees in development and in production mode: safe defaults, startup validation, static files, HTTPS handling and data location.

### Modified Capabilities
<!-- None: kid-authentication, family-management and fercoins behaviour is unchanged. -->

## Impact

- **Code**: `src/app/backend/settings.py` (env loading, validation, security settings, WhiteNoise, `DATA_DIR`); new `src/app/backend/tests.py`.
- **Dependencies**: adds `whitenoise` and `python-dotenv` to `src/pyproject.toml` / `uv.lock`.
- **Docker**: `Dockerfile` runs `collectstatic` at build time; `entrypoint.sh` no longer runs it at startup. The dev `docker-compose.yml` is unchanged; it already gets `DEBUG=true` from `src/.env`.
- **Operators**: production must set `SECRET_KEY` and `ALLOWED_HOSTS`, and should set `DATA_DIR` to a persistent volume.
- **Out of scope** (follow-up deploy change): choosing between the VPS and Fly.io, `fly.toml` or a Caddy/compose production file, volumes, a health-check endpoint exempt from the HTTPS redirect, a non-root production container, per-IP rate limiting.
