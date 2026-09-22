# Requirements: TCS Joining Tracker

**Defined:** 2026-09-19  
**Core Value:** Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication & Account Security (AUTH)

- [ ] **AUTH-01**: User can register with case-insensitive email, password complexity check, and Argon2id hashing.
- [ ] **AUTH-02**: User receives an email verification link (24-hour expiry); resend is rate-limited to 1 req/min.
- [ ] **AUTH-03**: User can request a password reset via email link with 60-minute expiry and session invalidation.
- [ ] **AUTH-04**: User authenticates via SimpleJWT with 15-minute access token and 7-day rotating blacklisted refresh token.
- [ ] **AUTH-05**: User can permanently delete their account with complete anonymization of past community contributions.
- [ ] **AUTH-06**: Login endpoint enforces rate limiting (5/min/IP) and returns generic failure responses to prevent user enumeration.

### Candidate Profile & Identity (PROF)

- [ ] **PROF-01**: Candidate can create and edit profile with batch (2024/2025/2026), stream (Prime/Digital/Ninja), region, and interview center.
- [ ] **PROF-02**: Candidate controls public identity mode: ANONYMOUS (default pseudonym) or custom DISPLAY_NAME.
- [ ] **PROF-03**: Profile enforces controlled status choices from REGISTERED to JOINED.
- [ ] **PROF-04**: Public profile serializers strictly exclude email addresses, phone numbers, and internal authentication identifiers.

### Recruitment Timeline Engine (TIME)

- [ ] **TIME-01**: Candidate can record recruitment milestones (Interview, Selection, Offer, Survey, JL, Date, Joined) with date and notes.
- [ ] **TIME-02**: Adding or updating milestones atomically synchronizes the candidate's current recruitment status.
- [x] **TIME-03**: Timeline endpoints enforce object-level ownership and return HTTP 404 on unauthorized access attempts (IDOR defense).
- [ ] **TIME-04**: Candidate can view an interactive chronological roadmap of their personal milestones with edit/delete controls. *(API half shipped in 4.2 — owners can list/edit/delete their own milestones; the interactive roadmap UI is Phase 9.3)*
- [x] **TIME-05**: Dashboard endpoint aggregates candidate status progression, latest milestone, and community comparison benchmarks.

### Community Discussions & Forum (COMM)

- [x] **COMM-01**: Candidates can browse a paginated community feed filtered by category, search keywords, and sort order (Latest vs Trending). *(5.2: `GET /community/posts/` with category/search filters, tab + whitelist orderings; trending = windowed activity score)*
- [x] **COMM-02**: Candidates can create discussion posts categorized by topic (JOINING_LETTER, OFFER, LOCATION, etc.) with rate limiting (5/hr). *(5.2: `POST /community/posts/` via 5.1's create_post; 30/min `community_writes` bucket — spec's 5/hr read as per-action floor, recorded deviation)*
- [x] **COMM-03**: Candidates can add comments and 1-level replies to discussion posts.
- [x] **COMM-04**: Candidates can upvote/unvote posts with database-level uniqueness enforcement (1 vote per user per post).
- [x] **COMM-05**: Content authors and moderators can soft-delete posts and comments, replacing body text with clean tombstones. *(model layer: flags + tombstone helpers; the delete endpoints are 5.2)*
- [x] **COMM-06**: Moderators can pin announcements and lock controversial threads to disable new comments. *(5.2: staff-only /lock//unlock/ + /pin//unpin/; author cannot lock own thread; locked posts 400 post_locked)*
- [x] **COMM-07**: Posts display public identity handles with deterministic avatars and cohort tags. *(5.2: AuthorPublicSerializer + server-side HMAC avatar_seed (uncomputable by clients); cohort tags via batch/hiring_type/region fields)*
- [x] **COMM-08**: Feed and comment querysets use `select_related()` and `.annotate()` to eliminate N+1 database queries. *(5.2: assertNumQueries budgets — feed ≤3, trending ≤3, thread ≤5 — plus distinct=True counts pinning the 3×2 multiplication trap)*

### In-App & Browser Push Notifications (NOTIF)

- [ ] **NOTIF-01**: Candidates receive in-app notifications with read tracking for comments, replies, upvote milestones, and announcements. *(model layer shipped in 6.1 — `Notification`/`Device`/`NotificationPreference` with read tracking, the `notification_read_state` constraint, compound indexes, and the `unread_count_for` seam; creation and the list/mark-read endpoints arrive in 6.2)*
- [ ] **NOTIF-02**: Candidates can register multiple browser/mobile devices with FCM tokens stored via write-only serializers.
- [ ] **NOTIF-03**: Celery background tasks dispatch FCM push notifications with exponential backoff and zero PII payloads.
- [ ] **NOTIF-04**: System suppresses self-action notifications and applies Redis thread push debouncing (15m window).
- [ ] **NOTIF-05**: Stale/unregistered FCM tokens are automatically marked inactive; inactive devices older than 30 days are pruned daily.
- [ ] **NOTIF-06**: Candidate can manage notification preferences and revoke individual registered devices.

### Community Analytics & Privacy Engine (ANAL)

- [x] **ANAL-01**: Candidates can view aggregated community benchmarks (total tracked, waiting for JL, received JL, joined). *(7.2: `GET /api/v1/analytics/overview/` per 04 §48, plus `GET /api/v1/public/stats/` per 04 §80 for the landing counters — anonymous by 04 §6)*
- [x] **ANAL-02**: Candidates can filter analytics by batch, hiring stream, and region. *(7.2: `?hiring_type=&region=` on `/batches/`, `?batch=&region=` on `/hiring-types/`, `?batch=&hiring_type=` on `/regions/`; whitelist-validated with a 400 that names the parameter, and values normalized so case/whitespace variants share one cache key)*
- [x] **ANAL-03**: System calculates average wait times (in days) between survey submission and joining letter issuance. *(7.1 shipped the engine; **7.2 closes the baseline divergence by publishing both intervals as separate metrics** — `survey_to_joining_letter` (READINESS_SURVEY → JOINING_LETTER, this requirement's literal wording and T7.7's) alongside `offer_to_joining_letter` (7.1 D1's chain). Each carries its own sample size, its own `<5` floor and per-source sample disclosure, exposed through the cached overview payload. Publishing one number would have required redefining either the requirement or the shipped engine.)*
- [x] **ANAL-04**: System strictly suppresses cohort breakdowns with fewer than 5 candidates to protect candidate anonymity. *(7.1 shipped the slice-level rule; **7.2 extends it to every result row** — a below-floor row is dropped entirely (never zeroed or partially revealed) and an all-below-floor response returns the 04 §53 payload. This closes 4.2's residual-risk note about a batch row of 3 inside a large national slice.)*
- [x] **ANAL-05**: All analytics responses are labeled as COMMUNITY_REPORTED and cached in Redis with hourly warmup tasks. *(7.2: `data_source` + non-affiliation disclaimer on every response including through the cache; payload-level caching via Django's cache framework with `ANALYTICS_CACHE_TTL = 7200` as the backstop behind `analytics.tasks.warm_analytics_cache`, which runs hourly on the `maintenance` queue from the beat entry reserved in `config/celery.py`. TTL deliberately deviates from T7.8's `ttl = 15m`, which cannot coexist with an hourly warmup.)*

### Moderation, Safety & Administration (MOD)

- [x] **MOD-01**: Candidates can report objectionable posts or comments selecting from standardized violation reasons. *(8.1: `POST /api/v1/reports/` with 08 §3.1's seven reasons, tombstone-inclusive targets, 04 §63–§65 envelope)*
- [x] **MOD-02**: Database enforces XOR check constraint guaranteeing a report targets either a post or a comment, never both. *(8.1: `report_exactly_one_target` CheckConstraint + mirrored `clean()`; target FKs use CASCADE, a documented deviation from 08 §3.2's SET_NULL, which would breach the constraint on target hard-delete)*
- [x] **MOD-03**: Duplicate pending reports on the same target by the same user are blocked, and reporting is throttled (10/hr). *(8.1: two conditional UniqueConstraints + service check with IntegrityError mapping; `reports` scope with `throttle_scope` on the view per 7.2 R1, 429 asserted)*
- [x] **MOD-04**: Automated regex heuristics scan post bodies for paid job scams, fee extortion, and NextStep password requests. *(8.1: `heuristics.py` with 08 §8.1's four patterns as code constants; hard-block 400 `scam_pattern_detected` pre-publication on all four write call sites — post/comment, create/edit with merged-state scanning — and a category-naming message that never echoes the regex; T8.5's 60-min debounce extended with a body hash, posts only)*
- [ ] **MOD-05**: Moderators can review reports in Django Admin with bulk actions (Dismiss, Soft-Delete, Lock, Warn, Ban).
- [ ] **MOD-06**: Banning an account atomically sets `is_active=False`, blacklists refresh tokens, and halts device push alerts.

### User Interface & PWA Client (UI)

- [ ] **UI-01**: Responsive Single Page Application (React 18 + Tailwind) supporting desktop 3-col, tablet 2-col, and mobile bottom tab bar.
- [ ] **UI-02**: Centralized Axios API client with automatic silent JWT refresh interceptors upon receiving HTTP 401.
- [ ] **UI-03**: Optimistic UI state updates on upvoting with automatic rollback on network failure.
- [ ] **UI-04**: Mandatory TCS non-affiliation disclaimer displayed on all public views, headers, footers, and analytics screens.
- [ ] **UI-05**: PWA service worker registered for background push display, deep-link routing, and offline mode indicators.

## v2 Requirements

Deferred to future post-MVP release.

### Advanced Community
- **COMM-V2-01**: Regional sub-communities with localized chat and batch verification badges.
- **COMM-V2-02**: Verified update system allowing candidates to submit redacted letter screenshots for mod review.
- **COMM-V2-03**: Email digest notifications summarizing weekly joining letter release trends.

### Native Platforms
- **APP-V2-01**: Native Android application via Kotlin / React Native.
- **APP-V2-02**: Native iOS application via Swift / React Native.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Official TCS Scraping | Violates terms of service, poses legal liabilities, and breaks credential safety |
| Private 1-on-1 Chat | Creates unmoderated harassment risks; public forum meets candidate needs safely |
| Microservices | Premature complexity; modular monolith provides superior velocity and data consistency |
| Elasticsearch | Unnecessary infrastructure overhead for MVP scale (~2,000 users); PostgreSQL search suffices |
| Paid Subscriptions | Platform is strictly a free peer-support community tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 2 | Complete — 2.1 model+CITEXT+Argon2id+complexity; 2.2 registration endpoint |
| AUTH-02 | Phase 2 | Complete — 2.2: 24h single-use verification, 1/min resend |
| AUTH-03 | Phase 2 | Complete — 2.2: 60-min reset, hash rotation revokes sessions |
| AUTH-04 | Phase 2 | Complete — 2.2: 15m/7d JWT, rotation + family reuse-revocation |
| AUTH-05 | Phase 2 | Complete — 2.2: anonymizing deletion, row retained as tombstone seam |
| AUTH-06 | Phase 2 | Complete — 2.2: 5/min combined-bucket login throttle, generic failures |
| PROF-01 | Phase 3 | Complete — 3.1: batch/stream/region/center model fields; batch via settings-driven BATCH_YEARS (2024–2026) |
| PROF-02 | Phase 3 | Complete — 3.1: ANONYMOUS default + DISPLAY_NAME mode; resolver never leaks email |
| PROF-03 | Phase 3 | Complete — 3.1: transition machine REGISTERED→JOINED per 03 §6; WITHDRAWN terminal (D1) |
| PROF-04 | Phase 3 | Complete — 3.2: /profile/ CRUD (active+verified gate, 409 duplicates, 405 delete), public /candidates/{id}/ §23 shape, Author/Candidate public serializers, reserved-token blocker |
| TIME-01 | Phase 4 | Complete — 4.1: TimelineEvent model (UUIDv4, 8 event types, CASCADE FK) with date + notes per 03 §7 |
| TIME-02 | Phase 4 | Complete — 4.1: record_timeline_event walks the 3.1 chain atomically (04 §85); forward-only D2 semantics; blocked chains roll back the insert |
| TIME-03 | Phase 4 | Complete — 4.2: every queryset scoped to `request.user` + `IsTimelineOwner` object check; foreign and nonexistent UUIDs return byte-identical 404s (06 §4.2.2, 04 §89) |
| TIME-04 | Phase 4 | Partial — 4.2: owner list/edit/delete endpoints shipped; interactive roadmap UI tracked with 9.3 |
| TIME-05 | Phase 4 | Complete — 4.2: /dashboard/ aggregates completion, current status, latest milestone, and threshold-suppressed COMMUNITY_REPORTED benchmarks; `unread_notifications` placeholder until Phase 6 |
| COMM-01 | Phase 5 | Complete — 5.2: feed with category/search filters, newest/oldest/votes/trending tabs, global pagination |
| COMM-02 | Phase 5 | Complete — 5.2: post create via 5.1 service; community_writes 30/min (spec's 5/hr deviated, recorded) |
| COMM-03 | Phase 5 | Complete — 5.1: Comment model with strict 1-level reply validation (nested_reply / parent_post_mismatch / parent_deleted) on the create_comment path |
| COMM-04 | Phase 5 | Complete — 5.1: unique_user_post_vote UNIQUE constraint on (user, post), verified at the DB level; toggle endpoints in 5.2 |
| COMM-05 | Phase 5 | Complete — 5.1+5.2: flags + tombstone helpers; author DELETE endpoints (soft, originals retained); writes into tombstones 404 content_deleted |
| COMM-06 | Phase 5 | Complete — 5.2: staff-only lock/pin (+unlock/unpin additions); locked posts refuse comments |
| COMM-07 | Phase 5 | Complete — 5.2: AuthorPublicSerializer + HMAC avatar_seed server-side |
| COMM-08 | Phase 5 | Complete — 5.2: query budgets as tests (feed ≤3, thread ≤5); distinct=True counts |
| NOTIF-01 | Phase 6 | Partial — 6.1: model layer (three models, read-state CheckConstraint, compound indexes, unread-count seam); notification creation + list/mark-read endpoints in 6.2 |
| NOTIF-02 | Phase 6 | Pending |
| NOTIF-03 | Phase 6 | Pending |
| NOTIF-04 | Phase 6 | Pending |
| NOTIF-05 | Phase 6 | Pending |
| NOTIF-06 | Phase 6 | Pending |
| ANAL-01 | Phase 7 | Complete — 7.2: `/analytics/overview/`, `/batches/`, `/hiring-types/`, `/regions/` (04 §48–§51) and `/public/stats/` (04 §80), all anonymous per 04 §6, all served through the payload cache |
| ANAL-02 | Phase 7 | Complete — 7.2: documented filter combinations per endpoint, whitelist-validated against the profile model's choices and `BATCH_YEARS` with 400 `invalid_filter`, and normalized so case/whitespace variants share a cache key |
| ANAL-03 | Phase 7 | Complete — 7.2: both baselines published separately (`survey_to_joining_letter` = READINESS_SURVEY→JL satisfying this requirement's literal wording, plus `offer_to_joining_letter` = 7.1 D1's chain), each with its own sample size, `<5` floor and per-source disclosure; surfaced through the cached overview payload |
| ANAL-04 | Phase 7 | Complete — 7.1 shipped slice-level suppression; 7.2 adds the **per-row** floor (below-floor rows dropped entirely, all-below-floor responses suppressed wholesale per 04 §53), with `COMMUNITY_REPORTED` + disclaimer on every payload |
| ANAL-05 | Phase 7 | Complete — 7.2: labeled + cached with the hourly `warm_analytics_cache` warmup; `ANALYTICS_CACHE_TTL = 7200` deviates from T7.8's `ttl = 15m` by design (see 7.2-SUMMARY.md) |
| MOD-01 | Phase 8 | Complete — 8.1: reporting endpoint with the seven standardized reasons (04 §63–§65) |
| MOD-02 | Phase 8 | Complete — 8.1: XOR CheckConstraint at DB level + clean() mirror; CASCADE target FKs documented deviation |
| MOD-04 | Phase 8 | Complete — 8.1: scanner on post/comment create+edit, hard-block pre-publication, code-constant patterns |
| MOD-05 | Phase 8 | Pending |
| MOD-06 | Phase 8 | Pending |
| UI-01 | Phase 9 | Pending |
| UI-02 | Phase 9 | Pending |
| UI-03 | Phase 9 | Pending |
| UI-04 | Phase 9 | Pending |
| UI-05 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 43 total
- Mapped to phases: 43
- Unmapped: 0 ✓

## Sub-Phase Traceability

Phases are decomposed into decimal sub-phases (directories under `.planning/phases/`) as the discuss/plan/execute unit. Phase-level mappings above remain the canonical requirement boundary; this table maps sub-phases to requirements and plans.

| Sub-phase | Requirements | Plans |
|-----------|--------------|-------|
| 1.1 Containerization & Compose Topology | — (infrastructure) | 01-01 |
| 1.2 Django Settings, Health Probes & CI | — (infrastructure) | 01-02, 01-03 |
| 2.1 Custom User Model & Password Hashing | AUTH-01 | 02-01 |
| 2.2 Registration, JWT & Account Lifecycle | AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06 | 02-02, 02-03 |
| 3.1 Candidate Profile Model & Status Machine | PROF-01, PROF-02, PROF-03 | 03-01 |
| 3.2 Profile API & Privacy Boundaries | PROF-04 | 03-02 |
| 4.1 Timeline Model & Atomic Status Sync | TIME-01, TIME-02 | 04-01 — Complete (2026-09-21): TimelineEvent + walk-the-chain sync, 30 tests |
| 4.2 Timeline API, IDOR Defense & Dashboard | TIME-03, TIME-04, TIME-05 | 04-02 — Complete (2026-09-22): timeline CRUD + 404 IDOR defense + dashboard, 81 new tests |
| 5.1 Forum Models & Deletion Semantics | COMM-03, COMM-04, COMM-05 | 05-01 — Complete (2026-09-22): Post/Comment/PostVote + soft-deletion semantics, 56 tests |
| 5.2 Feed, Comments & Voting Endpoints | COMM-01, COMM-02, COMM-06, COMM-07, COMM-08 | 05-02, 05-03 |
| 6.1 Notification & Device Models | NOTIF-01 | 06-01 — Complete (2026-09-22): Notification/Device/NotificationPreference + notification_read_state constraint, 45 new tests |
| 6.2 Device Registration & FCM Push | NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06 | 06-02, 06-03 |
| 7.1 Analytics Aggregation & Privacy Suppression | ANAL-03, ANAL-04 | 07-01 — Complete (2026-09-22): `apps/analytics` service layer (read-only, zero models/migrations) + cohort aggregation, wait-time engine, `<5` suppression, 22 tests + 16/16 live drill |
| 7.2 Analytics Endpoints & Redis Caching | ANAL-01, ANAL-02, ANAL-03, ANAL-05 | 07-02 — Complete (2026-09-22): five anonymous endpoints (04 §48–§51 + §80), payload-level Redis cache with the reserved hourly warmup, per-row `<5` suppression, `analytics_reads` throttle, whitelist filter validation, 32 new tests + 19/19 live HTTP drill checks |
| 8.1 Report Model & Scam Heuristics | MOD-01, MOD-02, MOD-03, MOD-04 | 08-01, 08-02 |
| 8.2 Admin Triage & Ban Workflow | MOD-05, MOD-06 | 08-03 |
| 9.1 SPA Foundation & API Client | UI-01, UI-02 | 09-01 |
| 9.2 Auth, Onboarding & Layout Views | UI-01, UI-04 | 09-02 |
| 9.3 Dashboard, Timeline & Feed Views | UI-03 | 09-03 |
| 9.4 Post, Analytics, Notifications & PWA | UI-05 | 09-04 |
| 10.1 Seed Data & E2E Journeys | Full system verification | 10-01 |
| 10.2 Security Audits, Hardening & Signoff | Full system verification | 10-02 |

Note: UI-01 (responsive SPA) spans sub-phases 9.1–9.4; foundation ownership in 9.1, layout shells in 9.2.

---
*Requirements defined: 2026-09-19*  
*Last updated: 2026-09-22 after 7.2 (analytics endpoints + Redis caching) execution*
