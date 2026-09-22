---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: milestone
current_phase: "7.2"
current_phase_name: Analytics Endpoints & Redis Caching
status: executed
stopped_at: 7.2 planned and executed (6 tasks, 5 commits) — five anonymous endpoints, payload cache + hourly warmup, per-row suppression; 638 tests green, 19/19 live HTTP drill; awaiting verification
last_updated: "2026-09-22T17:02:00.000Z"
last_activity: 2026-09-22
last_activity_desc: 7.2 executed — analytics endpoints, Redis caching and per-row suppression live; both of 7.1's owed decisions delivered
state_head: 814b9d58acf018267c3a09239d53a34d9ff86048
progress:
  total_phases: 10
  completed_phases: 5
  total_plans: 27
  completed_plans: 14
  percent: 52
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-19)

**Core value:** Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.
**Current focus:** Phase 7 — Community Analytics & Privacy Engine. Both plans (7.1 service layer, 7.2 endpoints + Redis caching) are executed; **Phase 7 now awaits verification** (`/gsd-ns-workflow verify 7.2`).

## Current Position

Phase: 7.2 EXECUTED (of 10 — Community Analytics & Privacy Engine); Phases 1-4 complete (4.2 independently verified PASS), **Phase 5 independently verified FAIL with two HIGH defects still live**, 6.1/6.2/7.1/7.2 executed but unverified
Plan: 07-01 executed 2026-09-22 (22 tests, 16/16 live drill); 07-02 executed 2026-09-22 (6 tasks, 32 new tests, 19/19 live HTTP drill, zero models/migrations)
Status: UAT-recorded, not verified — 6.1/6.2/7.1 UATs closed complete on user attestation (0 of 24 checks executed); 7.2 has no UAT session yet; all lack VERIFICATION.md and SECURITY.md and cannot transition
Last activity: 2026-09-22 -- Phase 7.2 planned and executed

Progress: [████░░░░░░] 48%

## Performance Metrics

**Velocity:**

- Total plans completed: 13
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
| 7. Community Analytics & Privacy Engine | 2/2 | - | - |
| 8. Moderation, Anti-Spam & Administration | 0/3 | - | - |
| 9. Frontend Single Page Application (React + Tailwind) | 0/4 | - | - |
| 10. Security Audits, E2E Testing, Seed Data & Launch Readiness | 0/2 | - | - |

**Recent Trend:**

- Last 5 plans: 05-02+05-03, 06-01, 06-02, 07-01, 07-02 (07-02: 32 new tests, 638-test suite green, zero migration drift, ruff clean, 19/19 live HTTP drill checks — and the drill found four real problems before the gates did: ambient dev data breaking two seeded assumptions, a wrong-endpoint filter probe, a same-second timestamp comparison, and a stale cache served to the first read)
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
- [Phase 7.1 — D1]: The wait-time baseline is the OFFER_LETTER event, then the INTERVIEW event, then `CandidateProfile.offer_letter_date`, then `interview_date`, and the endpoint is the JOINING_LETTER event; per candidate the *earliest* occurrence of each milestone wins, and a candidate whose JL precedes its baseline is dropped rather than clamped (a negative interval is corrupted data, not a negative wait). This is deliberately narrower than ANAL-03's literal "survey submission" baseline — recorded as an open divergence, not silently resolved.
- [Phase 7.1 — D2]: Suppression is **full-cohort** and keyed on `settings.ANALYTICS_MIN_COHORT_SIZE` (5): a filtered slice below the floor returns only `data_source`/`suppressed`/`message`/`disclaimer` — no counts and no zeroed or partial rows, because a zeroed bucket still discloses that the bucket exists. The floor is applied to the **slice total**, so a single result row inside a large slice can still report a count below 5 (per-bucket floors stay the open 4.2 residual-risk item).
- [Phase 7.1 — D3]: `apps/analytics` is enforced read-only by `test_phase_boundary.py` rather than by convention — no `models.py`, no `migrations/`, no `views.py`/`urls.py`/`serializers.py`, no `tasks.py`, and no `django.core.cache` import, plus a check that the app config registers zero models. 7.2 cannot grow an endpoint or a cache without failing that test and updating it deliberately.
- [Phase 7.1 — D4]: Every payload carries `data_source: "COMMUNITY_REPORTED"` **and** the non-affiliation disclaimer — including suppressed payloads, which 04 §53's documented suppression shape omits. The extra field is additive to the spec so a UI can render the disclaimer from any analytics response without a second code path.
- [Phase 7.2 — D-01/D-02/D-03]: The `<5` floor now applies to **each result row**, and a below-floor row is dropped entirely — not zeroed, not labeled, not counted — because the withheld count is itself a disclosure. If no row clears the floor the response is 04 §53's standard suppression payload (never `suppressed: false` with an empty `results[]`, and never the slice totals with the small rows omitted, which reveals them by subtraction). One `ANALYTICS_MIN_COHORT_SIZE` governs both levels; a second knob was rejected because two values that must stay in a privacy ordering are a misconfiguration risk. This **changes 7.1's shipped payloads** and requires updating its tests deliberately.
- [Phase 7.2 — D-04/D-05/D-06/D-07]: The cached unit is the **assembled response payload per endpoint + filter signature**, reusing 7.1's functions verbatim (one compute path, one serialize path). TTL is 7200s in a settings key read at call time — a **recorded deviation from `10_MVP_TASKS.md` T7.8's `ttl = 15m`**, which cannot coexist with an hourly warmup (a 15-minute TTL expires three times per cycle, making the beat task decorative); ROADMAP criterion 4 is authoritative. `generated_at` is written into the cached payload at compute time so a cache hit reports when its numbers were computed. `warm_analytics_cache` is routed to the `maintenance` queue, joining `prune_stale_devices`.
- [Phase 7.2 — D-08…D-12]: All five read endpoints are anonymous — 04 §6 lists "Landing-page information" and "Public aggregate statistics" under Anonymous, so this is spec-mandated, not chosen. 7.2 builds **04 §80 `GET /api/v1/public/stats/`** (the roadmap's "public landing stats endpoint", T7.9, consumed by 05_UI_UX §746) as its own thin endpoint because §80's cross-app count keys are not the analytics overview shape. **04 §52 `/analytics/timeline/` is deferred to backlog** (no requirement owns it, §108's test list omits it). An anon-scoped `analytics_reads` throttle closes the cache-busting path (unfiltered `default` was rejected because a caller can walk region × hiring_type × batch to force uncached computation), and filters are whitelist-validated against model choices + `BATCH_YEARS` with 400 on unknown values — which also bounds the cache key space.
- [Phase 7.2 — D-13…D-16]: ANAL-03 is closed **literally** by publishing **both intervals as separate metrics** — survey→JL (`READINESS_SURVEY`, the requirement's and T7.7's wording) and D1's offer→JL — each with its own sample size and its own `<5` floor, because the survey is later than the offer (different numbers, not interchangeable) and `12_SEED_DATA` gives only ≈20% of the cohort a survey event (a survey-only metric would routinely suppress). They surface through `/analytics/overview/` (04 defines no wait-time endpoint). Deleted/anonymized accounts **stay counted** exactly as 7.1's aggregations do, accepting 4.2's F1/F2 rather than changing published cohort semantics in an exposure phase. Each metric discloses its baseline and per-source sample sizes, so a mixed average is never presented as one number.
- [Phase 7.2 — R1]: **DRF's `ScopedRateThrottle` reads the scope from the view, not the class.** `allow_request` does `self.scope = getattr(view, 'throttle_scope', None)` and returns `True` — allowing the request — when the view declares none, so a class-level `scope` alone is inert. 7.2 therefore sets `throttle_scope` on its base view *and* asserts the bucket engages (429 after the rate is exceeded), because declaring the class and trusting it is exactly how a throttle silently does nothing. Found while wiring this: **community's `CommunityWriteRateThrottle` is inert on all six of its views** (see Pending Todos).
- [Phase 7.2 — R2]: The region filter is bounded by length (100, the model's `max_length`) and charset (`isalnum` plus ` -.'(),/&`) rather than by a vocabulary, because 3.1 D3 makes `region` free text and a whitelist built from regions that *currently* have candidates would 400 a legitimate region with no data yet. Digits are deliberately permitted (`Sector 62`), and safety comes from the key being a sha256 digest rather than the raw value — the charset check is input hygiene, not an injection barrier.
- [Phase 7.2 — R3]: **Cached analytics have no invalidation on data change.** A payload lives up to `ANALYTICS_CACHE_TTL` (2h) and is refreshed hourly by the warmup, so a manual data fix is not visible publicly until one of those fires. That is the designed trade-off (D-05) rather than a defect, but it is operationally visible: the 7.2 drill had to purge the `analytics:*` namespace before asserting *live* data, having been served the previous run's payload on its first read.
- [Phase 7.1 — R1/R2]: The aggregations are per-bucket ORM walks (one `values("batch").annotate(Count)` then one status-count query per bucket) rather than a single `GROUP BY (bucket, status)`, so each call costs O(buckets) queries; correct and readable at MVP scale, and 7.2's Redis warmup is what makes it cheap. The plan's unused `Avg`/`Max`/`Min`/`Q`/`Decimal` imports were dropped, and `DISCLAIMER_TEXT` was wrapped to satisfy the 100-char E501 limit.

### Pending Todos

- **Fix 05.2's two HIGH defects before any Phase 5 COMPLETE claim survives** (surfaced again by the v1.0 milestone summary): `feed_queryset` in `apps/community/views_services.py` never filters `is_deleted=False` (trending does), so deleted posts still appear in the default feed and in `?search=`; `PostListCreateView` declares no `throttle_classes` and there is no `DEFAULT_THROTTLE_CLASSES`, so `POST /api/v1/community/posts/` is unbounded. Both were verified still present in the current tree. Repair `test_deleted_posts_absent_from_feed` too — it asserts on the masked tombstone title, so it is vacuous and passed while the bug was live. Also open from that verification: the feed card's missing `body_preview` (F3) and the vote response's missing `voted` (F4).
- **Wire the account-deletion device revocation** (NEW — found by direct code inspection during the milestone summary, never recorded by any phase): `anonymize_delete_account` (`apps/accounts/services.py`) still carries the literal placeholder `# >>> Phase 6 hook: revoke all FCM device registrations here. <<<`, which 6.2's plan promised to replace with `user.devices.all().delete()`. A deleted account therefore keeps active `Device` rows with live FCM tokens, and the push worker will still attempt delivery to them. Fix alongside F1 (delete the profile + let the timeline cascade) in one atomic transaction.
- **Three UATs closed by attestation — but none of the three phases is verified** (2026-09-22): 6.1, 6.2 and 7.1 recorded 24 `pass` results at the user's instruction with `source: user-attested` and **not one check executed**; each file carries a provenance note naming the attester. These are acceptance decisions, not evidence. All three still need a canonical `VERIFICATION.md`, and the completion predicate cannot even be evaluated in this repo — `gsd_run phase uat-passed 6.1 --require-verification` returns `Error: Phase 6.1 not found` (the project-code resolution failure below). Separately, `workflow.security_enforcement` is on with two active `verify:post` step hooks (`secure-phase` → SECURITY.md, `validate-phase` → VALIDATION.md) and **no phase has ever produced a SECURITY.md**, so the security gate blocks advancement on its own. Do not report 6.1, 6.2 or 7.1 as transitioned.
- **Decide F1's disposition** (VERIFICATION.md 4.2): `anonymize_delete_account` does not delete the CandidateProfile or its timeline events, contrary to 06 §4.2 step 4 / §2.7 "Zero Orphaned PII". Either fix the 2.2 deletion service (delete the profile inside the same transaction; the FK cascade removes events) or record an explicit decision to retain anonymized profiles — then either way exclude them from the dashboard cohort (F2).
- ~~**Decide ANAL-03's true wait-time baseline**~~ — **RESOLVED 2026-09-22 by 7.2 D-13**: both intervals are published as separate metrics (survey→JL per the requirement, offer→JL per D1), each with its own sample size, own `<5` floor and baseline disclosure. ANAL-03 can move off Partial when 7.2 executes; no requirement text needs rewriting.
- Phase 7.2 (next): expose the 7.1 service layer as `GET /api/v1/analytics/overview|batches|hiring-types|regions/` (04 §48-51 shapes already match the service payloads), add `generated_at`, build `GET /api/v1/public/stats/` (04 §80), apply the per-row floor (D-01) and the survey→JL metric (D-13), wrap the helpers in the Redis caching layer with the hourly Celery Beat warmup, and keep every response attributed (`COMMUNITY_REPORTED` + disclaimer). **Context is gathered — plan 07-02 from `07.2-CONTEXT.md`.** Two carry-forward constraints for the planner: 7.2 must **update `test_phase_boundary.py` deliberately** (7.1 D3 asserts the app has no views/urls/tasks), and the route/decorator name must match `config/celery.py`'s reserved `analytics.tasks.warm_analytics_cache` exactly or the `maintenance` route silently does not apply. **04 §52 `/analytics/timeline/` is deferred to backlog by D-10** — it is a recorded gap, not an oversight.
- Phase 5.2 carried decision: 08 §406 renders a deleted post's author as unattributed — the author-nulling rule for deleted posts (and whether a tombstoned comment keeps its handle) is a 5.2 serializer decision.
- **Community's write throttle is inert (NEW — found while wiring 7.2's read throttle, never recorded by any phase):** `apps/community/throttles.py`'s `CommunityWriteRateThrottle` subclasses `ScopedRateThrottle`, but **none of the six community views that attach it declare `throttle_scope`**, and DRF's `ScopedRateThrottle.allow_request` returns `True` (allow) whenever the view declares no scope. So post/comment/vote/lock/pin writes are unthrottled in fact, not merely under-specified — the class being attached looks like protection in review. Fix: add `throttle_scope = "community_writes"` to those views (the `apps/accounts/views.py` pattern, which *does* engage) plus a test asserting the bucket actually 429s; also give `PostListCreateView` its missing `throttle_classes` (05.2 F2). `apps/notifications/throttles.py` is unaffected — it uses `UserRateThrottle`, where the class-level `scope` is authoritative.
- ~~Phase 7 wiring: per-bucket floor still open~~ — **RESOLVED 2026-09-22 by 7.2 D-01/D-02/D-03**: the floor applies per result row, below-floor rows are dropped entirely, and one setting governs both levels. Carries one consequence into execution: 7.1's tests that assert slice-level-only behaviour must be updated rather than deleted. Still open: the dashboard's own analytics block needs 4.2's profile-derived counts extended to the 7.1 helpers.
- Low-severity polish from 4.2 verification: shared JSON 404 for unresolvable paths (F3), `Allow` header on 405 (F4), whether `WITHDRAWN` should count as profile-completion progress (F5), timeline write throttling if abuse appears (F6).

### Blockers/Concerns

- **Phase 5 is marked COMPLETE while independently verified FAIL (HIGH):** 05-02's `VERIFICATION.md` verdict is FAIL on two HIGH acceptance-criteria defects, both re-confirmed live in the current tree (deleted posts in the feed/search; unthrottled post creation). STATE.md's prose, REQUIREMENTS.md (`COMM-01`/`COMM-02` = Complete) and ROADMAP.md (05-02/05-03 ticked, Phase 5 = 3/3) all contradict that verdict, and 05.2's findings were dropped from Pending Todos by later phases writing over this section. Do not carry a Phase 5 or milestone COMPLETE claim until F1/F2 are fixed and re-probed. Details: `.planning/phases/TCS-JL-05.2-feed-comments-and-voting-endpoints/VERIFICATION.md`, summarised in `.planning/reports/MILESTONE_SUMMARY-v1.0.md` § 6.
- **F1 (HIGH, pre-existing in Phase 2.2, surfaced by 4.2 verification):** deleted candidates retain their profile row (with `display_name`, `batch`, `region`, `current_status`) and all private timeline events. Not a 4.2 regression — 4.1/4.2 assumed the deletion flow was implemented. Blocks any milestone claim of 06 §4.2 compliance until decided. 7.1 inherits it directly: the aggregation cohorts count those retained profiles, so the analytics themselves now include anonymized-but-present candidates (the 4.2 F2 exclusion question is still unanswered).
- ~~**Per-bucket suppression gap (MEDIUM)**~~ — **RESOLVED 2026-09-22 by 7.2 D-01/D-02** (per-row floor; whole-response suppression when nothing survives). The vector closes when 7.2 executes; until then the live endpoints do not yet exist, so there is no exposure window in the current tree.
- **Community writes are unthrottled in fact (HIGH, new in 7.2):** see Pending Todos — the throttle class is attached to six views but never engages, because DRF reads the scope from the view and none of them declare one. Adjacent to 05.2's F2 (missing `throttle_classes` on post creation) but distinct from it: even the views that *have* the class attached get no rate limiting.
- **Public analytics will count anonymized accounts (accepted, new in 7.2 D-15):** 4.2's F1/F2 retention gap means a deleted candidate keeps a profile row, so **every published cohort count includes candidates who have left the community** — and 7.2 D-15 deliberately keeps that behaviour rather than changing cohort semantics inside an exposure phase. The fix belongs with the retention model (delete the profile + let the timeline cascade, alongside the still-unwired device revocation above). Until then, public numbers overstate the present community.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Timeline UI | TIME-04's interactive chronological roadmap with edit/delete controls | Deferred to 9.3 (UI-03); API half shipped in 4.2 | 2026-09-22 | v1.0 |
| Dashboard data | Real unread-notification count | Seam shipped in 6.1 (`unread_count_for`); the dashboard keeps its `0` placeholder until 6.2 wires it | 2026-09-22 | v1.0 |
| Analytics depth | Batch/hiring-type/region breakdowns + `/api/v1/analytics/*` | Service layer shipped in 7.1 (overview/batch/stream/region helpers + wait-time engine + `<5` suppression); the `/api/v1/analytics/*` endpoints and Redis caching carry to 7.2 | 2026-09-22 | v1.0 |
| Announcements | `Announcement` model, broadcast task, `notify_on_announcements` verification | Deferred from 6.2 to Phase 8 (T8.6) by D15; the reserved task route stays inert | 2026-09-22 | v1.0 |
| Push frontend | `firebase-messaging-sw.js` + soft-primer UX (T6.12) | Deferred from 6.2 to Phase 9.4 by D16; the payload contract is pinned by tests now | 2026-09-22 | v1.0 |
| Analytics | `GET /api/v1/analytics/timeline/` (04 §52) | Deferred by 7.2 D-10 — no ANAL requirement owns it and §108's required test list omits it; needs an event-level aggregation plus a per-day suppression rule. Recorded as a known gap | 2026-09-22 | v1.0 |
| API docs | OpenAPI/schema generation (04 §109) | Deferred by 7.2 to Phase 10.2 hardening; the project hand-writes endpoint contracts and the analytics phase stays read-only | 2026-09-22 | v1.0 |
| Deleted accounts in public analytics | Exclude anonymized profiles from published cohorts (4.2 F1/F2) | **Accepted, not forgotten** (7.2 D-15): belongs with the retention fix, and the consequence is recorded in Blockers/Concerns | 2026-09-22 | v1.0 |

## Session Continuity

Last session: 2026-09-22T17:02:00.000Z
Stopped at: 7.2 planned and executed. Five anonymous endpoints (04 §48–§51 + §80), payload-level Redis caching behind the reserved hourly warmup, per-row `<5` suppression, `analytics_reads` throttling and whitelist filter validation are live; every gate green (638 tests, ruff, `makemigrations --check`) and the 19/19 HTTP drill restored the database to 21 candidates / 66 events. Next: `/gsd-ns-workflow verify 7.2`, then Phase 8 (moderation).
Resume file: .planning/phases/TCS-JL-07.2-analytics-endpoints-and-redis-caching/07.2-SUMMARY.md

**Still owed elsewhere (unchanged by this session):** 7.1's canonical `VERIFICATION.md` is what unblocks its transition; 6.1/6.2/7.1 UATs remain attestation-only; Phase 5's two HIGH defects and F1's deletion-flow decision are live in the tree.
