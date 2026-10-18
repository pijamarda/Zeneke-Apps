#!/bin/sh
set -e

cd /app/app
python manage.py migrate --noinput

if [ "${DEBUG:-true}" = "false" ] || [ "${DEBUG:-true}" = "False" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
