# Steps followed for uv setup

uv run django-admin startproject backend .

## Run locally

From `src/app`:

```
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Settings read plain environment variables (see `src/.env.example`); `src/.env`
is only loaded by docker-compose. Without them, local defaults apply.

### Signing in

- **Parents** (superusers) sign in with Google/GitHub. When the OAuth keys are
  not set (typical locally), sign in at `/admin/login/` with the superuser you
  created; the session also works for the rest of the site.
- **Kids** are created by a parent at `/family/`, which shows a one-time
  6-digit setup code (valid 24h). The kid enters their username + that code on
  `/accounts/login/` and chooses their own 4-digit PIN. Parents can reset a PIN
  or unlock an account (5 wrong PINs lock it for 15 minutes) from `/family/`.

## Django specific commands

### Start the server
uv run manage.py runserver

### Run the tests
uv run manage.py test

### Add an application
uv run manage.py startapp bingo
