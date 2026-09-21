# Phase 2.2 — Discussion Record: Registration, JWT & Account Lifecycle

Date: 2026-09-21
Scope: Roadmap plans **02-02** (registration, verification, reset, rate-limited login) + **02-03** (JWT rotation/blacklist, `/me/`, account deletion), executed as **one combined pass** (decision D2).
Requirements covered: AUTH-02..AUTH-06 (AUTH-01 done in 2.1).

## Decisions locked (user)

- **D1 — Registration collision response: generic success + notify owner.**
  `POST /auth/register/` for an existing email returns the standard
  `"Registration successful. Please check your email to activate your account."`
  payload AND dispatches a "someone tried to register with this address" email to
  the existing owner (06 §2.4 recommended branch). No "email exists" errors, ever.
  Requires one extra email template (`account/emails/registration_collision.txt`).
  Non-existent emails get the same payload (no dispatch).
- **D2 — Execution shape: one combined pass.** Single PLAN.md with two
  verify-gated stages, one stack rebuild + verification round. 02-02/02-03 stay
  as roadmap accounting labels only.

## Spec-derived invariants (no decision needed — straight from 06 + 04)

- **JWT (06 §3):** 15-min access / 7-day refresh, `ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`, `UPDATE_LAST_LOGIN=True`, HS256,
  `SIGNING_KEY = env JWT_SECRET_KEY (fallback SECRET_KEY)`, audience
  `https://tracker.internal/api`, issuer `tcs-joining-tracker-auth`,
  `USER_ID_FIELD=id` (UUID). Access payload: UUID + `is_verified` claim only —
  never email/PII. Reuse-detection: replaying a rotated refresh token must
  blacklist the whole token family (success criterion 3).
- **Login (06 §7.2, 04 §14):** generic `INVALID_CREDENTIALS` body; scoped throttle
  `auth_login: 5/min` on a combined IP+email bucket (`throttle_login_{ip}_{email}`);
  constant-time behavior (Django's dummy-hash path covers unknown-email timing).
- **Unverified users (06 §2.6):** login issues tokens normally with
  `is_verified: false` surfaced in the user block; verified-only access arrives
  later as a `IsVerified` permission class consumed by Phase 5 mutations. `Banned`
  (`is_active=False`) accounts get 401 via SimpleJWT's default auth rule.
- **Verification (06 §2.5):** 24h single-use token via
  `django.core.signing.TimestampSigner` (salted per-purpose);
  `POST /auth/verification/verify/` (Option A) plus
  `POST /auth/verification/resend/` throttled `1/min` with generic response.
- **Password reset (06 §3.5):** `default_token_generator` (spec option 1),
  `PASSWORD_RESET_TIMEOUT=3600`, generic 200 on both request branches
  (`3/hour` throttle), confirm re-validates the full password pipeline, and the
  hash change inherently invalidates outstanding tokens + must bulk-blacklist
  the user's refresh tokens (revocation matrix trigger 2).
- **Logout (04 §16):** `POST /auth/logout/` → blacklist submitted refresh → `204`.
- **Deletion (06 §2.7):** `DELETE /api/v1/account/` with password re-auth →
  revoke devices (hook point; Device model arrives Phase 6), bulk-blacklist all
  refresh tokens, anonymize email to `deleted_<uuid4>@tracker.internal`,
  `is_active=False`, `is_verified=False`. **User row retained** — gives Phase 5's
  `Post.author`/`Comment.author` a SET_NULL/tombstone seam; threads preserved.
- **Throttle rates (06 §7.1):** `auth_login 5/min`, `auth_register 3/hour`,
  `auth_password_reset 3/hour`, `auth_verify_resend 1/min` — seeded into
  `DEFAULT_THROTTLE_RATES` (currently `{}` in base.py).

## Inputs already in place from 2.1

- `accounts.User`: UUIDv4 PK, CITEXT email, `uq_user_email_lower`, Argon2id
  hasher (m=65536, t=3, p=2), `ComplexityPasswordValidator` — registration path
  just consumes these.
- `config/settings/base.py`: SimpleJWT as `DEFAULT_AUTHENTICATION_CLASSES`;
  Celery routes already **reserve** `accounts.tasks.send_verification_email` /
  `send_password_reset_email` (create the tasks, don't re-route); console email
  backend in dev.
- Test harness green (27/27) — extend, don't rebuild.

## Deliverables (plan inputs)

1. **Settings/urls:** `SIMPLE_JWT` block; `rest_framework_simplejwt.token_blacklist`
   in `INSTALLED_APPS` (+migration); `DEFAULT_THROTTLE_RATES` seeded;
   `PASSWORD_RESET_TIMEOUT`; `/api/v1/` router incl. `auth/` + `me/` +
   `account/`; env additions (`JWT_SECRET_KEY`) to `.env.example` /
   `.env.prod.example` (client blocks writing the secret-bearing local files —
   user adds the value).
2. **accounts app:** `serializers.py` (Register, Login, Verify, Resend, Reset
   request/confirm, Logout, Deletion, `UserPrivateSerializer` for `/me/`),
   `throttles.py` (LoginRateThrottle combined bucket), `services.py`
   (register-with-collision-branch, verify-consume, reset-confirm + blacklist,
   anonymize-delete transaction), `tasks.py` (the two reserved Celery tasks,
   email dispatch), `emails.py` or templates under
   `apps/accounts/templates/`, `permissions.py` (`IsVerified` for later phases),
   migration for `created_at`/`updated_at` (06 §2.1 entity table; auto_now_add /
   auto_now).
3. **Tests:** registration happy-path + collision branch (generic body + owner
   email dispatched) + validation failures; verification expire/reuse/consume;
   login ok / generic-fail / unverified-flag / 429 after 5th attempt;
   refresh rotation + replay-revokes-family (the headline criterion);
   logout 204 + blacklist; reset request generic both branches / confirm
   rotates hash + kills old refresh; `/me/` shape (no PII leaks);
   deletion: wrong password 403, success anonymizes + blacklists + retains row.
4. **Wire-up:** Celery worker/beat unchanged (routes already present);
   compose unchanged except image rebuild.

## Verification gates (execute stage)

- Full pytest suite green in-stack (`docker compose run --rm web` + dev-deps),
  including the rotation-replay test.
- Live curl drill on the running stack: register → console email → verify →
  login → refresh → **replay old refresh → 401 + family dead** → `/me/` →
  logout 204 → reset round-trip → deletion re-auth fail then succeed.
- Throttle probes: 6th login attempt → 429 with `Retry-After`.
- `ruff check` + `format --check` clean; `makemigrations --check` clean
  (entrypoint gate).
- Prod compose still validates; `/health/ready/` untouched.

## Explicitly deferred

- Phase 3.1: CandidateProfile (Profile completed flag on /me/ stays false).
- Phase 5: tombstone consumption of anonymized users (author FK nulling).
- Phase 6: Device revocation inside deletion (hook documented in services.py).
- Phase 8: ban workflow (is_active=False + blacklist protocol shared with
  deletion service — extract the blacklist-all helper now).
