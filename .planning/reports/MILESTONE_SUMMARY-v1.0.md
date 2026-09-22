# Milestone v1.0 — Project Summary

**Generated:** 2026-09-22
**Purpose:** Team onboarding and project review
**Milestone status:** ⚠️ **In progress** — 13 of 22 sub-phases have executed, 9 have not started. There is no `v1.0` git tag and no archive, so this document reads from the live `.planning/` working set.

---

## 1. Project Overview

**What this is.** TCS Joining Tracker is an independent, community-driven web application for candidates waiting on Tata Consultancy Services joining letters, onboarding dates and recruitment updates. It gives each candidate a private milestone tracker, a public community forum, privacy-preserving aggregate analytics, and browser push notifications.

**Core value.** *Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.*

**Who it is for.** TCS candidates across India in the Prime, Digital and Ninja streams, most of them sitting in the 45–120+ day silence after their recruitment rounds. The problem it replaces is scattered, unsearchable WhatsApp/Telegram rumor groups.

**Business context.** Free, non-commercial, explicitly unaffiliated with TCS. Success is framed as 2,000+ registered candidates, sub-200ms API responses, zero public PII, and a community that verifies real joining trends.

**Where the build stands today.** The entire backend is live and green (606 tests): authentication, candidate profiles, the timeline engine, the forum, notifications with FCM push, and — as of today — the analytics aggregation service. What is **not** built: the analytics HTTP endpoints (7.2), moderation and admin (Phase 8), the entire React frontend (Phase 9), and launch hardening (Phase 10). Three executed sub-phases (6.1, 6.2, 7.1) have no independent verification report, and Phase 5 carries two unresolved HIGH defects while its tracking rows read "Complete" (Section 6).

---

## 2. Architecture & Technical Decisions

The system is a **modular Django monolith** — deliberately not microservices, so profile and timeline writes stay inside one ACID transaction.

- **Modular Django monolith** — avoids distributed-systems overhead and guarantees transactional consistency across profile + timeline.
  - **Why:** the timeline engine's core invariant (recording a milestone advances candidate status atomically) cannot be safely split across services.
  - **Phase:** 1.1 / PROJECT.md
- **Celery + Redis for anything third-party** — FCM push and transactional email never sit in the request cycle.
  - **Why:** Google FCM latency must not become the candidate's page-load latency.
  - **Phase:** 1.2, realised in 6.2
- **PostgreSQL 16 + `citext` + `uuid-ossp`** — case-insensitive email uniqueness enforced in the database, UUIDv4 primary keys everywhere.
  - **Phase:** 2.1
- **Argon2id + SimpleJWT with rotation and family reuse-revocation** — 15-minute access tokens, 7-day rotating refresh, a reused refresh token revokes its whole family.
  - **Phase:** 2.2
- **Event-sourced timeline, not date columns** — `TimelineEvent` with 8 milestone types, and status derived by walking a legal transition chain rather than being set directly.
  - **Why:** milestones stay extensible without migrations, and status can never drift from the events that justify it.
  - **Phase:** 4.1
- **Soft deletion for all community content; hard deletion refused** — a neutral tombstone copy covers author- and moderator-deletion alike, because one `is_deleted` flag cannot distinguish them.
  - **Phase:** 5.1
- **Integrity guarantees deliberately split by layer** — duplicate votes are impossible at the database level (`unique_user_post_vote`); the 1-level reply rule is application-level because PostgreSQL cannot express a cross-row `CHECK`.
  - **Phase:** 5.1
- **`CheckConstraint` for invariant-bearing state** — `notification_read_state` (`CHECK (NOT is_read OR read_at IS NOT NULL)`) is the project's first DB-level invariant, mirrored in `clean()` and written only through one sanctioned pair-writer.
  - **Phase:** 6.1
- **`PushBackend` seam with a credential-free recording backend** — the real Firebase adapter ships, but tests and dev never call FCM.
  - **Phase:** 6.2
- **Zero-PII push payloads by construction** — lock-screen text comes from per-type generic templates, so no comment body or display name can ever reach a notification.
  - **Phase:** 6.2
- **Read-only service app for analytics** — `apps/analytics` ships no models, no migrations, no views, no tasks; the boundary is enforced by a test, not by convention, so Phase 7.2 has to add its endpoint deliberately.
  - **Phase:** 7.1
- **Full-cohort privacy suppression** — below the configured floor the response is metadata only; the payload carries no counts, no zeroed buckets and no partial rows, so a small cohort cannot be inferred from an empty one.
  - **Phase:** 7.1 (rule), 4.2 (first use, dashboard benchmark)
- **React 18 + Tailwind + Vite SPA, generated from `05_UI_UX_SPECIFICATION.md`** — chosen for optimistic UI, a native-feeling mobile bottom tab bar and PWA support.
  - **Phase:** 1.1 (decision), 9.1–9.4 (build, not started). Stitch mockups deliberately deferred by the user on 2026-09-21 until 9.1 opens.

**Stack as pinned:** Django 5.2.6, DRF 3.16.1, PostgreSQL 16 (Docker `postgres:16.15-alpine`), Redis 7.4, Celery 5.5.3, gunicorn, `firebase-admin==7.6.0` (the only new runtime dependency since Phase 1). Python 3.11. Lint/format is ruff-only, `line-length = 100`, `.planning/` excluded.

---

## 3. Phases Delivered

Sub-phases are the execution unit; parent phases (1–10) remain the requirement boundary.

| Sub-phase | Name | Status | One-liner |
|---|---|---|---|
| 1.1 | Containerization & Compose Topology | ✅ Executed | Repo hygiene, shared Dockerfile, 6-service Compose topology (web, db, redis, celery worker, celery beat, nginx). |
| 1.2 | Django Settings, Health Probes & CI | ✅ Executed | Split settings, Postgres/Redis wiring, `/health/` + `/health/ready/`, GitHub Actions CI (ruff + pytest). |
| 2.1 | Custom User Model & Password Hashing | ✅ Executed | UUIDv4 user on `citext` email with Argon2id and complexity validation. |
| 2.2 | Registration, JWT & Account Lifecycle | ✅ Executed | Registration, 24h email verification, password reset, JWT rotation with family revocation, anonymizing deletion. |
| 3.1 | Candidate Profile Model & Status Machine | ✅ Executed | `CandidateProfile` with batch/stream/region/center, ANONYMOUS-or-DISPLAY_NAME identity, and the REGISTERED→JOINED transition machine. |
| 3.2 | Profile API & Privacy Boundaries | ✅ Executed | `/profile/` CRUD, public `/candidates/{id}/` shape, reserved-token blocking, serializer redaction. |
| 4.1 | Timeline Model & Atomic Status Sync | ✅ Executed | `TimelineEvent` (8 types) plus the walk-the-chain atomic status sync; blocked chains roll the insert back. |
| 4.2 | Timeline API, IDOR Defense & Dashboard | ✅ Executed · **verified PASS** | Timeline CRUD, byte-identical 404 IDOR defense, `/dashboard/` with suppressed `COMMUNITY_REPORTED` benchmarks. |
| 5.1 | Forum Models & Deletion Semantics | ✅ Executed | `Post`/`Comment`/`PostVote` with soft deletion, tombstone masking and the unique-vote constraint. |
| 5.2 | Feed, Comments & Voting Endpoints | ⚠️ **Executed · verified FAIL** | Feed/comments/votes/lock-pin endpoints — mechanically complete, but 2 HIGH defects live (Section 6). |
| 6.1 | Notification & Device Models | ✅ Executed · unverified | `Notification`/`Device`/`NotificationPreference`, the read-state `CheckConstraint`, compound indexes, unread-count seam. UAT paused at 1/7. |
| 6.2 | Device Registration & FCM Push | ✅ Executed · unverified | Device + notification + preferences APIs, Celery FCM worker with debounce and stale-token pruning, zero-PII templates, producer hooks. |
| 7.1 | Analytics Aggregation & Privacy Suppression | ✅ Executed today · unverified | Read-only analytics service: cohort aggregations, wait-time engine with fallback chain, mandatory `<5` suppression. UAT awaiting test 1. |
| 7.2 | Analytics Endpoints & Redis Caching | ⬜ Not started | Overview/batch/stream/region endpoints, `COMMUNITY_REPORTED` labeling, Redis caching with hourly Celery Beat warmup. |
| 8.1 | Report Model & Scam Heuristics | ⬜ Not started | XOR report target constraint, duplicate/throttle rules, scam regex interception. |
| 8.2 | Admin Triage & Ban Workflow | ⬜ Not started | Admin moderation queue and session-severing bans. |
| 9.1 | SPA Foundation & API Client | ⬜ Not started | Vite/React/Tailwind foundation, centralized Axios client with silent 401 refresh. |
| 9.2 | Auth, Onboarding & Layout Views | ⬜ Not started | Auth and onboarding views, responsive layout shells, mandatory disclaimer. |
| 9.3 | Dashboard, Timeline & Feed Views | ⬜ Not started | Dashboard, timeline roadmap UI, feed views (absorbs TIME-04's UI half). |
| 9.4 | Post, Analytics, Notifications & PWA | ⬜ Not started | Post detail, analytics dashboard with privacy callouts, notification center, service worker. |
| 10.1 | Seed Data & E2E Journeys | ⬜ Not started | Realistic synthetic seed data and end-to-end journey tests. |
| 10.2 | Security Audits, Hardening & Signoff | ⬜ Not started | Bandit/pip-audit, IDOR penetration tests, Nginx hardening, load test, launch sign-off. |

**Coverage:** 13 executed / 22 total. Of those 13, exactly **one** (4.2) has an independent verification report passing; **one** (5.2) has one that fails; three (6.1, 6.2, 7.1) have none yet; and 1.1–5.1 have none.

---

## 4. Requirements Coverage

From `.planning/REQUIREMENTS.md` (43 requirements), with corrections where the repo's own verification contradicts the recorded status.

**✅ Complete (25)**
- `AUTH-01`–`AUTH-06` — registration, verification, reset, JWT rotation, anonymizing deletion, login throttling.
- `PROF-01`–`PROF-04` — profile model, identity modes, status machine, profile API and public surface.
- `TIME-01`, `TIME-02`, `TIME-03`, `TIME-05` — timeline model, atomic sync, IDOR defense, dashboard.
- `COMM-03`, `COMM-04`, `COMM-05` — comment model + reply depth, unique voting, deletion semantics.
- `COMM-06`, `COMM-07`, `COMM-08` — staff lock/pin, public handles + deterministic avatars, N+1 discipline.

**⚠️ Partial (5)**
- `TIME-04` — timeline API complete; the interactive roadmap UI is deferred to 9.3.
- `NOTIF-01` — model layer only; the read/list endpoints that make a notification receivable ship in 6.2's work.
- `ANAL-03` — wait-time engine shipped in 7.1, but its literal "survey submission" baseline is not what the locked D1 chain implements (Section 6), and no endpoint exposes it yet.
- `COMM-01`, `COMM-02` — **recorded as Complete, actually deficient**: `COMM-02`'s rate-limited post creation is not rate-limited at all, and `COMM-01` inherits `COMM-02`'s feed defects (Section 6). These rows should read Partial or Fail.
- `NOTIF-02`–`NOTIF-06` — **recorded as Pending, actually shipped**: 6.2 shipped device registration, push dispatch, suppression/debounce, stale-token pruning and preferences, and its own SUMMARY claims them complete. The tracking rows were simply never updated, because 6.2's closing docs were never committed.

**✅ Complete at the service layer (1)**
- `ANAL-04` — the `<5` suppression rule is fully enforced across all four aggregations and the wait-time sample; only endpoint exposure is pending in 7.2.

**❌ Not started (12)**
- `ANAL-01`, `ANAL-02`, `ANAL-05` (7.2), `MOD-01`–`MOD-06` (Phase 8), `UI-01`–`UI-05` (Phase 9).

**No `MILESTONE-AUDIT.md` exists** — no milestone has been audited, and `RETROSPECTIVE.md` has never been written. `PROJECT.md`'s own requirement list is stale (last updated 2026-09-21 after Phase 2.2): it still shows every requirement unchecked and uses an older ID mapping (its `ANAL-02` is the suppression rule, which is `ANAL-04` in REQUIREMENTS.md).

---

## 5. Key Decisions Log

Aggregated from the per-phase CONTEXT files and STATE.md. The full text lives in STATE.md's `Accumulated Context`; these are the ones that constrain future work.

| # | Decision | Why it was made | Phase |
|---|---|---|---|
| D1 | Modular monolith over microservices | ACID across profile + timeline; velocity | 1.1 |
| D2 | Celery + Redis for FCM/email | Third-party latency out of the request cycle | 1.2 |
| D3 | Post categories are a merged union of three disagreeing spec lists, held in `POST_CATEGORIES` and read at call time | Keeps the API vocabulary aligned with `TimelineEvent` and lets the list extend without a migration | 5.1 |
| D4 | `Post.author`/`Comment.author` are required `PROTECT`; deletion anonymizes the User row and that row is the tombstone | No NULL-author branch anywhere; a hard user delete is refused | 5.1 |
| D5 | Deleted posts leave the feed; tombstoned comments stay in their threads; `Comment.parent` is `SET_NULL` | A disappearing parent must promote a reply, not destroy it | 5.1 — **the feed-exclusion half is NOT enforced in code (Section 6)** |
| D6 | One neutral tombstone string for author- and moderator-deletion | A single `is_deleted` flag cannot distinguish them | 5.1 |
| D7 | The 7 notification types are a model `TextChoices`, not a settings list | The values drive code dispatch; a settings-added type would reach the dispatcher with no handler | 6.1 |
| D8 | `notification_read_state` is one-directional and `mark_as_read()` is the only sanctioned pair-writer | Makes "read without a timestamp" unrepresentable | 6.1 |
| D9 | `Notification.objects.unread_count_for(user)` is the dashboard seam | Replaces the 4.2 `0` placeholder without a model change | 6.1 → wired in 6.2 |
| D10 | `firebase-admin` behind a `PushBackend` seam, verified credential-free | Keeps live FCM out of tests and dev | 6.2 |
| D11 | Thread pushes are debounced via the cache framework and *suppressed*, not queued; `VOTE_MILESTONE` exempt | One alert per 15 minutes per thread without dropping the in-app row | 6.2 |
| D12 | A token bound to another user is reassigned last-writer-wins; revoke is a soft deactivate | Shared/reinstalled browsers recover without token leakage | 6.2 |
| D13 | Wait-time baseline is the OFFER_LETTER event, then INTERVIEW, then profile dates; endpoint is JOINING_LETTER; negative intervals are dropped, never clamped | The offer letter is the milestone the community actually reports; clamping corrupted data would invent a plausible wait time | 7.1 |
| D14 | Suppression is full-cohort on the filtered slice: metadata only, never zeroed or partial rows | A zeroed bucket still discloses that the bucket exists | 7.1 |
| D15 | `apps/analytics` is read-only and enforced by test | 7.2 cannot grow an endpoint or a cache without failing the boundary test deliberately | 7.1 |

---

## 6. Tech Debt & Deferred Items

This is the section to read before trusting any "Complete" label.

### 🔴 Live defects that contradict recorded status

1. **Phase 5.2 was verified FAIL and is still marked Complete.** `VERIFICATION.md` for 05-02 records two HIGH acceptance-criteria defects, both **confirmed still present in the current tree**:
   - **F1 — soft-deleted posts remain in the default feed and in `?search=`.** `feed_queryset` (`apps/community/views_services.py`) never applies `is_deleted=False` (the trending queryset does). Deleted posts render as tombstone cards in the listing, violating 5.1 D5 / 03 §28 / P9. Guarded only by a **vacuous test** — `test_deleted_posts_absent_from_feed` asserts on the masked title (`"This content has been removed."`), which can never appear, so it passes with or without the bug.
   - **F2 — `POST /api/v1/community/posts/` is unthrottled.** `PostListCreateView` declares no `throttle_classes` and there is no `DEFAULT_THROTTLE_CLASSES` in `REST_FRAMEWORK`, so post creation is unbounded — the exact endpoint COMM-02 names. Every *other* community write is throttled.
   - Also still open from that verification: **F3** the feed card returns the full `body` instead of a `body_preview` (04 §30 shows the full body on both list and detail), and **F4** the vote response omits `voted`, so a client cannot read toggle state.
   - **And the finding was dropped:** 05.2's FAIL findings do not appear in STATE.md's Pending Todos any more. Later phases overwrote that section without carrying them forward, so the repo now claims Phase 5 COMPLETE in STATE.md, REQUIREMENTS.md (`COMM-01`/`COMM-02` = Complete) and ROADMAP.md (05-02/05-03 ticked, Phase 5 = 3/3).

2. **F1 from 4.2 (HIGH, pre-existing in 2.2) — account deletion retains candidate data.** `anonymize_delete_account` (`apps/accounts/services.py`) anonymizes the `User` row and stops: the `CandidateProfile` (with `display_name`, `batch`, `region`, `current_status`) and its private timeline events survive, contrary to 06 §4.2 step 4 and §2.7 "Zero Orphaned PII". Still live, still undecided. Three consequences now: private milestone history is retained indefinitely, the public `/candidates/{id}/` surface can still serve a deleted candidate's chosen name, and **every analytics cohort counts them** — Phase 7.1's aggregations read `CandidateProfile` directly, so this now inflates the numbers the public analytics API will serve.

3. **NEW (found while generating this summary) — the deletion flow's device-revocation hook was never wired.** `anonymize_delete_account` still carries the literal placeholder `# >>> Phase 6 hook: revoke all FCM device registrations here. <<<`, and no phase ever replaced it. 6.2's plan promised `user.devices.all().delete()` there. A deleted (anonymized) account therefore keeps active `Device` rows with live FCM tokens, so the push worker will still attempt delivery to a user who has exercised deletion.

### 🟡 Open design questions carried into the next phases

4. **ANAL-03's baseline disagrees with the code (7.1).** The requirement says "average wait times between *survey submission* and joining letter issuance"; the locked D1 chain starts at the offer letter and never reads a `READINESS_SURVEY` event. One of the two must move before verification time.
5. **Suppression is per-slice, not per result row (7.1).** A large slice can still emit a bucket row reporting 3 candidates — the differential-inference vector 4.2's residual-risk note named. 4.2 explicitly asked for a floor **per bucket**; either implement it in 7.2 or record that coarse batch/stream/region buckets make it unnecessary.
6. **Phase 1's ROADMAP progress row and the whole Progress table are stale** (Phase 1 shows 0/3 despite executing; Phase 5 shows 1/3 despite 3 plans; Phase 6 shows 0/3 despite 6 plans). STATE.md's own `completed_phases: 5` is likewise behind its own narrative text.

### 🟢 Deferred by explicit decision

| Category | Item | Status | Deferred at |
|---|---|---|---|
| Timeline UI | `TIME-04`'s interactive roadmap with edit/delete controls | UI half deferred to 9.3; API half shipped in 4.2 | 2026-09-22 |
| Announcements | `Announcement` model, broadcast task, preference verification | Deferred from 6.2 to Phase 8 (T8.6); route stays inert | 2026-09-22 |
| Push frontend | `firebase-messaging-sw.js` + soft-primer UX | Deferred from 6.2 to 9.4; payload contract pinned by tests | 2026-09-22 |
| Stitch design | MCP-generated UI mockups | Deliberately untouched until 9.1; generate from `05_UI_UX_SPECIFICATION.md` | 2026-09-21 |
| Analytics depth | `/api/v1/analytics/*` endpoints + Redis caching | Service layer shipped in 7.1; endpoints carried to 7.2 | 2026-09-22 |
| Low-severity polish | Shared JSON 404 for unresolvable paths (4.2 F3), `Allow` header on 405 (4.2 F4), whether `WITHDRAWN` counts as progress (4.2 F5), timeline write throttling (4.2 F6) | Unfixed, recorded | 2026-09-22 |

### ⚠️ Verification and tracking gaps

7. **Only 2 of 13 executed sub-phases have a `VERIFICATION.md`** (4.2 PASS, 5.2 FAIL). 6.1, 6.2 and 7.1 have SUMMARYs and UAT sessions but no verification; 1.1–5.1 have neither. Nothing has been independently verified since 5.2.
8. **Phase 6.2's closing documentation was never committed.** `06.2-SUMMARY.md`, `06.2-UAT.md` and `drill_06_02.py` are still untracked in git, which is why REQUIREMENTS.md's `NOTIF-02`–`NOTIF-06` rows still read Pending and Phase 6's ROADMAP row still reads 0/3.
9. **Three UAT sessions are open and paused:** 6.1 at test 1 of 7, 6.2 at test 1 of 6, and 7.1 at test 1 of 7 (started today, awaiting an answer). No phase has completed a UAT.
10. **No `v1.0` git tag, no `.planning/milestones/` archive, no `MILESTONE-AUDIT.md`, no `RETROSPECTIVE.md`.** The milestone has no machine-verifiable boundary, so "what shipped in v1.0" can only be reconstructed from commits and phase directories — which is how this document was produced.
11. **Three commits carry the 1.2/2.1 work under unusable messages** (`latest`, `latest`, `changes`). Phase 2.1 has no phase directory artifacts at all, and 1.2's directory is empty, so two completed sub-phases are discoverable only by reading a diff.
12. **The GSD CLI cannot resolve any phase directory in this repository.** `project_code` is `TCS-JL`, and `gsd-core`'s directory grammar accepts only a single-segment code, so every `gsd_run` verb that needs a phase directory (`init.execute-phase`, `find-phase`, `phase-plan-index`, `phase.complete`) reports nothing — for 7.1 *and* for already-executed phases. 7.1 had to be executed and its tracking updated by hand from the plan file. Settling this (rename phase dirs, or change `project_code`) affects every future workflow run.

---

## 7. Getting Started

**Run the stack.**

```bash
cp .env.example .env          # first time
make up                       # docker compose up -d --build — 6 services
make ps                       # service health
make logs                     # follow logs (last 100 lines)
```

`web` runs gunicorn behind nginx; the container entrypoint applies migrations and collects static files. Liveness is `/health/`, readiness `/health/ready/` (checks DB + Redis). Django settings are split (`config/settings/{base,local,test,prod}.py`) and `DJANGO_SETTINGS_MODULE=config.settings.local` in the container.

**Test and lint.** There is no `make test` target; run pytest in the web container. `requirements-dev.txt` is *not* baked into the image, so install it once per container:

```bash
docker compose exec -T web sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
docker compose exec -T web ruff check apps config && docker compose exec -T web ruff format --check apps config
docker compose exec -T web python manage.py makemigrations --check --dry-run
```

Currently: **606 passed**, ruff clean, no migration drift. `pytest.ini` sets `--reuse-db`, so the test database survives between runs.

> ⚠️ The running `web` container predates `firebase-admin==7.6.0` and fails 3 push-backend tests until `requirements.txt` is installed into it or the image is rebuilt (`make rebuild`).

**Key directories.**

| Path | What lives there |
|---|---|
| `apps/accounts/` | Custom `User`, registration/verification/reset, JWT, account deletion, throttles |
| `apps/candidates/` | `CandidateProfile`, the status state machine, profile CRUD + public candidate surface |
| `apps/timeline/` | `TimelineEvent`, the atomic status-sync service, timeline API, `/dashboard/` |
| `apps/community/` | `Post`/`Comment`/`PostVote`, feed/vote/lock-pin endpoints, tombstone helpers |
| `apps/notifications/` | `Notification`/`Device`/`NotificationPreference`, push backends, Celery worker, preferences API |
| `apps/analytics/` | Read-only aggregation + wait-time + `<5` suppression service (**no models, no views — by design**) |
| `config/` | Split settings, root URL conf, Celery app, WSGI |
| `.planning/` | GSD artifacts: ROADMAP, REQUIREMENTS, STATE, PROJECT, `phases/<sub-phase>/`, `reports/` |
| `01_…12_*.md` (root) | The product/API/architecture specifications the phases are built against |
| `docker/`, `nginx/` | Entrypoint script, Dockerfile (shared), nginx config |

**Where to look first.** `manage.py` → `config/urls.py` for the API map; `apps/timeline/services.py` for the project's most important invariant (atomic status sync); `apps/analytics/services.py` for the privacy contract; `.planning/ROADMAP.md` + `.planning/STATE.md` for what is actually done.

**Reading order for a new contributor:** this document → `.planning/ROADMAP.md` (what is planned) → `.planning/STATE.md` `Accumulated Context` (every locked decision) → the phase `VERIFICATION.md` files (what is actually proven) → the relevant `apps/*/services.py`.

**Known onboarding friction.** There is no `README.md`, no `CLAUDE.md`, no `CONTRIBUTING.md` and no `LICENSE` at the repo root — the specs and the Makefile are the only documented entry points. Three commit messages are unusable (Section 6.11), and the standard GSD workflow commands do not resolve phase directories (Section 6.12).

---

## Stats

- **Timeline:** 2026-09-20 → 2026-09-22 (3 days, single continuous build)
- **Sub-phases:** 13 executed / 22 total (9 not started); **1 verified PASS, 1 verified FAIL, 3 unverified, 8 never verified**
- **Commits:** 42 (`3fa0e4f` → `a27b5b0`)
- **Files changed:** 512 (+71,940 / −86) across the whole tree at HEAD — the raw figure counts the 1173 indexed project files against the root commit
- **Contributors:** 1 (`saitej-a`)
- **Tests:** 606 passing, 0 failing; ruff clean; zero migration drift
- **Runtime dependencies added since Phase 1:** exactly one (`firebase-admin`)

---
*Generated by `/gsd-milestone-summary` from `.planning/` artifacts, git history and direct code inspection (the two "NEW" findings in Section 6 were confirmed by reading the current source, not from any recorded artifact).*
