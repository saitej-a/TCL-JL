# TCS Joining Tracker

## What This Is

An independent, community-driven web application for candidates waiting for their Tata Consultancy Services (TCS) joining letters, onboarding dates, and recruitment updates. It provides a personal milestone tracker, structured community discussion forums, privacy-preserving aggregate wait-time analytics, and real-time browser push notifications.

## Core Value

Provide anxious candidates with complete clarity on their recruitment progress and community benchmarks without requiring them to expose their real identity or personal credentials.

## Business Context

- **Customer**: TCS candidates across India (Prime, Digital, Ninja streams) waiting for onboarding.
- **Revenue model**: 100% free, community-driven platform; open-source peer support.
- **Success metric**: 2,000+ registered candidates, sub-200ms API response time, zero PII leaks, active community verification of joining trends.
- **Strategy notes**: Independent platform strictly operating without official TCS affiliation or credential integration.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **AUTH-01**: User registration with case-insensitive email, password complexity, and Argon2id hashing.
- [ ] **AUTH-02**: Email verification token flow with 24-hour expiration and rate-limited resend.
- [ ] **AUTH-03**: Password reset flow with single-use 60-minute tokens and session revocation.
- [ ] **AUTH-04**: SimpleJWT authentication with 15-minute access token and 7-day rotating refresh tokens.
- [ ] **AUTH-05**: Account deletion with complete data anonymization preserving discussion integrity.
- [ ] **PROF-01**: Candidate profile creation capturing batch (2024/2025/2026), stream (Prime/Digital/Ninja), region, and interview center.
- [ ] **PROF-02**: Public identity modes supporting ANONYMOUS (default) and custom DISPLAY_NAME.
- [ ] **PROF-03**: Controlled candidate status state machine from REGISTERED to JOINED.
- [ ] **TIME-01**: TimelineEvent model capturing milestones (Interview, Selection, Offer, Survey, JL, Date, Joined).
- [ ] **TIME-02**: Atomic status synchronization advancing profile status when milestones are recorded.
- [ ] **TIME-03**: Insecure Direct Object Reference (IDOR) defense with strict ownership checks returning HTTP 404.
- [ ] **COMM-01**: Community discussion feed with category filtering, search, and sorting (Latest vs Trending).
- [ ] **COMM-02**: Discussion posts supporting plain text, upvoting, soft-deletion, pinning, and locking.
- [ ] **COMM-03**: Discussion comments supporting strict 1-level reply nesting.
- [ ] **COMM-04**: Unique post upvoting enforcing `UNIQUE(user, post)` database constraint.
- [ ] **NOTIF-01**: In-app notifications with read tracking for comments, replies, vote milestones, and announcements.
- [ ] **NOTIF-02**: Multi-device FCM registration with write-only token security.
- [ ] **NOTIF-03**: Asynchronous Celery push notification task with exponential backoff and zero PII payloads.
- [ ] **NOTIF-04**: Self-action notification suppression and Redis thread push debouncing.
- [ ] **ANAL-01**: Aggregate community analytics calculating wait times, stream breakdowns, and regional distributions.
- [ ] **ANAL-02**: Mandatory `<5` candidate privacy suppression threshold returning standard notice.
- [ ] **MOD-01**: Candidate reporting with database-level XOR target constraint (`post` vs `comment`).
- [ ] **MOD-02**: Active pending report deduplication and user throttling (10/hour).
- [ ] **MOD-03**: Automated scam regex heuristics intercepting paid job offers and fee solicitation.
- [ ] **MOD-04**: Admin moderation triage queue supporting dismiss, soft-delete, lock, warn, and ban actions.
- [ ] **UI-01**: Responsive React 18 frontend with desktop 3-col, tablet 2-col, and mobile 5-slot bottom tab bar.
- [ ] **UI-02**: Centralized Axios client with automatic silent JWT refresh interceptors on HTTP 401.
- [ ] **UI-03**: Optimistic UI state updates on upvoting with automatic error rollback.
- [ ] **UI-04**: Mandatory non-affiliation disclaimer and community-reported attribution displayed across all public views.

### Out of Scope

- **Official TCS Portal Scraping** — Violates terms of service, poses legal liabilities, and breaks credential safety.
- **Private 1-on-1 Messaging & Real-Time Chat** — Creates unmoderated harassment risks; community discussions satisfy communication needs.
- **Microservices Architecture** — Premature complexity; modular Django monolith provides superior velocity and transactional safety.
- **Elasticsearch / Dedicated Search Engines** — Unnecessary infrastructure burden for MVP scale (~2,000 users); PostgreSQL text search is sufficient.
- **Native Android / iOS Apps** — Mobile-first responsive web design and PWA service worker meet mobile requirements without app store friction.
- **Monetization & Payments** — Platform is strictly a free peer-support community tool.

## Context

- **Technical Environment**: Dockerized Django 5.x monolith with PostgreSQL 16, Redis 7, Celery 5.x, React 18, and Vite.
- **Target Audience**: Over 1,000+ candidates who have completed TCS recruitment rounds and are experiencing 45 to 120+ days of silence.
- **Key Problem**: Information is currently scattered across unsearchable WhatsApp and Telegram groups, creating vulnerability to employment scams and rumors.

## Constraints

- **Security & Privacy**: Zero candidate PII (email, phone, NextStep credentials) exposed publicly; small cohorts (<5 candidates) suppressed in analytics.
- **Performance**: Sub-100ms API response times on CRUD; sub-200ms p95 on feed queries; Celery background offload for push/email.
- **Legal**: Prominent display of the independent community non-affiliation disclaimer on every public view.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modular Django Monolith | Avoids distributed systems overhead; guarantees ACID transactions across profile and timeline events | ✓ Good |
| Celery + Redis for Push | Decouples third-party Google FCM latency from core web request cycles | ✓ Good |
| React + Tailwind + Vite SPA | Provides instant optimistic UI, native-feeling mobile bottom tab bar, and PWA capabilities | ✓ Good |
| Soft Deletion for Content | Preserves reply trees and conversation context; keeps evidence for moderation audit | ✓ Good |
| Strict 1-Level Reply Depth | Prevents runaway mobile indentation and complex nested queries while supporting clear dialogue | ✓ Good |
| Stitch UI generation deferred to Phase 9.1 | User decision 2026-09-21: MCP-based mockups stay untouched until the SPA phase starts; backend phases 3–8 first. Generate the design system from `05_UI_UX_SPECIFICATION.md` then the 12 views in 9.1–9.4 order | Pending |

---
*Last updated: 2026-09-21 after Phase 2.2 execution (AUTH-02..06 complete; Stitch deferred to 9.1)*
