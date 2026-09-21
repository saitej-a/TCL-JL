# CONTEXT — Phase 2.1: Custom User Model & Password Hashing Hardening

**Discussed:** 2026-09-21 (with user) · **Next step:** write PLAN for 02-01 · **Approach:** direct execution like Phase 1.2

## Roadmap definition (ROADMAP.md)

> **Goal:** `accounts.User` with UUIDv4 PK, case-insensitive CITEXT email, and Argon2id
> hashing (AUTH-01). **Plans:** 02-01. **Done when:** model migrates cleanly; Argon2id
> hashes on the registration path.

## Already delivered by Phase 1.2 (do not redo)

- `apps/accounts/models.py`: custom `User` (AbstractBaseUser + PermissionsMixin), UUIDv4
  PK, email as USERNAME_FIELD, lowercase normalization in both manager create methods.
- DB-level case-insensitive uniqueness via `UniqueConstraint(Lower("email"))` →
  `uq_user_email_lower` functional unique index (migration `0002_user`).
- Argon2 listed first in `PASSWORD_HASHERS` (but see finding #1 — params not actually wired).
- `pg_extension` uuid-ossp + citext already enabled (migration `0001_pg_extensions`).
- Test harness live (pytest-django, 10/10 green), ruff clean, CI workflow shipped.

## Findings from discussion

1. **`ARGON2_ARGS` in `config/settings/base.py` is inert.** Django's
   `Argon2PasswordHasher` never reads it — T2.3's exact parameters (64 MB memory,
   3 iterations, 2 threads) require a custom hasher subclass. This is the real T2.3 work.
2. **Email column is plain `varchar`.** Uniqueness folds case, but SQL lookups don't.
   Django 5.2 removed the built-in CI*/CIText fields (removed in 5.1), so CITEXT now
   requires a tiny custom field (`db_type = "citext"`).
3. **T2.4's password-complexity rules don't exist yet** (only min-length/common/numeric).

## Decisions locked with user (2026-09-21)

| Decision | Choice | Rationale |
|---|---|---|
| Email case-folding | **Custom CITEXT field** (`db_type="citext"`) | DB folds *every* comparison for the auth identity column (defense-in-depth); matches the 2.1 goal text literally; mechanism still fully supported in Django 5.2 despite built-in field removal. |
| T2.4 complexity rules | **Ship in 2.1** | Validator is a unit-testable pipeline component; T2.4's registration endpoint (Phase 2.2) then just wires it in — cleaner phase boundary. |

## Scope for plan 02-01

1. `apps/accounts/fields.py`: `CITextEmailField(EmailField)` with `db_type = "citext"` + migration altering the column (extension already enabled).
2. `apps/accounts/hashers.py`: `Argon2idHasher(Argon2PasswordHasher)` with 64 MB / 3 it / 2 threads; register first in `PASSWORD_HASHERS`; delete inert `ARGON2_ARGS`.
3. `apps/accounts/validation.py`: `ComplexityPasswordValidator` (min 10 chars, uppercase, lowercase, digit, special) wired into `AUTH_PASSWORD_VALIDATORS`.
4. Minimal `UserAdmin` registration for Django admin (staff usability; full admin tooling is T8.9).
5. Tests: Argon2id hash format+params proof on `set_password`/`create_user`, CITEXT lookup folding (wrong-case email retrieves the user), complexity-validator accept/reject matrix; existing constraint tests must stay green.

## Out of scope (Phase 2.2 per roadmap)

Registration/login/verification endpoints, SimpleJWT, password reset, `/me/`,
account deletion, rate-limiting (T2.4–T2.12).

## Verification gates for 02-01

- [ ] `pytest` green in-stack (ruff clean alongside)
- [ ] `makemigrations --check` green; migration applies on the live dev volume
- [ ] CITEXT lookup with wrong-case email returns the user
- [ ] Argon2id hash carries the spec'd cost params
