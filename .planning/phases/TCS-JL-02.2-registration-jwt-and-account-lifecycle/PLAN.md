# PLAN — Phase 2.2: Registration, JWT & Account Lifecycle (combined 02-02 + 02-03)

**Phase:** 2.2 · **Roadmap:** AUTH-02..AUTH-06 · **Status:** ✅ Executed 2026-09-21 · **Written:** 2026-09-21
**Inputs:** `CONTEXT.md` in this directory (decisions D1/D2 + spec-derived invariants from 06 + 04)
**Shape (D2):** one combined pass — the two verify-gated stages below, one stack rebuild, one live
verification round. Roadmap labels 02-02 / 02-03 remain accounting only and are **not** separate stages.
**Pre-condition:** stack state after the app restart is unknown — execution step 0 rebuilds and
boots the 6-service stack and waits for health before anything else.

## Goal (roadmap "done when")

> Registration, email verification, password reset, rate-limited anti-enumeration login,
> SimpleJWT rotation/blacklisting, `/me/`, and anonymizing account deletion (AUTH-02..06).
> Headline criteria: **replaying rotated refresh tokens revokes the session family**;
> **deletion anonymizes contributions while retaining the user row** (tombstone seam for Phase 5).

## Decisions carried from CONTEXT.md

| # | Decision | Consequence in this plan |
|---|----------|--------------------------|
| D1 | Registration collision → generic success + notify owner | `POST /auth/register/` returns the **identical** 201 message-only body for new, colliding, and (no dispatch) unknown emails; collision dispatches `registration_collision` email to the existing owner. No "email exists" error ever. |
| D2 | One combined pass, two verify-gated stages | Stage 1 = all code + automated gate; Stage 2 = single live verification round. |

**Response shapes pinned (spec-exact, flagged for review):**
- Register: `201` + `{"message": "Registration successful. Please check your email to activate your account."}` — **message-only** body on both branches (06 §2.4 recommended shape + D1). This deliberately omits the illustrative `user` block from 04 §12.1: echoing a user object (or a differing shape) on the collision branch would weaken anti-enumeration. 06+D1 are authoritative.
- Verify: `{"message": "Email verified successfully."}` (04 §13.2) · Resend: generic per 06 §2.5 ·
  Reset request: generic per 06 §3.5 · Reset confirm: `{"message": "Password reset successfully."}` (04 §17.2)
- Login failure: `{"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}` (04 §14) — same body for unknown email, wrong password, and banned (`is_active=False`) accounts.
- 429: `RATE_LIMITED` envelope + `Retry-After` header (06 §7.3); DRF's auto `Retry-After` preserved in the custom handler.
- Logout `204` (04 §16) · Deletion `204` (04 §78, wrong password → generic `403`).

---

## Stage 1 — Build & automated gate (all 02-02 + 02-03 code)

**Gate:** full pytest suite green in-stack + ruff clean + migrations complete. No live drill until this passes.

### 1.1 Settings & infra (`config/settings/base.py`)
- `SIMPLE_JWT` per 06 §3.2: 15-min access / 7-day refresh, `ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`, `UPDATE_LAST_LOGIN=True`, `HS256`,
  `SIGNING_KEY = env JWT_SECRET_KEY (fallback SECRET_KEY)`, audience `https://tracker.internal/api`,
  issuer `tcs-joining-tracker-auth`, `USER_ID_FIELD="id"` (UUID).
- `"rest_framework_simplejwt.token_blacklist"` into `INSTALLED_APPS` (its migrations apply on `migrate`).
- `DEFAULT_THROTTLE_RATES` seeded: `auth_login 5/min`, `auth_register 3/hour`,
  `auth_password_reset 3/hour`, `auth_verify_resend 1/min` (06 §7.1; currently `{}`).
- `PASSWORD_RESET_TIMEOUT = 3600` (06 §3.5).
- `.env.example`: add `JWT_SECRET_KEY` (dev falls back to `SECRET_KEY`, so optional locally).
  `.env.prod.example` is client-blocked → **user action**: add `JWT_SECRET_KEY` (distinct 256-bit value, 06 §3.1.1) to `.env.prod`.
- Token payload discipline: access carries **UUID + `is_verified` only** — never email/PII (06 §3.1.1).

### 1.2 accounts app code (new modules)
- `migrations/0004_user_timestamps.py`: `created_at` (`auto_now_add`) + `updated_at` (`auto_now`)
  per 06 §2.1 (executor hint: AddField with `auto_now_add` needs `default=timezone.now`,
  `preserve_default=False`; dev DB has zero users so backfill is trivial).
- `throttles.py`: `LoginRateThrottle(ScopedRateThrottle)` with combined IP+email bucket
  `throttle_login_{ip}_{email}` (06 §7.2); thin scoped throttles for register / reset / resend
  (views just set `throttle_scope`).
- `permissions.py`: `IsVerified` (Phase 5 consumption; unit-tested now, unused by views this phase —
  unverified users log in fine per 06 §2.6).
- `serializers.py`: Register (validate_password against the candidate user; `is_staff`/`is_superuser`
  never in fields — 06 §4.4), Login (TokenObtainPair subclass), Verify, Resend, ResetRequest,
  ResetConfirm, Logout, Deletion, `UserPrivateSerializer` (`id, email, is_verified, created_at,
  profile_completed=False` until Phase 3.1).
- `services.py`:
  - `register_user` — create unverified user; **collision branch**: existing email → dispatch
    collision email to owner, return the same payload (D1).
  - `consume_verification_token` — `TimestampSigner`, per-purpose salt (`accounts.email-verify.v1`),
    `max_age=86400`; single-use = reject when `is_verified` already True.
  - `request_password_reset` / `confirm_password_reset` — `default_token_generator` (spec option 1)
    packed as `uidb64.token` inside the single `token` field; confirm re-runs the full
    `validate_password` pipeline, rotates the hash (inherently kills outstanding reset tokens),
    then bulk-blacklists the user's refresh tokens (revocation matrix trigger 2).
  - `revoke_user_refresh_tokens(user)` — **extracted bulk blacklist-all helper now** (shared later by
    the Phase 8 ban workflow, per CONTEXT).
  - `revoke_token_family(user, fam)` — replay-revocation (see 1.3).
  - `anonymize_delete_account(user, password)` — re-auth (wrong pw → generic 403), then one
    transaction: device-revocation **hook point documented in code** (Device arrives Phase 6),
    `revoke_user_refresh_tokens`, email → `deleted_<uuid4>@tracker.internal`, `is_active=False`,
    `is_verified=False`, `set_unusable_password()`, **row retained** (Phase 5 `Post.author` /
    `Comment.author` SET_NULL tombstone seam).
- `tasks.py`: `send_verification_email`, `send_password_reset_email` (the two names Celery routes
  already reserve — create, don't re-route) + `send_registration_collision_email` (one additive route
  to `default`). Rendered from templates under `apps/accounts/templates/account/emails/`:
  `email_verification.txt`, `password_reset.txt`, `registration_collision.txt`. Services dispatch via
  `transaction.on_commit` so rolled-back writes never email.
- `exceptions.py`: minimal DRF exception handler for accounts views — spec error envelopes
  (`INVALID_CREDENTIALS`, `RATE_LIMITED` + `Retry-After`); attached per-view, global rollout deferred.
- `views.py` + `urls.py`: `RegisterView`, `VerifyEmailView`, `ResendVerificationView`, `LoginView`,
  `TokenRefreshView` (custom serializer), `LogoutView`, `PasswordResetRequestView`,
  `PasswordResetConfirmView`, `MeView`, `DeleteAccountView`; wired into `config/urls.py` under
  `api/v1/` (auth/ + me/ + account/). Logout: well-formed refresh → blacklist + `204` (idempotent);
  malformed → `400`.

### 1.3 JWT rotation & family reuse-detection (headline criterion 3)
SimpleJWT does **not** revoke descendants out of the box — built here:
- `FamilyTokenObtainPairSerializer`: sets a random `fam` (family) claim on the refresh at login;
  rotation inherits it automatically (claims survive `set_jti/set_exp/set_iat`).
- `FamilyTokenRefreshSerializer`: on rotation, re-hydrates the `is_verified` claim from the DB
  (login-time claims go stale after verification), records the rotated child as an `OutstandingToken`
  (SimpleJWT only records `for_user`-issued tokens, not rotated ones), returns access + new refresh.
- On a submitted refresh whose jti is **already blacklisted** (replay): decode payload (signature
  verified, expiry not enforced), resolve `fam` → `revoke_token_family` blacklists every outstanding
  token of that user sharing the `fam` claim → `401`. Undecodable/expired tokens → plain `401`.
- Test contract pins behavior, not internals (see 1.4 rotation tests).

### 1.4 Tests — extend the existing green suite (27 stay untouched)

| File | Proves |
|---|---|
| `test_registration.py` | 201 + identical message-only body on create/collision/unknown-email; collision dispatches owner email & creates no user (D1); validation failures (mismatch, weak pw, bad email); injected `is_staff`/`is_superuser` ignored |
| `test_verification.py` | verify flips `is_verified`; expired token rejected; reuse-after-verify rejected; resend generic 200 (incl. unknown email, no email sent) + 1/min → 429 |
| `test_login.py` | tokens + user block; **identical generic body** for unknown email / wrong password / banned account; unverified login issues tokens with `is_verified: false`; 6th attempt → 429 + `Retry-After`; different email same IP not collateral-blocked (combined-bucket semantics) |
| `test_token_rotation.py` | **headline:** refresh rotates → old refresh replayed → 401 **and** child refresh dead (family revoked); new refresh works when no replay; access payload has UUID + `is_verified` only (no email/PII) |
| `test_logout.py` | `204`; submitted refresh dead afterwards |
| `test_password_reset.py` | generic 200 both branches (email only for real user); confirm re-validates pipeline; hash rotates (old pw fails, new works); outstanding refresh dead after confirm; expired/bad token rejected; 3/hour → 429 |
| `test_me.py` | exact shape (`id, email, is_verified, created_at, profile_completed:false`); no password-hash/staff/token fields; 401 unauthenticated |
| `test_deletion.py` | wrong password → generic 403; success → 204; row retained with `deleted_*@tracker.internal`, `is_active/is_verified=False`, unusable password; all refresh blacklisted; login afterwards → generic 401 |
| `test_permissions.py` | `IsVerified` admits verified, rejects unverified + anonymous |

Celery email tasks run eagerly in tests via `override_settings(CELERY_TASK_ALWAYS_EAGER=True)` +
locmem backend (`mail.outbox`), inside `transaction=True` db marks to fire `on_commit` dispatches.

### 1.5 Execution order (Stage 1)
1. `docker compose up -d --build` → 6 services healthy (**the one rebuild**; dev code is bind-mounted, Stage 2 needs no rebuild)
2. Task 1.1 settings + `.env.example` → 1.2 migration → applied on the live volume by the entrypoint
3. 1.2 modules in dependency order: throttles/permissions/exceptions → serializers → services → tasks + templates → views/urls
4. 1.3 rotation/family serializers + services
5. 1.4 test files → `docker compose run --rm web python -m pytest`
6. **Stage 1 gate:** pytest green · `ruff check .` · `ruff format --check .` · `makemigrations --check` clean (entrypoint gate) — fix before Stage 2

## Stage 1 gate — met 2026-09-21

- [x] pytest green in-stack — **92/92** (65 new + 27 pre-existing untouched), `ruff check` + `format --check` clean, `makemigrations --check` clean
- [x] Executor findings vs plan: (a) User lacked `is_verified` — added to 0004; (b) ModelSerializer auto-`UniqueValidator` would have leaked "email exists" — serializer declares email explicitly (D1 preserved); (c) `apps/accounts/__init__.py` missing (2.1 anomaly) — created, tests no longer double-collect
- [x] Family reuse-detection smoke-verified before tests: rotate → replay 401 → child dead

## Stage 2 — Live verification round — all met 2026-09-21

- [x] Live curl drill: register 201 (generic) → verification email in worker logs → verify 200 → reuse 400 → login 200 → rotate → **replay 401 `INVALID_CREDENTIALS` and rotated child 401 (family revoked)** → `/me/` exact shape → logout 204 → refresh-after-logout 401 → reset round-trip (generic request 200 → confirm 200 → old pw 401 / new pw 200) → deletion: wrong pw 403 (generic), correct pw 204, DB row `deleted_…@tracker.internal` retained with flags false, post-deletion login 401
- [x] Throttle probe: 6th login attempt → 429 + `Retry-After: 60` header (live, through nginx)
- [x] D1 collision live: identical 201 body + `registration collision notice dispatched` in worker logs
- [x] `docker compose -f docker-compose.prod.yml config` validates; `/health/ready/` 200 db+cache ok; all 6 services healthy after restart

## Out of scope (explicitly deferred, per CONTEXT.md)

- Phase 3.1: CandidateProfile (`profile_completed` stays `false` on `/me/`).
- Phase 5: tombstone consumption of anonymized users (author FK nulling).
- Phase 6: device revocation inside deletion (hook documented in `services.py`).
- Phase 8: ban workflow (shares the extracted `revoke_user_refresh_tokens` helper).
- Global custom exception-handler rollout; HttpOnly-cookie token mode (SPA uses Bearer, 06 §3.3 option 1).
