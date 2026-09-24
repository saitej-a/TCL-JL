---
gsd_state_version: "1.0"
milestone: v1.0
current_phase: "9.4"
current_phase_name: Post, Analytics, Notifications & PWA
status: executing
stopped_at: "Phase 9.3 EXECUTED (2026-09-24): 4 backend repairs (D1–D4) + the three content views + create post; gates green (frontend 130 tests / lint / typecheck / build, backend 804, config-settings clean); both halves of the done-when observed live in a browser; the 7 Stitch mockups reconciled to the code (09.3-DESIGN-RECONCILIATION.md); next: verify 09-03"
last_updated: "2026-09-24T10:30:09.867Z"
last_activity: 2026-09-24
last_activity_desc: Phase 9.4 execution started
state_head: 9a4a8d60ed66d18c13b8f320e51b5e591fbbf2d3
progress:
  total_phases: 32
  completed_phases: 6
  total_plans: 21
  completed_plans: 19
milestone_name: milestone
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-19)

**Core value:** Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.
**Current focus:** Phase 9.4 — Post, Analytics, Notifications & PWA

## Current Position

Phase: 9.4 (Post, Analytics, Notifications & PWA) — EXECUTING
Plan: 1 of 1
Status: Executing Phase 9.4
Last activity: 2026-09-24 — Phase 9.4 execution started

Progress: [███████░░░] 70%

### 9.3 execution record (2026-09-24)

**Gates**, all green: `npm run lint` (0 errors, 7 pre-existing fast-refresh warnings), `npm run typecheck`,
`npm run test:run` (28 files / 130 tests), `npm run build`, backend `python -m pytest -q` = **804 passed**
(790 + 9.3's community tests), `git diff --quiet -- config/settings/` clean (the throttle scoping is on the
views, not settings). Two of these gates did not pass when the phase started: `npm run build` was failing on
committed code in `TimelinePage.handleSubmit` (a null-narrowing bug `tsc -b` catches and `tsc --noEmit` does
not), and two feed tests scripted a StrictMode replay the test renderer never performs.

**Live proofs observed in a browser** (signed-in UAT account `uat93@example.com`, created in the dev DB
only — labelled, profile + 4 real timeline events, so the stepper/roadmap had genuine data):

- *Anonymous read (D1)*: signed out, `GET /api/v1/community/posts/` → **200, count 21**; `POST /api/v1/community/posts/` →
  **401**; `POST /api/v1/community/posts/{id}/vote/` → **401**. The public feed renders 20 cards with no session.
- *Filtering (§7.6)*: clicking `Joining Letter` → `?category=JOINING_LETTER`, 6 posts, first card's badge `Joining Letter`,
  pager `Showing 1-6 of 6 posts · Page 1 of 1`. Clicking `Trending (Most Active)` → `?tab=trending`. Clicking `All` →
  category cleared. Typing `drill` → after the 300ms debounce `?tab=trending&search=drill`. `Next` → page 2 of 2,
  `Showing 21-21 of 21 posts`, 1 card rendered.
- *Upvote rollback (UI-03, the roadmap's done-when)*, with the vote request failed at the transport layer:
  committed state `▲ Upvote | 1` · pressed=false → **during flight, before any response: `▲ Upvoted | 2`,
  aria-pressed=true, aria-busy=true** → **after the failure: `▲ Upvote | 1`, aria-pressed=false, aria-busy=false,
  toast "Your vote could not be saved. Please try again."** → interceptors removed, real vote re-run:
  `▲ Upvoted | 2`, no toast, and an independent `GET /posts/{id}/` reported **`vote_count: 2`**.
- *Walk-the-chain (Task 7)*: `/timeline` → `Mark as Received` on the pending Joining Letter node opened the modal
  pre-filled with `Joining Letter (JOINING_LETTER)` + today's date; saving moved Current Status to `JL Received`,
  removed the pending/future slots, and surfaced the unverified warning strip (candidate-authored events are
  `is_verified=false`). `/dashboard` then showed `Status: JL Received (Since 24 Sep 2026)`, a completed `JL`
  stepper node dated `24 Sep 2026`, and the rail summary advanced — one mutation, both surfaces.
- *Pinned announcement (§7.6)*: a published+pinned announcement was created in the dev DB; the feed renders the
  pinned card (eyebrow, title, body, pinned meta) and `GET /announcements/` serves it anonymously (200).

**Backend proofs, run by name** (not inferred from a green suite): `test_deleted_posts_absent_from_feed`,
`test_throttle_scope_registered`, `test_throttle_scope_registered_in_settings`, `test_anon_read_throttle_engages`,
`test_authenticated_reads_unthrottled`, `test_write_throttle_engages` — 6 passed. The old
`test_feed_requires_authentication` no longer exists under that name: `apps/community/tests/test_feed_api.py:48`
carries "P5 superseded for reads by 9.3 D1, preserved for writes" and the anonymous-read module holds the
replacement 200 assertion plus 401s for every write.

**Fail-on-revert check for the repaired test** (Task 3's requirement, so it cannot be another vacuous assertion):
with `feed_queryset`'s `is_deleted=False` removed the test **FAILED** (AssertionError at
`test_feed_api.py:155`), and with the line restored it **PASSED** — the filter removal was reverted in place and
`apps/community/views_services.py` is byte-identical to its committed revision (`git diff` clean).

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
| 8. Moderation, Anti-Spam & Administration | 3/3 | - | - |
| 9. Frontend Single Page Application (React + Tailwind) | 3/4 | - | - |
| 10. Security Audits, E2E Testing, Seed Data & Launch Readiness | 0/2 | - | - |

**Recent Trend:**

- Last 5 plans: 06-02, 07-01, 07-02, 09-02, 09-03 (09-03: 4 backend repairs + the three content views + create post; frontend 130 tests / backend 804 / build green; both halves of the done-when observed live; and — the lesson of the phase — the design work had to be redone because the mockups were catalogued but never read, which the reconciliation turned into 22 alignments, 14 recorded divergences and 3 real defects)
- Trend: Stable

## Accumulated Context

### Roadmap Evolution

- Phases 1–10 decomposed into 22 decimal sub-phases (X.1/X.2 pattern; Phase 9 has four) as focused planning/execution units — directories scaffolded under `.planning/phases/`, mappings logged in ROADMAP.md Phase Details and REQUIREMENTS.md Sub-Phase Traceability.
- **Stitch (MCP server) is the designated UI-design tool** (user directive, 2026-09-23): generate and iterate screen mockups through the `stitch` connector (`generate_screen_from_text`, `generate_variants`, `create_design_system`/`upload_design_md`) instead of hand-describing layouts. **Applied for 9.2 (discuss stage):** Stitch project `3852118218307261541` holds design system `assets/9887579562818178405` (seeded from 05 §4 tokens) and **10 screen mockups** (desktop shell light+dark, mobile shell, landing, login, register, forgot-password, onboarding steps 1–3) — screen IDs catalogued in `09.2-CONTEXT.md`. **Planned for 9.3:** 7 more mockups (dashboard desktop+mobile, timeline roadmap, timeline modal, feed desktop+mobile, create post) from the same project/design system, generated as plan 09.3-01's Task 1 with IDs recorded in `09.3-CONTEXT.md`'s design table. Boundary: Stitch output is design reference, not code; implementation stays in `frontend/` against the 9.1 token layer.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 9.3 — D1–D8, planned 2026-09-23]: D1 open anonymous community reads (05 §3.1's public matrix wins over the shipped 401; writes untouched; `community_reads` throttle scope declared ON the view — 7.2 R1; the 401 test updated deliberately with the supersession documented). D2 `feed_queryset` filters `is_deleted=False` and the vacuous tombstone-title test is repaired to assert by id (default feed + `?search=`), keeping the row-retention assertion (08 §390). D3 the vote mutation response carries `has_voted` — the card's field name, one vocabulary — and 409 `already_voted` is handled as already-voted, never as a rollback. D4 write throttling made real: `throttle_scope` on every view that attaches `CommunityWriteRateThrottle` + `throttle_classes` on `PostListCreateView` + a 429 engagement proof and a scope introspection test. D5 §7.7 create post ships in 9.3 (unassigned by the roadmap; the feed's write path). D6 the dashboard's discussions block shows newest posts — §7.4's "in your stream" narrowing is a recorded divergence (a hiring-stream filter would be new feed API surface). D7 the 12-category vocabulary lives in ONE frontend module with a set-pinning test, because `GET /posts/categories/` stays unbuilt (declined; duplication recorded, reclaimed when the endpoint ships). D8 Stitch mockups for all four 9.3 surfaces before implementation (7 screens, same design system as 9.2).

- [Phase 9.1 — D1–D10, executed]: D1 token storage per 06 §3.3 Option 1 (access memory-only, refresh in `localStorage` under `tjt.refresh_token`, logout blacklists then clears); D2 single-flight refresh with one bounded replay (`_replayed` marker, module-level in-flight promise shared by AuthContext boot and the interceptor — concurrent 401s produce exactly ONE refresh POST, proven by test and live); D3 host Vite proxy on :5173 → nginx :80 (no CORS change; `VITE_API_BASE_URL` read only in `client.ts`); D4 production serving left open (base URL env-driven, history mode, fallback need recorded); D5 Tailwind v4 `@theme` tokens byte-exact from 05 §4 with class-strategy dark mode; D6 React 18 + TS strict + npm, no `any`; D7 axios + hooks + Context (no query/UI library); D8 Vitest + RTL via the adapter-swap technique (no mocking dep), CI wiring deferred; D9 bootable shell (router + `RequireAuth`/`PublicOnly` as layout routes + Error Boundary + stubs for every 05 §3.1 path); D10 T9.3 library + Disclaimer/EmptyState/IdentityPill with the three §5.6 strings stored once and pinned by test.

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
- [Phase 8.1 — D1]: `apps/moderation.Report` ships 08 §3.2's schema with a **CASCADE deviation**: target FKs use `on_delete=CASCADE`, not SET_NULL, because SET_NULL would UPDATE a surviving report to (NULL, NULL) on target hard-delete and breach `report_exactly_one_target` at delete time. Pending dedup is double-enforced (service query + two conditional UniqueConstraints); the reports throttle declares `throttle_scope` on the view (7.2 R1) and the 429 is asserted by test.
- [Phase 8.2 — D1/D2]: The ban protocol ships 08 §6's **two-step shape verbatim**: one transaction commits `is_active=False` + `banned_until` + the §11.1 `MODERATION_ACTION_TAKEN` log line, then an idempotent Celery task (`moderation.tasks.sever_banned_user_sessions`, dispatched via `transaction.on_commit` so a rolled-back ban never severs) blacklists every outstanding refresh token and deactivates all devices. Accepted window: a crash between commit and task leaves live sessions until retry — re-banning re-fires the task, and §6.2's 401-on-inactive already closes the API path at the flag. **Unban is one-way**: it reactivates the account but never revives devices or token blacklists (re-registration is the sanctioned path).
- [Phase 8.2 — D3]: Temporary suspensions ship: `User.banned_until` + `duration_days` on the ban request (0/absent = permanent) + a new hourly beat entry `reinstate-suspended-users-hourly` → `moderation.tasks.auto_reinstate_users`, which flips back only `is_active=False AND banned_until <= now`. Permanent bans (banned_until NULL) are never touched by the clock.
- [Phase 8.2 — D4/D5]: Five review actions ship (T8.7/MOD-05 over 04 §69's four): DISMISS → `DISMISSED`; REMOVE_CONTENT / LOCK_POST / WARN_USER / BAN_USER → `RESOLVED`; every path writes `reviewed_by`/`reviewed_at`/`moderator_notes`. The REST review endpoint and both Admin surfaces (`ReportAdmin` bulk actions, `UserAdmin` ban/unban) delegate to the **same** `moderation.services` writers, so they cannot drift; LOCK_POST on a comment-targeted report is a 400 with the status write rolled back.
- [Phase 8.2 — D6]: Queue ordering is 08 §4.1's **static severity weights** (SCAM 100 → OTHER 10) then newest-first, applied in Python over the PENDING page. §4.1's log2 report-velocity multiplier is a recorded divergence.
- [Phase 8.2 — D7]: The announcement system deferred by 6.2 D15 ships whole: `community.Announcement` (§7.1 shape), `publish()` as the single idempotent broadcast trigger (False→True only, never a post_save signal), in-app `ANNOUNCEMENT` rows created **unconditionally** for active verified users while the existing `send_push_notification` preference gate keeps the push opt-in (6.2 D13/D14 semantics), chunked fan-out via `ANNOUNCEMENT_PUSH_CHUNK = 500`, and byte-exact reserved names honoured (`community.tasks.clean_expired_announcements` beat :15, `notifications.tasks.broadcast_announcement` on the notifications queue).
- [Phase 8.2 — D9]: The moderation audit trail is §11.1 **structured logging only** — `log_moderation_action` emits one JSON event (with the keys attached as `extra=` LogRecord fields) per action on the `moderation` logger; no AuditLog model, and §4.2.4's infraction counter and §10's day-90 minimization stay unbuilt (recorded divergences).
- [Phase 8.2 — R1]: **06 §2.6 and 08 §6.2 conflict on suspended logins.** Shipped resolution: 403 `ACCOUNT_SUSPENDED` only after `check_password` proves ownership (a wrong password on a banned account still gets the generic 401), and the pre-existing `test_banned_account_same_body` was updated with the supersession documented in its docstring. Anti-enumeration is preserved because the 403 requires the correct password.
- [Phase 8.2 — R2]: **DRF stores an exception's `code` on the ErrorDetail, not the instance** — `PermissionDenied(msg, code=...)` puts it at `exc.detail.code`; a handler reading `exc.code` silently falls through to DRF's default body. Also: `revoke_user_refresh_tokens` counts tokens *processed*, not newly blacklisted (outstanding rows survive blacklisting), so the sever task reports a `BlacklistedToken` delta to stay honest under re-runs.
- [Phase 8.1 — D2]: The scam scanner **hard-blocks** (400 `scam_pattern_detected` pre-publication) rather than publish+auto-report (CONTEXT D1), on post/comment create AND edit with merged-state scanning (D5); the response names the violation category and never the regex (D2). Patterns are code constants per 08 §8.1 (D7 — deploy-gated tuning accepted); repetition detection deferred (user decision). The T8.5 debounce gains a body hash (D6), posts only, create only. Admin-editable patterns remain a deferred roadmap idea, NOT 8.2 scope.
- [Phase 7.2 — R3]: **Cached analytics have no invalidation on data change.** A payload lives up to `ANALYTICS_CACHE_TTL` (2h) and is refreshed hourly by the warmup, so a manual data fix is not visible publicly until one of those fires. That is the designed trade-off (D-05) rather than a defect, but it is operationally visible: the 7.2 drill had to purge the `analytics:*` namespace before asserting *live* data, having been served the previous run's payload on its first read.
- [Phase 7.1 — R1/R2]: The aggregations are per-bucket ORM walks (one `values("batch").annotate(Count)` then one status-count query per bucket) rather than a single `GROUP BY (bucket, status)`, so each call costs O(buckets) queries; correct and readable at MVP scale, and 7.2's Redis warmup is what makes it cheap. The plan's unused `Avg`/`Max`/`Min`/`Q`/`Decimal` imports were dropped, and `DISCLAIMER_TEXT` was wrapped to satisfy the 100-char E501 limit.

### Pending Todos

- **`/me/`'s `profile_completed` is still a hardcoded `False`** (NEW — surfaced while binding 9.1's client to the real payload). `UserPrivateSerializer.get_profile_completed` returns `False` with a comment saying CandidateProfile arrives in Phase 3.1 — 3.1 shipped and the stub never changed, and `apps/accounts/tests/test_me.py` asserts the stub. **9.2's onboarding wizard gates on this flag**, so every candidate would be sent through onboarding on every sign-in until it reads the real profile. Fix belongs with `/me/` plus a deliberate test update.
- **The private user payload carries no role flag** (NEW — 9.1 planning). `is_staff` appears in no serializer, so the SPA cannot render 05 §3.1's staff-only nav (`/admin/moderation/reports`, `/admin/announcements`) from `/me/`. Either add it to `UserPrivateSerializer` (1 line — needed before 9.2's nav can exist) or keep staff gating purely server-side and reveal no admin affordance. Recorded, not decided.
- **The public author payload exposes no identity mode** (NEW — 9.1 planning). `display_name` collapses to the literal `"Anonymous Candidate"` both for anonymous profiles and for profile-less/blank-name users, so 9.1's `IdentityPill` keys off that sentinel string. An explicit `identity_mode` field in `AuthorPublicSerializer` would remove the coupling if preferred. *(9.1 execution addendum: the serializer also ships NO `avatar_seed` despite 04/plan assuming one — IdentityPill derives the pastel deterministically from `display_name` instead; an `avatar_seed` field is typed optional for when the API adds it.)*
- **Category vocabulary vs the badge table (12 vs 10)** (NEW — 9.1 planning): `POST_CATEGORIES` ships 12 keys while 05 §4.1.4's badge matrix lists 10 — the spec's `OFFER` row is the API's `OFFER_LETTER`, and `LOCATION`/`DOCUMENTS` have no spec badge. 9.1's map covers all 12 with the slate `GENERAL` treatment as the explicit fallback; the spec table is the doc that is out of date.
- **Fix 05.2's two HIGH defects before any Phase 5 COMPLETE claim survives** (surfaced again by the v1.0 milestone summary): `feed_queryset` in `apps/community/views_services.py` never filters `is_deleted=False` (trending does), so deleted posts still appear in the default feed and in `?search=`; `PostListCreateView` declares no `throttle_classes` and there is no `DEFAULT_THROTTLE_CLASSES`, so `POST /api/v1/community/posts/` is unbounded. Both were verified still present in the current tree. Repair `test_deleted_posts_absent_from_feed` too — it asserts on the masked tombstone title, so it is vacuous and passed while the bug was live. Also open from that verification: the feed card's missing `body_preview` (F3) and the vote response's missing `voted` (F4). **→ Claimed by plan 09.3-01 (2026-09-23): F1 = Task 3 (D2), F2 = Task 4 (D4), F4 = Task 3 (D3, shipping the card's `has_voted` spelling); still live in the tree until 9.3 executes.**
- **Wire the account-deletion device revocation** (NEW — found by direct code inspection during the milestone summary, never recorded by any phase): `anonymize_delete_account` (`apps/accounts/services.py`) still carries the literal placeholder `# >>> Phase 6 hook: revoke all FCM device registrations here. <<<`, which 6.2's plan promised to replace with `user.devices.all().delete()`. A deleted account therefore keeps active `Device` rows with live FCM tokens, and the push worker will still attempt delivery to them. Fix alongside F1 (delete the profile + let the timeline cascade) in one atomic transaction.
- **Three UATs closed by attestation — but none of the three phases is verified** (2026-09-22): 6.1, 6.2 and 7.1 recorded 24 `pass` results at the user's instruction with `source: user-attested` and **not one check executed**; each file carries a provenance note naming the attester. These are acceptance decisions, not evidence. All three still need a canonical `VERIFICATION.md`, and the completion predicate cannot even be evaluated in this repo — `gsd_run phase uat-passed 6.1 --require-verification` returns `Error: Phase 6.1 not found` (the project-code resolution failure below). Separately, `workflow.security_enforcement` is on with two active `verify:post` step hooks (`secure-phase` → SECURITY.md, `validate-phase` → VALIDATION.md) and **no phase has ever produced a SECURITY.md**, so the security gate blocks advancement on its own. Do not report 6.1, 6.2 or 7.1 as transitioned.
- **Decide F1's disposition** (VERIFICATION.md 4.2): `anonymize_delete_account` does not delete the CandidateProfile or its timeline events, contrary to 06 §4.2 step 4 / §2.7 "Zero Orphaned PII". Either fix the 2.2 deletion service (delete the profile inside the same transaction; the FK cascade removes events) or record an explicit decision to retain anonymized profiles — then either way exclude them from the dashboard cohort (F2).
- ~~**Decide ANAL-03's true wait-time baseline**~~ — **RESOLVED 2026-09-22 by 7.2 D-13**: both intervals are published as separate metrics (survey→JL per the requirement, offer→JL per D1), each with its own sample size, own `<5` floor and baseline disclosure. ANAL-03 can move off Partial when 7.2 executes; no requirement text needs rewriting.
- Phase 7.2 (next): expose the 7.1 service layer as `GET /api/v1/analytics/overview|batches|hiring-types|regions/` (04 §48-51 shapes already match the service payloads), add `generated_at`, build `GET /api/v1/public/stats/` (04 §80), apply the per-row floor (D-01) and the survey→JL metric (D-13), wrap the helpers in the Redis caching layer with the hourly Celery Beat warmup, and keep every response attributed (`COMMUNITY_REPORTED` + disclaimer). **Context is gathered — plan 07-02 from `07.2-CONTEXT.md`.** Two carry-forward constraints for the planner: 7.2 must **update `test_phase_boundary.py` deliberately** (7.1 D3 asserts the app has no views/urls/tasks), and the route/decorator name must match `config/celery.py`'s reserved `analytics.tasks.warm_analytics_cache` exactly or the `maintenance` route silently does not apply. **04 §52 `/analytics/timeline/` is deferred to backlog by D-10** — it is a recorded gap, not an oversight.
- Phase 5.2 carried decision: 08 §406 renders a deleted post's author as unattributed — the author-nulling rule for deleted posts (and whether a tombstoned comment keeps its handle) is a 5.2 serializer decision.
- **Community's write throttle is inert (NEW — found while wiring 7.2's read throttle, never recorded by any phase):** `apps/community/throttles.py`'s `CommunityWriteRateThrottle` subclasses `ScopedRateThrottle`, but **none of the six community views that attach it declare `throttle_scope`**, and DRF's `ScopedRateThrottle.allow_request` returns `True` (allow) whenever the view declares no scope. So post/comment/vote/lock/pin writes are unthrottled in fact, not merely under-specified — the class being attached looks like protection in review. Fix: add `throttle_scope = "community_writes"` to those views (the `apps/accounts/views.py` pattern, which *does* engage) plus a test asserting the bucket actually 429s; also give `PostListCreateView` its missing `throttle_classes` (05.2 F2). `apps/notifications/throttles.py` is unaffected — it uses `UserRateThrottle`, where the class-level `scope` is authoritative. **→ Claimed by plan 09.3-01 (2026-09-23) as Task 4 (D4), with the engagement proof + scope introspection test; still inert until 9.3 executes.**
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
| ~~Announcements~~ | ~~`Announcement` model, broadcast task, `notify_on_announcements` verification~~ | **DELIVERED 2026-09-23 by 8.2 (plan 08-03)**: `community.Announcement` + publish/broadcast at the reserved route names + hourly expiry task + staff REST CRUD and an anonymous public read; the 6.2 D15 deferral is closed | 2026-09-22 | v1.0 |
| Push frontend | `firebase-messaging-sw.js` + soft-primer UX (T6.12) | Deferred from 6.2 to Phase 9.4 by D16; the payload contract is pinned by tests now | 2026-09-22 | v1.0 |
| Analytics | `GET /api/v1/analytics/timeline/` (04 §52) | Deferred by 7.2 D-10 — no ANAL requirement owns it and §108's required test list omits it; needs an event-level aggregation plus a per-day suppression rule. Recorded as a known gap | 2026-09-22 | v1.0 |
| API docs | OpenAPI/schema generation (04 §109) | Deferred by 7.2 to Phase 10.2 hardening; the project hand-writes endpoint contracts and the analytics phase stays read-only | 2026-09-22 | v1.0 |
| Deleted accounts in public analytics | Exclude anonymized profiles from published cohorts (4.2 F1/F2) | **Accepted, not forgotten** (7.2 D-15): belongs with the retention fix, and the consequence is recorded in Blockers/Concerns | 2026-09-22 | v1.0 |
| Moderation | §4.1's report-velocity multiplier (log2 escalation for multi-reporter targets) | Diverged by 8.2 D6 — static severity weights only; revisit if the queue ever outgrows manual triage | 2026-09-23 | v1.0 |
| Moderation | A queryable audit trail (`AuditLog` model) and §4.2.4's infraction counting | Diverged by 8.2 D9 — §11.1 structured logging only; `Report.reviewed_by/reviewed_at/moderator_notes` is the durable per-report record | 2026-09-23 | v1.0 |
| Moderation | §10's day-90 reporter anonymization / retention minimization | No requirement owns it; needs a beat task and a reporter-nulling rule | 2026-09-23 | v1.0 |
| Moderation | Reactivating devices on unban | Deliberately not built (8.2 D2) — severing is one-way and re-registration is the sanctioned path | 2026-09-23 | v1.0 |
| Moderation | Admin-editable scam patterns (carried from 8.1) | Still needs a roadmap edit before any phase takes it; not folded into 8.2 | 2026-09-23 | v1.0 |
| Feed/dashboard | `GET /community/categories/` endpoint (04's inventory lists it; `settings/base.py:169` claims it ships) | **Declined for 9.3 (D7)**: the 12-key vocabulary is duplicated into one frontend constant module pinned by test; reclaim this row the moment the endpoint is built | 2026-09-23 | v1.0 |
| Dashboard | §7.4's "latest discussions in your stream" hiring-stream filter | **Diverged by 9.3 D6**: the block shows the community's newest posts; a genuine stream filter is new feed API surface (posts carry a category, the stream lives on the author's profile) — buy deliberately later | 2026-09-23 | v1.0 |

## Session Continuity

Last session: 2026-09-24T12:00:00.000Z
Stopped at: Phase 9.3 EXECUTED — all 9 plan tasks done, gates green, both halves of the done-when proven live, tracking updated; run `/gsd-ns-workflow verify 9.3` next (the directive's §4: visually compare the running app against the Stitch screens and append divergences to `09.3-DESIGN-RECONCILIATION.md`)
Resume files: .planning/phases/TCS-JL-09.3-dashboard-timeline-and-feed-views/09.3-DESIGN-RECONCILIATION.md (the design record + what is still open), .planning/phases/TCS-JL-09.3-dashboard-timeline-and-feed-views/09.3-CONTEXT.md, frontend/ (the workspace), .planning/STATE.md

**Owed from 9.3's execution — open items, none silent:**

- **The four surfaces were reconciled from screenshots, not from the exported markup.** The agent can view a
  screen's PNG and read its text, but cannot read the `htmlCode` markup (the MCP returns URLs only; the URL reader
  strips attributes; a cross-origin fetch is refused; the download URL arrives as an attachment). Nine exact-spacing
  details are therefore eyeballed rather than measured; `design-refs/README.md` lists the 7 screen ids and download
  links — dropping those files in closes the gap for a pixel-level pass.
- **Verification has not run.** 9.3 has live proofs recorded above, but no canonical `VERIFICATION.md`; the visual
  side-by-side and the ≤400px/≥1280px breakpoint checks of the *new* content views are still owed.
- **The feed's design gaps stay recorded, not papered over** (`09.3-DESIGN-RECONCILIATION.md`): the `LIVE FEED •
  Updated 2 min ago` eyebrow (no live refresh exists), the notification pill, per-category counts, and the mobile
  pill row's horizontal scroll.
- **A dev-only UAT account now exists in the local database** (`uat93@example.com`, labelled, with a profile and 4
  timeline events) purely to drive the live proofs; it is not seed data and no migration or fixture references it.

**Owed from 9.3's planning (all recorded in the plan, none silently absorbed):** (a) the three planning questions' answers are binding — D1/D2/D3/D4/D5 chosen by the user, D7's categories endpoint explicitly DECLINED (recorded in Deferred Items when 9.3 executes); (b) two vacuous/encoding tests (`test_feed_requires_authentication`, `test_deleted_posts_absent_from_feed`) must be updated deliberately with the fail-on-revert proof, not silently greened; (c) D6's stream-filter divergence and D7's endpoint gap must land in STATE.md Deferred Items at execution, not just in the CONTEXT file; (d) the 7 Stitch screen IDs must replace the CONTEXT design table's "to generate" wording.

**Owed from 9.1's planning (all recorded in the plan, none silently absorbed):** (a) the outer-scope question stays flip-able — 09.1-01 ships the router + `RequireAuth` + Error Boundary + stub pages per D9's default; (b) four cross-phase findings now sit in Pending Todos below (the `profile_completed` stub, the missing `is_staff` in the private payload, the author identity-mode coupling, and the 12-vs-10 category/badge divergence); (c) the production serving model for the built SPA remains unresolved (D4) — whichever wins needs a history-mode fallback or deep links 404.

**Carried from 8.2's verification (small, deliberate, not silently dropped):** O1 — `community.tasks.clean_expired_announcements` has no explicit route, so hourly housekeeping runs on `default` while its peers sit on `maintenance` (harmless and as-planned; one settings line either way). O2 — four of 04 §107's moderation test names are absent but their behavior is covered by differently-named 8.1 tests. O3 — no pytest guard on `ban_user`'s commit→dispatch; the drill covers it live, a mock would put it in CI. O4/O5 are doc-only (CONTEXT's `community.tasks.auto_reinstate_users` typo; the `0005` migration number).

**Still owed elsewhere (unchanged by this session):** 7.1's canonical `VERIFICATION.md` is what unblocks its transition; 6.1/6.2/7.1 UATs remain attestation-only; Phase 5's two HIGH defects and F1's deletion-flow decision are live in the tree.
