# Phase 3.1 — Discussion Record: Candidate Profile Model & Status Machine

Date: 2026-09-21
Scope: Roadmap plan 03-01 (T3.1–T3.3) — model layer only: 1:1 CandidateProfile, status
state machine, public identity toggle. API/serializer boundaries are Phase 3.2 (03-02).
Requirements covered: PROF-01, PROF-02, PROF-03.

## Decisions locked (user)

- **D1 — Status vocabulary: 11 values, WITHDRAWN reachable as terminal.**
  T3.2's set: REGISTERED, INTERVIEWED, SELECTED, OFFER_RECEIVED, READINESS_SURVEY,
  WAITING_FOR_JOINING_LETTER, JOINING_LETTER_RECEIVED, JOINING_DATE_RECEIVED, JOINED,
  WITHDRAWN, OTHER. WITHDRAWN is terminal and reachable **from any status** (covers
  offer revocations / resignations); OTHER is a normal non-terminal status.
- **D2 — Transition enforcement: diagram edges exactly.**
  Service layer (T3.2) validates against exactly: the forward chain
  REGISTERED→INTERVIEWED→SELECTED→OFFER_RECEIVED→READINESS_SURVEY→
  WAITING_FOR_JOINING_LETTER→JOINING_LETTER_RECEIVED→JOINING_DATE_RECEIVED→JOINED;
  the four escape edges SELECTED/OFFER_RECEIVED/READINESS_SURVEY/
  WAITING_FOR_JOINING_LETTER→OTHER; the reverse edge OTHER→WAITING_FOR_JOINING_LETTER;
  plus D1's *→WITHDRAWN terminal edges. Everything else rejected (service raises;
  API renders 400 in 3.2). Same-status no-ops are allowed (idempotent saves).
- **D3 — Batch: configurable choices list; region stays free text.**
  `batch` is a CharField validated against a configurable `BATCH_YEARS` list in
  Django settings (ships as ["2024","2025","2026"] per REQUIREMENTS PROF-01).
  Adding 2027 later = settings change, no migration. Model-level choices are set
  from settings at class definition (validated via field validator so runtime
  settings changes re-validate).
- **D4 — Profile existence: nullable 1:1, created via API.**
  `user = OneToOneField(User, null=True, related_name="candidate_profile")` with
  unique constraint (OneToOne semantics); no auto-creation signals.
  `get_public_display_name()` safely returns "Anonymous Candidate" for users
  without a profile and for ANONYMOUS mode. Deleted-account tombstones (2.2)
  never gain profiles.

## Spec-derived invariants (no decision needed)

- Model per 03 §5: UUIDv4 PK; display_name (optional), public_identity_mode choice
  ANONYMOUS/DISPLAY_NAME (default ANONYMOUS), region, interview_center, interview_date
  (nullable), joining_location (nullable), offer_letter_date (nullable),
  expected_joining_date (nullable), current_status (D1 set, default REGISTERED),
  created_at/updated_at (auto).
- `get_public_display_name()` per T3.3: ANONYMOUS (or missing profile/blank
  display_name) → "Anonymous Candidate"; DISPLAY_NAME → sanitized display_name.
- Indexes per 03 §17: single-column on batch, hiring_type, region, current_status,
  joining_location, interview_date, offer_letter_date, expected_joining_date.
  Composite deferred to Phase 7 (analytics query patterns are the real driver).
- Status transitions validated in the **service layer** (`apps/candidates` or
  `accounts`-adjacent service module — planner's call), never trusting client values.
- 02 §17: status changes may optionally create timeline events — actual atomic sync
  is Phase 4.1 (TIME-02); 3.1 only notes the seam.
- Public display never exposes email (03 §5; PROF-04 enforcement is 3.2).

## Inputs already in place

- `accounts.User` UUID PK, CITEXT email, is_verified, deletion tombstones
  (deleted_*@tracker.internal, is_active=False) — profiles must never be created
  for inactive users (3.2 API gate; model layer just stays nullable).
- `apps/` project layout + 92-test green suite + CI gates from Phases 1–2.
- New app boundary: 10_MVP T3.1 places CandidateProfile in `apps/candidates/models.py`
  (matches 09 §3.1 app map); settings INSTALLED_APPS + apps.py update required.

## Open items for planning (3.1 PLAN.md)

1. App name: `candidates` (T3.1's path) vs `profiles` — planner picks, T3.1 wording
   suggests `candidates`.
2. WITHDRAWN terminal edges from *any* status — encode as explicit dict entries
   or as a special case in the transition validator (planner's call).
3. Test matrix: transition accept/reject pairs incl. WITHDRAWN-from-every-status,
   display-name method (ANONYMOUS/DISPLAY_NAME/missing profile/blank name),
   batch validator (in-list / out-of-list / settings-driven), nullable-1:1 invariants,
   index presence via migration inspection.
