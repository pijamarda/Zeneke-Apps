# Design

## Context

- `src/app/backend/settings.py` reads plain `os.environ`. `DEBUG` defaults to `true`, `SECRET_KEY` falls back to a committed `django-insecure-...` key, `ALLOWED_HOSTS` is parsed without trimming, and there are no HTTPS-related settings.
- `src/.env` is only read by docker-compose (`env_file`); a bare `uv run manage.py ...` ignores it.
- The production image runs gunicorn. `entrypoint.sh` runs `collectstatic` at startup when `DEBUG=false`, but nothing serves `STATIC_ROOT`, which was verified: `/static/css/style.css` returns 404.
- SQLite is at `BASE_DIR / 'db.sqlite3'`, i.e. `/app/app/db.sqlite3` inside the image.
- Target hosts are a VPS (Caddy or nginx in front) or Fly.io. Both terminate TLS and forward `X-Forwarded-Proto`.

Requirements are in `specs/runtime-configuration/spec.md`; see `proposal.md` for the motivation.

## Goals / Non-Goals

**Goals:**
- One `settings.py` that is safe with no configuration and convenient with a local `.env`.
- Fail at import time, so `manage.py`, gunicorn and the Docker entrypoint all stop before serving anything.

**Non-Goals:**
- Split settings modules (`settings/dev.py`, `settings/prod.py`). One file with a `DEBUG` branch is enough at this size.
- `django-environ` or similar. Two tiny helpers cover what's needed.
- Host-specific files (`fly.toml`, a production compose file with Caddy), health checks, non-root production containers.

## Decisions

### 1. Load `src/.env` with python-dotenv, never overriding
At the top of `settings.py`: `load_dotenv(BASE_DIR.parent / '.env', override=False)`. `override=False` gives "environment wins" for free. The file is excluded from the image by `.dockerignore` (`**/.env`), so in production it is a no-op.
- *Alternative:* `django-environ`. Rejected: a bigger API than needed for about ten variables.

### 2. Small env helpers, explicit parsing
`env_bool(name, default)` returns true only for the case-insensitive string `true`. `env_list(name)` splits on commas, strips spaces and drops blanks. An empty string counts as unset everywhere. That lets tests force "missing" by setting a variable to `''`, which also beats any developer `.env`.

### 3. Validate at import, raise `ImproperlyConfigured`
When `DEBUG` is false:
- `SECRET_KEY` must exist, be at least 50 characters, contain at least 5 unique characters and not start with `django-insecure-`. These are the same criteria as Django's `security.W009` check, re-implemented as three constants, because Django's helpers are private.
- `ALLOWED_HOSTS` must be non-empty.

The error messages name the variable and point to `src/.env.example`. In development, the existing `django-insecure-...` key stays as a fallback that is clearly marked as dev-only, so sessions survive restarts locally.

### 4. A production security block
```
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env or 3600)
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
```
`SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` stay off on purpose, since HSTS starts short and other subdomains may exist. Their deploy-check warnings (`security.W005`, `security.W021`) are listed in `SILENCED_SYSTEM_CHECKS` with a comment, so `check --deploy` stays clean. Django sends HSTS only on secure requests, which matches the spec.
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL` is belt and braces: allauth already builds absolute URLs through `request.build_absolute_uri()`, which honours the proxy header.

### 5. `CSRF_TRUSTED_ORIGINS` derived from `ALLOWED_HOSTS`
For each host: `zeneke.example.com` becomes `https://zeneke.example.com`, `.example.com` becomes `https://*.example.com`, and `*` is skipped. If `CSRF_TRUSTED_ORIGINS` is set, it replaces the derived list. In development nothing is derived, and Django's same-origin checks for localhost already pass.

### 6. WhiteNoise for static files; collect at build time
Add `whitenoise.middleware.WhiteNoiseMiddleware` right after `SecurityMiddleware`. In production, `STORAGES['staticfiles']` is `whitenoise.storage.CompressedManifestStaticFilesStorage`, which gives hashed, compressed, long-cacheable files. In development it stays Django's default storage, because the manifest storage fails for any `{% static %}` path when `collectstatic` hasn't been run. That would break `runserver` and the test suite, which runs with `DEBUG=False` but imports settings with the `.env` `DEBUG=true`.

The Dockerfile runs `collectstatic` during the build, with build-only values: `DEBUG=false`, a random `SECRET_KEY` generated in that `RUN` step, and `ALLOWED_HOSTS=build`. The image then contains its assets, and startup no longer writes files. The `collectstatic` block is removed from `entrypoint.sh`. In dev compose the bind mount hides `/app/app/staticfiles`, which is harmless, because runserver with `DEBUG=true` serves from the apps' static directories.
- *Alternative:* the proxy serves `STATIC_ROOT`. Rejected: Fly has no separate file server by default, and it would differ between the two hosts.

### 7. `DATA_DIR` for the database
`DATA_DIR = Path(env or BASE_DIR)`, with `mkdir(parents=True, exist_ok=True)`, and the database `NAME = DATA_DIR / 'db.sqlite3'`. Unset, it resolves to exactly today's path, so dev compose and existing local databases are untouched. Production sets `DATA_DIR=/data` on a volume. That is configured in the deploy change.

### 8. Testing approach
`src/app/backend/tests.py` (discovered by `manage.py test`, since `backend` is a package):
- **Settings logic** runs in subprocesses (`python -c "import django; django.setup(); ..."`) with a controlled environment where every relevant variable is set explicitly (`''` for "missing"). That covers the default mode, key and host validation, list parsing, derived origins, `DATA_DIR` and the HSTS default.
- **`.env` precedence** is tested by calling the same `load_dotenv(path, override=False)` on a temp file with `os.environ` patched. The behaviour comes from the library; the test pins how we use it.
- **Request behaviour** uses `override_settings` with the production values in a normal `TestCase`: redirect without the header, HSTS with it, `Secure` cookies, a CSRF-checked POST with an `Origin` from the allowed host, and the Google login redirect containing an `https://` callback.
- **Static serving** is verified end to end against the built image (see tasks), because it depends on build-time `collectstatic`.

## Risks / Trade-offs

- [**BREAKING for local runs:** a developer without `src/.env` now gets an `ImproperlyConfigured` error] → the error message says to copy `src/.env.example`, which sets `DEBUG=true`. Your existing `.env` already has `DEBUG=true`.
- [`X-Forwarded-Proto` can be spoofed if gunicorn is reachable directly, without the proxy] → this only affects `is_secure()`. The deploy change must not publish port 8000 publicly (bind it to localhost on the VPS; Fly is private by default).
- [HSTS caches an "HTTPS only" rule in browsers] → it starts at 1 hour; raise it later through `SECURE_HSTS_SECONDS`.
- [Health checks over plain HTTP get redirected (Fly)] → handled in the deploy change, with `SECURE_REDIRECT_EXEMPT` for a health path.
- [A `{% static %}` reference to a missing file returns 500 in production with manifest storage] → there is currently only one reference (`css/style.css`); the end-to-end check catches regressions.

## Migration Plan

1. Merge. Locally, nothing changes as long as `src/.env` has `DEBUG=true`.
2. When deploying, set `SECRET_KEY` (generate it with `python -c "import secrets; print(secrets.token_urlsafe(50))"`), `ALLOWED_HOSTS`, `DATA_DIR`, and optionally `SECURE_HSTS_SECONDS`.
3. Rollback: revert the commit. The settings are self-contained; there are no data migrations.
