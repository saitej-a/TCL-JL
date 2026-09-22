---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 6.2 context gathered (6.1 UAT paused at test 1 of 7)
last_updated: "2026-09-22T11:20:00.000Z"
last_activity: 2026-09-22 -- Phase 6.2 context gathered
progress:
  total_phases: 10
  completed_phases: 5
  total_plans: 27
  completed_plans: 12
  percent: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-19)

**Core value:** Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.
**Current focus:** Phase 5 COMPLETE (all COMM requirements shipped). Next: Phase 6 — In-App Notifications & FCM Web Push.

## Current Position

Phase: 6.2 CONTEXT GATHERED (of 10 — In-App Notifications & FCM Web Push); Phases 1-5 COMPLETE, 6.1 executed, 6.1 UAT paused
Plan: 06-01 executed 2026-09-22 (5 tasks, one migration, 45 new tests); 06.2 context locked (16 decisions, 4 open questions)
Status: 6.1 awaiting a UAT response (test 1 of 7 presented); 6.2 ready to plan
Last activity: 2026-09-22 -- Phase 6.2 context gathered

Progress: [████░░░░░░] 44%

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: — (per-plan timing not yet instrumented)
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Project Foundation, Docker & Environment Setup | 3/3 | - | - |
| 2. Authentication, Identity & Custom User System | 3/3 | - | - |
| 3. Candidate Profiles & Public Identity Controls | 2/2 | - | - |
| 4. Recruitment Timeline Engine | 2/2 | - | - |
| 5. Community Discussions & Forum System | 3/3 | - | - |
| 6. In-App Notifications & FCM Web Push System | 1/3 | - | - |
| 7. Community Analytics & Privacy Engine | 0/2 | - | - |
| 8. Moderation, Anti-Spam & Administration | 0/3 | - | - |
| 9. Frontend Single Page Application (React + Tailwind) | 0/4 | - | - |
| 10. Security Audits, E2E Testing, Seed Data & Launch Readiness | 0/2 | - | - |

**Recent Trend:**

- Last 5 plans: 04-01, 04-02, 05-01, 05-02+05-03, 06-01 (06-01: 45 new tests, two own-test bugs found and fixed by the live drill, 486-test suite green)
- Trend: Stable

## Accumulated Context

### Roadmap Evolution

- Phases 1–10 decomposed into 22 decimal sub-phases (X.1/X.2 pattern; Phase 9 has four) as focused planning/execution units — directories scaffolded under `.planning/phases/`, mappings logged in ROADMAP.md Phase Details and REQUIREMENTS.md Sub-Phase Traceability.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: Modular Django monolith chosen over premature microservices for velocity and ACID consistency.
- [Phase 1]: Celery + Redis chosen for asynchronous decoupling of third-party Google FCM and transactional emails.
- [Phase 1]: React 18 + Tailwind CSS + Vite chosen for mobile-first PWA responsiveness.
- [Phase 4.1 — D1]: Walk-the-chain status sync: event types map to target statuses; sync advances hop-by-hop along the 3.1 legal edges (multi-hop backfills OK); at/past = idempotent no-op; blocked chains (terminal, OTHER-pre-WAITING) raise + roll back the event insert.
- [Phase 4.1 — D2]: Forward-only status: event edits/deletes never regress `current_status`; only event_type edits re-sync (toward the new mapped target).
- [Phase 4.2 — D1]: Dashboard ships its complete 04 §28 key contract now: the community block is computed for real from candidate profiles; `community.unread_notifications` is an explicit `0` placeholder wired in Phase 6.
- [Phase 4.2 — D2]: Benchmark = waiting-state total + per-status distribution, both threshold-suppressed (`ANALYTICS_MIN_COHORT_SIZE = 5`, 04 §53) and labeled `COMMUNITY_REPORTED` (04 §65.20); suppressed output omits the counts rather than zeroing them.
- [Phase 4.2 — D3]: Timeline `event_date` bound = today + 24 months (settings-driven), applied to every event type, plus a present-or-past carve-out for `JOINING_LETTER`; `JOINING_DATE` stays legitimately future-datable.
- [Phase 4.2 — R4]: `auto_update_status` is not client-controllable — the API hardcodes `True`, so a caller cannot record a milestone while leaving `current_status` stale (04 §121).
- [Phase 5.1 — D1]: Post categories are the merged union of three disagreeing spec lists (12 keys, `OFFER` folded into 01's `OFFER_LETTER` so the vocabulary matches `TimelineEvent`), held in `POST_CATEGORIES` and read at call time — the field carries no `choices`, so extending the list needs no migration.
- [Phase 5.1 — D2]: `Post.author`/`Comment.author` are required and `PROTECT`; the retained anonymized User row (2.2) is the tombstone, which 3.2's author serializer already renders safely — no NULL-author branch anywhere. Consequence: a hard user delete is refused, so F1's fix must delete the *profile*.
- [Phase 5.1 — D3]: One neutral tombstone copy (`This content has been removed.`) covers author- and moderator-deletion alike, because the single `is_deleted` flag cannot distinguish them; originals stay in the row (08 §390) and masking happens only in `tombstones.display_*`.
- [Phase 5.1 — D4/P1]: Deleted posts leave the feed (03 §28) while tombstoned comments stay in their threads; `Comment.parent` is `SET_NULL` (not CASCADE/PROTECT) so a disappearing parent promotes a reply instead of destroying it, and post hard-deletion is never blocked.
- [Phase 5.1 — P4]: Integrity guarantees are deliberately unequal and documented as such — duplicate votes are impossible at the database level (`unique_user_post_vote`), while the 1-level reply rule is application-level because PostgreSQL cannot express a cross-row `CHECK`.
- [Phase 6.1 — D1/D2]: All seven 07 §3.1 notification types ship as a nested model `TextChoices` (not a settings-held list like 5.1 D1) because the values drive code dispatch in 6.2/6.3 — a settings-added type would reach the dispatcher with no handler. The model `TextChoices` is the closed, system-owned vocabulary; only four types have v1 producers and the docstring says so.
- [Phase 6.1 — D3/D4]: `title`/`message` are **stored snapshots** written at creation, and 6.1 composes/renders nothing — anonymity-safe labels belong to 6.2's `create_notification` service (via 3.2's `AuthorPublicSerializer` semantics), which is what keeps 07 §8's zero-PII push rule achievable at write time.
- [Phase 6.1 — D5]: `notification_read_state` (`CHECK (NOT is_read OR read_at IS NOT NULL)`) is the project's first `CheckConstraint` and the phase's hard guarantee; it is deliberately one-directional (`read_at` set while unread is legal). `clean()` mirrors it with code `read_state_inconsistent`, and `mark_as_read()` is the single sanctioned pair writer (one UPDATE naming both columns, idempotent).
- [Phase 6.1 — D6]: `NotificationManager.unread_count_for(user)` ships now — the seam 4.2 D1 promised; the dashboard keeps its explicit `0` placeholder until 6.2 wires the call.
- [Phase 6.2 — D1/D2]: `firebase-admin` behind a `PushBackend` seam (first new dependency since Phase 1); the real adapter ships but is verified credential-free — recording backend plus unit tests asserting the `MulticastMessage`, no live FCM call in 6.2.
- [Phase 6.2 — D3/D4/D5]: thread debounce **suppresses** (cache framework, not raw Redis) and exempts non-thread types plus `VOTE_MILESTONE`; milestone thresholds are settings-held with a count-watermark dedupe needing no migration; the stored row keeps the rich in-app text while the push body comes from a per-type generic template, so no comment body can reach a lock screen.
- [Phase 6.2 — D6/D7/D8/D9]: a token bound to another user is reassigned last-writer-wins; revoke is a soft deactivate with the daily prune task as the only row deleter; device list uses the standard paginated envelope; `last_seen_at` moves on device endpoints only.
- [Phase 6.2 — D13/D14]: 6.2 adds `GET|PATCH /api/v1/notifications/preferences/` (07 §11 omits it but NOTIF-06 requires it), and the flags gate the push only — all seven types mapped, with `MODERATION`/`SYSTEM` under `push_enabled` alone.
- [Phase 6.2 — D15/D16]: announcements are deferred wholesale to Phase 8, so only three types have live producers at 6.2's end (correcting 6.1 D1's "four"); the service worker is deferred to 9.4 with the push payload contract pinned by tests instead.
- [Phase 6.1 — R1/R2/R3/R9]: The plan's pinned index name `idx_notif_recipient_read_created` is 32 chars and Django rejects names over 30, so it shipped as `idx_notif_recip_read_created`; the constraint uses `condition=` (the deprecated `check=` would warn on Django 5.2); `Device.__str__` renders no email/token (03 §8); `auto_now` fields refresh only when named in `update_fields`.

### Pending Todos

- **Resume the 6.1 UAT** (`.planning/phases/TCS-JL-06.1-notification-device-models/06.1-UAT.md`, status `testing`): test 1 of 7 (cold start smoke test) was presented with evidence and is awaiting `pass` or an issue description. `audit-open` reports no other open items.
- **Decide F1's disposition** (VERIFICATION.md 4.2): `anonymize_delete_account` does not delete the CandidateProfile or its timeline events, contrary to 06 §4.2 step 4 / §2.7 "Zero Orphaned PII". Either fix the 2.2 deletion service (delete the profile inside the same transaction; the FK cascade removes events) or record an explicit decision to retain anonymized profiles — then either way exclude them from the dashboard cohort (F2).
- Phase 6.2 (next — context gathered, ready to plan): `06.2-CONTEXT.md` locks 16 decisions; the planner must honour the seam wiring (`unread_count_for` into `apps/timeline/services.py:212`), anonymity-safe composition in `create_notification`, `fcm_token` `write_only=True`, and the paired `is_read`/`read_at` write in mark-all-read.
- Phase 5.2 carried decision: 08 §406 renders a deleted post's author as unattributed — the author-nulling rule for deleted posts (and whether a tombstoned comment keeps its handle) is a 5.2 serializer decision.
- Phase 6/7 wiring: the notifications **seam** exists (`NotificationManager.unread_count_for`, 6.1) but `community.unread_notifications` still returns the 4.2 placeholder until 6.2 calls it; extend the dashboard analytics block beyond the profile-derived counts in Phase 7, applying the cohort floor **per bucket**, not just globally (4.2's residual-risk note).
- Low-severity polish from 4.2 verification: shared JSON 404 for unresolvable paths (F3), `Allow` header on 405 (F4), whether `WITHDRAWN` should count as profile-completion progress (F5), timeline write throttling if abuse appears (F6).

### Blockers/Concerns

- **F1 (HIGH, pre-existing in Phase 2.2, surfaced by 4.2 verification):** deleted candidates retain their profile row (with `display_name`, `batch`, `region`, `current_status`) and all private timeline events. Not a 4.2 regression — 4.1/4.2 assumed the deletion flow was implemented. Blocks any milestone claim of 06 §4.2 compliance until decided.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Timeline UI | TIME-04's interactive chronological roadmap with edit/delete controls | Deferred to 9.3 (UI-03); API half shipped in 4.2 | 2026-09-22 | v1.0 |
| Dashboard data | Real unread-notification count | Seam shipped in 6.1 (`unread_count_for`); the dashboard keeps its `0` placeholder until 6.2 wires it | 2026-09-22 | v1.0 |
| Analytics depth | Batch/hiring-type/region breakdowns + `/api/v1/analytics/*` | Deferred to Phase 7 (its suppression rules cover that surface) | 2026-09-22 | v1.0 |
| Announcements | `Announcement` model, broadcast task, `notify_on_announcements` verification | Deferred from 6.2 to Phase 8 (T8.6) by D15; the reserved task route stays inert | 2026-09-22 | v1.0 |
| Push frontend | `firebase-messaging-sw.js` + soft-primer UX (T6.12) | Deferred from 6.2 to Phase 9.4 by D16; the payload contract is pinned by tests now | 2026-09-22 | v1.0 |

## Session Continuity

Last session: 2026-09-22T11:20:00.000Z
Stopped at: Phase 6.2 context gathered — 06.2-CONTEXT.md written (16 decisions, 4 open questions); 6.1 UAT still paused at test 1 of 7
Resume file: .planning/phases/TCS-JL-06.2-device-registration-fcm-push/06.2-CONTEXT.md
