#!/bin/sh
set -e

cd /app/app
python manage.py migrate --noinput

exec "$@"
