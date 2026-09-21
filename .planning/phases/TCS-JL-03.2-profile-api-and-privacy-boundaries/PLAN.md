# PLAN 03-02 — Profile API & Privacy Boundaries

**Phase:** 3.2 · **Roadmap:** PROF-04 (exposes PROF-01..03 through the API) · **Status:** ✅ Executed (2026-09-21) · **Written:** 2026-09-21
**Inputs:** `CONTEXT.md` in this directory (decisions D1–D4 + invariants); 04 §19–§23; 06 §5.1–§5.3; 10_MVP T3.4–T3.8; 02 §11–12
**Scope discipline:** API layer only on top of 3.1 — serializers, views, URLs, permissions, impersonation validator, tests. **No model changes, no migrations expected** (`makemigrations --check` must stay clean). Timeline sync (4.1), feed consumption of public serializers (5.x), moderation tooling (8) are later phases.
**Pre-condition:** 3.1 executed & pushed (`161d834`); 6-service stack healthy; 145-test suite green (92 accounts + 53 candidates).

## Goal (roadmap "done when")

> Public serializers leak no PII; impersonation attempts are rejected.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | POST honors a requested `current_status` via the transition chain, atomically | Create pins REGISTERED then `transition_status` inside one transaction; illegal edge (incl. 04 §20's own example body) → 400 on `current_status`, nothing persisted |
| D2 | Public endpoint built now: `GET /api/v1/candidates/{id}/` | Exact 04 §23 safe shape; `CandidatePublicSerializer` is the single redaction boundary Phase 5 reuses |
| D3 | Impersonation blocker: case-insensitive **substring** match | Settings-held `RESERVED_DISPLAY_NAME_TOKENS`; validated even in ANONYMOUS mode; lookalikes blocked, rare false positives accepted |
| D4 | `DELETE /api/v1/profile/` → 405 | Envelope points to `DELETE /api/v1/account/` (04 §22 preferred MVP) |

**Spec-derived, no decision:** create/update gated on **active + verified** users (3.1 D4 note;
tombstones never own profiles); duplicate creation rejected (T3.4) as **409 `profile_exists`**;
PATCH "only fields permitted for candidate self-editing" (04 §21) with `current_status`
routed through 3.1's `transition_status` — the single mutation point 4.1's TIME-02 wraps;
error style = 2.2's project envelope via the accounts exception handler; zero-exposure set
(04 §23 + 06 §5.3): email, phone, FCM token, password, private notes, internal moderation state.

## Stage 1 — Build & automated gate

**Gate:** full pytest green (145 pre-existing stay untouched) + `ruff check`/`format` clean + `makemigrations --check` clean. No live drill until this passes.

### 1.1 Settings (`config/settings/base.py`)
```python
# Reserved display-name tokens (T3.7 via 3.2 D3). Extend via settings, no deploy.
RESERVED_DISPLAY_NAME_TOKENS = ["TCS", "Tata", "HR", "Admin", "Official", "Moderator"]
```
Read **at call time** in the validator (same pattern as `BATCH_YEARS`) so
`override_settings` tests and ops changes apply without code edits.

### 1.2 `apps/candidates/serializers.py`
- **`CandidatePrivateSerializer`** (owner GET/PATCH representation, exact 04 §19 shape):
  `id, display_name, public_identity_mode, batch, hiring_type, region, interview_center,
  interview_date, joining_location, current_status, offer_letter_date,
  expected_joining_date, created_at, updated_at`. `id`, `created_at`, `updated_at`,
  `current_status` read-only here (status moves only via the validated PATCH flow).
- **`CandidateProfileCreateSerializer`**: fields per 04 §20 **minus `current_status`**
  (handled as the D1 side-channel), `display_name` + `batch` validated, `user` taken from
  `request.user`. `validate()` enforces: user active+verified; no existing profile.
  Exposes `requested_status` (optional kwarg) to the service.
- **`validate_display_name(value)`** (module-level, shared by create/PATCH paths):
  strip → casefold → substring-compare against `settings.RESERVED_DISPLAY_NAME_TOKENS`
  (casefolded); hit ⇒ `ValidationError(code="reserved_display_name")` listing nothing
  specific (avoid teaching bypasses). Also wired as the model-independent validator so
  ANONYMOUS-mode names can't smuggle reserved strings for later mode flips (D3).
- **`CandidatePublicSerializer`** (profile-sourced, exact 04 §23 shape):
  `id, display_name (resolved via get_public_display_name), batch, hiring_type, region,
  current_status`. Nothing else — no email/phone/interview internals/timestamps.
- **`AuthorPublicSerializer`** (user-sourced, per 06 §5.1/§5.2 — defined here so Phase 5
  imports from the profile domain): `id` (user UUID),
  `display_name = SerializerMethodField` via 3.1's `resolve_public_display_name`,
  `batch`/`hiring_type`/`region` via `candidate_profile` with **None-safe sources**
  (profile-less user ⇒ `None`, never a crash, never an email). Never any other field.

### 1.3 `apps/candidates/services.py` — additions (keep 3.1 code untouched)
- `ProfileAlreadyExistsError(Exception)` with `code = "profile_exists"`.
- `create_profile(user, data, requested_status=None) -> CandidateProfile`:
  `with transaction.atomic():` create with `current_status=Status.REGISTERED` (race-safe:
  catch `IntegrityError` → re-raise as `ProfileAlreadyExistsError`), then — D1 — if
  `requested_status` not None/REGISTERED, `transition_status(profile, requested_status)`.
  `InvalidTransitionError` propagates ⇒ whole transaction rolls back (no profile row).
- `update_profile(profile, data) -> CandidateProfile`:
  `with transaction.atomic():` pop `current_status` if present → save remaining fields →
  `transition_status(profile, requested)` if requested. Rejected transition leaves the
  field save rolled back too (mixed PATCHes are all-or-nothing).

### 1.4 `apps/candidates/permissions.py`
- `IsProfileOwner(BasePermission)`: object-level `obj.user_id == request.user.id`.
  (The `/profile/` routes always resolve the object from `request.user`; the class exists
  to make the T3.5 ownership discipline explicit and unit-testable, and for reuse if a
  lookup route ever appears.)

### 1.5 `apps/candidates/views.py`
- `ProfileView` (self-service singleton):
  - `permission_classes = [IsAuthenticated, IsVerified]` (accounts' shipped class; 403
    "Email verification required." for unverified, 401 for anonymous).
  - `get_object()` → `request.user.candidate_profile` or 404 (project envelope).
  - GET → private serializer (§19). POST → create serializer + `create_profile` → 201 §19
    shape; `ProfileAlreadyExistsError` → **409 `profile_exists`**; `InvalidTransitionError`
    → 400 on `current_status` with the machine's code.
  - PATCH → update serializer + `update_profile` → 200 §19 shape.
  - D4: omit `delete` from `http_method_names` **and** override
    `http_method_not_allowed()` to return the project envelope with
    code `method_not_allowed` and detail pointing to `DELETE /api/v1/account/`.
- `PublicCandidateView` (D2): `RetrieveAPIView`, `AllowAny`,
  `queryset = CandidateProfile.objects.select_related("user")`, pk is the profile UUID,
  missing ⇒ 404 envelope; renders `CandidatePublicSerializer` only.
- Executor check: confirm `REST_FRAMEWORK["EXCEPTION_HANDLER"]` is wired to
  `apps.accounts.exceptions.auth_exception_handler` (2.2 established it); if any 2.2 view
  bypassed it, render new errors through the same handler — no bespoke body shapes.

### 1.6 URLs
- New `apps/candidates/urls.py`: `path("profile/", ProfileView.as_view(), name="profile")`,
  `path("candidates/<uuid:pk>/", PublicCandidateView.as_view(), name="public-candidate")`.
- `config/urls.py`: `path("api/v1/", include("apps.candidates.urls"))` (alongside the
  accounts includes; final paths `/api/v1/profile/`, `/api/v1/candidates/{id}/`).

### 1.7 Tests — `apps/candidates/tests/` (new `conftest.py` + 6 files)

Conftest: `api` (DRF `APIClient`), `verified_user`, `unverified_user`, `inactive_user`,
`make_profile` helpers (accounts' conftest is not shared across apps).

| File | Proves |
|---|---|
| `test_profile_create.py` | 201 §19 shape; defaults REGISTERED/ANONYMOUS; duplicate POST → 409 `profile_exists`; unverified/inactive/anonymous → 403/403/401; D1: `current_status=INTERVIEWED` → 201 + status INTERVIEWED; D1 rollback: `current_status=WAITING_FOR_JOINING_LETTER` → 400 on `current_status` **and profile absent**; `current_status=JOINED` → 400 (not an edge from REGISTERED); `batch="2027"` → 400 `batch_not_offered` |
| `test_profile_read_update.py` | GET exact §19 keys; PATCH region/center ok; PATCH bad batch → 400; PATCH `current_status` legal edge → 200 + persisted; illegal edge → 400 machine code **and the same PATCH's other fields not saved** (atomicity); same-status PATCH no-op; `id`/`user` immutable via PATCH; reserved `display_name` PATCH → 400 `reserved_display_name` |
| `test_profile_delete.py` | DELETE → 405 envelope pointing at `/api/v1/account/`; account + profile still intact after |
| `test_public_candidate.py` | 200 with **exactly** the §23 keys; ANONYMOUS mode → "Anonymous Candidate"; blank name + DISPLAY_NAME → anonymous fallback; response contains no email/phone/interview/timestamp fields; missing UUID → 404; unauthenticated request succeeds (AllowAny) |
| `test_serializers_redaction.py` | T3.6/T3.8 core: over a maximally-populated profile, both public serializers omit the full zero-exposure set (email, phone, FCM token, password, notes, moderation state); `AuthorPublicSerializer` on profile-less user → display "Anonymous Candidate", batch/hiring/region None (no crash); on tombstoned user (2.2 anonymize shape) → anonymous, email absent; resolved name matches `get_public_display_name` in all 5 resolver cases |
| `test_impersonation.py` | every reserved token rejected case-insensitively ("tcs", "Official"); lookalike substrings rejected ("TCSOfficial", "hr_team", "Administrator"); innocent names pass ("Sai", "Ravi Kumar"); D3 tradeoff pinned: incidental substrings ("Sahir") are rejected too — documented behavior; ANONYMOUS mode does not bypass validation; `override_settings` list extension applies without code change |
| `test_permissions.py` | `IsProfileOwner`: owner True, other user False, anonymous False; view gating: unverified user PATCH/POST → 403, verified → allowed |

### 1.8 Execution order (Stage 1)
1. 1.1 settings token list → 1.2 serializers (+ validator) → 1.3 services → 1.4 permissions
2. 1.5 views → 1.6 URLs
3. 1.7 tests → `docker compose run --rm web python -m pytest` (install `requirements-dev.txt`
   in the ephemeral container first — known flow from 3.1)
4. **Gate:** pytest green · `ruff check apps config` · `ruff format --check apps config` ·
   `makemigrations --check --dry-run` (must report "No changes detected" — no models touched)

## Stage 2 — Live verification round

- [x] Stack restart (`docker compose restart web celery_worker celery_beat`); `/health/` and
  `/health/ready/` still 200; no new migrations applied (none expected)
- [x] curl drill through nginx: register+verify (worker-log token, 2.2 flow) →
  `POST /api/v1/profile/` 201 §19 shape → GET shape → `PATCH current_status=INTERVIEWED` 200 →
  `PATCH current_status=JOINED` 400 machine code with region-edit in the same PATCH left
  unsaved → duplicate `POST` → **409** → `DELETE /api/v1/profile/` → **405 envelope naming
  `/account/`** → `GET /api/v1/candidates/{id}/` unauthenticated 200 with exactly the §23 keys
  → grep the body for the owner's email (absent)
  *(executed 2026-09-21: all green — register 201 → verify 200 → login → create 201 exact
  §19 shape → PATCH INTERVIEWED 200 → PATCH JOINED 400 `status_invalid_transition` with region
  left untouched → 409 `profile_exists` → 405 envelope → public GET 200 six-key body, owner
  email grep count 0 → 404 envelope on missing UUID)*
- [x] Impersonation live: `PATCH display_name="TCSOfficial"` → 400 `reserved_display_name`
- [x] Full pytest re-run green; ruff clean; `makemigrations --check` clean
  *(116 passed in apps/candidates; 208 total across the suite)*
- [x] Prod compose still validates (`docker compose --env-file .env.prod ... config -q`);
  docs updated: `.planning/STATE.md`, `REQUIREMENTS.md` (PROF-04 → Complete; sub-phase
  table 3.2 note), ROADMAP (03-02 checked, Phase 3 → 2/2 Complete + summary row), PLAN gate checkboxes

## Out of scope (Phase 4.1+)

- Atomic timeline-event sync around `transition_status` (4.1, TIME-02 — the service stays
  the single mutation point; views call it via `update_profile` only)
- Community feed usage of `AuthorPublicSerializer`/`CandidatePublicSerializer` (5.x — they
  import from `apps.candidates.serializers`)
- Deterministic pseudonym avatar hash (06 §5.1.2 — ships with Phase 5/9 rendering)
- Display-name impersonation *reports* / admin triage (Phase 8); profile admin remains 3.1-minimal
- Composite indexes (Phase 7 analytics patterns)
