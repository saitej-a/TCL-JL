# Shared image for web, celery_worker, celery_beat (D-08).
# Entrypoints are swapped per-service via compose `command:`; Phase 1.2 replaces
# the placeholder default CMD with gunicorn.
FROM python:3.11.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY docker/ /app/docker/

CMD ["python", "/app/docker/web_placeholder.py"]
