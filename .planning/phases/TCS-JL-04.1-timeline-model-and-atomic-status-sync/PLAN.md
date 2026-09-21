# PLAN 04-01 — Timeline Model & Atomic Status Sync

**Phase:** 4.1 · **Roadmap:** TIME-01, TIME-02 · **Status:** ✅ Executed (2026-09-21) · **Written:** 2026-09-21
**Inputs:** `CONTEXT.md` in this directory (decisions D1–D2 + invariants); 03 §7 (TimelineEvent), §17 (indexes), §27 (timeline validation); 04 §24–27 (shapes — consumed in 4.2), §85 (transaction sequence); 06 §4.2 (deletion flow step 4), §6 permission matrix; 10_MVP T4.1–T4.3 (+ T4.9 sync portions)
**Scope discipline:** Model + service layer only. **No API endpoints, serializers, URLs, or permissions** (all 4.2 / plan 04-02). No dashboard, no date-sanitization (T4.5), no analytics. New `apps/timeline` app ⇒ **one new migration expected**; drift check runs *after* generation.
**Pre-condition:** 3.2 executed & pushed (`0987a56`); stack healthy; 208-test suite green (92 accounts + 116 candidates).

## Goal (roadmap "done when")

> Recording a milestone updates profile status in the same database transaction.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | **Walk-the-chain status sync** — event types map to statuses; sync advances along legal `ALLOWED_TRANSITIONS` edges, multi-hop for backfills; at/past = idempotent no-op; blocked chains raise and roll back the event insert | Interleaved/out-of-order milestones just work (03 §27); genuinely impossible walks (terminal, OTHER-as-current) 400 in 4.2 with nothing persisted |
| D2 | **Forward-only** — edit/delete never regresses status; `event_type` edits re-run D1 sync toward the new mapped target; date/description edits and deletes leave status untouched | Status is append-only history; fixing a wrong status = PATCH through legal edges (3.2 `update_profile`) |

**Planner resolutions (CONTEXT open items 1–4):**

- **R1 — `auto_update_status=True` default** (T4.3's signature wording); callers may opt out per call; sync still composes `transition_status` — the single mutation point.
- **R2 — Deterministic chain-order walk, not BFS.** An explicit `CHAIN_ORDER` tuple (the 9 chain statuses in edge order) drives hop generation; every consecutive pair is asserted by test to be a legal edge (guards against 3.1 drift). OTHER-as-current is a special rule: reachable only to WAITING-or-later. No graph search, no cycle risk (WAITING⇄OTHER 2-cycle exists in the table).
- **R3 — Reuse `InvalidTransitionError`** with existing codes (`status_terminal` for terminal blocks, `status_invalid_transition` for unreachable targets). No new error class — same semantic, one vocabulary, 4.2 renders 400 identically.
- **R4 — Test matrix** below (30 tests; suite 208 → 238).

## Sync algorithm (pinned)

```python
EVENT_TYPE_TO_STATUS = {          # targets ⊆ CHAIN_ORDER; OTHER/WITHDRAWN unreachable by design
    INTERVIEW: INTERVIEWED, SELECTION: SELECTED, OFFER_LETTER: OFFER_RECEIVED,
    READINESS_SURVEY: READINESS_SURVEY, JOINING_LETTER: JOINING_LETTER_RECEIVED,
    JOINING_DATE: JOINING_DATE_RECEIVED, JOINED: JOINED,
}

def _walk_status(profile, target):            # inside caller's transaction
    current = profile.current_status
    if current == target: return              # idempotent (incl. terminal same-status)
    if current in TERMINAL_STATUSES:          # JOINED/WITHDRAWN + different target (D1: blocked)
        raise InvalidTransitionError("status_terminal", ...)
    if current == OTHER:                      # only OTHER→WAITING re-enters the chain
        if CHAIN_ORDER.index(target) < CHAIN_ORDER.index(WAITING_FOR_JOINING_LETTER):
            raise InvalidTransitionError("status_invalid_transition", ...)
        path = [WAITING, *chain-after-WAITING-up-to-target]
    else:
        ci, ti = CHAIN_ORDER.index(current), CHAIN_ORDER.index(target)
        if ci > ti: return                    # at/past → backfilled milestone, no-op
        path = list(CHAIN_ORDER[ci+1 : ti+1]) # each consecutive pair = legal edge
    for step in path:
        transition_status(profile, step)      # re-validates every hop; raise ⇒ caller rolls back
```

Pinned consequences (tested, documented): `JOINED` + any non-JOINED event → `status_terminal` (D1's own example); `WITHDRAWN` + any event → `status_terminal`; `OTHER` + pre-WAITING target → `status_invalid_transition`.

## Stage 1 — Build & automated gate

**Gate:** full pytest green (208 pre-existing untouched) + `ruff check`/`format` clean + `makemigrations --check` clean *after* generating the new migration. No live drill until this passes.

### 1.1 App registration
- New `apps/timeline/` (`apps.py`, `models.py`, `services.py`, `migrations/`, `tests/`); add `"apps.timeline"` to `INSTALLED_APPS` in `config/settings/base.py` (3.1 pattern). No other settings changes.

### 1.2 `apps/timeline/models.py` — `TimelineEvent` (T4.1, 03 §7)
- `id` UUIDv4 PK (`default=uuid.uuid4, editable=False`).
- `candidate` FK → `candidates.CandidateProfile`, `on_delete=CASCADE` (06 §4.2 deletion step 4), `related_name="timeline_events"`.
- `event_type` CharField(20), `EventType` TextChoices — exactly: INTERVIEW, SELECTION, OFFER_LETTER, READINESS_SURVEY, JOINING_LETTER, JOINING_DATE, JOINED, OTHER (T4.1 set).
- `event_date` DateField(); `description` TextField(blank=True, default=""); `is_verified` BooleanField(default=False); `created_at`/`updated_at` auto.
- Meta: `ordering = ["-event_date", "-created_at"]`; indexes per T4.2: `(candidate, -event_date)` name `idx_event_candidate_date`, `(event_type, event_date)` name `idx_event_type_date` (descending `-` prefix supported on Django 5.x — verified in the generated migration).
- `__str__` = `"{candidate} · {event_type} @ {event_date}"`.

### 1.3 `apps/timeline/services.py`
- `EVENT_TYPE_TO_STATUS`, `CHAIN_ORDER` (9 statuses; module constant), `_walk_status` (algorithm above).
- `record_timeline_event(candidate, *, event_type, event_date, description="", is_verified=False, auto_update_status=True) -> TimelineEvent` (T4.3): `with transaction.atomic():` create row, then `_walk_status` if mapped & opted in. Any raise ⇒ row + hops roll back (04 §85).
- `update_timeline_event(event, data) -> TimelineEvent` (D2): atomic — setattr/save provided fields (`event_type`, `event_date`, `description`, `is_verified` all editable); if `event_type` **changed** and new type is mapped → `_walk_status(candidate, mapped)` (no-op if at/past; raise ⇒ whole update rolls back). Type change to OTHER or date/description-only edits never sync.
- `delete_timeline_event(event)` (D2): plain delete; status untouched. Single deletion path for 4.2.
- Import direction: `timeline → candidates.services` (matches 03 §2 ownership flow). **No direct `current_status` writes anywhere in the app** — only via `transition_status`.

### 1.4 Migration
- `0001_initial` with both compound indexes (candidate FK column + descending event_date; event_type + event_date). Names/cols confirmed in the file; DB-level verified in Stage 2.

### 1.5 Tests — `apps/timeline/tests/` (new `conftest.py` + 4 files)

Conftest: local `make_user` / `make_profile` helpers (apps' conftests are not shared — 3.2 precedent).

| File | Proves |
|---|---|
| `test_timeline_model.py` (8) | UUIDv4 auto-assigned; exact 8 event_type choices; defaults (is_verified False, description ""); CASCADE — deleting profile deletes its events; `related_name`; Meta ordering; both indexes on Meta + present in `0001_initial` (names, columns, descending event_date) |
| `test_record_sync.py` (10) | D1 matrix: each of the 7 mapped types advances correctly (incl. SELECTION & JOINED from REGISTERED = multi-hop); no-op at target; no-op past target (SELECTION while OFFER_RECEIVED — backfill); `JOINED` + INTERVIEW → `status_terminal` **and event row absent** (rollback proof); `WITHDRAWN` + JOINED event → `status_terminal`; OTHER + INTERVIEW → `status_invalid_transition`; OTHER + JOINING_LETTER → walks to JOINING_LETTER_RECEIVED; OTHER event type → status untouched, row saved; `auto_update_status=False` → no sync; success asserts event + status in one go (04 §85) |
| `test_update_delete_sync.py` (7) | D2 matrix: JOINING_LETTER→JOINED edit walks status forward; OTHER→INTERVIEW edit (unmapped→mapped) syncs from REGISTERED; edit to OTHER type → no sync, type persisted; description/date-only edit → status untouched; backwards type edit → no-op (forward-only), type persisted; INTERVIEW edit while OTHER-as-current → raise **and type change rolled back**; delete → row gone, status untouched |
| `test_walk_invariants.py` (5) | Guards: every consecutive CHAIN_ORDER pair ∈ ALLOWED_TRANSITIONS; chain = 9 statuses REGISTERED→JOINED; every EVENT_TYPE_TO_STATUS target ∈ CHAIN_ORDER; OTHER/WITHDRAWN absent from mapping targets; mapped types are real choices, OTHER deliberately unmapped |

### 1.6 Execution order (Stage 1)
1. 1.1 app scaffold + INSTALLED_APPS → 1.2 model → `makemigrations timeline` → 1.4 verify migration
2. 1.3 services
3. 1.5 tests → `docker compose run --rm web python -m pytest` (dev requirements in ephemeral container — known flow from 3.1)
4. **Gate:** pytest green · `ruff check apps config` · `ruff format --check apps config` · `makemigrations --check --dry-run`

## Stage 2 — Live verification round

- [x] Stack restart (`docker compose restart web celery_worker celery_beat`); `/health/` and
  `/health/ready/` 200 after boot; `manage.py migrate timeline` applied `timeline.0001_initial`
  cleanly (verified via `showmigrations`; table + both compound indexes confirmed with `\d
  timeline_timelineevent` — `idx_event_candidate_date (candidate_id, event_date DESC)`,
  `idx_event_type_date (event_type, event_date)`)
- [x] ORM drill (`manage.py shell`): fresh profile → INTERVIEW → status INTERVIEWED (single
  hop); JOINED event → multi-hop walk to JOINED; OFFER_LETTER while JOINED →
  `InvalidTransitionError(status_terminal)` raised **and** event count unchanged (04 §85 rollback);
  OTHER event → status still JOINED, row saved; delete_timeline_event → row gone, status untouched
  *(executed 2026-09-21: all 5 checks green)*
- [x] Full pytest re-run green; ruff clean; `makemigrations --check` clean
  *(238 passed in apps-wide run; 30 new in apps/timeline)*
- [x] Prod compose validates (`docker compose --env-file .env.prod ... config -q` — required
  env interpolated from shell, matching the deployment environment's injector; `.env.prod`
  intentionally holds no secrets); docs updated: `.planning/STATE.md`, `REQUIREMENTS.md`
  (TIME-01/02 → Complete; sub-phase table 4.1 note), ROADMAP (04-01 checked, Phase 4 row),
  PLAN gate checkboxes

## Out of scope (Phase 4.2+)

- `/api/v1/timeline/` CRUD, serializers (04 §24–27 shapes), pagination, date-sanitization (T4.5 "distant future"), `IsTimelineOwner` IDOR 404s (06 §4.3.3), `GET /api/v1/dashboard/` (T4.8) — plan 04-02
- Unread-notification count on dashboard (Phase 6); analytics reads of events (Phase 7); `is_verified` admin tooling (Phase 8); seed events (Phase 10)
- No frontend concerns (Phase 9)

## Security notes (ASVS L1)

- Services take explicit `candidate`/event objects — no ambient request state; the IDOR surface arrives with the 4.2 API and must scope every queryset to `request.user` (06 §6: timeline = private tier, own-only).
- Rollback semantics double as consistency protection: no partial event/status state can ever be observed.
