# Phase 4.1 — Discussion Record: Timeline Model & Atomic Status Sync

Date: 2026-09-21
Scope: Roadmap plan 04-01 (T4.1–T4.3) — model layer only: `TimelineEvent` model,
compound indexes, and the atomic `record_timeline_event` status-sync service.
API/serializers/IDOR/dashboard are Phase 4.2 (04-02).
Requirements covered: TIME-01, TIME-02.

## Decisions locked (user)

- **D1 — Walk-the-chain status sync.** `record_timeline_event` maps event types to
  statuses (INTERVIEW→INTERVIEWED, SELECTION→SELECTED, OFFER_LETTER→OFFER_RECEIVED,
  READINESS_SURVEY→READINESS_SURVEY, JOINING_LETTER→JOINING_LETTER_RECEIVED,
  JOINING_DATE→JOINING_DATE_RECEIVED, JOINED→JOINED) and advances
  `current_status` along legal `ALLOWED_TRANSITIONS` edges — multiple hops allowed
  when backfilling out-of-order milestones. At/past the mapped status = idempotent
  no-op. Blocked chains (terminal status, e.g. JOINED reached but INTERVIEW arrives
  later) raise and roll back the event insert: 400 with the machine's transition
  code surfaced in Phase 4.2. OTHER events and OTHER/WITHDRAWN statuses have no
  event mapping — those status moves stay PATCH-only (3.2 `update_profile` path).
- **D2 — Forward-only sync; no status regression on edit/delete.** Editing or
  deleting a status-driving event never moves `current_status` backwards (TIME-02
  is silent on removal; status is forward-moving). Editing `event_type` re-runs D1
  sync toward the new mapped status (legal-edge walk, same rollback semantics).
  Deleting an event or editing date/description leaves status untouched. Fixing a
  mistaken status means PATCHing the profile through legal edges.

## Spec invariants carried (no decision)

- Model per 03 §7 + T4.1: `apps/timeline/models.py`, UUIDv4 PK, `candidate` FK →
  CandidateProfile (CASCADE — 06 §4.2 deletion step 4 deletes private timeline
  events), `event_type` choices INTERVIEW/SELECTION/OFFER_LETTER/READINESS_SURVEY/
  JOINING_LETTER/JOINING_DATE/JOINED/OTHER, `event_date` (Date), `description`
  (optional text), `is_verified` (Boolean, default False), created_at/updated_at.
- Indexes per T4.2 + 03 §17: compound `(candidate, -event_date)` for timeline
  rendering, `(event_type, event_date)` for analytics aggregation.
- Atomicity per T4.3 + 04 §85: `record_timeline_event` wrapped in
  `@transaction.atomic` — event insert + profile status update commit together or
  roll back together. `transition_status` (3.1) stays the single mutation point
  for status; the timeline service composes it (seam noted in
  apps/candidates/services.py).
- 03 §27: do not blindly reject unusual real-world timelines — D1's walk-the-chain
  accepts out-of-order arrivals when the chain permits; only genuinely blocked
  chains fail.
- No API endpoints in this phase (04 §24–27 CRUD, `IsTimelineOwner` IDOR 404s, and
  `GET /api/v1/dashboard/` are plan 04-02 / Phase 4.2). Service-level tests only
  (T4.9's status-sync portions).
- Config: new `apps/timeline` app needs INSTALLED_APPS + apps.py registration
  (same pattern as 3.1's candidates app).

## Inputs already in place

- 3.1 status machine: `ALLOWED_TRANSITIONS`, `TERMINAL_STATUSES`,
  `InvalidTransitionError` (codes `status_terminal` / `status_invalid_transition`),
  idempotent same-status no-ops, `*→WITHDRAWN` terminal edges (event sync never
  targets WITHDRAWN — no event type maps to it).
- 3.2 `update_profile` already wraps field saves + transitions atomically for the
  PATCH path; 4.1's service wraps event insert + transition the same way.
- 208-test green suite, ruff gates, migration-drift checks from Phases 1–3.
- CandidateProfile.current_status is a plain CharField with choices — no DB-level
  transition enforcement; the service layer is the only writer besides 3.2 paths.

## Open items for planning (4.1 PLAN.md)

1. Sync trigger scope: auto-update on every `record_timeline_event` call with
   `auto_update_status=True` default (T4.3 signature) vs opt-in per call —
   planner pins the default.
2. Walk-the-chain implementation: loop `transition_status` hop-by-hop vs
   computed shortest path — hop-by-hop loop is the natural fit since every chain
   step is a legal edge; planner confirms + caps iterations defensively.
3. D1 blocked-chain failure mode: reuse `InvalidTransitionError` codes vs a new
   `StatusSyncBlockedError` wrapping it — planner's call (4.2 renders 400 either way).
4. Test matrix: per-event-type mapping, backfill multi-hop walk, no-op at/past
   status, terminal-blocked rollback (event row absent + status unchanged),
   OTHER-event no-sync, edit-type re-sync (D2), delete leaves status (D2),
   index presence via migration inspection, FK CASCADE on profile deletion.
