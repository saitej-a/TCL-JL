# PLAN 02-01 — Custom User Model & Password-Hashing Hardening

**Phase:** 2.1 · **Roadmap:** AUTH-01 · **Status:** ✅ Executed 2026-09-21 · **Written:** 2026-09-21
**Inputs:** `CONTEXT.md` in this directory (findings + two locked decisions)
**Pre-condition:** dev stack is down after the app restart — first execution step is `docker compose up -d` and confirming the 6 services recover healthy.

## Goal (roadmap "done when")

> Custom user model migrates cleanly; **Argon2id hashes on the registration path** with the
> T2.3 cost parameters (64 MB / 3 iterations / 2 threads); email case-folding enforced in the
> database via CITEXT; T2.4 password-complexity rules shipped as a validator.

## Tasks

### 1. `apps/accounts/fields.py` — CITEXT email (decision: custom field)

```python
class CITextEmailField(EmailField):
    description = "Email (case-insensitive via PostgreSQL citext)"
    def db_type(self, connection):
        return "citext"
```

- Swap `User.email` to `CITextEmailField()` (managers/USERNAME_FIELD unchanged).
- Migration `0003_citext_email`: `makemigrations accounts` → expect `AlterField`.
  **Contingency:** if the generated SQL fails on the live DB (missing `USING` cast),
  replace with `RunSQL("ALTER TABLE accounts_user ALTER COLUMN email TYPE citext
  USING email::citext", reverse_sql=...->varchar)` + `state_operations=[AlterField]`.
  Verify with `sqlmigrate accounts 0003` before applying.
- Keep `uq_user_email_lower` constraint this phase (accepted redundancy with citext;
  swap to `unique=True` in a later cleanup, not here — one schema change at a time).
- Keep manager write-time lowercase normalization (belt-and-braces).

### 2. `apps/accounts/hashers.py` — real T2.3 parameters (fixes inert `ARGON2_ARGS`)

```python
class Argon2idHasher(Argon2PasswordHasher):
    algorithm = "argon2id"     # explicit label
    time_cost = 3
    memory_cost = 65536        # 64 MiB in KiB
    parallelism = 2
```

- Register `"accounts.hashers.Argon2idHasher"` **first** in `PASSWORD_HASHERS`
  (first hasher = the one `set_password`/`create_user` use → the registration path).
- Delete `ARGON2_ARGS` from `config/settings/base.py` (inert setting; was never read).
- No hash-upgrade migration needed: dev DB only, zero users.

### 3. `apps/accounts/validation.py` — T2.4 complexity validator (decision: ship in 2.1)

`ComplexityPasswordValidator(min_length=10)` raising `ValidationError` with distinct codes:
`password_too_short` (<10), `password_no_upper`, `password_no_lower`, `password_no_digit`,
`password_no_special` (special = any non-alphanumeric). Wire into `AUTH_PASSWORD_VALIDATORS`
after `UserAttributeSimilarityValidator`. Implement `get_help_text()`.

### 4. `apps/accounts/admin.py` — minimal `UserAdmin`

Full `fieldsets`/`add_fieldsets` override (Django's default `UserAdmin` hardcodes
`username`), `ordering = ("email",)`, `list_display = ("email","is_staff","is_active","date_joined")`,
`search_fields = ("email",)`. Full admin triage tooling stays T8.9.

### 5. Tests — extend the existing green suite

| File | Proves |
|---|---|
| `tests/test_password_hashing.py` | `make_password` output matches `$argon2id$v=19$m=65536,t=3,p=2$…`; `create_user` stores Argon2id; verify/check_password round-trip |
| `tests/test_citext_email.py` | user created `Case@Test.com` is fetched by `filter(email="case@test.com")` (DB fold); case-changing email update keeps one row; wrong-case login-lookup helper behaves case-insensitively |
| `tests/test_password_complexity.py` | accept matrix (1 valid pw) + one reject per rule (short, no-upper, no-lower, no-digit, no-special) with correct `code`s |
| existing 10 tests | remain green untouched |

## Execution order

1. `docker compose up -d` → verify 6 services healthy (stack recovery)
2. Tasks 2→3 (settings-adjacent, no schema) → unit tests
3. Task 1 field + migration → `sqlmigrate` review → apply on live volume → lookup tests
4. Task 4 admin → smoke `createsuperuser` flow via `shell`
5. Full gate: `ruff check . && ruff format --check . && python -m pytest` in-stack

## Verification gates — all met 2026-09-21

- [x] `pytest` green — **27/27** (17 new + 10 existing untouched), `ruff` clean
- [x] `makemigrations --check --dry-run` → "No changes detected"
- [x] Migration `0003_alter_user_email` applied on the live dev volume; `sqlmigrate` showed a plain `ALTER COLUMN "email" TYPE citext` (no `USING` cast needed)
- [x] Wrong-case CITEXT lookup returns the user (proven in psql AND pytest)
- [x] Argon2id hash carries `m=65536,t=3,p=2`; `create_user` path emits it (proven under `override_settings` so it holds in CI too)
- [x] `.planning/STATE.md` + `REQUIREMENTS.md` traceability updated

## Out of scope (Phase 2.2)

Registration/login/verification/reset endpoints, SimpleJWT, `/me/`, deletion, rate limiting,
any serializer beyond what tests need.
