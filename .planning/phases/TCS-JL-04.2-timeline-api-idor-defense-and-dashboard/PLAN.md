# PLAN 04-02 — Timeline API, IDOR Defense & Dashboard

**Phase:** 4.2 · **Roadmap:** TIME-03, TIME-04 (API half), TIME-05 · **Status:** ✅ Executed (2026-09-22) · **Written:** 2026-09-22
**Inputs:** `CONTEXT.md` in this directory (decisions D1–D3 + invariants); 04 §9 (pagination), §24–§28 (shapes), §53 (privacy threshold), §65.20 + §88–§89 (authz/enumeration), §84 (app layout), §103 (required timeline tests), §121 (DoD); 06 §4.2 (IDOR pipeline: 404 not 403), §4.3.3 (`IsTimelineOwner`), §6 (timeline = private tier); 10_MVP T4.4–T4.9
**Scope discipline:** API layer only on top of 4.1. **No model changes, no migrations expected** (`makemigrations --check` must stay clean). No timeline-service changes. No community/notification/analytics app work — Phase 6/7 dependencies are stubbed exactly as D1 pins. No frontend (TIME-04's UI is Phase 9.3).
**Pre-condition:** 4.1 executed & committed (`38e1a07`); stack healthy; 238-test suite green (92 accounts + 116 candidates + 30 timeline).

## Goal (roadmap "done when")

> Unauthorized timeline access returns 404; dashboard aggregates community benchmarks.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | Dashboard ships **complete-shaped** now: community block computed for real from `CandidateProfile`; `unread_notifications` = explicit `0` placeholder (Phase 6 fills it) | 04 §28 keys stable from day one; Phase 9.3 UI never churns when Phases 6/7 land |
| D2 | Benchmark = **waiting total + status distribution**, each threshold-suppressed (04 §53) and labeled `COMMUNITY_REPORTED` | "Benchmarks" plural satisfied without micro-cohort leakage; raw small counts are never exposed |
| D3 | `event_date` bound: **today + 24 months for all types** (settings-driven), plus **JOINING_LETTER present-or-past only**; `JOINING_DATE` legitimately future | Garbage dates blocked; real-world future milestones still recordable |

**Planner resolutions (CONTEXT open items 1–5):**

- **R1 — `completion_percentage` is a 7-item equal-weight checklist** in `candidates.services` (profile field knowledge stays with the profile model). Identity fields are **excluded by design**: `display_name`/`public_identity_mode` are a privacy choice (3.1 D1), so an ANONYMOUS candidate who never shares a name must still be able to reach 100%. Detailed below. 04 §28's "90" is illustrative only — our reachable values are integer multiples of ~14 (0/14/29/43/57/71/86/100); recorded as a documented deviation, not a bug.
- **R2 — Dashboard lives in `apps/timeline/`**, route `/api/v1/dashboard/`, registered from `apps/timeline/urls.py`. Two reasons: 04 §84's app layout lists exactly four domain apps (`accounts`, `candidates`, `timeline`, `community`/`notifications`) and **no `dashboard` app** — the dashboard is a route, not a domain; and 4.1 pinned the import direction `timeline → candidates`, so hosting it in `candidates` would invert that arrow for no gain. Phases 6/7 extend the payload in place.
- **R3 — Suppression threshold `ANALYTICS_MIN_COHORT_SIZE = 5`** (04 §53's recommended initial value) in `config/settings/base.py`, read at call time. When the global profile count is below it, the analytics block renders `{data_source, suppressed: true, message}` and **omits** `community_waiting_count` + `status_distribution` entirely — omitted keys beat misleading zeros.
- **R4 — The API hardcodes `auto_update_status=True`.** No client parameter on POST, none on PATCH. A client-controllable switch would let a caller record a JOINING_LETTER while leaving `current_status` stale, making 04 §121's "timeline/status consistency is implemented" client-defeatable. 4.1's service parameter stays for service-layer callers (seed data Phase 10, moderation Phase 8).
- **R5 — Test matrix** below (62 tests; suite 238 → 300).

## Pinned design

### Endpoint / error contract

| Route | Views | Notes |
|---|---|---|
| `GET /api/v1/timeline/` | `TimelineEventListCreateView` | Paginated, owner-scoped, `-event_date, -created_at` order |
| `POST /api/v1/timeline/` | same | 201, 04 §25 shape; syncs status (R4) |
| `PATCH /api/v1/timeline/{event_id}/` | `TimelineEventDetailView` | 200; re-sync on mapped `event_type` change (4.1 D2) |
| `DELETE /api/v1/timeline/{event_id}/` | same | 204; status untouched |
| `GET /api/v1/timeline/{event_id}/` | — | **405** — 04 §24 specifies no detail read (spec-exact; test pins it) |
| `GET /api/v1/dashboard/` | `DashboardView` | 200, 04 §28 shape (D1/D2) |

Error codes pinned (2.2 project envelope via the accounts handler; DRF field-validation failures keep DRF's field-error shape untouched, per 3.2):

```text
400  event_date_out_of_range   POST/PATCH date beyond horizon or before EARLIEST_EVENT_DATE
400  event_date_future         JOINING_LETTER dated in the future (D3 carve-out)
400  invalid_event_type        unknown event_type, or unknown ?event_type= filter value
400  <transition code>         status_sync blocked chain — 4.1's codes pass through verbatim
401  authentication_required   anonymous
403  verification_required     unverified / inactive (IsActive + IsVerified)
404  profile_not_found         verified user without a CandidateProfile (3.2 precedent)
404  timeline_event_not_found  foreign OR nonexistent UUID — identical body, enumeration-proof
405  method_not_allowed        GET on detail
```

### Pagination (04 §9)

Global `PageNumberPagination` + `PAGE_SIZE = 20` is already configured and `page_size_query_param` is **not** set, so client-supplied `?page_size=100000` is ignored — 04 §9's "controlled maximum" is satisfied with **no config change** (a test pins the ignore). No `?ordering=` parameter: `Meta.ordering` governs (spec §24.1 shows newest-first only).

### Date bounds (D3)

```python
# apps/timeline/validators.py
EARLIEST_EVENT_DATE = date(2000, 1, 1)                    # absurd-past floor
horizon = date.today() + timedelta(days=settings.TIMELINE_FUTURE_HORIZON_DAYS)   # default 730
```
`settings.TIMELINE_FUTURE_HORIZON_DAYS = 730` (ops-tunable per D3 "settings-driven"), read at call time so `override_settings` applies. The horizon check runs in `validate_event_date` (field validator → applied on POST **and** PATCH); the JOINING_LETTER carve-out needs both fields, so it runs in `TimelineEventWriteSerializer.validate()`, resolving the *effective* type/date from `attrs` falling back to `self.instance` (so a PATCH of only `event_date` on an existing JOINING_LETTER is still caught).

### Sync through the API

POST/PATCH/DELETE call 4.1's `record_timeline_event` / `update_timeline_event` / `delete_timeline_event` — **no service edits**. `InvalidTransitionError` renders through 3.2's `_TransitionRejected` pattern (400 + machine code). The views never write `current_status` directly. `auto_update_status=True` hardcoded (R4).

### `completion_percentage` (R1)

```python
# apps/candidates/services.py
PROFILE_COMPLETION_FIELDS = ("interview_center", "interview_date", "offer_letter_date",
                             "joining_location", "expected_joining_date")

def compute_profile_completion(profile, *, has_events: bool = False) -> int:
    """7 equal-weight items: 5 enrichment fields + 'status past REGISTERED' + 'has ≥1 event'.
    Identity fields excluded — anonymity must never look like incompleteness."""
```
`has_events` is a **parameter, not an import**, because `candidates → timeline` would cycle against 4.1's pinned `timeline → candidates` direction; `build_dashboard_payload` supplies it. Item 6 = `current_status != REGISTERED`. Result `round(100 * filled / 7)`.

### Dashboard payload (D1/D2, 04 §28)

```json
{
  "profile":   {"completion_percentage": 71, "current_status": "WAITING_FOR_JOINING_LETTER"},
  "timeline":  {"latest_event": {"event_type": "READINESS_SURVEY", "event_date": "2026-05-15"}},
  "community": {"unread_notifications": 0},
  "analytics": {
    "data_source": "COMMUNITY_REPORTED", "suppressed": false,
    "community_waiting_count": 412,
    "status_distribution": {"REGISTERED": 3, "…": 0}
  }
}
```

- `latest_event` = first of `.order_by("-event_date", "-created_at")`, **`null` when the candidate has no events**; exactly the two spec keys (no `description` — §28 shows two, and 04 §744's rule on confidential timeline notes argues for minimum surface).
- `latest_event` and the whole payload are built by `services.build_dashboard_payload(profile) -> dict` — one place owns the shape; the view is a thin `Response(...)`.
- `WAITING_STATUSES = {WAITING_FOR_JOINING_LETTER, JOINING_LETTER_RECEIVED, JOINING_DATE_RECEIVED}` — the pre-joining pipeline tail; `JOINED` and `WITHDRAWN` excluded (they aren't waiting).
- `status_distribution` carries **all 11 status keys** with integer counts (stable frontend keys, zeros reveal nothing).
- `unread_notifications: 0` with a code comment + docstring naming **Phase 6** as the wiring point (T4.8's notifications field).
- Suppression per R3; `data_source: "COMMUNITY_REPORTED"` always present (04 §65.20, 01 §1007 — never presented as official TCS information).
- Cost: one `values("current_status").annotate(Count)` + one `COUNT(*)` for the threshold + one latest-event query. No per-candidate data in the payload.

## Stage 1 — Build & automated gate

**Gate:** full pytest green (238 pre-existing untouched) + `ruff check`/`format` clean + `makemigrations --check` clean. No live drill until this passes.

### 1.1 Settings (`config/settings/base.py`) — two additions only
`ANALYTICS_MIN_COHORT_SIZE = 5` (04 §53, R3) and `TIMELINE_FUTURE_HORIZON_DAYS = 730` (D3). Both read at call time.

### 1.2 `apps/timeline/validators.py`
`EARLIEST_EVENT_DATE`; `validate_event_date(value)` (range check, codes `event_date_out_of_range`); `validate_event_type(value)` (choices check, code `invalid_event_type`, shared with the list-filter path).

### 1.3 `apps/timeline/serializers.py`
- `TimelineEventSerializer` — **output** (owner read + POST response): `id, event_type, event_date, description, is_verified, created_at`. A documented superset of 04 §24.1 and §25 (each is a subset of these six); `id`, `created_at`, `is_verified` read-only.
- `TimelineEventWriteSerializer` — POST/PATCH input: `event_type`, `event_date`, `description`. `event_type` required + validated (T4.5's `invalid_event_type` test); `description` optional (≤ 04 §25's free text). `validate()` applies `validate_event_date` per-field and the D3 JOINING_LETTER carve-out against effective values. **`is_verified` is never accepted** (06 §4.4 vertical-escalation defense — it's a Phase 8 moderation flag); `candidate` comes from `request.user`, never the body (06 §4.5).

### 1.4 `apps/timeline/permissions.py`
`IsTimelineOwner(BasePermission)` — `has_object_permission` returns `obj.candidate.user_id == request.user.id` (06 §4.3.3). Declared on the detail view **in addition to** query scoping (defense in depth: a permission-wiring mistake still cannot leak, because `get_queryset()` never returns a foreign row).

### 1.5 `apps/timeline/services.py` — dashboard addition only
Add `build_dashboard_payload(profile) -> dict` + `WAITING_STATUSES`. **4.1's three service functions and `_walk_status` stay untouched.**

### 1.6 `apps/timeline/views.py`
- `TimelineEventListCreateView(SpecErrorMixin, ListCreateAPIView)`.
  - `permission_classes = [IsAuthenticated, IsActive, IsVerified]`.
  - `get_queryset()` → `TimelineEvent.objects.filter(candidate__user=request.user)`; `?event_type=` validated against choices (unknown ⇒ 400 `invalid_event_type`).
  - `_get_profile()` → 404 `profile_not_found` when absent (3.2 `ProfileView._get_profile` shape).
  - POST → write serializer → `record_timeline_event(profile, event_type=…, event_date=…, description=…, auto_update_status=True)` → 201 output serializer.
- `TimelineEventDetailView(SpecErrorMixin, UpdateDestroyAPIView)` — **no `GET`** (405 per §24); `permission_classes` as above + `IsTimelineOwner`; `get_queryset()` scoped to `request.user` (foreign/nonexistent ⇒ 404 `timeline_event_not_found`, identical body); PATCH → `update_timeline_event`; DELETE → `delete_timeline_event` → 204.
- `DashboardView(SpecErrorMixin, APIView)` — `GET` only; `_get_profile()` 404; `Response(build_dashboard_payload(profile))`.
- All three route `InvalidTransitionError` → 400 through the 3.2 `_TransitionRejected` pattern; missing-profile and missing-event 404s use project envelopes (no third body style).

### 1.7 `apps/candidates/services.py` — `compute_profile_completion` (R1)
Pure function + `PROFILE_COMPLETION_FIELDS` constant; no model/migration change, no other function touched.

### 1.8 URLs
- New `apps/timeline/urls.py`: `timeline/` → list-create, `timeline/<uuid:pk>/` → detail, `dashboard/` → DashboardView.
- `config/urls.py`: add `path("api/v1/", include("apps.timeline.urls"))` alongside the accounts/candidates includes.

### 1.9 Tests — `apps/timeline/tests/` (extend `conftest.py` + 5 files) and `apps/candidates/tests/` (1 file)

`conftest.py` additions: `api` (DRF `APIClient`), `auth_api(user)` factory returning a client `force_authenticate`d as that user, `make_event` helper, plus unverified/inactive user fixtures (3.2 precedent — apps' conftests are not shared).

| File | Proves |
|---|---|
| `test_timeline_list.py` (11) | 04 §24.1 `count/next/previous/results` shape; exact six result keys; newest-first + `created_at` tiebreak; **owner scoping** (other candidate's events absent even with 200 of them); empty list; `?event_type=JOINING_LETTER` filters; unknown `?event_type=BOGUS` → 400 `invalid_event_type`; `?page_size=999` ignored (04 §9); anonymous → 401; unverified/inactive → 403; no profile → 404 `profile_not_found` |
| `test_timeline_create.py` (13) | 201 + 04 §25 keys; JOINING_LETTER → status JOINING_LETTER_RECEIVED; SELECTION from REGISTERED → multi-hop SELECTED; blocked chain (JOINED then INTERVIEW) → 400 `status_terminal` **and event row absent** (04 §85 atomicity through the API); OTHER event → 201 + status untouched; unknown `event_type` → 400 `invalid_event_type`; `is_verified: true` in body → **ignored, stays false**; `description` omitted → `""`; D3: today+730 → 201, today+731 → 400 `event_date_out_of_range`, `1999-12-31` → 400, JOINING_LETTER tomorrow → 400 `event_date_future`, JOINING_DATE +6 months → 201; `candidate`/`user` in body cannot retarget the owner (06 §4.5) |
| `test_timeline_detail.py` (14) | GET detail → 405 `method_not_allowed`; PATCH date+description → 200, status untouched; PATCH `event_type` → mapped target re-syncs forward (4.1 D2); PATCH to a blocked type → 400 **and type change rolled back**; PATCH `event_date` outside horizon → 400; PATCH JOINING_LETTER to future date → 400; DELETE own → 204, row gone, status untouched; **IDOR:** PATCH foreign UUID → 404 + foreign row **and** foreign user's status unchanged; DELETE foreign UUID → 404 + row intact; nonexistent UUID → 404 with a body **byte-identical** to the foreign case (enumeration-proof, 04 §89); anonymous → 401; unverified → 403 |
| `test_idor_permissions.py` (7) | `IsTimelineOwner` unit: owner True, other user False, anonymous False, profile-less user False; **query-scoping invariant**: user A's list/detail queries can never resolve user B's event even when A supplies B's real UUID; cross-user write attempts leave B's event count and status untouched; the 404 for foreign vs nonexistent is indistinguishable in status, code, and message (the T4.7/06 §4.2.2 core) |
| `test_dashboard.py` (11) | exact 04 §28 top-level keys (`profile/timeline/community/analytics`); `timeline.latest_event` null with zero events, else newest by date (not by creation order) with **exactly** `event_type`+`event_date`; `community.unread_notifications == 0` (D1 placeholder); `data_source == "COMMUNITY_REPORTED"` (04 §65.20); `community_waiting_count` counts only `WAITING_STATUSES` — `JOINED`/`WITHDRAWN`/`REGISTERED` excluded; `status_distribution` has all 11 keys; **suppression:** <5 profiles → `suppressed: true` + message and `community_waiting_count`/`status_distribution` **absent**; ≥5 → full block (via `override_settings` boundary at exactly the threshold and threshold−1); anonymous → 401; no profile → 404; profile block mirrors `current_status` |
| `apps/candidates/tests/test_profile_completion.py` (6) | 0% sparse; each of the 5 fields + `has_events` + status-past-REGISTERED independently moves the needle; 100% fully-satisfied; **privacy pin:** ANONYMOUS mode with empty `display_name` still reaches 100 (R1 — anonymity ≠ incompleteness); WITHDRAWN counts as "past REGISTERED"; rounding is integer and monotonic |

### 1.10 Execution order (Stage 1)
1. 1.1 settings → 1.2 validators → 1.3 serializers → 1.9 `conftest` additions
2. 1.4 permissions → 1.5 dashboard service → 1.6 views → 1.8 URLs → 1.7 candidates helper
3. 1.9 tests → `docker compose run --rm web sh -c "pip install -q -r requirements/dev.txt && python -m pytest"` (ephemeral container needs dev deps in the same run — known 4.1 flow)
4. **Gate:** pytest green · `ruff check apps config` · `ruff format --check apps config` · `makemigrations --check --dry-run`

## Stage 2 — Live verification round *(executed 2026-09-22: 31/31 checks green)*

- [x] Stack restart (`docker compose restart web`); `/health/` + `/health/ready/` 200 after boot,
  and anonymous `GET /api/v1/timeline/` + `/api/v1/dashboard/` both 401 (routes live, gate on)
- [x] **Real HTTP drill** (not ORM-only, unlike 4.1 — this phase *is* the API): two throwaway
  verified candidates + real JWTs from `POST /api/v1/auth/login/`, against the running stack's
  `/api/v1/` endpoints. All 31 checks passed:
      empty list shape · `POST SELECTION` → 201 + multi-hop status `SELECTED` (read back via
      `GET /profile/`) · spec keys on the create response · `PATCH` own description → 200 ·
      `GET /timeline/{id}/` → 405 `method_not_allowed` · `PUT` → 405 · `POST JOINED` then late
      `POST INTERVIEW` → 400 `status_terminal` **with the event count unchanged** (04 §85
      atomicity over the wire) · future `JOINING_LETTER` → 400 `event_date_future` · +731 days →
      400 · **IDOR**: A `PATCH`/`DELETE` B's real UUID → 404 with B's row untouched and the
      response bytes *identical* to a nonexistent UUID · owner DELETE → 204 · `GET /dashboard/`
      → exact 04 §28 keys, `COMMUNITY_REPORTED` label, `unread_notifications: 0`, latest event,
      and suppression flipping from `true` (4 profiles) to a full block at ≥5 · deletion leaves
      `current_status` at JOINED (D2 forward-only)
- [x] Full pytest re-run green (**319 passed**, was 238); ruff check + format clean;
  `makemigrations --check` clean — **no new migration**, as planned
- [x] `EXPLAIN` the list query in psql: `Bitmap Index Scan on idx_event_candidate_date` — 4.1's
  compound index is the one the API's owner-scoped, date-ordered query actually plans onto
- [x] Prod compose validates (`docker compose --env-file .env.prod -f docker-compose.prod.yml
  config -q`, deploy-injected env interpolated from the shell — 4.1 flow); docs updated:
  `.planning/STATE.md`, `REQUIREMENTS.md` (TIME-03 + TIME-05 Complete; **TIME-04 marked
  partial** — API half done, UI is Phase 9.3), `ROADMAP.md` (04-02 checked, Phase 4 → 2/2
  Complete), PLAN gate checkboxes

## Out of scope (later phases)

- The interactive chronological roadmap UI with edit/delete controls — TIME-04's remaining half, Phase 9.3 (UI-03)
- Real `unread_notifications` (Phase 6), the full `/api/v1/analytics/*` surface with its richer filters (Phase 7), `is_verified` moderation tooling (Phase 8), seed timelines (Phase 10)
- Community posts/comments/votes (Phase 5); no rate-limit scopes added for timeline writes (04 §90 lists timeline under none of the throttled categories — revisit only if abuse appears)

## Security notes (ASVS L1)

- **Two independent IDOR layers.** Every queryset is scoped to `request.user` *and* `IsTimelineOwner` guards the object — either alone would be sufficient, so a mistake in one is not a breach. Foreign and nonexistent UUIDs are indistinguishable (status, code, message), satisfying 04 §89's enumeration rule.
- **Identity never comes from the body** (06 §4.5): `candidate` is derived from `request.user`; `user`/`candidate` keys in a payload cannot retarget ownership (tested).
- **Vertical escalation closed** (06 §4.4): `is_verified` is read-only in every serializer; a client cannot self-verify a milestone.
- **Aggregate-only community data.** The dashboard exposes no per-candidate rows, no identifiers, and no notes — only counts, threshold-suppressed and community-labeled (04 §53, §65.20; 06 §6 timeline = private tier).
- **Timeline notes stay private:** `description` is never surfaced outside the owner's own timeline responses (04 §744's spirit) and never enters the dashboard payload.
