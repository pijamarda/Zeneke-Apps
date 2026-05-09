#!/bin/sh
set -e

cd /app/app
uv run python manage.py migrate --noinput

if [ "${DEBUG:-true}" = "false" ] || [ "${DEBUG:-true}" = "False" ]; then
    uv run python manage.py collectstatic --noinput
fi

exec "$@"
