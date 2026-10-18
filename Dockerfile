FROM python:3.12-slim

# Pinned so builds are repeatable; keep in step with the uv used locally (`uv --version`).
COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /uvx /bin/

# Keep the virtualenv outside /app so the dev bind mount (./src:/app) never hides it
# and every `--build` picks up dependency changes.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY src/pyproject.toml src/uv.lock ./
RUN uv sync --frozen --no-cache

COPY src/ .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app/app

# Collect static files into the image. The key and host only satisfy production
# settings validation for this step; they are not kept in the image.
RUN DEBUG=false ALLOWED_HOSTS=build \
    SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
    python manage.py collectstatic --noinput

# Unprivileged runtime user. /data (DATA_DIR in production) is owned by it, and a
# named volume mounted there inherits that ownership when first created.
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin zeneke \
    && mkdir /data && chown zeneke:zeneke /data

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

USER zeneke

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
