FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
