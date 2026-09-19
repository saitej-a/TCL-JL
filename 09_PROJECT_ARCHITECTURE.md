# 09 — Project Architecture Specification

# TCS Joining Tracker — End-to-End System Architecture & Engineering Blueprint

> **Document:** 09_PROJECT_ARCHITECTURE.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification  
> **Backend Architecture:** Modular Django 5.x Monolith + Django REST Framework 3.15+ + Celery 5.x  
> **Frontend Architecture:** React 18+ (TypeScript) + Vite + Tailwind CSS + Service Worker (PWA)  
> **Persistence & Caching:** PostgreSQL 16+ (Primary Relational Store) + Redis 7+ (Broker, Cache, Throttling)  
> **Push Gateway:** Firebase Cloud Messaging (FCM HTTP v1 API)  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

All architectural patterns, subsystem boundaries, data models, integration pipelines, and deployment topologies must strictly maintain this independence:
1. **Zero TCS Corporate Infrastructure Touchpoints:** The system operates in complete network, physical, and logical isolation from TCS servers, corporate intranets, or NextStep portals. There are **zero** web scrapers, automated credential authenticators, or unauthorized TCS API connections.
2. **Community-Reported Data Invariant:** The data architecture treats all candidate-submitted dates, statuses, and locations as voluntarily contributed peer data. The persistence layer explicitly records the provenance of all metrics as `COMMUNITY_REPORTED` and enforces small-group privacy thresholds.
3. **Candidate Anonymity & Safety:** The system architecture guarantees candidate privacy by decoupling authentication credentials from public identities and preventing de-anonymization attacks.

---

# 1. Executive Summary & Architectural Goals

The TCS Joining Tracker architecture is engineered to resolve a critical social problem: the information void, fragmentation, and psychological stress experienced by thousands of candidates waiting for their TCS Joining Letter (JL).

### Primary System Capabilities:
- **Personal Timeline Management:** Enables candidates to maintain an auditable, timestamped progression of their recruitment milestones (Interview, Selection, Offer Letter, Joining Readiness Survey, Joining Letter, Joining Date, Joined).
- **Community Discussion Hub:** Categorized, moderated peer forums where candidates can share updates, ask questions, upvote verified information, and coordinate onboarding.
- **Privacy-Preserving Aggregate Analytics:** Real-time data pipeline transforming individual candidate submissions into cohort-level wait-time benchmarks, regional distributions, and hiring stream trends without exposing individual candidate records.
- **Multi-Channel Notifications:** Instant in-app alerts coupled with asynchronous web push notifications via Firebase Cloud Messaging (FCM) to reach candidates across desktop and mobile devices.

---

## 1.1 Architectural Axioms & Principles

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        CORE ARCHITECTURAL PRINCIPLES                        │
  ├───────────────────┬───────────────────┬───────────────────┬─────────────────┤
  │ 1. Pragmatic      │ 2. Clean Service  │ 3. Asynchronous   │ 4. Single Source│
  │    Monolith       │    Layer          │    Resilience     │    of Truth     │
  │ Modular Django;   │ Business logic    │ Slow third-party  │ PostgreSQL holds│
  │ avoid premature   │ lives in services,│ I/O offloaded to  │ all persistent  │
  │ microservices.    │ not fat views.    │ Celery workers.   │ domain records. │
  └───────────────────┴───────────────────┴───────────────────┴─────────────────┘
```

1. **Modular Django Monolith:** For an MVP targeting ~2,000 registered candidates and ~500 daily active users, a well-structured Django monolith provides superior developer velocity, unified transactional integrity, straightforward debugging, and zero distributed-system overhead compared to premature microservices.
2. **Clean Service Layer Pattern:** Django views handle HTTP transport, authentication, and serialization; Django models handle relational persistence; business workflows (e.g., timeline progression, vote toggling, report review, push fan-out) reside exclusively in dedicated `services.py` modules.
3. **Asynchronous Non-Blocking Operations:** The primary web request-response cycle must remain sub-100ms. All external network I/O (FCM push delivery, email dispatch) and expensive background maintenance are delegated to Celery workers via Redis.
4. **PostgreSQL as Authoritative Store:** Redis is strictly an ephemeral cache, throttle tracker, and message broker. If Redis crashes or flushes, zero candidate domain data or timeline history is lost.
5. **Zero-Trust Client Separation:** The React frontend is treated as an untrusted consumer. All business rules, role-based access control, object permissions, and validation logic are enforced server-side.

---

# 2. High-Level System Architecture & Component Topology

The platform deploys as a multi-tier containerized architecture with clear layer segregation:

```
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                                     CLIENT TIER (BROWSER & MOBILE PWA)                           │
  │  React 18 (TypeScript) + Tailwind CSS + Service Worker (PWA) + Firebase Messaging JS SDK         │
  └────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                   │ HTTPS / TLS 1.3
                                                   ▼
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                                   EDGE & REVERSE PROXY TIER                                      │
  │  Nginx Web Server: TLS Termination + Static Asset Caching + HTTP Headers + Gzip/Brotli           │
  └────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                   │ Reverse Proxy (Unix Socket / HTTP)
                                                   ▼
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                              APPLICATION TIER (WSGI / GUNICORN)                                  │
  │  Django 5.x Application Monolith + Django REST Framework                                         │
  │  ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────────┐ │
  │  │ accounts     │ candidates   │ timeline     │ community    │ notifications│ moderation       │ │
  │  └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────────┘ │
  └───────────────┬────────────────────────────────┬────────────────────────────────┬────────────────┘
                  │                                │                                │
                  │ SQL Connection                 │ Redis Protocol                 │ Enqueue Task
                  ▼                                ▼                                ▼
  ┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
  │      DATABASE TIER           │ │   CACHE & BROKER TIER        │ │     WORKER TIER (CELERY)     │
  │ PostgreSQL 16+               │ │ Redis 7+                     │ │ Celery Background Workers    │
  │ • ACID Transactions          │ │ • Celery Message Broker      │ │ • FCM Push Multicast Worker  │
  │ • Relational Integrity       │ │ • Application Cache (TTL)    │ │ • Email Verification Worker  │
  │ • UUIDv4 Primary Keys        │ │ • Distributed Rate Limiting  │ │ • Celery Beat Periodic Cron  │
  │ • Aggregate Analytics        │ │ • Thread Push Debounce Keys  │ │ • Stale Device Pruning       │
  └──────────────────────────────┘ └──────────────────────────────┘ └──────────────┬───────────────┘
                                                                                   │
                                                                                   │ FCM HTTP v1 (TLS)
                                                                                   ▼
                                                                    ┌──────────────────────────────┐
                                                                    │ EXTERNAL PUSH GATEWAY        │
                                                                    │ Google Firebase Cloud        │
                                                                    │ Messaging (FCM)              │
                                                                    └──────────────────────────────┘
```

---

## 2.1 Subsystem Responsibilities

| Subsystem / Tier | Core Technology | Primary Architectural Responsibility |
|---|---|---|
| **Client Tier** | React 18, TypeScript, Tailwind, Vite | Single Page Application (SPA) providing responsive UI, timeline steppers, community feed, optimistic upvotes, and Service Worker background push handling. |
| **Reverse Proxy Tier** | Nginx | Terminates TLS 1.3, serves optimized static/media bundles, enforces HTTP security headers (HSTS, CSP), buffers slow clients, and proxies `/api/` to Gunicorn. |
| **Application Tier** | Python 3.11+, Django 5.x, DRF | Implements business logic, API serialization, JWT authentication, object-level authorization, transaction management, and analytics aggregation. |
| **Database Tier** | PostgreSQL 16+ | Authoritative relational persistence, foreign key cascades, unique constraints (e.g. 1 vote per post), CITEXT email indexing, and atomic timeline updates. |
| **Cache & Broker Tier** | Redis 7+ | In-memory key-value store acting as Celery task broker, rate-limiting counter, thread debounce register, and cache for aggregated public statistics. |
| **Worker Tier** | Celery 5.x, Celery Beat | Asynchronous execution of I/O-intensive tasks: FCM push multicast delivery, verification email dispatch, token cleanup, and stale device housekeeping. |
| **External Push Gateway** | Firebase Cloud Messaging | Dispatches native lockscreen push alerts to registered browser and mobile endpoints worldwide. |

# 3. Modular Django Monolith Architecture & App Boundaries

The backend application is structured as a modular Django monolith housed in `tcs_joining_tracker/`. Each business capability is encapsulated within a focused, self-contained Django application with explicit boundaries.

```
  DJANGO APP DEPENDENCY & INTERACTION GRAPH
  ┌─────────────────────────────────────────────────────────────┐
  │                         `accounts`                          │
  │               User Entity & JWT Authentication              │
  └──────────────┬──────────────────────────────┬───────────────┘
                 │ 1:1                          │ FK
                 ▼                              ▼
  ┌─────────────────────────────┐┌──────────────────────────────┐
  │        `candidates`         ││         `community`          │
  │ CandidateProfile & Identity ││ Posts, Comments, Votes, Ann. │
  └──────────────┬──────────────┘└──────┬────────────────┬──────┘
                 │ 1:M                  │ FK             │ FK
                 ▼                      ▼                ▼
  ┌─────────────────────────────┐┌──────────────┐┌──────────────┐
  │         `timeline`          ││`notifications││ `moderation` │
  │ TimelineEvent & Status Sync ││ Device, FCM  ││ Report, Audit│
  └──────────────┬──────────────┘└──────────────┘└──────────────┘
                 │                      ▲                ▲
                 │ Reads                │ Alerts         │ Flags
                 ▼                      │                │
  ┌─────────────────────────────────────┴────────────────┴──────┐
  │                         `analytics`                         │
  │            Read-Only Cohort-Level Aggregation               │
  └─────────────────────────────────────────────────────────────┘
```

---

## 3.1 Django Application Responsibilities & Domain Ownership

| App Name | Domain Models Owned | Primary Architectural Responsibilities |
|---|---|---|
| **`accounts`** | `User`, `PasswordResetToken` | Custom user model (UUIDv4 PK, case-insensitive email), JWT authentication, password hashing (Argon2id), registration validation, email verification tokens, and account deletion protocols. |
| **`candidates`** | `CandidateProfile` | Candidate recruitment attributes (batch, hiring stream, region, interview center, joining location), public identity modes (`ANONYMOUS` vs `DISPLAY_NAME`), and candidate status choice state machine. |
| **`timeline`** | `TimelineEvent` | Recruitment milestone events (Interview, Selection, Offer, Survey, JL, Joining Date, Joined). Orchestrates atomic synchronization between new events and `CandidateProfile.current_status`. |
| **`community`** | `Post`, `Comment`, `PostVote`, `Announcement` | Community forum management: discussion posts, 1-level nested replies, unique upvoting, soft-deletion handling, category taxonomy, and admin announcement publishing. |
| **`notifications`**| `Notification`, `Device`, `NotificationPreference`| In-app notification persistence, browser FCM device token registration, notification preferences, and Celery background push notification tasks. |
| **`moderation`** | `Report`, `AuditLog` | Content violation reporting, database-level XOR target constraints, admin report triage queue, automated scam regex heuristics, and user suspension workflows. |
| **`analytics`** | *(Read-Only / No write models)* | Cohort-level aggregation engine: calculates wait-time averages, stream distributions, and regional benchmarks. Strictly enforces the `<5` candidate privacy suppression threshold. |
| **`config`** | Global settings, URLs, WSGI, ASGI, Celery | Root application configuration, environment variable parsing, database routers, shared middleware, and base Celery app instance. |

---

## 3.2 Inter-App Communication Rules & Dependency Hygiene

To prevent spaghetti code, tight coupling, and circular import deadlocks (`ImportError`):

1. **Strictly Unidirectional Dependencies:** Apps higher in the hierarchy may depend on apps lower, but never vice versa. For example, `timeline` depends on `candidates`, but `candidates` never imports models from `timeline`.
2. **Service-Layer Communication:** When an action spans multiple domains (e.g., adding a timeline event updates candidate status and creates an in-app notification), the workflow is coordinated by a unified service function in `timeline/services.py`, rather than placing cross-app queries inside model `save()` methods.
3. **Decoupling via Celery Tasks:** When an event in `community` triggers a notification in `notifications`, the community view commits its transaction and invokes a Celery task by name:
   ```python
   # Inside community/services.py:
   from notifications.tasks import send_push_notification_task
   
   # Task dispatched asynchronously without synchronous model coupling
   send_push_notification_task.delay(str(notification.id))
   ```
4. **Prohibition of Circular Imports:** Avoid importing models at the module level when defining foreign keys. Always use string references:
   ```python
   # Correct decoupled relationship:
   post = models.ForeignKey('community.Post', on_delete=models.CASCADE)
   
   # Prohibited (causes circular imports during Django initialization):
   from community.models import Post
   post = models.ForeignKey(Post, on_delete=models.CASCADE)
   ```

---

# 4. Service Layer & Business Logic Architecture

A cornerstone of the TCS Joining Tracker architecture is the **Service Layer Pattern**. The application explicitly rejects "Fat Models" (which bloat data entities with transport and notification logic) and "Fat Views" (which couple business rules to HTTP requests).

```
  LAYERED ARCHITECTURAL RESPONSIBILITIES
  ┌─────────────────────────────────────────────────────────────┐
  │ HTTP Transport Layer (DRF ViewSets / APIViews)              │
  │ • Parse HTTP request, headers, query params                 │
  │ • Authenticate via JWT & evaluate permission classes        │
  │ • Deserialize input & return HTTP status responses          │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Calls
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Business Logic Layer (`services.py` in each app)            │
  │ • Validate domain invariants (e.g. valid status progression)│
  │ • Manage database transactions (`transaction.atomic()`)     │
  │ • Execute cross-model mutations and business workflows      │
  │ • Enqueue background Celery tasks                           │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Reads/Writes
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Persistence Layer (Django Models & PostgreSQL)              │
  │ • Enforce database-level schema, constraints, unique keys   │
  │ • Query optimization (`select_related`, `annotate`)         │
  └─────────────────────────────────────────────────────────────┘
```

---

## 4.1 Exemplary Service Implementation: Timeline Event & Status Sync

When a candidate records a `JOINING_LETTER` event, `timeline/services.py` ensures the event is saved, the candidate's profile status is updated, and community metrics are kept consistent within a single database transaction:

```python
from django.db import transaction
from django.core.exceptions import ValidationError
from candidates.models import CandidateProfile
from .models import TimelineEvent

@transaction.atomic
def record_timeline_event(
    candidate: CandidateProfile,
    event_type: str,
    event_date,
    description: str = "",
    auto_update_status: bool = True
) -> TimelineEvent:
    """
    Creates a new timeline event and atomically updates the candidate's
    current status if appropriate, ensuring transactional integrity.
    """
    # 1. Create the timeline event
    event = TimelineEvent.objects.create(
        candidate=candidate,
        event_type=event_type,
        event_date=event_date,
        description=description
    )

    # 2. Synchronize candidate profile status if requested
    if auto_update_status:
        STATUS_MAP = {
            TimelineEvent.EventType.INTERVIEW: CandidateProfile.Status.INTERVIEWED,
            TimelineEvent.EventType.SELECTION: CandidateProfile.Status.SELECTED,
            TimelineEvent.EventType.OFFER_LETTER: CandidateProfile.Status.OFFER_RECEIVED,
            TimelineEvent.EventType.READINESS_SURVEY: CandidateProfile.Status.READINESS_SURVEY,
            TimelineEvent.EventType.JOINING_LETTER: CandidateProfile.Status.JOINING_LETTER_RECEIVED,
            TimelineEvent.EventType.JOINING_DATE: CandidateProfile.Status.JOINING_DATE_RECEIVED,
            TimelineEvent.EventType.JOINED: CandidateProfile.Status.JOINED,
        }

        new_status = STATUS_MAP.get(event_type)
        if new_status:
            candidate.current_status = new_status
            if event_type == TimelineEvent.EventType.JOINING_LETTER and not candidate.joining_location:
                # Optionally sync joining location if provided
                pass
            candidate.save(update_fields=['current_status', 'updated_at'])

    return event
```

---

## 4.2 Exemplary Service Implementation: Comment Creation & Notification

In `community/services.py`, creating a comment automatically evaluates whether an in-app notification and background push task should be dispatched:

```python
from django.db import transaction
from notifications.models import Notification
from notifications.tasks import send_push_notification_task
from .models import Post, Comment

@transaction.atomic
def create_comment_service(author, post: Post, body: str, parent: Comment = None) -> Comment:
    """
    Creates a comment and enqueues an asynchronous notification to the
    content owner, strictly suppressing self-notifications.
    """
    if post.is_locked:
        raise ValueError("Cannot comment on a locked discussion.")

    if parent and parent.parent is not None:
        raise ValueError("Replies are capped at 1-level depth.")

    comment = Comment.objects.create(
        post=post,
        author=author,
        parent=parent,
        body=body
    )

    # Determine recipient: Parent comment author if reply, else post author
    recipient = parent.author if parent else post.author

    # Self-Action Suppression Invariant
    if recipient != author:
        notif_type = Notification.NotificationType.REPLY if parent else Notification.NotificationType.COMMENT
        title = "New Reply to Your Comment" if parent else "New Comment on Your Post"
        
        display_name = author.candidate_profile.get_public_display_name() if hasattr(author, 'candidate_profile') else "A candidate"
        message = f"{display_name} commented: '{body[:60]}...'" if len(body) > 60 else f"{display_name} commented: '{body}'"

        notification = Notification.objects.create(
            recipient=recipient,
            type=notif_type,
            title=title,
            message=message,
            post=post,
            comment=comment
        )

        # Enqueue external push notification after transaction commits
        transaction.on_commit(lambda: send_push_notification_task.delay(str(notification.id)))

    return comment
```

---

## 4.3 Request-Response Lifecycle Architecture

Every incoming HTTP request traverses a standardized lifecycle pipeline:

```
  REQUEST-RESPONSE LIFECYCLE WALKTHROUGH
  ┌────────────────────────────────────────────────────────┐
  │ 1. Nginx Reverse Proxy                                 │
  │    • Validates SSL/TLS 1.3 & passes to Gunicorn socket │
  ├────────────────────────────────────────────────────────┤
  │ 2. Django Middleware Stack                             │
  │    • SecurityMiddleware (HSTS, nosniff, xframe)        │
  │    • CorsMiddleware (Validates CORS allowlist)         │
  │    • Custom RateLimitingMiddleware                     │
  ├────────────────────────────────────────────────────────┤
  │ 3. DRF Authentication & Permissions                    │
  │    • SimpleJWT `JWTAuthentication` validates Bearer tk │
  │    • Checks `user.is_active` (Banned user rejection)   │
  │    • Evaluates permission classes (e.g. `IsAuthor`)    │
  ├────────────────────────────────────────────────────────┤
  │ 4. DRF Serializer Layer                                │
  │    • Validates payload types, lengths, required fields │
  ├────────────────────────────────────────────────────────┤
  │ 5. Business Service Layer (`services.py`)              │
  │    • Executes domain logic inside `transaction.atomic` │
  │    • Queries PostgreSQL with `select_related()`        │
  │    • Schedules Celery background task via `on_commit`  │
  ├────────────────────────────────────────────────────────┤
  │ 6. Response Formatting                                 │
  │    • Returns consistent JSON payload + HTTP status     │
  └────────────────────────────────────────────────────────┘
```

# 5. Frontend Client Architecture (React + TypeScript + Tailwind CSS)

The frontend is architected as a high-performance Single Page Application (SPA) with Progressive Web App (PWA) capabilities, built using React 18, TypeScript, Tailwind CSS, and Vite.

```
  FRONTEND ARCHITECTURAL LAYERS
  ┌────────────────────────────────────────────────────────┐
  │ Presentation Layer (Pages & Reusable Components)       │
  │ • Route Views: `/dashboard`, `/timeline`, `/community` │
  │ • UI Components: Buttons, Cards, Modals, Badges, Tabs   │
  ├────────────────────────────────────────────────────────┤
  │ State Management & Context Layer                       │
  │ • `AuthContext`: Access token, user session, logout    │
  │ • `ThemeContext`: Light / Dark / System theme sync     │
  │ • `NotificationContext`: Unread count, toast alerts    │
  ├────────────────────────────────────────────────────────┤
  │ Hook & Data Synchronization Layer                      │
  │ • Custom Hooks: `useTimeline`, `usePosts`, `useDebounce`│
  │ • Optimistic UI mutators with automatic rollback       │
  ├────────────────────────────────────────────────────────┤
  │ Centralized API Client Layer (`src/api/`)              │
  │ • Axios instance with automatic JWT refresh interceptor│
  │ • Strict TypeScript interfaces matching backend models │
  ├────────────────────────────────────────────────────────┤
  │ Service Worker Layer (`public/firebase-messaging-sw.js`)│
  │ • Background push notification handler                 │
  │ • Offline asset caching & network status detection     │
  └────────────────────────────────────────────────────────┘
```

---

## 5.1 Centralized API Client Architecture & Interceptors

All network requests route through a single, centralized Axios client instance (`src/api/client.ts`). The client encapsulates JWT token attachment, automated 401 token refresh, and request replay without leaking credentials.

```typescript
// src/api/client.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10s request timeout
});

// Request Interceptor: Attach Bearer Access Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Silent Token Refresh on HTTP 401
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: AxiosError | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Detect 401 Unauthorized and attempt refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url?.includes('/auth/login/') || originalRequest.url?.includes('/auth/token/refresh/')) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        // No refresh token available; trigger logout
        window.dispatchEvent(new Event('auth:logout'));
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh: refreshToken,
        });

        const newAccessToken = data.access;
        localStorage.setItem('access_token', newAccessToken);
        if (data.refresh) {
          localStorage.setItem('refresh_token', data.refresh); // If rotation enabled
        }

        apiClient.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
        processQueue(null, newAccessToken);

        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as AxiosError, null);
        window.dispatchEvent(new Event('auth:logout'));
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

---

## 5.2 Optimistic UI Update Pattern (Upvoting Example)

To ensure instant responsiveness on mobile devices, client interactions such as voting execute optimistically before network confirmation:

```typescript
// Inside usePosts hook:
const toggleVote = async (postId: string, currentVoted: boolean, currentCount: number) => {
  // 1. Optimistic local state update
  setPosts((prev) =>
    prev.map((p) =>
      p.id === postId
        ? {
            ...p,
            voted: !currentVoted,
            vote_count: currentVoted ? currentCount - 1 : currentCount + 1,
          }
        : p
    )
  );

  try {
    // 2. Network mutation
    if (currentVoted) {
      await apiClient.delete(`/posts/${postId}/vote/`);
    } else {
      await apiClient.post(`/posts/${postId}/vote/`);
    }
  } catch (err) {
    // 3. Rollback on failure with toast feedback
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId ? { ...p, voted: currentVoted, vote_count: currentCount } : p
      )
    );
    showToast('Failed to update vote. Please check your connection.', 'error');
  }
};
```

---

# 6. Data Flow & Event Choreography

The following sequence diagrams illustrate the technical interaction contracts across frontend, backend, PostgreSQL, Redis, Celery, and FCM.

---

## 6.1 Flow: Adding a Timeline Event & Status Synchronization

```
  Candidate          React Client       Django API View      Timeline Service       PostgreSQL DB
      │                   │                    │                     │                    │
      │ 1. Submits Event  │                    │                     │                    │
      │ ────────────────> │                    │                     │                    │
      │                   │ 2. POST /timeline/ │                     │                    │
      │                   │ ─────────────────> │                     │                    │
      │                   │                    │ 3. Validate Serializer                   │
      │                   │                    │ ──────────────────> │                    │
      │                   │                    │                     │ 4. BEGIN TX        │
      │                   │                    │                     │ ─────────────────> │
      │                   │                    │                     │ 5. Insert Event    │
      │                   │                    │                     │ ─────────────────> │
      │                   │                    │                     │ 6. Update Status   │
      │                   │                    │                     │ ─────────────────> │
      │                   │                    │                     │ 7. COMMIT TX       │
      │                   │                    │                     │ ─────────────────> │
      │                   │                    │ 8. HTTP 201 Created │                    │
      │                   │ <───────────────── │ <────────────────── │                    │
      │ 9. UI Refreshed   │                    │                     │                    │
      │ <──────────────── │                    │                     │                    │
```

---

## 6.2 Flow: Comment Creation, Celery Offloading & Push Fan-Out

```
  Candidate B         Django API View         PostgreSQL          Redis Broker          Celery Worker           Google FCM
       │                     │                    │                     │                     │                     │
       │ 1. POST /comments/  │                    │                     │                     │                     │
       │ ──────────────────> │                    │                     │                     │                     │
       │                     │ 2. Save Comment &  │                     │                     │                     │
       │                     │    Notification    │                     │                     │                     │
       │                     │ ─────────────────> │                     │                     │                     │
       │                     │ 3. Enqueue Celery  │                     │                     │                     │
       │                     │    Task on Commit  │                     │                     │                     │
       │                     │ ───────────────────────────────────────> │                     │                     │
       │ 4. 201 Created      │                    │                     │                     │                     │
       │ <────────────────── │                    │                     │                     │                     │
       │ (Fast Response)     │                    │                     │ 5. Pop Task         │                     │
       │                     │                    │                     │ ──────────────────> │                     │
       │                     │                    │                     │                     │ 6. Load Active Devs │
       │                     │                    │ <──────────────────────────────────────── │                     │
       │                     │                    │                     │                     │ 7. Send Multicast   │
       │                     │                    │                     │                     │ ──────────────────> │
       │                     │                    │                     │                     │ 8. Deactivate Stale │
       │                     │                    │ <──────────────────────────────────────── │    Tokens if any    │
```

---

## 6.3 Flow: Privacy-Preserving Cohort Analytics (<5 Threshold)

```
  Candidate           React Client         Django Analytics API         Analytics Service         PostgreSQL DB
      │                    │                        │                           │                      │
      │ 1. Opens Trends    │                        │                           │                      │
      │ ─────────────────> │                        │                           │                      │
      │                    │ 2. GET /batches/?...   │                           │                      │
      │                    │ ─────────────────────> │                           │                      │
      │                    │                        │ 3. Evaluate Filters       │                      │
      │                    │                        │ ────────────────────────> │                      │
      │                    │                        │                           │ 4. Count Cohort Size │
      │                    │                        │                           │ ───────────────────> │
      │                    │                        │                           │ 5. Returns count = 3 │
      │                    │                        │                           │ <─────────────────── │
      │                    │                        │                           │                      │
      │                    │                        │ 6. Threshold Check:       │                      │
      │                    │                        │    count < 5 -> SUPPRESS  │                      │
      │                    │                        │ ────────────────────────> │                      │
      │                    │ 7. Return 200 OK       │                           │                      │
      │                    │    `suppressed: true`  │                           │                      │
      │                    │ <───────────────────── │                           │                      │
      │ 8. UI Displays:    │                        │                           │                      │
      │    Privacy Notice  │                        │                           │                      │
      │ <───────────────── │                        │                           │                      │
```

# 7. Background Processing & Celery Queue Topology

Asynchronous task execution is powered by Celery 5.x with Redis 7+ as the message broker and result backend.

```
  CELERY QUEUE & WORKER TOPOLOGY
  ┌─────────────────────────────────────────────────────────────┐
  │ Django Web Workers (Gunicorn)                               │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Enqueue Task by Queue Name
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Redis Message Broker (db=1)                                 │
  │ ┌───────────────────────────┬─────────────────────────────┐ │
  │ │ `notifications` Queue     │ `default` / `tasks` Queue   │ │
  │ └───────────────────────────┴─────────────────────────────┘ │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Consumed by
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Celery Worker Processes                                     │
  │ • Worker Pool 1: `celery -A config worker -Q notifications` │
  │ • Worker Pool 2: `celery -A config worker -Q default`       │
  │ • Celery Beat:   `celery -A config beat` (Periodic Cron)    │
  └─────────────────────────────────────────────────────────────┘
```

---

## 7.1 Queue Partitioning & Worker Isolation

To prevent notification bursts (such as an administrative announcement broadcast) from starving transactional application tasks (such as verification email dispatches), queues are isolated:

1. **`notifications` Queue:** Dedicated to `send_push_notification_task` and `broadcast_announcement_task`. Scaled independently with high I/O concurrency (eventlet/gevent or prefork pool).
2. **`default` Queue:** Handles transactional user tasks such as `send_verification_email_task` and `send_password_reset_email_task`.
3. **`maintenance` Queue:** Handles low-priority batch jobs and periodic Celery Beat cron routines.

```python
# config/settings.py
CELERY_TASK_QUEUES = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'notifications': {
        'exchange': 'notifications',
        'routing_key': 'notifications',
    },
    'maintenance': {
        'exchange': 'maintenance',
        'routing_key': 'maintenance',
    },
}

CELERY_TASK_ROUTES = {
    'notifications.tasks.send_push_notification': {'queue': 'notifications'},
    'notifications.tasks.broadcast_announcement': {'queue': 'notifications'},
    'accounts.tasks.send_verification_email': {'queue': 'default'},
    'accounts.tasks.send_password_reset_email': {'queue': 'default'},
    'notifications.tasks.prune_stale_devices': {'queue': 'maintenance'},
}
```

---

## 7.2 Celery Beat Periodic Tasks Schedule

Configured in `config/celery.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'prune-inactive-devices-daily': {
        'task': 'notifications.tasks.prune_stale_devices',
        'schedule': crontab(hour=3, minute=0),  # Daily at 03:00 UTC
    },
    'clean-expired-announcements-hourly': {
        'task': 'community.tasks.clean_expired_announcements',
        'schedule': crontab(minute=15),        # Every hour at :15
    },
    'warm-analytics-cache-hourly': {
        'task': 'analytics.tasks.warm_analytics_cache',
        'schedule': crontab(minute=45),        # Hourly cache warmup
    },
}
```

---

# 8. Database Architecture & PostgreSQL Optimization

PostgreSQL 16 is the authoritative, ACID-compliant relational store.

```
  DATABASE STORAGE ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────┐
  │ PostgreSQL 16+ Database (`tcs_joining_tracker`)             │
  ├─────────────────────────────────────────────────────────────┤
  │ Relational Integrity Invariants:                            │
  │ • UUIDv4 Primary Keys across all user-facing tables         │
  │ • `CITEXT` / Functional Unique Lowercase Index on `email`   │
  │ • Compound indexes aligned with query ordering & filtering  │
  │ • Check constraints (`report_exactly_one_target`)           │
  │ • Unique constraints (`UNIQUE(user_id, post_id)` for votes) │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Managed Connection
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Connection Pooling (Django `CONN_MAX_AGE = 600`)            │
  │ Persistent TCP connections avoid per-request handshake cost │
  └─────────────────────────────────────────────────────────────┘
```

---

## 8.1 Indexing Strategy & Compound Query Support

Every index in the database is bound to an explicit production query pattern. Unused indexes are strictly avoided to minimize write overhead:

```python
# Optimized Database Indexes Reference
class CandidateProfile(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['batch', 'hiring_type']),
            models.Index(fields=['batch', 'current_status']),
            models.Index(fields=['region', 'current_status']),
        ]

class TimelineEvent(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['candidate', '-event_date']),
            models.Index(fields=['event_type', 'event_date']),
        ]

class Post(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['is_pinned', '-created_at']),
            models.Index(fields=['is_deleted', '-created_at']),
        ]

class Comment(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['post', 'parent', 'created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

class Notification(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]
```

---

## 8.2 Eliminating N+1 Query Anti-Patterns

A severe performance bottleneck in ORM applications is the N+1 query problem, where iterating over a queryset triggers individual subqueries for related models.

### Mandated Query Optimizations:
1. **Feed Query with Author & Pre-Computed Counters:**
   ```python
   # INSTEAD OF N+1:
   # posts = Post.objects.filter(is_deleted=False)
   # for p in posts: p.author.candidate_profile (N queries!)

   # MANDATED OPTIMIZED QUERY:
   posts = Post.objects.filter(is_deleted=False)       .select_related('author', 'author__candidate_profile')       .annotate(
           vote_count=models.Count('votes', distinct=True),
           comment_count=models.Count('comments', filter=models.Q(comments__is_deleted=False), distinct=True)
       )       .order_by('-is_pinned', '-created_at')[:20]
   ```
2. **Comment Hierarchy Optimization:**
   ```python
   # Fetch post comments and 1-level replies in a single query:
   comments = Comment.objects.filter(post_id=post_id, is_deleted=False)       .select_related('author', 'author__candidate_profile')       .prefetch_related(
           models.Prefetch(
               'replies',
               queryset=Comment.objects.filter(is_deleted=False).select_related('author', 'author__candidate_profile')
           )
       )       .filter(parent__isnull=True)       .order_by('created_at')
   ```

---

# 9. Caching Strategy & Redis Topology

Redis 7+ operates as the system's multi-purpose ephemeral data tier, partitioned by database numbers:
- `db=0`: Application Object Cache & Rate Limiting Buckets
- `db=1`: Celery Message Broker
- `db=2`: Celery Result Backend (Optional / Short TTL)

```
  CACHE NAMESPACE & INVALIDATION MATRIX
  ┌─────────────────────────┬─────────┬──────────────┬──────────────────────────┐
  │ Cache Key Pattern       │ TTL     │ Store Type   │ Invalidation Trigger     │
  ├─────────────────────────┼─────────┼──────────────┼──────────────────────────┤
  │ `stats:public_overview` │ 10 mins │ JSON String  │ Post-save on Candidate / │
  │                         │         │              │ TimelineEvent            │
  ├─────────────────────────┼─────────┼──────────────┼──────────────────────────┤
  │ `analytics:batches:*`   │ 15 mins │ JSON String  │ Celery Beat warmup task  │
  ├─────────────────────────┼─────────┼──────────────┼──────────────────────────┤
  │ `categories:list`       │ 24 hrs  │ JSON String  │ Static category change   │
  ├─────────────────────────┼─────────┼──────────────┼──────────────────────────┤
  │ `debounce_push_post:*`  │ 15 mins │ Integer (1)  │ Auto-expires (TTL)       │
  ├─────────────────────────┼─────────┼──────────────┼──────────────────────────┤
  │ `throttle_login_*`      │ 1 min   │ Sliding Win  │ Auto-expires (TTL)       │
  └─────────────────────────┴─────────┴──────────────┴──────────────────────────┘
```

### Absolute Cache Security Invariant:
**Private candidate records, individual recruitment dates, auth tokens, and user profile fields must NEVER be stored in shared or public cache keys.** Shared cache keys store exclusively aggregate sums, group counts, or public category listings.

# 10. Infrastructure, Deployment & Containerization

The platform is fully containerized using Docker and Docker Compose, ensuring strict parity between local development, continuous integration, and production staging.

```
  CONTAINER DEPLOYMENT TOPOLOGY (DOCKER COMPOSE)
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Port 80 / 443 (Host Network)                                                │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ `nginx` Container (Reverse Proxy, SSL Termination, Static Asset Server)     │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ Upstream Proxy (Port 8000)
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ `web` Container (Gunicorn WSGI Application Server - 4 Workers)              │
  └──────────────┬───────────────────────┬───────────────────────┬──────────────┘
                 │ Port 5432             │ Port 6379             │ Enqueue
                 ▼                       ▼                       ▼
  ┌────────────────────────┐   ┌────────────────────┐   ┌───────────────────────┐
  │ `db` Container         │   │ `redis` Container  │   │ `celery_worker` Cont. │
  │ PostgreSQL 16 Alpine   │   │ Redis 7 Alpine     │   │ Background Tasks      │
  │ Volume: `postgres_data`│   │ Volume: `redis_dat`│   └───────────────────────┘
  └────────────────────────┘   └────────────────────┘              │
                                                         ┌─────────┴────────────┐
                                                         │ `celery_beat` Cont.  │
                                                         │ Cron Scheduler       │
                                                         └──────────────────────┘
```

---

## 10.1 Production Docker Compose Specification (`docker-compose.prod.yml`)

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    container_name: tcs_tracker_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-tcs_tracker}
      POSTGRES_USER: ${POSTGRES_USER:-tcs_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-tcs_user} -d ${POSTGRES_DB:-tcs_tracker}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal_network

  redis:
    image: redis:7-alpine
    container_name: tcs_tracker_redis
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal_network

  web:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: tcs_tracker_web
    restart: unless-stopped
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 60
    env_file: .env.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal_network

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: tcs_tracker_celery_worker
    restart: unless-stopped
    command: celery -A config worker --loglevel=INFO -Q default,notifications,maintenance --concurrency=4
    env_file: .env.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal_network

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: tcs_tracker_celery_beat
    restart: unless-stopped
    command: celery -A config beat --loglevel=INFO
    env_file: .env.production
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - internal_network

  nginx:
    image: nginx:alpine
    container_name: tcs_tracker_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/prod.conf:/etc/nginx/conf.d/default.conf:ro
      - ./backend/staticfiles:/var/www/static:ro
      - ./frontend/dist:/var/www/frontend:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - web
    networks:
      - internal_network

volumes:
  postgres_data:
  redis_data:

networks:
  internal_network:
    driver: bridge
```

---

## 10.2 Health Checks & Container Readiness (`common/views.py`)

The platform implements dual health check endpoints for load balancers and container orchestrators:

1. **Liveness Probe (`GET /health/`):**
   - Returns instant `HTTP 200 OK` (`{"status": "ok"}`). Used to verify the Gunicorn process is accepting TCP connections.
2. **Readiness Probe (`GET /health/ready/`):**
   - Actively verifies connectivity to PostgreSQL and Redis:
   ```python
   from django.db import connection
   from django.core.cache import cache
   from rest_framework.response import Response
   from rest_framework.views import APIView
   from rest_framework import status

   class HealthReadyView(APIView):
       authentication_classes = []
       permission_classes = []

       def get(self, request):
           checks = {"database": False, "redis": False}
           try:
               connection.ensure_connection()
               checks["database"] = True
           except Exception as e:
               checks["database_error"] = str(e)

           try:
               cache.set('health_check', 'ok', timeout=5)
               checks["redis"] = cache.get('health_check') == 'ok'
           except Exception as e:
               checks["redis_error"] = str(e)

           all_healthy = checks["database"] and checks["redis"]
           status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
           return Response({"status": "healthy" if all_healthy else "degraded", "checks": checks}, status=status_code)
   ```

---

# 11. CI/CD, Quality Gates & Testing Architecture

All pull requests and deployment commits pass through automated quality gates before reaching staging or production environments.

```
  CI/CD PIPELINE STAGES (GITHUB ACTIONS)
  ┌───────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Stage 1: Lint &   │ ---> │ Stage 2: Security Scans │ ---> │ Stage 3: Test Suite     │
  │ Code Formatting   │      │ • Bandit (AST analysis) │      │ • Pytest (Backend)      │
  │ • Black / Ruff    │      │ • Pip-Audit (CVEs)      │      │ • TypeScript `tsc`      │
  │ • Flake8          │      │ • ESLint (Frontend)     │      │ • Jest / Vitest (React) │
  └───────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                           │
                                                                           ▼
                                                              Stage 4: Build & Deploy
                                                              • Vite production build
                                                              • Docker image push
                                                              • Zero-downtime reload
```

---

# 12. Scalability, Sizing & Bottleneck Analysis

## 12.1 MVP Target Sizing & Resource Allocations

```
  MVP SIZING BASELINE
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ Parameter                       │ Target Metric                             │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Total Registered Candidates     │ ~2,000 candidates                         │
  │ Daily Active Users (DAU)        │ ~500 candidates                           │
  │ Peak Concurrent Users           │ ~20 - 50 concurrent connections           │
  │ Daily Timeline Events Created   │ ~150 - 300 updates / day                  │
  │ Daily Community Posts & Comments│ ~200 - 500 contributions / day            │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

- **Minimum Server Spec:** 2 vCPU, 4 GB RAM, 40 GB NVMe SSD (e.g. AWS t4g.medium / DigitalOcean Basic Droplet).
- **Resource Budgeting:**
  - Gunicorn Web: 4 worker processes × 120MB = ~480MB RAM
  - Celery Worker: 4 worker threads × 150MB = ~600MB RAM
  - PostgreSQL 16: `shared_buffers = 512MB`, `work_mem = 16MB`
  - Redis 7: `maxmemory 256MB` with `volatile-lru` eviction
  - Nginx + OS Kernel: ~400MB RAM

---

## 12.2 Growth Path to 50,000 Users Without Rewrite

The architecture is deliberately structured so the system can scale 25× without altering application code or data models:

1. **Database Layer:** Deploy a dedicated managed PostgreSQL instance (e.g. AWS RDS) and introduce **PgBouncer** connection pooling to manage thousands of client connections effortlessly.
2. **Horizontal Web Scaling:** Scale Gunicorn across multiple stateless Docker application containers behind an AWS Application Load Balancer or Nginx cluster.
3. **Background Worker Scaling:** Scale Celery worker containers horizontally to consume from the Redis queue.
4. **Media & File Attachments:** Direct-to-S3 pre-signed upload pattern with CloudFront CDN caching offloads all binary handling from web servers.

---

# 13. Complete Project Directory Layout

```text
tcs_joining_tracker/
├── backend/
│   ├── manage.py
│   ├── Dockerfile
│   ├── Dockerfile.prod
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   │
│   ├── config/                        # Global Project Configuration
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   ├── celery.py                  # Celery App & Beat Schedule
│   │   ├── urls.py                    # Root URL Routing
│   │   └── settings/
│   │       ├── __init__.py
│   │       ├── base.py                # Shared Django Settings
│   │       ├── local.py               # Local Development Settings
│   │       └── production.py          # Hardened Production Settings
│   │
│   ├── apps/                          # Modular Django Applications
│   │   ├── accounts/                  # User Entity, Auth, Password Reset
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── services.py
│   │   │   ├── throttles.py
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── candidates/                # CandidateProfile, Identity Modes
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── services.py
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── timeline/                  # TimelineEvents & Status Sync
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── services.py
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── community/                 # Posts, Comments, Votes, Announcements
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── services.py
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── notifications/             # In-App Alerts, Devices, FCM Tasks
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── services.py            # Firebase Multicast SDK Logic
│   │   │   ├── tasks.py               # Celery Push & Broadcast Tasks
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── moderation/                # Reports, Audit, Scam Heuristics
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── admin.py               # Customized Django Admin
│   │   │   ├── heuristics.py          # Anti-Scam Regex Rules
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   ├── analytics/                 # Read-Only Cohort Aggregations
│   │   │   ├── views.py
│   │   │   ├── services.py            # Privacy Threshold Engine (<5)
│   │   │   ├── urls.py
│   │   │   └── tests/
│   │   │
│   │   └── common/                    # Cross-App Utilities
│   │       ├── permissions.py         # IDOR & Ownership Classes
│   │       ├── logging.py             # PII Redaction Filter
│   │       ├── views.py               # Health Readiness Probes
│   │       └── pagination.py          # Standard PageNumberPagination
│   │
│   └── tests/                         # Global Integration & End-to-End Tests
│       ├── conftest.py
│       └── integration/
│
├── frontend/                          # React + TypeScript + Tailwind
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── public/
│   │   ├── manifest.json
│   │   ├── firebase-messaging-sw.js   # Service Worker Push Handler
│   │   └── icons/
│   └── src/
│       ├── api/                       # Axios Client & API Endpoints
│       │   ├── client.ts
│       │   ├── auth.ts
│       │   ├── timeline.ts
│       │   └── community.ts
│       ├── components/                # Reusable UI Library
│       ├── context/                   # AuthContext, ThemeContext
│       ├── hooks/                     # Custom Data Hooks
│       ├── pages/                     # Route Views
│       └── types/                     # TypeScript Interfaces
│
├── nginx/                             # Nginx Configuration
│   ├── dev.conf
│   └── prod.conf
│
├── docker-compose.yml                 # Local Development Compose
├── docker-compose.prod.yml            # Production Deployment Compose
└── .env.example                       # Environment Variable Template
```

---

# 14. Architectural Definition of Done & AI Agent Directives

The system architecture is verified and complete when all of the following conditions are met:

- [ ] **Docker Compose Functional:** Entire stack boots cleanly via `docker compose up` with zero container crashes.
- [ ] **Database Integrity:** PostgreSQL migrations run cleanly; foreign keys, unique constraints, and XOR checks validated.
- [ ] **Decoupled Service Layer:** Core business actions reside in `services.py` modules wrapped in `transaction.atomic()`.
- [ ] **Asynchronous Task Queue:** Celery workers process notifications and emails asynchronously through Redis.
- [ ] **Privacy-Preserving Analytics:** Analytics endpoints enforce the `<5` candidate suppression threshold.
- [ ] **Optimized Querysets:** Zero N+1 query warnings across post lists, timeline events, and comment threads.
- [ ] **Centralized API Client:** Frontend Axios client cleanly executes silent JWT refresh upon receiving HTTP 401.
- [ ] **Service Worker Registered:** PWA manifest and push service worker operational.
- [ ] **Legal Disclaimers Enforced:** Non-affiliation statements rendered on public headers, footers, and analytics screens.

---

# 15. AI Agent Implementation Directives for Architecture

When generating or refactoring code across the project, AI coding agents must strictly obey these engineering directives:

1. **Respect Subsystem Boundaries:** Never query models from other apps directly inside viewsets. Always route cross-app business workflows through domain service functions.
2. **Never Execute Slow I/O in Views:** Network calls (emails, FCM push, external APIs) must always be offloaded to Celery background tasks via `task.delay()`.
3. **Always Use UUIDs for Public Entities:** Never create sequential integer primary keys on user-facing models.
4. **Prevent N+1 Queries:** Always pair querysets with `select_related()` on foreign keys and `prefetch_related()` on many-to-many or reverse foreign keys.
5. **Always Enforce Atomic Transactions:** Any multi-model write operation (e.g. creating an event and updating candidate status) must execute within `@transaction.atomic`.
6. **Preserve Independence Mandate:** Never generate code that attempts to scrape, authenticate with, or reverse-engineer official TCS NextStep portals.
