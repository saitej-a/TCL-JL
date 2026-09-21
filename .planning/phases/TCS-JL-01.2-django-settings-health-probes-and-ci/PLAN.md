# PLAN — Phase 1.2: Django Settings, Health Probes & CI

**Status:** ✅ Executed 2026-09-21 · **Created:** 2026-09-21 · **Approach:** Direct execution (no separate executor agent)

## Goal

Complete Phase 1 per `10_MVP_TASKS.md` T1.3–T1.8: modular Django 5.x project with split
settings, PostgreSQL extensions, Redis partitioning, Celery topology, health probes (T1.7),
and CI (T1.8) — all verified against the running 6-service stack, not documented-only.

## Decisions (locked with user, 2026-09-21)

| Decision | Choice | Rationale |
|---|---|---|
| CI linters | **Ruff only** | Ruff supersedes Flake8; one fast tool, no triple-config drift. Spec's "Black/Flake8" satisfied by Ruff's format+lint rules. |
| Test harness | **Ship in 1.2** | pytest-django + `config/settings/test.py` + smoke tests land here so Phase 2 auth tests start on a working harness. |
| Prod smoke test | **Finish before planning** | Completed 2026-09-21: TLS 1.3 + HSTS + 301 + JSON root verified on `tcsjl-prod`, then torn down. |

## Already executed & verified (2026-09-20/21)

- T1.3 `config/settings/{base,local,production}.py`, `config/{celery,wsgi,asgi,urls,views}.py`, `apps/` layout
- T1.4 Migration `accounts/0001_pg_extensions` (`uuid-ossp`, `citext`) + `CONN_MAX_AGE=600` + conn health checks
- T1.5 django-redis on db0 (cache round-trip verified); broker db1 (worker `Connected to redis://redis:6379/1`)
- T1.6 Celery app, 3 queues (`default`/`notifications`/`maintenance`), beat schedule (3 crons), `control.ping` → pong
- Custom `accounts.User` (UUIDv4 PK, `uq_user_email_lower` unique constraint) as migration base for Phase 2
- Entry points: shared `docker/entrypoint.sh` (migrations gated to web via `RUN_DB_MIGRATIONS`, `exec` for PID-1 signal handling), gunicorn CMD, compose dev+prod
- Infra hardening found by verification: nginx runtime DNS (`resolver 127.0.0.11`) fixes boot race; root JSON status view (prod DEBUG=0 correctly 404'd the old empty root); web container healthcheck gates nginx

## Remaining work

### 1. T1.7 — Health probes
- `GET /health/` — liveness: process up → `200 {"status":"alive"}` (no deps touched)
- `GET /health/ready/` — readiness: `SELECT 1` + Redis `PING` (via cache client); all ok → `200 {"database":"ok","cache":"ok"}`; any failure → `503` with failing component named
- Wire compose healthchecks to `/health/ready/` (replaces bare-TCP check)

### 2. Test harness
- `requirements-dev.txt`: pytest, pytest-django, ruff
- `pytest.ini` / config: `DJANGO_SETTINGS_MODULE=config.settings.test`, `--reuse-db`
- `config/settings/test.py`: fast Argon2 param override, console email, eager-off Celery
- Smoke tests (`apps/accounts/tests/`): health endpoints (ok + degraded→503), User manager (create/superuser/case-insensitive dup constraint)

### 3. T1.8 — CI (GitHub Actions)
- `.github/workflows/ci.yml` on PR → `main`: jobs on `ubuntu-latest`
  - services: `postgres:16` + `redis:7` (health-gated)
  - steps: install `-r requirements.txt -r requirements-dev.txt` → `ruff check .` → `ruff format --check .` → `pytest`
- Required-status branch protection on `main` is a repo-settings action for the user (cannot be done from code).

## Verification (definition of done for this plan) — all met 2026-09-21

- [x] `pytest` green inside the stack — **10/10** under both local and test settings
- [x] `ruff check .` + `ruff format --check .` clean (via in-container run, mirroring CI)
- [x] `/health/` → 200; `/health/ready/` → 200 db+cache ok; **503 drill done** (redis stopped → 503 naming `cache`, liveness stayed 200, self-healed after restart)
- [x] Both compose healthchecks now gate on `/health/ready/`; web shows healthy
- [x] Production secret gate: import without `DJANGO_SECRET_KEY` → RuntimeError; with key → imports (CI-safe)
- [ ] CI first green run + branch protection on `main` — **user action on GitHub** (push, enable required status checks)
- [x] `.planning/STATE.md` updated: Phase 1.2 complete

## Out of scope

- Nginx TLS/headers hardening (10.2) · Bandit/pip-audit (10.3) · E2E tests (10.1/10.2)
- Any API endpoints (Phase 2+); admin customization (8)
