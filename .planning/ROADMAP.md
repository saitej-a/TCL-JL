# Roadmap: TCS Joining Tracker

## Overview

TCS Joining Tracker is delivered in 10 sequential, test-driven phases that establish the containerized infrastructure, custom user authentication system, candidate profiles, recruitment timeline engine, community discussion forums, asynchronous FCM notifications, aggregate privacy-preserving analytics, administrative moderation workflows, responsive React single-page frontend, and end-to-end launch verification.

## Phases

- [ ] **Phase 1: Project Foundation, Docker & Environment Setup** - Containerized stack (Django, PostgreSQL, Redis, Celery, Nginx), Git repo, and CI gates.
- [ ] **Phase 2: Authentication, Identity & Custom User System** - Custom User model (UUIDv4, case-insensitive email), Argon2id hashing, SimpleJWT rotation, email verification, and password reset.
- [ ] **Phase 3: Candidate Profiles & Public Identity Controls** - 1:1 CandidateProfile model, status choice state machine, ANONYMOUS vs DISPLAY_NAME modes, and serializer boundaries.
- [ ] **Phase 4: Recruitment Timeline Engine** - TimelineEvent model, atomic status synchronization service, IDOR protection, and candidate dashboard endpoint.
- [ ] **Phase 5: Community Discussions & Forum System** - Categorized posts, 1-level nested replies, unique upvoting constraint, soft-deletion handling, and N+1 query elimination.
- [ ] **Phase 6: In-App Notifications & FCM Web Push System** - Notification model, multi-device registration, Celery push tasks with exponential backoff, and background service worker.
- [ ] **Phase 7: Community Analytics & Privacy Engine** - Cohort aggregation engine, wait-time benchmarks, mandatory `<5` candidate privacy suppression, and Redis caching.
- [ ] **Phase 8: Moderation, Anti-Spam & Administration** - XOR report model, automated scam regex heuristics, Django Admin triage tools, and session-severing user ban workflows.
- [ ] **Phase 9: Frontend Single Page Application (React + Tailwind)** - 12 responsive views, centralized Axios client with silent 401 refresh, optimistic upvoting, and PWA integration.
- [ ] **Phase 10: Security Audits, E2E Testing, Seed Data & Launch Readiness** - Realistic synthetic seed data, Bandit/Pip-audit scans, penetration tests, Nginx hardening, and load testing.

## Phase Details

### Phase 1: Project Foundation, Docker & Environment Setup
**Goal**: Establish a unified, containerized local and production development environment with database extensions, health probes, and CI linting.  
**Depends on**: Nothing (first phase)  
**Requirements**: Foundational infrastructure  
**Success Criteria**:
  1. `docker compose up` boots Django, PostgreSQL 16, Redis 7, Celery Worker, Celery Beat, and Nginx cleanly without container exits.
  2. Database migrations enable `uuid-ossp` and `citext` extensions.
  3. Liveness probe (`/health/`) and readiness probe (`/health/ready/`) return HTTP 200 with live DB/Redis connectivity.
  4. CI pipeline passes Black, Flake8, and pytest test runs.
**Plans**: 3 plans  
Plans:
- [ ] 01-01: Git repository initialization, branch rules, and Docker Compose topology (web, db, redis, celery, nginx).
- [ ] 01-02: Django 5.x project initialization with modular split settings and PostgreSQL/Redis connection pooling.
- [ ] 01-03: Health readiness endpoints (`/health/`, `/health/ready/`) and GitHub Actions CI workflow.

### Phase 2: Authentication, Identity & Custom User System
**Goal**: Implement secure candidate registration, password hashing, email verification, password reset, and JWT session handling.  
**Depends on**: Phase 1  
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06  
**Success Criteria**:
  1. User can register with case-insensitive email and receive a 24-hour verification token.
  2. Passwords hashed using Argon2id with 64MB memory cost and PBKDF2 fallback.
  3. SimpleJWT issues 15-minute access tokens and 7-day rotating refresh tokens; replaying rotated tokens revokes the session family.
  4. Account deletion completely anonymizes candidate records while preserving discussion integrity.
**Plans**: 3 plans  
Plans:
- [ ] 02-01: Custom `accounts.User` model with UUIDv4 PK, `CITEXT` email, and Argon2id password hasher configuration.
- [ ] 02-02: Registration, email verification, password reset, and rate-limited login endpoints with anti-enumeration responses.
- [ ] 02-03: SimpleJWT token rotation/blacklisting configuration, current user (`/me/`) endpoint, and account deletion service.

### Phase 3: Candidate Profiles & Public Identity Controls
**Goal**: Build candidate recruitment profiles with strict privacy segregation between private auth credentials and public handles.  
**Depends on**: Phase 2  
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04  
**Success Criteria**:
  1. Candidate can create and edit their profile with batch, stream, region, and interview center.
  2. Public identity mode properly toggles between ANONYMOUS (default) and custom DISPLAY_NAME.
  3. Controlled status choices enforced from REGISTERED to JOINED.
  4. Public serializers strictly omit email, phone, and internal IDs.
**Plans**: 2 plans  
Plans:
- [ ] 03-01: `CandidateProfile` model (1:1 with User), status choices, and public identity toggle logic.
- [ ] 03-02: Profile CRUD endpoints (`/api/v1/profile/`), serializer boundary segregation, and display name impersonation blocking.

### Phase 4: Recruitment Timeline Engine
**Goal**: Implement the personal recruitment timeline, milestone event tracking, and atomic status synchronization.  
**Depends on**: Phase 3  
**Requirements**: TIME-01, TIME-02, TIME-03, TIME-04, TIME-05  
**Success Criteria**:
  1. Candidate can record milestones (Interview, Selection, Offer, Survey, JL, Date, Joined) with date and notes.
  2. Recording a JL event atomically updates the candidate's profile status in the same database transaction.
  3. Timeline queries strictly scope to `request.user` and return HTTP 404 on unauthorized access attempts.
  4. Authenticated dashboard endpoint aggregates status progression, latest milestone, and community comparison benchmarks.
**Plans**: 2 plans  
Plans:
- [ ] 04-01: `TimelineEvent` model, chronological compound indexes, and atomic status synchronization service.
- [ ] 04-02: Timeline CRUD endpoints (`/api/v1/timeline/`), `IsTimelineOwner` IDOR permissions, and candidate dashboard endpoint.

### Phase 5: Community Discussions & Forum System
**Goal**: Build categorized discussion threads, 1-level nested comments, unique post voting, and soft deletion.  
**Depends on**: Phase 3  
**Requirements**: COMM-01, COMM-02, COMM-03, COMM-04, COMM-05, COMM-06, COMM-07, COMM-08  
**Success Criteria**:
  1. Candidates can browse a paginated feed filtered by category, search keywords, and sorting order.
  2. Comment replies are strictly capped at 1-level depth (`parent.parent is None`).
  3. Post upvoting enforces `UNIQUE(user, post)` constraint, preventing duplicate votes.
  4. Soft-deleted content displays clean tombstones without breaking reply hierarchies.
  5. Feed querysets use `select_related()` and `.annotate()` to eliminate N+1 queries.
**Plans**: 3 plans  
Plans:
- [ ] 05-01: `Post`, `Comment`, and `PostVote` models with soft-deletion flags, reply depth validators, and unique vote constraints.
- [ ] 05-02: Feed listing, search, category filtering, post creation (rate-limited), and post detail endpoints.
- [ ] 05-03: Comment listing/creation, upvote toggle endpoints, and staff lock/pin controls.

### Phase 6: In-App Notifications & FCM Web Push System
**Goal**: Build persistent in-app notifications and real-time browser push alerts using Firebase Cloud Messaging and Celery.  
**Depends on**: Phase 5  
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06  
**Success Criteria**:
  1. In-app notifications created for comments, replies, upvote milestones, and announcements with read tracking.
  2. Multi-device FCM token registration stores tokens via write-only serializers.
  3. Celery background tasks dispatch FCM push notifications with exponential backoff and zero PII payloads.
  4. Self-action notifications are suppressed; Redis debounces thread push alerts to 1 per 15 minutes.
  5. Stale tokens are deactivated on `UnregisteredError`; inactive devices older than 30 days are pruned daily.
**Plans**: 3 plans  
Plans:
- [ ] 06-01: `Notification`, `Device`, and `NotificationPreference` models with compound indexes.
- [ ] 06-02: Device registration (write-only token), device revocation, notification list, and mark-read endpoints.
- [ ] 06-03: Firebase Admin SDK integration, Celery push multicast task, self-action suppression, and service worker push handler.

### Phase 7: Community Analytics & Privacy Engine
**Goal**: Implement cohort-level recruitment analytics, wait-time calculations, and the mandatory `<5` candidate privacy suppression threshold.  
**Depends on**: Phase 4  
**Requirements**: ANAL-01, ANAL-02, ANAL-03, ANAL-04, ANAL-05  
**Success Criteria**:
  1. Aggregate metrics calculate wait times, stream breakdowns, and regional distributions from community data.
  2. Cohorts with fewer than 5 candidates trigger the mandatory privacy suppression response.
  3. All analytics responses carry the `COMMUNITY_REPORTED` attribution and non-affiliation disclaimer.
  4. Overview and batch statistics are cached in Redis with hourly Celery Beat warmup routines.
**Plans**: 2 plans  
Plans:
- [ ] 07-01: Analytics aggregation service, wait-time calculation engine, and `<5` candidate privacy suppression threshold.
- [ ] 07-02: Overview, batch, stream, regional analytics endpoints, Redis caching layer, and public landing stats endpoint.

### Phase 8: Moderation, Anti-Spam & Administration
**Goal**: Build candidate content reporting, automated scam heuristics, Django Admin moderation tools, and user suspension workflows.  
**Depends on**: Phase 5  
**Requirements**: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, MOD-06  
**Success Criteria**:
  1. Candidate can report posts or comments with database-level XOR constraint enforcing exactly one target.
  2. Duplicate pending reports on the same target are blocked; report creation is throttled to 10/hour.
  3. Automated regex heuristics intercept paid job scams, fee extortion, and NextStep password requests.
  4. Banning an account atomically sets `is_active=False`, blacklists refresh tokens, and halts device push alerts.
  5. Staff can triage reports and soft-delete content directly in Django Admin.
**Plans**: 3 plans  
Plans:
- [ ] 08-01: `Report` model with database XOR check constraint, reporting endpoint, and pending deduplication.
- [ ] 08-02: Automated scam regex heuristics scanner and 60-minute duplicate post debouncing in Redis.
- [ ] 08-03: Django Admin `ReportAdmin` customization, announcement model/broadcast task, and user suspension protocol.

### Phase 9: Frontend Single Page Application (React + Tailwind)
**Goal**: Construct the 12 core responsive views, centralized Axios client, optimistic UI mutators, and PWA integration.  
**Depends on**: Phase 8  
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05  
**Success Criteria**:
  1. 12 responsive views render cleanly across desktop (3-col), tablet (2-col), and mobile (5-slot bottom tab bar with 44px touch targets).
  2. Centralized Axios client automatically performs silent JWT refresh on HTTP 401 and replays requests.
  3. Upvote pill component updates optimistically with automatic rollback on network failure.
  4. Mandatory TCS non-affiliation disclaimer appears across all public headers, footers, and analytics views.
  5. Service worker displays background push notifications and deep-links on click.
**Plans**: 4 plans  
Plans:
- [ ] 09-01: Vite + React 18 + TypeScript + Tailwind setup, design system tokens, and centralized Axios client with 401 interceptors.
- [ ] 09-02: Responsive layout shells, landing screen with live stats, authentication views, and 3-step onboarding wizard.
- [ ] 09-03: Candidate dashboard with stepper bar, interactive timeline roadmap, and community feed with category tabs.
- [ ] 09-04: Post detail with 1-level comments, analytics dashboard with privacy callouts, notification center, and PWA service worker.

### Phase 10: Security Audits, E2E Testing, Seed Data & Launch Readiness
**Goal**: Perform comprehensive security audits, load testing, seed data provisioning, Nginx hardening, and final production sign-off.  
**Depends on**: Phase 9  
**Requirements**: Full system verification  
**Success Criteria**:
  1. Synthetic seed data generator populates 50 realistic candidates, 220+ timeline events, 25 posts, and 8 moderation cases.
  2. Bandit AST scans and Pip-Audit vulnerability checks report zero high/medium security issues.
  3. Automated penetration tests confirm IDOR protection on timeline events and zero duplicate voting leaks.
  4. Nginx security headers (HSTS 1 year, CSP, X-Frame-Options DENY) validated.
  5. 50-concurrent-user load tests confirm sub-200ms p95 API response times.
**Plans**: 2 plans  
Plans:
- [ ] 10-01: Synthetic seed data management command (`seed_community_data.py`) and Playwright/Cypress end-to-end user journey tests.
- [ ] 10-02: Security audits (Bandit, Pip-Audit, IDOR penetration), Nginx TLS hardening, load testing, and production launch sign-off.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Foundation, Docker & Environment Setup | 0/3 | Not started | - |
| 2. Authentication, Identity & Custom User System | 0/3 | Not started | - |
| 3. Candidate Profiles & Public Identity Controls | 0/2 | Not started | - |
| 4. Recruitment Timeline Engine | 0/2 | Not started | - |
| 5. Community Discussions & Forum System | 0/3 | Not started | - |
| 6. In-App Notifications & FCM Web Push System | 0/3 | Not started | - |
| 7. Community Analytics & Privacy Engine | 0/2 | Not started | - |
| 8. Moderation, Anti-Spam & Administration | 0/3 | Not started | - |
| 9. Frontend Single Page Application (React + Tailwind) | 0/4 | Not started | - |
| 10. Security Audits, E2E Testing, Seed Data & Launch Readiness | 0/2 | Not started | - |
