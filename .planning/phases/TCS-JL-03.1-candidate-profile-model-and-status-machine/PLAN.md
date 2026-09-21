# PLAN 03-01 — CandidateProfile Model & Status State Machine

**Phase:** 3.1 · **Roadmap:** PROF-01..PROF-03 · **Status:** ✅ Executed (2026-09-21) · **Written:** 2026-09-21
**Inputs:** `CONTEXT.md` in this directory (decisions D1–D4 + invariants); 03 §5–§6/§17; 10_MVP T3.1–T3.3; 02 §11–12
**Scope discipline:** model layer only. Serializers, `/api/v1/profile/` CRUD, PROF-04 redaction and
impersonation blocking are Phase 3.2 (03-02). Timeline sync seam is noted, built in 4.1.
**Pre-condition:** 6-service stack healthy after Phase 2.2; 92-test suite green.

## Goal (roadmap "done when")

> Profile model and status state machine enforce valid transitions.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | 11 statuses; WITHDRAWN terminal, reachable from any status | Choice set incl. WITHDRAWN; terminal rule in validator |
| D2 | Enforce diagram edges exactly (+ D1 terminals); same-status no-ops allowed | Explicit `ALLOWED_TRANSITIONS` dict; violations raise at service layer |
| D3 | Batch validated against settings-driven `BATCH_YEARS`; region free text | Validator (not frozen model choices) so cohorts expand via settings |
| D4 | Nullable 1:1, no auto-create; display-name resolver safe for missing profiles | `OneToOneField(null=True, related_name="candidate_profile")` |

**Spec-derived, no decision:** hiring_type as model choices PRIME/DIGITAL/NINJA/OTHER (03 §5 and
T3.1 agree); `public_identity_mode` ANONYMOUS default; current_status default REGISTERED;
single-column indexes per 03 §17 (composites deferred to Phase 7).

## Stage 1 — Build & automated gate

**Gate:** full pytest green in-stack + ruff clean + `makemigrations --check` clean. No live drill until this passes.

### 1.1 App scaffold
- New `apps/candidates/` (`__init__.py`, `apps.py` with `name = "apps.candidates"`, `migrations/`),
  registered as `"apps.candidates.apps.CandidatesConfig"` in `INSTALLED_APPS` (after accounts).
- Executor hint: create `__init__.py` files **explicitly** — Phase 2.1 silently missed
  `accounts/__init__.py` and pytest double-collected until it was added.

### 1.2 `apps/candidates/models.py`
```python
class CandidateProfile(models.Model):
    class PublicIdentityMode(models.TextChoices):
        ANONYMOUS = "ANONYMOUS", "Anonymous"
        DISPLAY_NAME = "DISPLAY_NAME", "Display Name"

    class Status(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        INTERVIEWED = "INTERVIEWED", "Interviewed"
        SELECTED = "SELECTED", "Selected"
        OFFER_RECEIVED = "OFFER_RECEIVED", "Offer Received"
        READINESS_SURVEY = "READINESS_SURVEY", "Readiness Survey"
        WAITING_FOR_JOINING_LETTER = "WAITING_FOR_JOINING_LETTER", "Waiting for Joining Letter"
        JOINING_LETTER_RECEIVED = "JOINING_LETTER_RECEIVED", "Joining Letter Received"
        JOINING_DATE_RECEIVED = "JOINING_DATE_RECEIVED", "Joining Date Received"
        JOINED = "JOINED", "Joined"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"      # terminal (D1)
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="candidate_profile")  # D4
    display_name = models.CharField(max_length=50, blank=True, default="")
    public_identity_mode = models.CharField(max_length=12, choices=PublicIdentityMode.choices,
                                            default=PublicIdentityMode.ANONYMOUS)
    batch = models.CharField(max_length=10, validators=[validate_batch_year])
    hiring_type = models.CharField(max_length=10, choices=HiringType.choices)
    region = models.CharField(max_length=100)                       # free text (D3)
    interview_center = models.CharField(max_length=200, blank=True, default="")
    interview_date = models.DateField(null=True, blank=True)
    joining_location = models.CharField(max_length=200, blank=True, default="")
    current_status = models.CharField(max_length=32, choices=Status.choices,
                                      default=Status.REGISTERED)
    offer_letter_date = models.DateField(null=True, blank=True)
    expected_joining_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```
- `validate_batch_year` (`apps/candidates/validators.py`): value ∈ `settings.BATCH_YEARS`
  (string compare), else `ValidationError("batch_not_offered", …)`. Read `BATCH_YEARS`
  **inside** the validator so `override_settings` changes re-validate (D3; test proves it).
  `BATCH_YEARS = ["2024", "2025", "2026"]` added to `config/settings/base.py`.
- `get_public_display_name()` (T3.3): profile None / mode ANONYMOUS / blank display_name →
  `"Anonymous Candidate"`; DISPLAY_NAME → stripped display_name (falls back to anonymous
  label when blank). Module-level helper `resolve_public_display_name(user)` so callers
  without a profile never crash (D4).
- `user.on_delete=SET_NULL` is belt-and-braces: deletion service anonymizes rather than
  deletes User rows (2.2); SET_NULL merely guards future policy changes. Profiles for
  tombstoned users are never created (3.2 gates on active+verified — out of scope here).
- `Meta`: `db_table = "candidates_profile"`-default fine; `indexes` per 03 §17 —
  single-column Index on batch, hiring_type, region, current_status, joining_location,
  interview_date, offer_letter_date, expected_joining_date. Constraint: `CheckConstraint`
  DISPLAY_NAME ⇒ display_name non-blank is **rejected** (blank display_name legitimately
  falls back to anonymous label in the resolver; no DB constraint).

### 1.3 `apps/candidates/services.py` — status machine (D2)
```python
ALLOWED_TRANSITIONS = {
    REGISTERED: {INTERVIEWED},
    INTERVIEWED: {SELECTED},
    SELECTED: {OFFER_RECEIVED, OTHER},
    OFFER_RECEIVED: {READINESS_SURVEY, OTHER},
    READINESS_SURVEY: {WAITING_FOR_JOINING_LETTER, OTHER},
    WAITING_FOR_JOINING_LETTER: {JOINING_LETTER_RECEIVED, OTHER},
    JOINING_LETTER_RECEIVED: {JOINING_DATE_RECEIVED},
    JOINING_DATE_RECEIVED: {JOINED},
    OTHER: {WAITING_FOR_JOINING_LETTER},
    JOINED: set(),
    WITHDRAWN: set(),
}
TERMINAL_STATUSES = {JOINED, WITHDRAWN}
```
- `transition_status(profile, new_status) -> CandidateProfile`:
  same-status → no-op (idempotent, returns unchanged instance);
  `new_status == WITHDRAWN and current not in TERMINAL` → allowed (D1 terminal rule —
  single special case instead of 10 duplicate dict edges, noted in a comment);
  else must be in `ALLOWED_TRANSITIONS[current]`; violations raise
  `InvalidTransitionError(ValueError)` with codes `status_terminal`, `status_invalid_transition`.
  On success: `profile.current_status = new_status; profile.save(update_fields=[...])`.
- Seam note (comment only): 4.1 wraps status changes with timeline-event creation in one
  transaction (TIME-02). No timeline code here.

### 1.4 Migration `0001_initial`
- Generated (`makemigrations candidates`); verify it carries the 8 single-column indexes
  and OneToOne unique+nullable column. Applied on the live dev volume during Stage 2 boot.

### 1.5 `apps/candidates/admin.py` (minimal)
- `@admin.register(CandidateProfile)` with `list_display = ("user", "batch", "hiring_type",
  "current_status", "public_identity_mode")` + `current_status` in `list_filter`.
  Full triage tooling stays Phase 8 — this just keeps dev manageable.

### 1.6 Tests — extend the 92-test suite (all untouched stay green)

| File | Proves |
|---|---|
| `tests/test_status_machine.py` | accept matrix: every dict edge (forward chain, 3 escape edges incl. SELECTED→OTHER, OTHER→WAITING_FOR_JOINING_LETTER); WITHDRAWN reachable from **every** non-terminal status; rejected: any backward jump (e.g. SELECTED→INTERVIEWED), skip-ahead (REGISTERED→SELECTED), outgoing from JOINED and WITHDRAWN; same-status no-op doesn't bump `updated_at` and doesn't raise; error codes surfaced on the exception |
| `tests/test_profile_model.py` | creation defaults (REGISTERED, ANONYMOUS, blank display_name); nullable 1:1: user without profile has no `candidate_profile`, a second profile for the same user is impossible (OneToOne uniqueness); tombstoned user (2.2 anonymize service) simply has no profile; `get_public_display_name`/`resolve_public_display_name` 5 cases (missing profile, ANONYMOUS, DISPLAY_NAME, blank display_name, whitespace-only) with no email ever in output; batch validator: accepts "2025", rejects "2027" with `batch_not_offered`, **accepts after `override_settings(BATCH_YEARS=…+"2027")`** (D3 settings-driven proof); hiring_type choices enforce {PRIME, DIGITAL, NINJA, OTHER}; Meta indexes present (inspect `CandidateProfile._meta.indexes` names/columns) |

Celery/eager fixtures not needed this phase (no email); conftest `api` fixture unused until 3.2.

### 1.7 Execution order (Stage 1)
1. 1.1 scaffold + settings `BATCH_YEARS` + `INSTALLED_APPS`
2. 1.2 models/validators → 1.3 services
3. 1.4 `makemigrations candidates` → review generated SQL/index list
4. 1.5 admin (one registration)
5. 1.6 tests → `docker compose run --rm web python -m pytest`
6. **Gate:** pytest green · `ruff check .` · `ruff format --check .` · `makemigrations --check`

## Stage 2 — Live verification (model phase; lightweight)

- [x] Stack restart applies 0001 on the live volume via entrypoint; `/health/ready/` still 200
- [x] `manage.py shell` drill: create profile for a fresh dev user → transition chain
  REGISTERED→…→JOINING_LETTER_RECEIVED succeeds; attempt REGISTERED→SELECTED (raises),
  JOINED→anything (raises `status_terminal`); WITHDRAWN from mid-chain works, then is terminal;
  display-name resolution across ANONYMOUS/DISPLAY_NAME
  *(executed 2026-09-21: DRILL-SUCCESS — full chain walk, terminal rejections, OTHER↔W4JL escape/reverse,
  WITHDRAWN terminal, display/blank fallback, no email leak, no-profile resolver)*
- [x] Full pytest re-run green; ruff clean; `makemigrations --check` clean
  *(53 passed in apps/candidates — 2 more than planned: bogus-status and WITHDRAWN-resurrection pins)*
- [x] Prod compose still validates; docs updated: `.planning/STATE.md`,
  `REQUIREMENTS.md` (PROF-01..03 → Complete; PROF-04 stays 3.2),
  ROADMAP Phase 3 row (1/2), PLAN gate checkboxes

## Out of scope (Phase 3.2+)

- `/api/v1/profile/` CRUD, serializers, PRIV/public redaction (PROF-04), impersonation
  blocking (T3.7), creation gating on active+verified users
- Atomic timeline sync (4.1, TIME-02); composite indexes (Phase 7 analytics patterns);
  admin triage (Phase 8)
