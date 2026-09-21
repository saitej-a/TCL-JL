#!/bin/sh
# Shared entrypoint for web / celery_worker / celery_beat (D-08).
# RUN_DB_MIGRATIONS=1 (web only) validates & applies migrations before serving.
set -e

if [ "${RUN_DB_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] django system check"
    python manage.py check
    echo "[entrypoint] verifying migrations are complete"
    python manage.py makemigrations --check --dry-run
    echo "[entrypoint] applying migrations"
    python manage.py migrate --no-input
fi

echo "[entrypoint] collecting static files"
python manage.py collectstatic --no-input

echo "[entrypoint] exec: $*"
exec "$@"
