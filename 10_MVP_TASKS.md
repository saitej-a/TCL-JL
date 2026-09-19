# 10 — MVP Implementation Tasks & Phased Execution Plan

# TCS Joining Tracker — Comprehensive Engineering Task Breakdown

> **Document:** 10_MVP_TASKS.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification & Work Breakdown Structure (WBS)  
> **Target Timeline:** 8 Weeks (10 Phased Iterations)  
> **Execution Model:** Phased, Test-Driven, AI-Agent & Developer Ready  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

All tasks defined in this work breakdown structure must adhere to the following delivery guardrails:
1. **Zero Credential Scraping:** Under no circumstances should any task implement automated credential checkers, NextStep scraping scripts, or tools designed to harvest corporate TCS infrastructure.
2. **Mandatory Non-Affiliation Display:** Every landing view, public header, footer, registration modal, and analytics screen created across these tasks must prominently feature the non-affiliation disclaimer.
3. **Truth in Data Aggregation:** Tasks implementing analytics, dashboards, or charts must explicitly label metrics as **"Community-reported data"** and enforce the **`<5` candidate privacy suppression threshold**.
4. **Strict Anonymity Protection:** Candidate email addresses, phone numbers, password hashes, and FCM tokens must remain strictly quarantined from public serializers and client bundles.

---

# 1. Project Phasing & Roadmap Overview

The MVP is organized into **10 well-defined, sequential phases** that systematically construct the backend services, frontend application, testing suites, and deployment infrastructure.

```
  PHASED ROADMAP OVERVIEW
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ PHASE 1: Project Foundation, Docker & Environment Setup (Week 1)           │
  │ • Docker Compose (Django, PostgreSQL, Redis, Celery, Nginx), Git repo, CI   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 2: Authentication, Identity & Custom User System (Week 1-2)           │
  │ • Custom User model, Argon2id, SimpleJWT, registration, email verify, reset │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 3: Candidate Profiles & Privacy Controls (Week 2)                     │
  │ • CandidateProfile (1:1), status state machine, Anonymous vs Display Name   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 4: Recruitment Timeline Engine (Week 3)                               │
  │ • TimelineEvent CRUD, status auto-sync transactions, ordering, validation   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 5: Community Discussions & Forum System (Week 3-4)                    │
  │ • Posts, 1-level replies, unique upvoting, soft-delete, category taxonomy   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 6: In-App Notifications & FCM Web Push System (Week 5)                │
  │ • Notification model, Device FCM registration, Celery tasks, Service Worker │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 7: Community Analytics & Privacy Engine (Week 5-6)                    │
  │ • Aggregation services, wait-time statistics, <5 candidate suppression      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 8: Moderation, Anti-Spam & Administration (Week 6)                    │
  │ • XOR Report model, scam regex heuristics, Django Admin, user ban workflows │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 9: Frontend Single Page Application (React + Tailwind) (Week 7)       │
  │ • 12 core screens, responsive mobile layout, optimistic UI, Axios client    │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 10: Security Audits, E2E Testing, Seed Data & Launch (Week 8)         │
  │ • Seed scripts, Bandit/Pip-audit scans, Nginx hardening, final sign-off     │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. Phase 1 — Project Foundation, Repository & Docker Topology

**Objective:** Establish a containerized development environment with PostgreSQL, Redis, Celery, and automated linting.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T1.1  │ Repository Initialization & Branch Protection Strategy              │ None         │
  │ T1.2  │ Docker Compose Topology (Backend, DB, Redis, Celery, Nginx)          │ T1.1         │
  │ T1.3  │ Django 5.x Project Initialization & Modular Directory Setup         │ T1.2         │
  │ T1.4  │ PostgreSQL 16 Integration & UUID Extension Configuration            │ T1.3         │
  │ T1.5  │ Redis 7 Integration & Cache/Broker Configuration                    │ T1.4         │
  │ T1.6  │ Celery 5.x Configuration & Beat Scheduler Setup                     │ T1.5         │
  │ T1.7  │ Liveness & Readiness Health Probes (`/health/`, `/health/ready/`)   │ T1.6         │
  │ T1.8  │ CI Pipeline Setup (GitHub Actions: Ruff, Black, Flake8, Pytest)     │ T1.7         │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T1.1:** Initialize Git repository. Configure `.gitignore` to strictly exclude `.env`, `*.pem`, `serviceAccountKey.json`, `media/`, and `node_modules/`. Define branch protection rules (`main` requires PR and passing tests).
- **T1.2:** Write `docker-compose.yml` for local development and `docker-compose.prod.yml` for production containing:
  - `web`: Python 3.11 + Django 5.x
  - `db`: PostgreSQL 16 Alpine with persistent volume `postgres_data`
  - `redis`: Redis 7 Alpine with persistent volume `redis_data`
  - `celery_worker`: Background task worker consuming `default`, `notifications`, `maintenance`
  - `celery_beat`: Cron scheduler for periodic maintenance
  - `nginx`: Reverse proxy with TLS 1.3 and static asset volume
- **T1.3:** Create modular Django structure under `tcs_joining_tracker/` featuring `apps/` subdirectory and split settings (`config/settings/base.py`, `local.py`, `production.py`).
- **T1.4:** Configure Django PostgreSQL connection with `CONN_MAX_AGE = 600`. Enable PostgreSQL `uuid-ossp` and `citext` extensions via initial migration.
- **T1.5:** Configure `django-redis` backend partitioning: `db=0` (Cache/Throttling), `db=1` (Celery broker), `db=2` (Results).
- **T1.6:** Initialize Celery app instance in `config/celery.py`. Verify worker connectivity and tasks auto-discovery.
- **T1.7:** Implement `HealthReadyView` checking live database and Redis ping. Return HTTP 200 on success, HTTP 503 on degraded connectivity.
- **T1.8:** Create `.github/workflows/ci.yml` running linting and pytest test execution on every pull request.

---

# 3. Phase 2 — Authentication, Identity & Custom User System

**Objective:** Implement secure candidate registration, Argon2id hashing, email verification, password reset, and JWT session handling.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T2.1  │ Custom User Model (`accounts.User`) with UUIDv4 Primary Keys        │ Phase 1      │
  │ T2.2  │ Normalized Case-Insensitive Email Field & Indexing                  │ T2.1         │
  │ T2.3  │ Password Hashing Pipeline (Argon2id + PBKDF2-SHA256)                │ T2.2         │
  │ T2.4  │ Registration Endpoint with Password Complexity Validation           │ T2.3         │
  │ T2.5  │ Email Verification Token Generation & Celery Email Dispatcher       │ T2.4         │
  │ T2.6  │ Email Verification Confirm & Resend Endpoints                       │ T2.5         │
  │ T2.7  │ SimpleJWT Authentication, Token Rotation & Blacklist Setup          │ T2.6         │
  │ T2.8  │ Login Endpoint with Generic Failure Responses (Anti-Enumeration)   │ T2.7         │
  │ T2.9  │ Password Reset Request & Confirm Protocol                           │ T2.8         │
  │ T2.10 │ Current User Profile Endpoint (`GET /api/v1/me/`)                   │ T2.9         │
  │ T2.11 │ Account Deletion & Right to Be Forgotten Anonymization Service      │ T2.10        │
  │ T2.12 │ Automated Pytest Suite for Authentication & Token Security          │ T2.11        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T2.1:** Implement custom `User` inheriting `AbstractBaseUser` and `PermissionsMixin`. Set `id = models.UUIDField(primary_key=True, default=uuid.uuid4)`. Exclude `is_staff` and `is_superuser` from user registration serializers.
- **T2.2:** Configure `email` field with `CITEXT` or create functional database index `LOWER(email)`. Normalize emails to lowercase upon registration and login.
- **T2.3:** Add `Argon2PasswordHasher` as primary hasher in `settings.py` with 64MB memory cost, 3 iterations, and 2 threads.
- **T2.4:** Implement `POST /api/v1/auth/register/`. Enforce password complexity (min 10 chars, uppercase, lowercase, digit, special character). Rate limit to 3 registrations/hour/IP.
- **T2.5:** Create `TimestampSigner` token service for email activation (24-hr lifespan). Offload email sending to Celery task `send_verification_email_task`.
- **T2.6:** Implement `POST /api/v1/auth/verification/verify/` and rate-limited `resend/` endpoint (1 req/min). Return generic success on resend.
- **T2.7:** Configure SimpleJWT: 15-minute access token lifespan, 7-day refresh token lifespan, `ROTATE_REFRESH_TOKENS = True`, and `BLACKLIST_AFTER_ROTATION = True`.
- **T2.8:** Implement `POST /api/v1/auth/login/`. Enforce `LoginRateThrottle` (5 attempts/min/IP). Return generic `"Invalid email or password"` on failures.
- **T2.9:** Implement `POST /api/v1/auth/password-reset/request/` and `confirm/`. Use single-use 60-minute cryptographically signed tokens. Blacklist all outstanding user refresh tokens upon password reset.
- **T2.10:** Implement `GET /api/v1/me/` using `UserPrivateSerializer`. Redact password hashes, FCM tokens, and IP addresses.
- **T2.11:** Implement `DELETE /api/v1/account/` executing the data anonymization protocol: revoke FCM devices, blacklist refresh tokens, delete CandidateProfile/TimelineEvents, and anonymize community post authorship.
- **T2.12:** Write unit and integration tests covering registration, token replay detection, brute-force throttling, and account deletion.

---

# 4. Phase 3 — Candidate Profiles & Public Identity Controls

**Objective:** Build candidate recruitment profiles with strict privacy segregation between private identity and public community handles.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T3.1  │ CandidateProfile Model with 1:1 Relationship to User                │ Phase 2      │
  │ T3.2  │ Recruitment Status Choice State Machine & Validations               │ T3.1         │
  │ T3.3  │ Public Identity Mode (`ANONYMOUS` vs `DISPLAY_NAME`) Logic          │ T3.2         │
  │ T3.4  │ Candidate Profile Creation & Validation (`POST /api/v1/profile/`)   │ T3.3         │
  │ T3.5  │ Candidate Profile Read & Update (`GET/PATCH /api/v1/profile/`)      │ T3.4         │
  │ T3.6  │ Serializer Boundary Segregation (Private vs Public Serializers)     │ T3.5         │
  │ T3.7  │ Impersonation Blocker (Prevent "TCS", "HR", "Admin" in names)       │ T3.6         │
  │ T3.8  │ Automated Pytest Suite for Profile CRUD & Identity Masking          │ T3.7         │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T3.1:** Implement `CandidateProfile` in `apps/candidates/models.py` with fields: `user` (OneToOne PK), `display_name`, `public_identity_mode`, `batch` (e.g. 2025), `hiring_type` (Prime/Digital/Ninja/Other), `region`, `interview_center`, `joining_location`, `current_status`.
- **T3.2:** Define controlled status choices: `REGISTERED`, `INTERVIEWED`, `SELECTED`, `OFFER_RECEIVED`, `READINESS_SURVEY`, `WAITING_FOR_JOINING_LETTER`, `JOINING_LETTER_RECEIVED`, `JOINING_DATE_RECEIVED`, `JOINED`, `WITHDRAWN`, `OTHER`. Validate transitions in service layer.
- **T3.3:** Implement `get_public_display_name()` method returning `"Anonymous Candidate"` if mode is `ANONYMOUS`, or the sanitized display name if `DISPLAY_NAME`.
- **T3.4:** Implement `POST /api/v1/profile/` requiring authenticated user. Reject duplicate profile creation for the same user account.
- **T3.5:** Implement `GET /api/v1/profile/` and `PATCH /api/v1/profile/`. Enforce `IsCandidateProfileOwner` permission.
- **T3.6:** Create distinct `CandidatePrivateSerializer` (for profile owner) and `AuthorPublicSerializer` (for community feeds). Strictly exclude email, phone, and internal IDs from public serializers.
- **T3.7:** Implement validator in `display_name` field preventing reserved strings (`"TCS"`, `"Tata"`, `"HR"`, `"Admin"`, `"Official"`, `"Moderator"`).
- **T3.8:** Write automated tests verifying profile uniqueness, status choices, and guaranteed redaction of private attributes in public serializers.

# 5. Phase 4 — Recruitment Timeline Engine

**Objective:** Implement the personal recruitment timeline, milestone event tracking, and atomic status synchronization.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T4.1  │ TimelineEvent Model with UUIDv4 and Controlled Event Types          │ Phase 3      │
  │ T4.2  │ Database Indexes on (candidate, -event_date) and (event_type, date) │ T4.1         │
  │ T4.3  │ Atomic Status Synchronization Service (`record_timeline_event`)     │ T4.2         │
  │ T4.4  │ Timeline Event List & Pagination Endpoint (`GET /api/v1/timeline/`) │ T4.3         │
  │ T4.5  │ Timeline Event Creation Endpoint (`POST /api/v1/timeline/`)         │ T4.4         │
  │ T4.6  │ Timeline Event Update & Delete (`PATCH/DELETE /api/v1/timeline/:id`)│ T4.5         │
  │ T4.7  │ Object-Level Ownership & IDOR Protection (`IsTimelineOwner`)        │ T4.6         │
  │ T4.8  │ Authenticated Candidate Dashboard Endpoint (`GET /dashboard/`)      │ T4.7         │
  │ T4.9  │ Automated Pytest Suite for Timeline Operations & Status Sync        │ T4.8         │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T4.1:** Implement `TimelineEvent` in `apps/timeline/models.py` with fields: `id` (UUIDv4), `candidate` (FK to CandidateProfile), `event_type` (`INTERVIEW`, `SELECTION`, `OFFER_LETTER`, `READINESS_SURVEY`, `JOINING_LETTER`, `JOINING_DATE`, `JOINED`, `OTHER`), `event_date`, `description`, `is_verified`.
- **T4.2:** Create compound indexes: `(candidate, -event_date)` for fast timeline rendering and `(event_type, event_date)` for analytics aggregation.
- **T4.3:** Implement `record_timeline_event` service function wrapped in `@transaction.atomic`. If `auto_update_status=True`, automatically advance `CandidateProfile.current_status` to match the milestone.
- **T4.4:** Implement `GET /api/v1/timeline/` returning paginated chronological events belonging strictly to `request.user.candidate_profile`.
- **T4.5:** Implement `POST /api/v1/timeline/`. Validate date validity (cannot be arbitrarily in the distant future).
- **T4.6:** Implement `PATCH` and `DELETE /api/v1/timeline/{id}/`.
- **T4.7:** Enforce `IsTimelineOwner` permission class. Return `HTTP 404 Not Found` if a user requests or attempts to modify another candidate's timeline event.
- **T4.8:** Implement `GET /api/v1/dashboard/` returning current candidate status, latest timeline event, unread notification count, and community waiting totals.
- **T4.9:** Write automated tests testing status auto-progression, IDOR blocking, and date ordering.

---

# 6. Phase 5 — Community Discussions & Forum System

**Objective:** Build categorized discussion threads, 1-level nested comments, unique post voting, and soft deletion.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T5.1  │ Post Model with Categories, Pinning, Locking & Soft-Deletion Flags  │ Phase 3      │
  │ T5.2  │ Comment Model Supporting Strict 1-Level Nesting (`parent_id`)       │ T5.1         │
  │ T5.3  │ PostVote Model with Unique Constraint `UNIQUE(user, post)`          │ T5.2         │
  │ T5.4  │ Category Listing Endpoint (`GET /api/v1/posts/categories/`)         │ T5.3         │
  │ T5.5  │ Community Post Feed Endpoint with Pagination & Filtering            │ T5.4         │
  │ T5.6  │ Post Search by Title & Body (PostgreSQL Full-Text Search)           │ T5.5         │
  │ T5.7  │ Create Post Endpoint with Rate Limiting (`POST /api/v1/posts/`)     │ T5.6         │
  │ T5.8  │ Post Detail Endpoint with Author Resolution (`GET /posts/{id}/`)    │ T5.7         │
  │ T5.9  │ Post Edit & Soft-Delete (`PATCH/DELETE /api/v1/posts/{id}/`)        │ T5.8         │
  │ T5.10 │ Comment List & Create Endpoint (`GET/POST /posts/{id}/comments/`)   │ T5.9         │
  │ T5.11 │ Upvote Toggle Endpoint (`POST/DELETE /api/v1/posts/{id}/vote/`)     │ T5.10        │
  │ T5.12 │ Lock & Pin Post Endpoints (Staff/Moderator Only)                    │ T5.11        │
  │ T5.13 │ Automated Pytest Suite for Feed, Votes, Comments & Soft Deletion    │ T5.12        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T5.1:** Implement `Post` in `apps/community/models.py` with fields: `id` (UUIDv4), `author` (FK User), `title`, `body`, `category` (`JOINING_LETTER`, `JOINING_DATE`, `OFFER`, `INTERVIEW`, `TCS_PROCESS`, `GENERAL`, `DISCUSSION`, `HELP`, `ANNOUNCEMENT`, `OTHER`), `is_pinned`, `is_locked`, `is_deleted`.
- **T5.2:** Implement `Comment` model with `post` (FK), `author` (FK), `parent` (Self FK, nullable), `body`, `is_deleted`. Enforce validator preventing `parent.parent != None` (strict 1-level replies).
- **T5.3:** Implement `PostVote` model with `user` (FK), `post` (FK). Enforce database-level `UniqueConstraint(fields=['user', 'post'], name='unique_user_post_vote')`.
- **T5.4:** Implement `GET /api/v1/posts/categories/` returning category keys and human-readable labels.
- **T5.5:** Implement `GET /api/v1/posts/` supporting `?category=`, `?ordering=-created_at`, and pagination. Use `select_related('author', 'author__candidate_profile')` and SQL `.annotate()` for vote/comment counts.
- **T5.6:** Integrate PostgreSQL search vectors on `title` and `body` with query debounce support.
- **T5.7:** Implement `POST /api/v1/posts/`. Enforce `PostCreateRateThrottle` (5 posts/hour). Author resolved from `request.user`.
- **T5.8:** Implement `GET /api/v1/posts/{id}/`. If `is_deleted=True`, mask title and body with tombstone copy.
- **T5.9:** Implement `PATCH` and `DELETE /api/v1/posts/{id}/`. Delete sets `is_deleted=True` (soft deletion). Enforce `IsAuthorOrModerator`.
- **T5.10:** Implement `GET` and `POST /api/v1/posts/{id}/comments/`. Creating comments on locked posts returns HTTP 403 `POST_LOCKED`.
- **T5.11:** Implement explicit `POST /posts/{id}/vote/` (add vote) and `DELETE /posts/{id}/vote/` (remove vote). Prevent duplicate voting.
- **T5.12:** Implement moderator endpoints `POST /posts/{id}/lock/` and `pin/` restricted to `is_staff`.
- **T5.13:** Write comprehensive tests for feed pagination, vote count integrity, locked post rejections, and reply depth limits.

---

# 7. Phase 6 — In-App Notifications & FCM Web Push System

**Objective:** Build persistent in-app notifications and real-time browser push alerts using Firebase Cloud Messaging and Celery.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T6.1  │ Notification Model with Read Tracking & Entity Foreign Keys         │ Phase 5      │
  │ T6.2  │ Device Model for Multiple FCM Browser Tokens                        │ T6.1         │
  │ T6.3  │ NotificationPreference Model for Per-User Alert Toggles             │ T6.2         │
  │ T6.4  │ Write-Only Device Registration Endpoint (`POST /api/v1/devices/`)   │ T6.3         │
  │ T6.5  │ List & Revoke Device Endpoints (`GET/DELETE /api/v1/devices/{id}/`) │ T6.4         │
  │ T6.6  │ List In-App Notifications (`GET /api/v1/notifications/`)            │ T6.5         │
  │ T6.7  │ Mark Read & Mark-All-Read Endpoints                                 │ T6.6         │
  │ T6.8  │ Firebase Admin SDK Multicast Service Setup                          │ T6.7         │
  │ T6.9  │ Asynchronous Celery Push Notification Task (`send_push_notification`│ T6.8         │
  │ T6.10 │ Self-Action Suppression & Anti-Storm Redis Debouncing               │ T6.9         │
  │ T6.11 │ Automatic Stale Token Invalidation & Daily Pruning Celery Beat Cron  │ T6.10        │
  │ T6.12 │ Client Service Worker (`firebase-messaging-sw.js`) Background Push  │ T6.11        │
  │ T6.13 │ Automated Pytest Suite for In-App & Mocked Push Delivery            │ T6.12        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T6.1:** Implement `Notification` in `apps/notifications/models.py` with fields: `recipient`, `type` (`COMMENT`, `REPLY`, `VOTE_MILESTONE`, `ANNOUNCEMENT`, `MODERATION`, `TIMELINE_REMINDER`), `title`, `message`, `is_read`, `read_at`, `post` (FK, nullable), `comment` (FK, nullable). Compound index on `(recipient, is_read, -created_at)`.
- **T6.2:** Implement `Device` model with `user` (FK), `fcm_token` (Text, unique), `device_type` (`WEB`, `ANDROID`, `IOS`), `browser`, `is_active`, `last_seen_at`.
- **T6.3:** Implement `NotificationPreference` with booleans for comments, replies, upvote milestones, announcements, and master `push_enabled`.
- **T6.4:** Implement `POST /api/v1/devices/` using `DeviceRegistrationSerializer` with `fcm_token` marked `write_only=True`. Rate limit to 10 requests/hour.
- **T6.5:** Implement `GET /api/v1/devices/` and `DELETE /api/v1/devices/{id}/` allowing candidates to revoke active devices.
- **T6.6:** Implement `GET /api/v1/notifications/` with `?is_read=false` filtering and pagination.
- **T6.7:** Implement `POST /api/v1/notifications/{id}/read/` and `POST /api/v1/notifications/read-all/`.
- **T6.8:** Initialize Firebase Admin Python SDK using service account credentials. Implement `send_fcm_multicast_message` handling up to 500 tokens per batch.
- **T6.9:** Implement `send_push_notification_task` in Celery with exponential backoff (`max_retries=3`). Send zero-PII push banners.
- **T6.10:** Implement self-action check (`if recipient == actor: return`) and Redis push debouncing (`debounce_push_post_{user}_{post}`).
- **T6.11:** Catch `UnregisteredError` from FCM and mark `Device.is_active=False`. Configure Celery Beat cron `prune_stale_devices` to purge inactive devices older than 30 days.
- **T6.12:** Write `public/firebase-messaging-sw.js` handling `onBackgroundMessage` and `notificationclick` deep linking.
- **T6.13:** Write automated tests covering self-action suppression, in-app notifications, write-only device tokens, and mocked Firebase multicast dispatch.

# 8. Phase 7 — Community Analytics & Privacy Engine

**Objective:** Implement cohort-level recruitment analytics, wait-time calculations, and the mandatory `<5` candidate privacy suppression threshold.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T7.1  │ Analytics Aggregation Engine & Service Layer (`analytics/services`) │ Phase 4      │
  │ T7.2  │ Mandatory `<5` Candidate Privacy Suppression Logic Implementation   │ T7.1         │
  │ T7.3  │ Public Overview Analytics Endpoint (`GET /api/v1/analytics/overview/│ T7.2         │
  │ T7.4  │ Analytics by Batch Endpoint (`GET /api/v1/analytics/batches/`)      │ T7.3         │
  │ T7.5  │ Analytics by Hiring Stream (`GET /api/v1/analytics/hiring-types/`)  │ T7.4         │
  │ T7.6  │ Analytics by Region (`GET /api/v1/analytics/regions/`)              │ T7.5         │
  │ T7.7  │ Timeline Progression Wait-Time Benchmarking Service                 │ T7.6         │
  │ T7.8  │ Redis Analytics Caching & Celery Beat Warmup Routine                │ T7.7         │
  │ T7.9  │ Public Landing Stats Endpoint (`GET /api/v1/public/stats/`)         │ T7.8         │
  │ T7.10 │ Automated Pytest Suite for Analytics, Suppression & Performance     │ T7.9         │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T7.1:** Implement aggregation service querying `CandidateProfile` and `TimelineEvent` using Django SQL annotations (`Count`, `Avg`, `Min`, `Max`).
- **T7.2:** Implement `MIN_ANALYTICS_GROUP_SIZE = 5` threshold. If a filtered cohort has fewer than 5 candidates, return `{"suppressed": true, "message": "Not enough community data to display this breakdown."}`.
- **T7.3:** Implement `GET /api/v1/analytics/overview/` returning total tracked candidates, waiting for JL, received JL, and confirmed joining dates. Label provenance as `COMMUNITY_REPORTED`.
- **T7.4:** Implement `GET /api/v1/analytics/batches/` with `?hiring_type=` and `?region=` filtering.
- **T7.5:** Implement `GET /api/v1/analytics/hiring-types/` breaking down Digital, Ninja, Prime distributions.
- **T7.6:** Implement `GET /api/v1/analytics/regions/` with safe regional aggregation.
- **T7.7:** Implement service computing average wait duration (in days) between `READINESS_SURVEY` and `JOINING_LETTER` events.
- **T7.8:** Cache overview and batch statistics in Redis (`ttl = 15m`). Implement Celery Beat warmup task `warm_analytics_cache`.
- **T7.9:** Implement lightweight `GET /api/v1/public/stats/` for unauthenticated landing page KPI counters.
- **T7.10:** Write automated tests testing privacy suppression thresholds, accurate aggregation counts, and zero PII leakage.

---

# 9. Phase 8 — Moderation, Anti-Spam & Administration

**Objective:** Build candidate content reporting, automated scam heuristics, Django Admin moderation tools, and user suspension workflows.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T8.1  │ Report Model with Database-Level XOR Constraint                     │ Phase 5      │
  │ T8.2  │ Candidate Content Reporting Endpoint (`POST /api/v1/reports/`)      │ T8.1         │
  │ T8.3  │ Duplicate Report Prevention & User Throttling (10/hour)             │ T8.2         │
  │ T8.4  │ Automated Scam Regex Heuristics Scanner (`moderation/heuristics.py`)│ T8.3         │
  │ T8.5  │ Duplicate Submission MD5 Debouncing in Redis (60-minute window)     │ T8.4         │
  │ T8.6  │ Announcement Model (`community.Announcement`) with Pinning & Expiry │ T8.5         │
  │ T8.7  │ Admin Moderation Queue Endpoints (`GET/POST /api/v1/moderation/*`)  │ T8.6         │
  │ T8.8  │ User Suspension Protocol (Session severing, JWT blacklist, devices) │ T8.7         │
  │ T8.9  │ Django Admin Customization (`ReportAdmin`, bulk triage actions)     │ T8.8         │
  │ T8.10 │ Announcement CRUD & Push Broadcast Integration                      │ T8.9         │
  │ T8.11 │ Automated Pytest Suite for Reporting, Moderation & Scam Filters     │ T8.10        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T8.1:** Implement `Report` model in `apps/moderation/models.py` with `CheckConstraint(check=(post__isnull=False ^ comment__isnull=False))` enforcing exactly one target.
- **T8.2:** Implement `POST /api/v1/reports/` accepting `post_id` or `comment_id`, `reason` (`SPAM`, `HARASSMENT`, `MISINFORMATION`, `ABUSIVE_CONTENT`, `PERSONAL_INFORMATION`, `SCAM`, `OTHER`), and optional description.
- **T8.3:** Block duplicate reports from the same user while an earlier report is `PENDING`. Attach `ReportRateThrottle` (10/hour).
- **T8.4:** Implement pre-save regex scanner detecting paid Telegram scam links, fee extortion, and NextStep password solicitation.
- **T8.5:** Store MD5 hash of `(author_id + title)` in Redis with a 60-minute TTL to reject rapid duplicate threads.
- **T8.6:** Implement `Announcement` model in `apps/community/models.py` with `title`, `body`, `is_published`, `is_pinned`, `expires_at`.
- **T8.7:** Implement staff endpoints `GET /api/v1/moderation/reports/` and `POST /reports/{id}/review/` supporting `DISMISS`, `REMOVE_CONTENT`, `LOCK_POST`, `WARN_USER`, `BAN_USER`.
- **T8.8:** Implement user ban workflow setting `user.is_active=False`, blacklisting all user refresh tokens, and marking all active devices inactive.
- **T8.9:** Configure Django Admin `ReportAdmin` with bulk actions: "Dismiss reports" and "Resolve and soft-delete content".
- **T8.10:** Implement `broadcast_announcement_task` chunking push delivery across all registered devices.
- **T8.11:** Write automated tests covering XOR constraints, permission boundaries, scam keyword detection, and session severing on user bans.

# 10. Phase 9 — Frontend Single Page Application (React + Tailwind CSS)

**Objective:** Construct the 12 core responsive views, centralized Axios client, optimistic UI mutators, and PWA integration.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T9.1  │ Vite + React 18 + TypeScript + Tailwind CSS Project Setup           │ None         │
  │ T9.2  │ Centralized Axios Client with Silent 401 JWT Refresh Interceptors   │ T9.1         │
  │ T9.3  │ Design System Components (Buttons, Badges, Modals, Toasts, Skeletons│ T9.2         │
  │ T9.4  │ Global Layout Shells (Desktop 3-Col, Tablet 2-Col, Mobile Bottom Tab│ T9.3         │
  │ T9.5  │ Public Landing Screen (`/`) with Live Stats & Non-Affiliation Banner│ T9.4         │
  │ T9.6  │ Authentication Views (`/login`, `/register`, `/verify-email`, reset)│ T9.5         │
  │ T9.7  │ 3-Step Candidate Onboarding Wizard (Profile, Privacy Mode, Timeline)│ T9.6         │
  │ T9.8  │ Authenticated Candidate Dashboard (`/dashboard`) with Stepper Bar   │ T9.7         │
  │ T9.9  │ Interactive Recruitment Timeline View (`/timeline`) with Add Modal  │ T9.8         │
  │ T9.10 │ Community Feed View (`/community`) with Category Tabs & Search      │ T9.9         │
  │ T9.11 │ Post Detail View (`/community/posts/:id`) with 1-Level Comments     │ T9.10        │
  │ T9.12 │ Optimistic Upvoting Component with Automatic Failure Rollback       │ T9.11        │
  │ T9.13 │ Community Analytics Dashboard (`/analytics`) with Privacy Warnings  │ T9.12        │
  │ T9.14 │ Notification Center (`/notifications`) with Read/Unread Filtering   │ T9.13        │
  │ T9.15 │ Profile & Settings Tabs (`/settings`) with FCM Device Revocation    │ T9.14        │
  │ T9.16 │ PWA Service Worker Registration & Soft Push Permission Primer       │ T9.15        │
  │ T9.17 │ Client-Side Form Validation, Error Handling & Empty States          │ T9.16        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T9.1:** Initialize frontend with Vite. Configure Tailwind CSS with slate neutral palette, indigo brand accents, and custom font scale.
- **T9.2:** Implement `src/api/client.ts` with request interceptor attaching Bearer access token and response interceptor silently refreshing tokens on HTTP 401.
- **T9.3:** Build component library: `Button` (Primary, Secondary, Outline, Danger, Loading), `Input`, `Textarea` with character tally, `Badge` with category colors, `Modal`, `Toast`, and `Skeleton` shimmer cards.
- **T9.4:** Implement responsive layout shells: Top navigation bar, Left sidebar (desktop), and 5-slot Mobile Bottom Tab Bar with 44px minimum touch targets.
- **T9.5:** Build Landing Page (`/`) featuring hero value proposition, live counters fetched from `/api/v1/public/stats/`, feature cards, and sticky non-affiliation disclaimer.
- **T9.6:** Build authentication views (`/login`, `/register`, `/verify-email-pending`, `/verify-email/:token`, `/forgot-password`, `/reset-password/:token`).
- **T9.7:** Build 3-step onboarding wizard:
  - Step 1: Batch, Hiring Stream, Region, Interview Center.
  - Step 2: Privacy Mode toggle (`ANONYMOUS` vs `DISPLAY_NAME`).
  - Step 3: Initial recruitment milestone dates.
- **T9.8:** Build Candidate Dashboard (`/dashboard`) featuring milestone progression stepper bar, wait-time benchmark cards, and stream-filtered discussions.
- **T9.9:** Build Timeline Roadmap (`/timeline`) with vertical milestone stepper, inline quick actions, and Add/Edit event modal.
- **T9.10:** Build Community Feed (`/community`) with instant category chips, 300ms debounced search, sorting tabs, and pinned announcements.
- **T9.11:** Build Post Detail screen (`/community/posts/:id`) with post body, author metadata, comment composer, 1-level reply indentation, and locked post alerts.
- **T9.12:** Implement Upvote Pill component with immediate optimistic UI increment and automatic rollback if the API returns an error.
- **T9.13:** Build Analytics view (`/analytics`) rendering KPI cards, stream distributions, wait-time distributions, and `<5` candidate privacy suppression notices.
- **T9.14:** Build Notification Center (`/notifications`) with real-time unread badges, mark-read actions, and deep-link click routing.
- **T9.15:** Build Settings view (`/settings`) across 5 tabs including public identity mode, password update, FCM device list with revocation, and account deletion.
- **T9.16:** Register PWA service worker. Implement two-step soft permission primer modal for push notifications.
- **T9.17:** Verify universal empty states (empty feed, empty timeline, empty notifications) and user-friendly error banners.

---

# 11. Phase 10 — Security Audits, E2E Testing, Seed Data & Launch Readiness

**Objective:** Perform comprehensive security audits, load testing, seed data provisioning, Nginx hardening, and final production sign-off.

```
  ┌───────┬─────────────────────────────────────────────────────────────────────┬──────────────┐
  │ Task  │ Description & Deliverables                                          │ Dependencies │
  ├───────┼─────────────────────────────────────────────────────────────────────┼──────────────┤
  │ T10.1 │ Production Seed Data Generator (`12_SEED_DATA.md` Implementation)   │ Phase 8, 9   │
  │ T10.2 │ End-to-End User Journey Tests (Playwright / Cypress)                │ T10.1        │
  │ T10.3 │ Static Security Analysis (Bandit & Pip-Audit CI Integration)        │ T10.2        │
  │ T10.4 │ Penetration & IDOR Vulnerability Audit                              │ T10.3        │
  │ T10.5 │ Nginx Hardening, TLS 1.3 & HTTP Security Headers Validation         │ T10.4        │
  │ T10.6 │ Load & Stress Testing (Locust / k6: 50 Concurrent Users)           │ T10.5        │
  │ T10.7 │ Database Backup & Disaster Recovery Automation Script               │ T10.6        │
  │ T10.8 │ Final Pre-Launch Verification Checklist & Sign-Off                  │ T10.7        │
  └───────┴─────────────────────────────────────────────────────────────────────┴──────────────┘
```

### Detailed Task Specifications:
- **T10.1:** Implement `python manage.py seed_community_data` generating realistic, sanitized test candidates, timelines, posts, comments, and announcements without real personal data.
- **T10.2:** Write end-to-end integration tests validating:
  - New candidate registration -> Email verification -> Onboarding -> Timeline setup.
  - Post creation -> Upvote toggle -> Peer comment -> Notification receipt.
  - Candidate account deletion -> Community post anonymization.
- **T10.3:** Run Bandit AST scans (`bandit -r apps/ config/`) and Pip-Audit (`pip-audit --strict`). Confirm zero high/medium vulnerabilities.
- **T10.4:** Execute penetration tests targeting IDOR on timeline events, duplicate voting, rate-limit bypassing, and cross-site scripting in post bodies.
- **T10.5:** Validate Nginx configuration: HSTS (`max-age=31536000`), CSP directives, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
- **T10.6:** Run load tests simulating 50 concurrent candidates browsing community feeds, submitting timeline updates, and toggling upvotes. Confirm p95 API response times remain sub-200ms.
- **T10.7:** Create automated PostgreSQL backup script with daily snapshots, 30-day retention, and test restore verification.
- **T10.8:** Complete final sign-off against the Verification Checklist and Definition of Done.

# 12. Cross-Phase Dependency & Traceability Matrix

Every implementation task directly fulfills requirements established in the specification documents:

```
  SPECIFICATION TRACEABILITY MATRIX
  ┌────────────┬─────────────────────────────┬─────────────────────────────────┐
  │ Task Phase │ Primary Driving Document    │ Key Architectural Invariants    │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 1    │ 09_PROJECT_ARCHITECTURE.md  │ Modular Django, Docker Compose  │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 2    │ 06_AUTH_SECURITY.md         │ Argon2id, SimpleJWT, Zero Enum │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 3    │ 03_DATABASE_DESIGN.md       │ CandidateProfile, Anon Identity │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 4    │ 02_USER_FLOWS.md            │ Atomic Timeline & Status Sync   │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 5    │ 04_API_SPECIFICATION.md     │ 1-Level Replies, Unique Votes   │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 6    │ 07_NOTIFICATION_SYSTEM.md   │ Celery Offload, FCM Multicast   │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 7    │ 01_PRODUCT_REQUIREMENTS.md  │ <5 Candidate Privacy Suppress   │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 8    │ 08_MODERATION.md            │ XOR Report, Scam Regex Filter   │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 9    │ 05_UI_UX_SPECIFICATION.md   │ 12 Views, Optimistic Upvotes    │
  ├────────────┼─────────────────────────────┼─────────────────────────────────┤
  │ Phase 10   │ 06_AUTH_SECURITY.md         │ Bandit, Pip-Audit, E2E Testing  │
  └────────────┴─────────────────────────────┴─────────────────────────────────┘
```

---

# 13. Comprehensive Task Verification Checklist & Definition of Done

A task is considered complete and eligible to be marked done only when all of the following conditions are verified:

- [ ] **Working Artifact Delivered:** The deliverable is a working, tested codebase backed by real tool and test output, not a description or stub.
- [ ] **Database Integrity:** Database migrations apply and reverse cleanly without schema errors.
- [ ] **Object-Level Permissions:** Endpoints enforce authenticated ownership and return HTTP 404 on unauthorized access.
- [ ] **Zero PII Exposure:** Public serializers strictly omit email addresses, phone numbers, password hashes, and FCM tokens.
- [ ] **Automated Tests Included:** Every new model, service, view, and task is accompanied by automated pytest unit and integration tests.
- [ ] **Zero N+1 Queries:** Database query counts validated with `django-debug-toolbar` or `django-queries-count`.
- [ ] **Non-Affiliation Compliance:** All UI views and analytics screens render the mandated independent community disclaimer.
- [ ] **Clean Code & Linting:** Code passes Black, Flake8, and TypeScript type checks without warnings.

---

# 14. AI Coding Agent Directives for Task Execution

When an AI coding agent executes any task from this document, it must strictly comply with the following instructions:

1. **Follow the Phased Order:** Never jump to frontend development (Phase 9) before backend data models, services, and APIs (Phases 1-8) are complete and tested.
2. **Never Write Stubs or Mock Success:** Keep working until the code actually executes and passes automated tests. Never substitute plausible-looking fake responses for real execution.
3. **Always Use Absolute Paths:** Construct and use absolute file paths for all filesystem and project operations.
4. **Enforce Atomic Transactions:** Whenever multiple database rows are created or modified (e.g. creating a timeline event and updating candidate status), always wrap the logic in `@transaction.atomic`.
5. **Never Execute Slow Network Calls in Views:** Offload FCM push notifications and verification emails strictly to Celery background workers.
6. **Protect Privacy Invariants:** Never alter serializers to expose user email addresses or FCM tokens in public responses.
7. **Honor the Non-Affiliation Boundary:** Never implement tools or scrapers targeting official TCS NextStep portals or employee networks.
