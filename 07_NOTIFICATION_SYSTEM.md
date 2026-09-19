# 07 — Notification System Specification

# TCS Joining Tracker — Notification & Browser Push Architecture

> **Document:** 07_NOTIFICATION_SYSTEM.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification  
> **Target Framework:** Django 5.x + Django REST Framework + Celery 5.x + Redis 7+  
> **Push Notification Provider:** Firebase Cloud Messaging (FCM) via Firebase Admin Python SDK  
> **Frontend Integration:** Web Push API + Service Worker (`firebase-messaging-sw.js`) + React (PWA)  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

From a notification delivery and content perspective, the following legal and operational invariants must be enforced:
1. **No False Authority:** Notification banners, push messages, and system alerts must **never** claim or imply that a notification is an "Official TCS Notification", "TCS Corporate HR Communication", or "NextStep Portal Alert".
2. **Clear Community Attributions:** Push notifications regarding batch progress, joining letter releases, or survey rollouts must explicitly state that the update is **community-reported** (e.g., *"Candidates from 2025 Digital Hyderabad are reporting joining letters on the community tracker"*).
3. **Zero Official Credential Infiltration:** Notifications must never request candidate NextStep passwords, TCS credentials, offer letter acceptance OTPs, or fee payments. Any community discussion referencing scam fees must be flagged immediately.

---

# 1. Document Overview & Notification Strategy

## 1.1 Purpose & Scope

This specification defines the complete architecture, data models, asynchronous task pipelines, security constraints, and client-side integration patterns for notifications in the TCS Joining Tracker MVP.

The notification system serves as the primary engagement loop and anxiety-reduction mechanism for candidates waiting for their TCS Joining Letter (JL). When candidates are waiting for months without official communication, peer activity in the same hiring stream or region provides vital reassurance and actionable context.

### System Responsibilities:
- **In-App Notifications:** Persistent, auditable records stored in PostgreSQL that track user-specific events (comments, replies, upvote milestones, announcements, and moderation actions).
- **External Web Push Notifications:** Real-time push delivery to desktop and mobile browsers via Firebase Cloud Messaging (FCM), even when the web application tab is closed.
- **Asynchronous Task Offloading:** Immediate HTTP API response times (<100ms) by routing all push payload generation, token resolution, and third-party FCM API calls through Redis and Celery workers.
- **Privacy & Security Enforcement:** Zero-PII exposure in push payloads, write-only device token handling, multi-device fan-out, and automatic invalidation of stale browser tokens.

---

## 1.2 Core Notification Principles

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        CORE NOTIFICATION PRINCIPLES                         │
  ├───────────────────┬───────────────────┬───────────────────┬─────────────────┤
  │ 1. Non-Blocking   │ 2. Zero-PII in    │ 3. Self-Action    │ 4. Anti-Storm   │
  │    Async Pipeline │    Push Payloads  │    Suppression    │    Debouncing   │
  │ Web API never     │ Push networks     │ Users never get   │ Votes batched;  │
  │ waits on FCM;     │ see only generic  │ alerts for their  │ no notification │
  │ Celery handles it.│ routing data.     │ own comments.     │ floods allowed. │
  └───────────────────┴───────────────────┴───────────────────┴─────────────────┘
```

1. **Non-Blocking Asynchronous Processing:** Database writes for comments or upvotes must commit immediately. Dispatching push notifications is strictly deferred to Celery background workers.
2. **Zero-PII Push Payloads:** Data routed through Google/Apple push servers must not reveal candidate email addresses, full names, or sensitive recruitment notes.
3. **Self-Action Suppression:** Candidates must **never** receive notifications for actions they initiated themselves (e.g., writing a comment on their own post, voting on their own content, or replying to their own comment).
4. **Notification Storm Prevention:** High-frequency events (such as upvotes) must not generate individual notifications per event. Upvotes use milestone-based thresholds (10, 25, 50, 100 upvotes).

---

# 2. Dual Notification System Architecture

The application decouples notifications into two concurrent delivery streams:

```
                                NOTIFICATION DISPATCH PIPELINE
                                              │
                                   [Candidate Action Event]
                                (e.g., New Comment on Post)
                                              │
                                              ▼
                             ┌─────────────────────────────────┐
                             │    Service Layer / API View     │
                             │  1. Create DB Comment Record    │
                             │  2. Identify Target Recipient   │
                             └────────────────┬────────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        [STREAM 1: SYNCHRONOUS IN-APP]                 [STREAM 2: ASYNCHRONOUS PUSH]
                     │                                                 │
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │ Insert `Notification`   │                       │ Enqueue Celery Task via │
        │ Record into PostgreSQL  │                       │ Redis Broker            │
        └────────────┬────────────┘                       └────────────┬────────────┘
                     │                                                 │
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │ Available Instantly via │                       │ Celery Background Worker│
        │ `GET /api/v1/           │                       │ 1. Load Active Devices  │
        │  notifications/`        │                       │ 2. Build Zero-PII Body  │
        └─────────────────────────┘                       │ 3. Send to Firebase SDK │
                                                          └────────────┬────────────┘
                                                                       │
                                                                       ▼
                                                          ┌─────────────────────────┐
                                                          │ Firebase Cloud Messaging│
                                                          │ (FCM HTTP v1 API)       │
                                                          └────────────┬────────────┘
                                                                       │
                                                                       ▼
                                                          ┌─────────────────────────┐
                                                          │ Target Browser / Mobile │
                                                          │ Service Worker Displays │
                                                          │ Native Push Banner      │
                                                          └─────────────────────────┘
```

### Architectural Contrast:

| Dimension | In-App Notifications (Stream 1) | Browser Push Notifications (Stream 2) |
|---|---|---|
| **Authoritative Store** | PostgreSQL `Notification` table | Ephemeral; delivered via FCM to device |
| **Delivery Reliability** | 100% persistent in database | Best-effort; subject to OS/browser power rules |
| **Latency** | Instantaneous upon DB commit | 500ms - 3000ms (asynchronous Celery task) |
| **Content Detail** | Rich contextual preview & comment body | Brief title + generic call to action |
| **Prerequisites** | Authenticated session | Granted browser notification permission |
| **User Control** | Permanent history until dismissed/read | Toggleable per device in browser settings |

---

# 3. Database Schema & Data Models

The notification architecture is implemented across three primary database models in the `notifications` app:
1. `Notification`: The authoritative log of in-app alerts.
2. `Device`: Registered browser/mobile endpoints possessing FCM tokens.
3. `NotificationPreference`: Granular candidate notification controls.

```
  DATABASE RELATIONSHIP DIAGRAM
  ┌────────────────────────┐          ┌────────────────────────┐
  │ accounts.User          │ 1      * │ notifications.Device   │
  │ • id (UUID)            ├──────────┤ • id (UUID)            │
  │ • email                │          │ • fcm_token (Text)     │
  │ • is_active            │          │ • device_type (Choice) │
  └───────────┬────────────┘          │ • is_active (Boolean)  │
              │                       └────────────────────────┘
              │ 1
              ├──────────────────────────────────┐
              │ 1                                │ 1
              ▼ *                                ▼ 1
  ┌────────────────────────┐          ┌────────────────────────┐
  │ Notification           │          │ NotificationPreference │
  │ • id (UUID)            │          │ • id (UUID)            │
  │ • recipient (FK User)  │          │ • user (OneToOne User) │
  │ • type (Choice)        │          │ • notify_on_comment    │
  │ • title (VarChar 255)  │          │ • notify_on_reply      │
  │ • message (Text)       │          │ • notify_on_vote       │
  │ • is_read (Boolean)    │          │ • notify_announcements │
  │ • read_at (DateTime)   │          │ • push_enabled         │
  │ • post (FK Post)       │          └────────────────────────┘
  │ • comment (FK Comment) │
  └────────────────────────┘
```

---

## 3.1 The `Notification` Model (`notifications/models.py`)

```python
import uuid
from django.db import models
from django.conf import settings

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        COMMENT = 'COMMENT', 'New Comment'
        REPLY = 'REPLY', 'New Reply'
        VOTE_MILESTONE = 'VOTE_MILESTONE', 'Upvote Milestone'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        MODERATION = 'MODERATION', 'Moderation Alert'
        TIMELINE_REMINDER = 'TIMELINE_REMINDER', 'Timeline Reminder'
        SYSTEM = 'SYSTEM', 'System Alert'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Optional contextual references (Explicit Foreign Keys)
    post = models.ForeignKey(
        'community.Post',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    comment = models.ForeignKey(
        'community.Comment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def mark_as_read(self):
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
```

---

## 3.2 The `Device` Model (`notifications/models.py`)

The `Device` model isolates FCM registration tokens from the core `User` model, supporting multiple browsers, laptops, and mobile devices per user account.

```python
class Device(models.Model):
    class DeviceType(models.TextChoices):
        WEB = 'WEB', 'Web Browser'
        ANDROID = 'ANDROID', 'Android Web/PWA'
        IOS = 'IOS', 'iOS Web/PWA'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='devices',
        db_index=True
    )
    fcm_token = models.TextField(unique=True, help_text="Firebase registration token")
    device_type = models.CharField(
        max_length=16,
        choices=DeviceType.choices,
        default=DeviceType.WEB
    )
    browser = models.CharField(max_length=64, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_type} ({self.browser})"
```

---

## 3.3 The `NotificationPreference` Model (`notifications/models.py`)

Permits candidates to control which event categories dispatch external push notifications versus remaining silent in-app alerts.

```python
class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    notify_on_comment = models.BooleanField(default=True, help_text="Notify when someone comments on your post")
    notify_on_reply = models.BooleanField(default=True, help_text="Notify when someone replies to your comment")
    notify_on_vote_milestone = models.BooleanField(default=True, help_text="Notify on post upvote milestones")
    notify_on_announcements = models.BooleanField(default=True, help_text="Notify on admin community announcements")
    notify_timeline_reminders = models.BooleanField(default=True, help_text="Periodic reminders to update timeline")
    push_enabled = models.BooleanField(default=True, help_text="Global master toggle for browser push")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

# 4. Notification Event Taxonomy & Trigger Rules

Every notification is triggered by an explicit domain event in the business logic service layer.

```
  EVENT DISPATCH MATRIX
  ┌──────────────────┬───────────────────────┬───────────────────────┬────────────────────────┐
  │ Event Type       │ Trigger Condition     │ Target Recipient      │ Deep-Link Click Target │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `COMMENT`        │ User writes a comment │ Author of the post    │ `/community/posts/     │
  │                  │ on another's post     │ (Suppressed if self)  │  {post_id}#comment-id` │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `REPLY`          │ User writes a reply   │ Author of the parent  │ `/community/posts/     │
  │                  │ to a top-level comment│ comment (No self-notif│  {post_id}#reply-id`   │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `VOTE_MILESTONE` │ Post reaches upvote   │ Author of the post    │ `/community/posts/     │
  │                  │ milestone (10, 25, 50)│                       │  {post_id}`            │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `ANNOUNCEMENT`   │ Admin publishes a     │ All active registered │ `/community/posts/     │
  │                  │ community announcement│ candidates            │  {post_id}` or modal   │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `MODERATION`     │ Post locked, deleted, │ Author of the         │ In-app notice          │
  │                  │ or user warned by mod │ reported content      │ `/dashboard`           │
  ├──────────────────┼───────────────────────┼───────────────────────┼────────────────────────┤
  │ `TIMELINE_`      │ 30 days since last    │ Candidate whose status│ `/timeline`            │
  │ `REMINDER`       │ timeline update       │ is WAITING            │                        │
  └──────────────────┴───────────────────────┴───────────────────────┴────────────────────────┘
```

---

## 4.1 Detailed Event Specifications

### 4.1.1 Event: `COMMENT`
- **Trigger:** A candidate creates a top-level comment on a post (`parent == NULL`).
- **Suppression Rule:** If `comment.author == post.author`, **do not dispatch**.
- **In-App Title:** `New Comment on Your Post`
- **In-App Message:** `"{display_name} commented on '{post_title}': '{comment_preview}'"`
- **Push Notification Title:** `New Discussion Reply`
- **Push Notification Body:** `Someone commented on your post: "{post_title_truncated}"`

### 4.1.2 Event: `REPLY`
- **Trigger:** A candidate creates a child comment replying to an existing comment (`parent != NULL`).
- **Suppression Rule:** If `reply.author == parent.author`, **do not dispatch**.
- **In-App Title:** `New Reply to Your Comment`
- **In-App Message:** `"{display_name} replied to your comment on '{post_title}': '{reply_preview}'"`
- **Push Notification Title:** `New Reply Received`
- **Push Notification Body:** `Someone replied to your comment in the TCS Joining Tracker community.`

### 4.1.3 Event: `VOTE_MILESTONE`
- **Trigger:** A post's upvote count hits a defined milestone: `[10, 25, 50, 100, 250, 500]`.
- **Anti-Storm Rule:** Individual upvotes **never** dispatch notifications. Only crossing milestone thresholds emits a notification.
- **In-App Title:** `Upvote Milestone Reached`
- **In-App Message:** `"Your discussion '{post_title}' has reached {count} upvotes!"`
- **Push Notification Title:** `Discussion Trending`
- **Push Notification Body:** `Your post reached {count} upvotes in the community tracker.`

### 4.1.4 Event: `ANNOUNCEMENT`
- **Trigger:** An administrator creates and publishes an `Announcement` record with `is_published = True`.
- **In-App Title:** `Official Community Update`
- **In-App Message:** `"{announcement_title} - {announcement_preview}"`
- **Push Notification Title:** `Community Update`
- **Push Notification Body:** `"{announcement_title}"`

---

# 5. Asynchronous Task Processing with Celery & Redis

Push notification delivery involves network I/O to external Google FCM servers. To ensure sub-100ms API response times for candidate actions, all push notifications are dispatched asynchronously via Celery workers with a Redis message broker.

```
  CELERY TASK DISPATCH ARCHITECTURE
  ┌────────────────────────────────────────────────────────┐
  │ Django API View (e.g., Create Comment Endpoint)        │
  │ • Write Comment to DB inside atomic transaction        │
  │ • Write In-App Notification to DB                      │
  │ • Call Celery Task:                                    │
  │   `send_push_notification_task.delay(notification_id)` │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ Redis Broker (Queue: `notifications_queue`)            │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ Celery Worker Process                                  │
  │ • Fetch Notification & Recipient from DB               │
  │ • Query Recipient's Active `Device` records           │
  │ • Filter against `NotificationPreference`              │
  │ • Send via Firebase Admin Python SDK                   │
  │ • Catch Invalid Tokens & Mark `Device.is_active=False` │
  └────────────────────────────────────────────────────────┘
```

---

## 5.1 Celery Task Implementations (`notifications/tasks.py`)

```python
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Notification, Device, NotificationPreference
from .services import send_fcm_multicast_message

logger = logging.getLogger('notifications')

@shared_task(
    bind=True,
    name='notifications.send_push_notification',
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    queue='notifications'
)
def send_push_notification_task(self, notification_id: str):
    """
    Asynchronously delivers a web push notification to all active devices
    registered by the notification recipient.
    """
    try:
        notification = Notification.objects.select_related('recipient').get(id=notification_id)
    except NotificationDoesNotExist:
        logger.warning(f"Notification {notification_id} does not exist; discarding task.")
        return

    recipient = notification.recipient

    # Check recipient global and category notification preferences
    prefs = getattr(recipient, 'notification_preferences', None)
    if prefs and not prefs.push_enabled:
        logger.info(f"Push disabled globally for user {recipient.id}; skipping push.")
        return

    if prefs:
        if notification.type == Notification.NotificationType.COMMENT and not prefs.notify_on_comment:
            return
        if notification.type == Notification.NotificationType.REPLY and not prefs.notify_on_reply:
            return
        if notification.type == Notification.NotificationType.VOTE_MILESTONE and not prefs.notify_on_vote_milestone:
            return
        if notification.type == Notification.NotificationType.ANNOUNCEMENT and not prefs.notify_on_announcements:
            return

    # Fetch active devices for recipient
    devices = list(Device.objects.filter(user=recipient, is_active=True))
    if not devices:
        logger.debug(f"User {recipient.id} has no active push devices.")
        return

    tokens = [d.fcm_token for d in devices]

    # Construct clean, zero-PII push payload
    title = notification.title
    body = notification.message
    # Truncate push body for mobile lockscreen ergonomics
    if len(body) > 120:
        body = body[:117] + "..."

    data_payload = {
        "notification_id": str(notification.id),
        "type": notification.type,
        "click_action": f"/community/posts/{notification.post_id}" if notification.post_id else "/dashboard"
    }

    # Dispatch to Firebase
    failed_tokens = send_fcm_multicast_message(tokens, title, body, data_payload)

    # Deactivate any tokens flagged as expired or unregistered by FCM
    if failed_tokens:
        Device.objects.filter(fcm_token__in=failed_tokens).update(
            is_active=False,
            updated_at=timezone.now()
        )
        logger.info(f"Deactivated {len(failed_tokens)} stale FCM tokens for user {recipient.id}.")
```

---

## 5.2 Broadcast Task for Announcements (`notifications/tasks.py`)

```python
@shared_task(
    bind=True,
    name='notifications.broadcast_announcement',
    queue='notifications'
)
def broadcast_announcement_task(self, announcement_id: str):
    """
    Dispatches a push notification to ALL active devices across the platform
    for a published administrative announcement.
    """
    from community.models import Announcement
    try:
        announcement = Announcement.objects.get(id=announcement_id, is_published=True)
    except Announcement.DoesNotExist:
        return

    # Stream active device tokens in batches of 500 (FCM multicast max limit)
    BATCH_SIZE = 500
    token_batch = []
    
    device_qs = Device.objects.filter(
        is_active=True,
        user__notification_preferences__notify_on_announcements=True
    ).values_list('fcm_token', flat=True).iterator(chunk_size=BATCH_SIZE)

    for token in device_qs:
        token_batch.append(token)
        if len(token_batch) >= BATCH_SIZE:
            send_fcm_multicast_message(
                tokens=token_batch,
                title="TCS Tracker Community Update",
                body=announcement.title[:120],
                data_payload={"type": "ANNOUNCEMENT", "announcement_id": str(announcement.id)}
            )
            token_batch = []

    if token_batch:
        send_fcm_multicast_message(
            tokens=token_batch,
            title="TCS Tracker Community Update",
            body=announcement.title[:120],
            data_payload={"type": "ANNOUNCEMENT", "announcement_id": str(announcement.id)}
        )
```

---

# 6. Firebase Cloud Messaging (FCM) Integration Architecture

The backend communicates with Firebase using the authoritative `firebase-admin` Python SDK, utilizing the modern **FCM HTTP v1 API**.

```
  FIREBASE ADMIN SDK MULTICAST PIPELINE
  ┌────────────────────────────────────────────────────────┐
  │ Celery Worker with Firebase Admin SDK                  │
  ├────────────────────────────────────────────────────────┤
  │ Payload:                                               │
  │ • WebpushConfig (headers, notification, data)          │
  │ • MulticastMessage (tokens=[token_1, token_2, ...])    │
  └───────────────────────────┬────────────────────────────┘
                              │ HTTPS POST (TLS 1.3)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ Google Firebase Cloud Messaging Gateway (HTTP v1)      │
  └───────────────────────────┬────────────────────────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
      [Success Responses]              [Error Responses]
      BatchResponse.success_count      • `UnregisteredError`
                                       • `InvalidArgumentError`
                                       (Collect stale tokens for cleanup)
```

---

## 6.1 Firebase SDK Initialization & Multicast Service (`notifications/services.py`)

```python
import os
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict, Optional

logger = logging.getLogger('notifications')

_firebase_app: Optional[firebase_admin.App] = None

def get_firebase_app() -> firebase_admin.App:
    global _firebase_app
    if _firebase_app is None:
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            # Fallback to application default credentials (GCP / environment)
            _firebase_app = firebase_admin.initialize_app()
    return _firebase_app

def send_fcm_multicast_message(
    tokens: List[str],
    title: str,
    body: str,
    data_payload: Dict[str, str]
) -> List[str]:
    """
    Dispatches a multicast push notification to up to 500 registration tokens.
    Returns a list of failed / invalid tokens that should be marked inactive.
    """
    if not tokens:
        return []

    app = get_firebase_app()

    # Webpush specific configuration
    webpush_config = messaging.WebpushConfig(
        notification=messaging.WebpushNotification(
            title=title,
            body=body,
            icon="/icons/icon-192x192.png",
            badge="/icons/badge-72x72.png",
        ),
        fcm_options=messaging.WebpushFCMOptions(
            link=data_payload.get("click_action", "/dashboard")
        ),
        headers={
            "Urgency": "high",
            "TTL": "86400"  # 24 hours retention on push gateways
        }
    )

    multicast_msg = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data=data_payload,
        webpush=webpush_config
    )

    failed_tokens = []

    try:
        response: messaging.BatchResponse = messaging.send_each_for_multicast(
            multicast_msg,
            app=app
        )
        logger.info(
            f"FCM batch delivered: {response.success_count} success, "
            f"{response.failure_count} failure out of {len(tokens)} tokens."
        )

        for idx, resp in enumerate(response.responses):
            if not resp.success:
                exc = resp.exception
                # Check if token is invalid or unregistered
                if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                    failed_tokens.append(tokens[idx])
                else:
                    logger.warning(f"FCM delivery error on token {tokens[idx][:8]}...: {exc}")

    except Exception as e:
        logger.error(f"Critical failure sending FCM multicast: {e}", exc_info=True)
        # Re-raise to trigger Celery retry
        raise e

    return failed_tokens
```

# 7. Device Token Lifecycle & Management

Device tokens are ephemeral, device-specific credentials generated by the client browser via the Firebase JS SDK.

```
  DEVICE TOKEN LIFECYCLE FLOW
  ┌────────────────────────────────────────────────────────┐
  │ 1. Browser grants push permission                      │
  │    `getToken(messaging, {vapidKey: ...})`              │
  ├────────────────────────────────────────────────────────┤
  │ 2. Client POSTs token to `/api/v1/devices/`            │
  │    • Device created / reactivated in PostgreSQL        │
  ├────────────────────────────────────────────────────────┤
  │ 3. Active Operation                                    │
  │    • Celery delivers push alerts to active device      │
  │    • `last_seen_at` refreshed on client API calls      │
  ├────────────────────────────────────────────────────────┤
  │ 4. Token Rotation (Browser / Firebase SDK updates tk)  │
  │    • Client PATCHes new token to `/api/v1/devices/:id/`│
  ├────────────────────────────────────────────────────────┤
  │ 5. Invalidation (User revokes / uninstalls browser)    │
  │    • FCM returns `UnregisteredError` during send       │
  │    • Celery updates `Device.is_active = False`         │
  ├────────────────────────────────────────────────────────┤
  │ 6. Automatic Purging                                   │
  │    • Celery Beat cron permanently deletes inactive     │
  │      devices older than 30 days                        │
  └────────────────────────────────────────────────────────┘
```

---

## 7.1 Multi-Device Fan-Out Architecture

A single candidate may access the tracker across multiple devices (e.g., Google Chrome on Windows 11 workstation and Safari on iOS/PWA).

### Fan-Out Rules:
1. When an event fires, the Celery task fetches **all** active `Device` records bound to the candidate:
   ```python
   devices = Device.objects.filter(user=recipient, is_active=True)
   ```
2. The multicast payload is dispatched to all tokens concurrently.
3. If one device succeeds while another returns `UnregisteredError`, the system deactivates only the failed token without terminating push alerts on the surviving devices.
4. **Device Revocation UI:** In the Profile & Settings view (`/settings`), candidates can review all registered devices (e.g., *"Chrome on Windows (Last seen today at 14:32)"*) with a direct **"Revoke Device"** action.

---

## 7.2 Stale Device Pruning Task (`notifications/tasks.py`)

Configured via Celery Beat to execute daily at 03:00 UTC:

```python
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import Device

@shared_task(name='notifications.prune_stale_devices')
def prune_stale_devices_task():
    """
    Deletes inactive devices older than 30 days to keep the devices table lean.
    """
    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Device.objects.filter(
        is_active=False,
        updated_at__lt=cutoff
    ).delete()
    logger.info(f"Pruned {deleted_count} inactive device records older than 30 days.")
```

---

# 8. Push Payload Security & Zero-PII Rules

Push notifications traverse untrusted external infrastructure (public transit networks, Google FCM cloud servers, Apple APNs gateways, and device lockscreens).

```
  PUSH PAYLOAD SECURITY ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────┐
  │ Push Notification Packet (Traversing FCM & Public Networks) │
  ├─────────────────────────────────────────────────────────────┤
  │ • Notification Title: "New Community Reply"                 │
  │ • Notification Body: "Someone replied to your comment on   │
  │   TCS Joining Tracker."                                     │
  │ • Target URL: "/community/posts/9a9f8d8b-7c1a..."           │
  │                                                             │
  │ [!] STRICTLY PROHIBITED IN PUSH PACKET:                     │
  │ ❌ Candidate email address                                  │
  │ ❌ Candidate real name / phone number                       │
  │ ❌ Specific internal user ID                                │
  │ ❌ Candidate NextStep credentials or interview results      │
  └─────────────────────────────────────────────────────────────┘
```

### Inviolable Push Security Constraints:
1. **Zero-PII Body:** Never display candidate email addresses, physical location details, or sensitive comments in lockscreen push banners.
2. **Write-Only Serializer:** The `fcm_token` is marked `write_only = True` in DRF serializers; it is **never** echoed back in any API response.
3. **Multi-Tenant Protection:** Device registrations require active JWT Bearer authentication. An attacker cannot register devices on behalf of another user account.

---

# 9. Service Worker & Frontend PWA Integration

The frontend uses standard Web Push APIs coordinated through a custom Service Worker.

## 9.1 Service Worker Implementation (`public/firebase-messaging-sw.js`)

```javascript
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

// Initialize Firebase in Service Worker context
firebase.initializeApp({
  apiKey: "AIzaSy...",
  authDomain: "tcs-joining-tracker.firebaseapp.com",
  projectId: "tcs-joining-tracker",
  storageBucket: "tcs-joining-tracker.appspot.com",
  messagingSenderId: "123456789012",
  appId: "1:123456789012:web:abcdef..."
});

const messaging = firebase.messaging();

// Handle Background Push Messages
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Background push received:', payload);

  const title = payload.notification?.title || "TCS Tracker Community Alert";
  const options = {
    body: payload.notification?.body || "You have a new community update.",
    icon: "/icons/icon-192x192.png",
    badge: "/icons/badge-72x72.png",
    data: {
      url: payload.data?.click_action || "/dashboard"
    }
  };

  self.registration.showNotification(title, options);
});

// Handle Notification Click / Deep-Linking
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/dashboard';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus existing tab if open
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
```

---

## 9.2 Push Permission UX: Soft Primer vs. Native Prompt

Browsers permanently block push notifications if a user clicks "Block" on an abrupt native browser prompt. The platform therefore enforces a **two-step soft primer pattern**:

```
  SOFT NOTIFICATION PERMISSION FLOW
  ┌────────────────────────────────────────────────────────┐
  │ Soft Permission Primer Modal (In-App UI)               │
  ├────────────────────────────────────────────────────────┤
  │ 🔔 Stay Updated on Joining Letters                     │
  │                                                        │
  │ Would you like real-time browser alerts when other     │
  │ candidates report joining letters for your batch?     │
  │                                                        │
  │ [Not Now]                   [Enable Notifications]     │
  └───────────────────────────┬────────────────────────────┘
                              │ (User clicks Enable)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ Native Browser Permission Prompt                       │
  │ "tracker.internal wants to send you notifications"     │
  │                                                        │
  │ [Block]                                       [Allow]  │
  └───────────────────────────┬────────────────────────────┘
                              │ (User grants permission)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ Client generates FCM token & calls:                    │
  │ `POST /api/v1/devices/`                                │
  └────────────────────────────────────────────────────────┘
```

# 10. Anti-Spam, Rate Limiting & Notification Storm Prevention

To prevent candidate fatigue and protect system resources, notifications are governed by strict throttling and anti-storm safeguards.

```
  NOTIFICATION STORM MITIGATION
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ Potential Storm Trigger         │ Architectural Mitigation                  │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Rapid comment thread discussion │ In-app notifications group by post;       │
  │ (e.g. 50 comments in 10 mins)   │ Push notifications throttled to max       │
  │                                 │ 1 push alert per thread per 15 minutes.   │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Viral post receiving 500 upvotes│ Milestone thresholding: Upvotes notify    │
  │                                 │ ONLY at [10, 25, 50, 100, 250, 500].      │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Bot device registration loop    │ Device registration rate-limited to       │
  │                                 │ max 10 requests per hour per user/IP.     │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Self-actions                    │ Programmatically suppressed at service    │
  │                                 │ layer; zero self-notifications generated. │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 10.1 Thread Push Debouncing via Redis

When a post experiences rapid discussion activity, sending a separate push notification for every single comment would inundate the author's mobile device.

### Debouncing Implementation:
1. When a comment notification is evaluated for push delivery, the Celery task checks a Redis debounce key:
   ```text
   key = f"debounce_push_post_{recipient_id}_{post_id}"
   ```
2. If the key exists (TTL: 15 minutes / 900s), the in-app notification is created as normal, but the push notification is suppressed or batched.
3. The key is set with `SET NX EX 900` upon sending the first push notification.

---

# 11. REST API Contract for Notifications & Devices

The notifications application exposes standard REST endpoints under `/api/v1/notifications/` and `/api/v1/devices/`.

---

## 11.1 List In-App Notifications

```http
GET /api/v1/notifications/
```

### Query Parameters:
- `page`: Integer (Default: 1)
- `is_read`: Boolean (`true` or `false`)

### Response (`200 OK`):
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "7b8e1f2a-9c3d-4e5f-a1b2-3c4d5e6f7a8b",
      "type": "REPLY",
      "title": "New Reply to Your Comment",
      "message": "Sai T. replied to your comment on '2025 Digital Joining Letter status'",
      "is_read": false,
      "read_at": null,
      "post_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",
      "comment_id": "4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a",
      "created_at": "2026-09-19T14:32:00Z"
    }
  ]
}
```

---

## 11.2 Mark Single Notification Read

```http
POST /api/v1/notifications/{notification_id}/read/
```

### Response (`200 OK`):
```json
{
  "id": "7b8e1f2a-9c3d-4e5f-a1b2-3c4d5e6f7a8b",
  "is_read": true,
  "read_at": "2026-09-19T14:35:12Z"
}
```

- **Permission:** Recipient only. Other candidates attempting to mark this read receive `HTTP 404 Not Found`.

---

## 11.3 Mark All Notifications Read

```http
POST /api/v1/notifications/read-all/
```

### Response (`200 OK`):
```json
{
  "updated_count": 8,
  "message": "All unread notifications marked as read."
}
```

---

## 11.4 Register FCM Device Token

```http
POST /api/v1/devices/
```

### Request Payload:
```json
{
  "fcm_token": "bk3RNwTe3H0:CI2k_HHBc5VoAZlUhTRS7Z8w2B_L...",
  "device_type": "WEB",
  "browser": "Chrome on Windows 11"
}
```

### Response (`201 Created`):
```json
{
  "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "device_type": "WEB",
  "browser": "Chrome on Windows 11",
  "is_active": true,
  "last_seen_at": "2026-09-19T14:30:00Z",
  "created_at": "2026-09-19T14:30:00Z"
}
```

- **Security Constraint:** Note that `fcm_token` is omitted from the response object.

---

## 11.5 List Registered Devices

```http
GET /api/v1/devices/
```

### Response (`200 OK`):
```json
{
  "results": [
    {
      "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "device_type": "WEB",
      "browser": "Chrome on Windows 11",
      "is_active": true,
      "last_seen_at": "2026-09-19T14:30:00Z"
    }
  ]
}
```

---

## 11.6 Revoke / Deactivate Device

```http
DELETE /api/v1/devices/{device_id}/
```

### Response (`204 No Content`)

- Deactivates the device record immediately.
- Stops all future push delivery to this browser.

---

# 12. Failure Modes, Resilience & Edge Cases

```
  RESILIENCE & RECOVERY MATRIX
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ Failure Scenario                │ System Defense & Recovery Action          │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Google FCM Service Outage       │ Celery retries with exponential backoff   │
  │ (500 Server Error from Firebase)│ (3 attempts: 2s, 8s, 32s). In-app         │
  │                                 │ notifications remain completely intact.   │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ User Revokes Browser Permission │ FCM returns `UnregisteredError`. Celery   │
  │ in Chrome/Safari                │ worker automatically marks `is_active=F`. │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Target Post / Comment Deleted   │ Foreign keys use `CASCADE` or `SET_NULL`; │
  │ Before User Opens Notification  │ Frontend navigates to post with friendly  │
  │                                 │ notice: "This content was removed."       │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ Redis Queue Backpressure        │ Notifications queue is partitioned from   │
  │ (Heavy traffic spike)           │ core application tasks; worker concurrency│
  │                                 │ auto-scales to drain backlog.             │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

### Isolated Failure Boundary:
A complete network failure of Firebase Cloud Messaging will **never** cause the Django API to fail or roll back a candidate's comment or recruitment timeline update. In-app database transactions commit independently of push task execution.

# 13. Monitoring, Telemetry & Observability

To maintain operational visibility into push notification delivery health, the system records key performance indicators (KPIs) and telemetry metrics.

```
  NOTIFICATION TELEMETRY METRICS
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ Metric Name                     │ Type & Description                        │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `notifications_inapp_created`   │ Counter: Total in-app notifications saved │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `push_dispatched_total`         │ Counter: Total push messages sent to FCM  │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `push_delivery_success_total`   │ Counter: Successful device deliveries     │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `push_delivery_failure_total`   │ Counter: Failed device deliveries         │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `stale_tokens_deactivated`      │ Counter: Expired/unregistered tokens      │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `push_dispatch_latency_ms`      │ Histogram: Event trigger to FCM response  │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 13.1 Structured Log Event Sample

When a notification is dispatched, Celery emits a structured JSON log entry:

```json
{
  "timestamp": "2026-09-19T14:32:05.120Z",
  "logger": "notifications",
  "level": "INFO",
  "event": "PUSH_NOTIFICATION_SENT",
  "notification_id": "7b8e1f2a-9c3d-4e5f-a1b2-3c4d5e6f7a8b",
  "recipient_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",
  "notification_type": "REPLY",
  "device_count": 2,
  "success_count": 2,
  "failure_count": 0,
  "latency_ms": 142
}
```

---

# 14. Testing Strategy & Automated Test Suite

All notification components must be backed by automated test cases written with `pytest` and `pytest-django`, using mocks for external Firebase services.

```
  AUTOMATED TEST MATRIX
  ┌─────────────────────────────────────────────────────────────┐
  │ tests/notifications/                                        │
  │ ├── test_inapp_notifications.py                             │
  │ ├── test_self_action_suppression.py                         │
  │ ├── test_device_registration_security.py                    │
  │ ├── test_push_celery_task.py                                │
  │ └── test_stale_token_deactivation.py                        │
  └─────────────────────────────────────────────────────────────┘
```

---

## 14.1 Automated Test Examples (`pytest-django`)

### 14.1.1 Testing Self-Action Suppression
```python
import pytest
from community.models import Post, Comment
from notifications.models import Notification

@pytest.mark.django_db
def test_author_commenting_on_own_post_generates_no_notification(candidate_user):
    post = Post.objects.create(
        author=candidate_user,
        title="My Own Post",
        body="Discussing my timeline...",
        category="JOINING_LETTER"
    )

    # Author comments on their own post
    Comment.objects.create(
        post=post,
        author=candidate_user,
        body="Adding extra details to my own post"
    )

    # In-app notification must NOT be created
    notif_count = Notification.objects.filter(recipient=candidate_user).count()
    assert notif_count == 0
```

### 14.1.2 Testing In-App Notification on Other User's Comment
```python
@pytest.mark.django_db
def test_peer_comment_generates_inapp_notification(post_author_user, peer_user):
    post = Post.objects.create(
        author=post_author_user,
        title="Question on Joining Letter",
        body="Waiting for 2025 Digital JL",
        category="JOINING_LETTER"
    )

    # Peer candidate comments on author's post
    Comment.objects.create(
        post=post,
        author=peer_user,
        body="I received mine yesterday in Hyderabad!"
    )

    # Notification must exist for post author
    notif = Notification.objects.filter(recipient=post_author_user).first()
    assert notif is not None
    assert notif.type == Notification.NotificationType.COMMENT
    assert notif.is_read is False
```

### 14.1.3 Testing Celery Push Task with Mocked Firebase
```python
from unittest.mock import patch, MagicMock
from notifications.tasks import send_push_notification_task
from notifications.models import Device

@pytest.mark.django_db
@patch('notifications.services.send_fcm_multicast_message')
def test_push_task_calls_fcm_and_deactivates_stale_tokens(mock_fcm, post_author_user, notification_instance):
    # Register an active device for the user
    device = Device.objects.create(
        user=post_author_user,
        fcm_token="sample_token_123",
        is_active=True
    )

    # Mock FCM returning this token as failed/unregistered
    mock_fcm.return_value = ["sample_token_123"]

    # Execute task
    send_push_notification_task(str(notification_instance.id))

    # Verify FCM service called
    assert mock_fcm.called

    # Device must be deactivated automatically
    device.refresh_from_db()
    assert device.is_active is False
```

### 14.1.4 Testing Write-Only FCM Token in API Responses
```python
from rest_framework import status

@pytest.mark.django_db
def test_device_api_never_returns_fcm_token(authenticated_client):
    res = authenticated_client.post("/api/v1/devices/", {
        "fcm_token": "secret_firebase_token_abc_123",
        "device_type": "WEB",
        "browser": "Firefox on Linux"
    }, format="json")

    assert res.status_code == status.HTTP_201_CREATED
    assert "fcm_token" not in res.data
    assert res.data["is_active"] is True
```

---

# 15. Implementation Checklist & Definition of Done

The notification system is complete and verified when all of the following criteria are validated:

- [ ] **Data Model Implementation:** `Notification`, `Device`, and `NotificationPreference` models migrated in PostgreSQL.
- [ ] **Indexes Created:** Compound index on `(recipient, is_read, -created_at)` confirmed in PostgreSQL query planner.
- [ ] **Self-Action Suppression:** Verified across comment creation, reply creation, and upvoting.
- [ ] **Celery & Redis Worker Active:** Notification task queue configured and operational with exponential backoff retries.
- [ ] **Zero-PII Push Payloads:** Verified that no candidate email, real name, or private notes are contained in FCM push payloads.
- [ ] **FCM Multicast Configured:** `send_each_for_multicast` implemented with batch limit ceiling of 500 tokens.
- [ ] **Stale Token Pruning:** Unregistered tokens marked inactive immediately; daily Celery Beat pruning task operational.
- [ ] **Service Worker Verified:** `firebase-messaging-sw.js` handles background push display and deep-links on click.
- [ ] **Soft Primer UX:** Two-step permission primer implemented on frontend; no abrupt native browser prompts.
- [ ] **All Automated Tests Pass:** Pytest test suite validates 100% of notification workflows and security invariants.
- [ ] **Non-Affiliation Compliance:** Notification copy strictly adheres to independent community branding.

---

# 16. AI Agent Implementation Directives for Notifications

When generating, modifying, or refactoring notification code, AI coding agents must strictly enforce the following rules:

1. **Never Make Synchronous Push Calls in API Views:** Push notification delivery must always be dispatched via `send_push_notification_task.delay()`. Never call Firebase APIs directly inside a Django request/response view.
2. **Never Return FCM Tokens in API Serializers:** Ensure `fcm_token` has `write_only=True` on request serializers and is absent from response models.
3. **Always Scope In-App Notifications by Authenticated User:** When listing or marking notifications as read, always filter by `recipient=request.user`.
4. **Never Dispatch Self-Notifications:** Always check `if actor == target_recipient: return` before creating notifications.
5. **Always Handle FCM Errors Gracefully:** Never allow an `UnregisteredError` or network timeout to crash the Celery worker; collect failed tokens and deactivate them in bulk.
6. **Preserve Independent Community Identity:** Never use official TCS trademarks, HR signatures, or portal titles in notification templates.
