# Tasks

Run Django commands from `src/app` with `uv run python manage.py ...`.

## 1. Dependencies

- [x] 1.1 Add `whitenoise` and `python-dotenv` with `uv add` (from `src/`), and verify `pyproject.toml` and `uv.lock` list both and `uv run python -c "import whitenoise, dotenv"` succeeds.

## 2. Environment loading, defaults and validation

- [x] 2.1 In `backend/settings.py`: load `src/.env` with `override=False`; add `env_bool` / `env_list` helpers (an empty string counts as unset); make `DEBUG` default to false; keep the `django-insecure-` key as a dev-only fallback; parse `ALLOWED_HOSTS` with `env_list`; raise `ImproperlyConfigured` in production for a missing or insecure `SECRET_KEY` (missing, under 50 characters, under 5 unique characters, `django-insecure-` prefix) or an empty `ALLOWED_HOSTS`, with messages naming the variable and pointing to `src/.env.example`. Verify `manage.py check` still passes locally with the existing `src/.env`.
- [x] 2.2 Add `backend/tests.py` subprocess tests (every relevant variable set explicitly, `''` meaning missing): DEBUG unset or empty means production; `true` / `True` means development; production without a key, with a `django-insecure-` key, or with a short key fails and names `SECRET_KEY`; development without a key starts; production without hosts fails and names `ALLOWED_HOSTS`; `"a.example.com, b.example.com,"` parses to exactly two hosts. Add an in-process test that `load_dotenv(tmp, override=False)` keeps an already-set `DEBUG=false` over a file's `DEBUG=true`. Verify `manage.py test backend` passes.

## 3. HTTPS, cookies and trusted origins

- [x] 3.1 Add the production block (`SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, Secure session and CSRF cookies, `SECURE_HSTS_SECONDS` from env with a default of 3600, `ACCOUNT_DEFAULT_HTTP_PROTOCOL='https'`, `SILENCED_SYSTEM_CHECKS` for `security.W005`/`W021` with a comment) and `CSRF_TRUSTED_ORIGINS` derived from `ALLOWED_HOSTS` (`host` becomes `https://host`, `.domain` becomes `https://*.domain`, `*` is skipped) with an env override. Verify that `DEBUG=false SECRET_KEY=<50 random chars> ALLOWED_HOSTS=zeneke.example.com manage.py check --deploy` reports no issues.
- [x] 3.2 Add tests: subprocess checks of the derived origins, the override, the HSTS default (3600) and a configured value; `override_settings` request tests: a request without the proxy header gets a 301 to `https://`; with `X-Forwarded-Proto: https`, the response has `Strict-Transport-Security: max-age=3600`; a kid PIN sign-in over HTTPS sets a `Secure` session cookie; a POST with `Origin: https://zeneke.example.com` under the derived origins isn't rejected by CSRF (use `Client(enforce_csrf_checks=True)`); the Google login redirect contains an `https%3A%2F%2F` callback; in development a localhost sign-in still works and the cookie is not `Secure`. Verify `manage.py test backend` passes.

## 4. Static files and data directory

- [x] 4.1 Add `WhiteNoiseMiddleware` right after `SecurityMiddleware`; set `STORAGES` (WhiteNoise compressed manifest storage in production, Django's default in development); add `DATA_DIR` (default `BASE_DIR`, created if missing) and the database path `DATA_DIR / 'db.sqlite3'`. Verify `manage.py test` (the full suite) passes and that the local `runserver` serves `/static/css/style.css` with 200.
- [x] 4.2 Add tests: in a subprocess with `DATA_DIR=<tmpdir>/nested`, run `migrate` and check that `<tmpdir>/nested/db.sqlite3` exists; without `DATA_DIR`, the configured database name is `src/app/db.sqlite3`. Verify `manage.py test backend` passes.

## 5. Docker and documentation

- [x] 5.1 In the `Dockerfile`, run `collectstatic --noinput` at build time with `DEBUG=false`, a `SECRET_KEY` generated inside that `RUN` step and `ALLOWED_HOSTS=build`; remove the `collectstatic` block from `entrypoint.sh`. Verify `docker build` succeeds and the image contains `/app/app/staticfiles/staticfiles.json`.
- [x] 5.2 Update `src/.env.example` (development values `DEBUG=true`, `ALLOWED_HOSTS=localhost,127.0.0.1`, and commented `DATA_DIR`, `SECURE_HSTS_SECONDS`, `CSRF_TRUSTED_ORIGINS` with one-line explanations) and add a "Production environment" section to `src/README.md` (required and optional variables, how to generate a key, that a missing `.env` locally now means production mode). Verify the README's key-generation command runs as written.

## 6. Integration check

- [x] 6.1 Run the full suite and `makemigrations --check`. Then run the built image with production values (`DEBUG=false`, a random key, `ALLOWED_HOSTS=localhost`, `DATA_DIR=/data` on a temporary volume) and verify with curl: `/static/css/style.css` returns 200 with the CSS when `X-Forwarded-Proto: https` is sent; a request without the header returns 301 to `https://`; a response with the header carries HSTS; the database file appears in the volume; starting the image without `SECRET_KEY` exits with an error that mentions `SECRET_KEY`. Also confirm that the dev `docker compose up --build` still serves the site and its CSS on `http://localhost:8000`.

## Workflow follow-up

- Archive the change after review.
- Follow-up change to propose: deploying to the chosen host (VPS with Caddy or Fly.io), with a volume for `DATA_DIR`, secrets, a health check exempt from the HTTPS redirect, the Google redirect URI for the domain, and a non-root production container.
