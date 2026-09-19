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
- [ ] **TIME-03**: Timeline endpoints enforce object-level ownership and return HTTP 404 on unauthorized access attempts (IDOR defense).
- [ ] **TIME-04**: Candidate can view an interactive chronological roadmap of their personal milestones with edit/delete controls.
- [ ] **TIME-05**: Dashboard endpoint aggregates candidate status progression, latest milestone, and community comparison benchmarks.

### Community Discussions & Forum (COMM)

- [ ] **COMM-01**: Candidates can browse a paginated community feed filtered by category, search keywords, and sort order (Latest vs Trending).
- [ ] **COMM-02**: Candidates can create discussion posts categorized by topic (JOINING_LETTER, OFFER, LOCATION, etc.) with rate limiting (5/hr).
- [ ] **COMM-03**: Candidates can add comments and 1-level replies to discussion posts.
- [ ] **COMM-04**: Candidates can upvote/unvote posts with database-level uniqueness enforcement (1 vote per user per post).
- [ ] **COMM-05**: Content authors and moderators can soft-delete posts and comments, replacing body text with clean tombstones.
- [ ] **COMM-06**: Moderators can pin announcements and lock controversial threads to disable new comments.
- [ ] **COMM-07**: Posts display public identity handles with deterministic avatars and cohort tags.
- [ ] **COMM-08**: Feed and comment querysets use `select_related()` and `.annotate()` to eliminate N+1 database queries.

### In-App & Browser Push Notifications (NOTIF)

- [ ] **NOTIF-01**: Candidates receive in-app notifications with read tracking for comments, replies, upvote milestones, and announcements.
- [ ] **NOTIF-02**: Candidates can register multiple browser/mobile devices with FCM tokens stored via write-only serializers.
- [ ] **NOTIF-03**: Celery background tasks dispatch FCM push notifications with exponential backoff and zero PII payloads.
- [ ] **NOTIF-04**: System suppresses self-action notifications and applies Redis thread push debouncing (15m window).
- [ ] **NOTIF-05**: Stale/unregistered FCM tokens are automatically marked inactive; inactive devices older than 30 days are pruned daily.
- [ ] **NOTIF-06**: Candidate can manage notification preferences and revoke individual registered devices.

### Community Analytics & Privacy Engine (ANAL)

- [ ] **ANAL-01**: Candidates can view aggregated community benchmarks (total tracked, waiting for JL, received JL, joined).
- [ ] **ANAL-02**: Candidates can filter analytics by batch, hiring stream, and region.
- [ ] **ANAL-03**: System calculates average wait times (in days) between survey submission and joining letter issuance.
- [ ] **ANAL-04**: System strictly suppresses cohort breakdowns with fewer than 5 candidates to protect candidate anonymity.
- [ ] **ANAL-05**: All analytics responses are labeled as COMMUNITY_REPORTED and cached in Redis with hourly warmup tasks.

### Moderation, Safety & Administration (MOD)

- [ ] **MOD-01**: Candidates can report objectionable posts or comments selecting from standardized violation reasons.
- [ ] **MOD-02**: Database enforces XOR check constraint guaranteeing a report targets either a post or a comment, never both.
- [ ] **MOD-03**: Duplicate pending reports on the same target by the same user are blocked, and reporting is throttled (10/hr).
- [ ] **MOD-04**: Automated regex heuristics scan post bodies for paid job scams, fee extortion, and NextStep password requests.
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
| AUTH-01 | Phase 2 | Pending |
| AUTH-02 | Phase 2 | Pending |
| AUTH-03 | Phase 2 | Pending |
| AUTH-04 | Phase 2 | Pending |
| AUTH-05 | Phase 2 | Pending |
| AUTH-06 | Phase 2 | Pending |
| PROF-01 | Phase 3 | Pending |
| PROF-02 | Phase 3 | Pending |
| PROF-03 | Phase 3 | Pending |
| PROF-04 | Phase 3 | Pending |
| TIME-01 | Phase 4 | Pending |
| TIME-02 | Phase 4 | Pending |
| TIME-03 | Phase 4 | Pending |
| TIME-04 | Phase 4 | Pending |
| TIME-05 | Phase 4 | Pending |
| COMM-01 | Phase 5 | Pending |
| COMM-02 | Phase 5 | Pending |
| COMM-03 | Phase 5 | Pending |
| COMM-04 | Phase 5 | Pending |
| COMM-05 | Phase 5 | Pending |
| COMM-06 | Phase 5 | Pending |
| COMM-07 | Phase 5 | Pending |
| COMM-08 | Phase 5 | Pending |
| NOTIF-01 | Phase 6 | Pending |
| NOTIF-02 | Phase 6 | Pending |
| NOTIF-03 | Phase 6 | Pending |
| NOTIF-04 | Phase 6 | Pending |
| NOTIF-05 | Phase 6 | Pending |
| NOTIF-06 | Phase 6 | Pending |
| ANAL-01 | Phase 7 | Pending |
| ANAL-02 | Phase 7 | Pending |
| ANAL-03 | Phase 7 | Pending |
| ANAL-04 | Phase 7 | Pending |
| ANAL-05 | Phase 7 | Pending |
| MOD-01 | Phase 8 | Pending |
| MOD-02 | Phase 8 | Pending |
| MOD-03 | Phase 8 | Pending |
| MOD-04 | Phase 8 | Pending |
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

---
*Requirements defined: 2026-09-19*  
*Last updated: 2026-09-19 after initial GSD specification*
