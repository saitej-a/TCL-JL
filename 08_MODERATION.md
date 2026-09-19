# 08 — Moderation System Specification

# TCS Joining Tracker — Content Moderation, Safety & Administration Architecture

> **Document:** 08_MODERATION.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification  
> **Target Framework:** Django 5.x + Django REST Framework + PostgreSQL 16+  
> **Target Administration Interface:** Django Admin + Protected Staff REST APIs  
> **Target Queue & Worker:** Redis 7+ + Celery 5.x  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

From a community moderation and safety perspective, this boundary establishes strict operational requirements:
1. **Aggressive Scam Suppression:** Candidates experiencing prolonged waiting periods for their Joining Letter (JL) are acutely vulnerable to employment fraud. The moderation system must aggressively detect, quarantine, and purge bad actors soliciting fees, offering "joining letter expediting", or redirecting candidates to paid Telegram/WhatsApp VIP groups.
2. **Combating False TCS Authority:** Users falsely claiming to be "TCS HR Representatives", "Internal Recruitment Managers", or "Official Gatekeepers" must be sanctioned immediately. No user account may adopt official TCS branding, logos, or corporate titles.
3. **Defense Against Defamation & Misinformation:** While candidates are encouraged to share genuine timeline dates, posts spreading manufactured rumors (e.g., false claims of mass offer cancellations without evidence) must be reviewed, locked, or labeled to prevent widespread panic.

---

# 1. Document Overview, Philosophy & Non-Affiliation Boundary

## 1.1 Purpose & Scope

This specification defines the complete end-to-end content moderation architecture, reporting workflows, violation taxonomy, administrative tools, and automated heuristics for the TCS Joining Tracker MVP.

The community thrives only when candidates feel safe sharing truthful recruitment milestones without fear of abuse, doxxing, or fraud. The moderation system empowers candidates to report objectionable content, equips administrators with rapid triage tools, and maintains an immutable audit trail of all enforcement actions.

### Core Moderation Responsibilities:
- **Candidate Empowerment:** Frictionless, anonymous reporting of objectionable posts and comments.
- **Queue Triage & Resolution:** Prioritized administrative queue allowing moderators to dismiss, lock, soft-delete, warn, or ban with sub-second efficiency.
- **Auditability & Integrity:** Soft deletion of offending content preserves thread hierarchy, avoids dangling references, and retains evidence for administrative review.
- **Scam & Bot Shield:** Automated heuristics and Redis-backed rate limiting intercept spam before it reaches the community feed.

---

## 1.2 Moderation Philosophy

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        CORE MODERATION PHILOSOPHY                           │
  ├───────────────────┬───────────────────┬───────────────────┬─────────────────┤
  │ 1. Candidate      │ 2. Proportional   │ 3. Preservation   │ 4. Transparent  │
  │    Safety         │    Intervention   │    of Context     │    Enforcement  │
  │ Zero tolerance    │ Warnings for minor│ Soft-delete keeps │ Audit logs track│
  │ for scams, fees,  │ errors; instant   │ reply hierarchy   │ every moderator │
  │ or personal doxx. │ bans for scams.   │ intact.           │ action.         │
  └───────────────────┴───────────────────┴───────────────────┴─────────────────┘
```

1. **Candidate Safety First:** The psychological well-being and privacy of candidates is paramount. Any attempt to expose real identities (doxxing), extract money, or harass candidates results in immediate account termination.
2. **Proportional Intervention:** Sanctions match the severity of the offense. Minor off-topic discussions receive a friendly note or thread lock; malicious scams receive permanent bans and token blacklisting.
3. **Preservation of Conversation Context:** Content is never silently hard-deleted from the database. Soft deletion replaces offending text with a clean tombstone (`[This content has been removed by a moderator]`), preventing broken conversation trees.
4. **Transparent Enforcement:** All administrative actions (who reviewed what report, when, and with what rationale) are durably recorded in audit logs.

---

# 2. Community Guidelines & Acceptable Use Policy (AUP)

The Acceptable Use Policy establishes the boundaries of healthy participation on the platform.

```
  COMMUNITY POLICY & VIOLATION TAXONOMY
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ TIER 1: CRITICAL VIOLATIONS (Immediate Permanent Ban & Immediate Content Removal) │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ • Paid Recruitment Scams: Offering to sell joining letters, skip queues,   │
  │   or charging money for onboarding assistance.                              │
  │ • Impersonation of TCS Officials: Pretending to be official TCS HR/staff.  │
  │ • Doxxing & PII Exposure: Posting candidate emails, phone numbers,          │
  │   home addresses, or government ID numbers.                                 │
  │ • Phishing & Malware: Distributing suspicious links or credential harvesters│
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ TIER 2: SEVERE VIOLATIONS (Content Removal, Thread Lock, Account Warning)   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ • Malicious Misinformation: Fabricating batch cancellations or joining dates│
  │ • Harassment & Hate Speech: Abusing fellow candidates or discriminatory slurs│
  │ • Unsolicited Promotion: Promoting commercial courses, YouTube channels,     │
  │   or paid consultation services.                                            │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ TIER 3: MINOR VIOLATIONS (Friendly Warning, Re-Categorization, or Lock)     │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ • Off-topic or Duplicate Threads: Posting identical questions repeatedly.   │
  │ • Wrong Category: Posting interview questions under JOINING_LETTER category.│
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.1 Explicit Prohibitions

1. **Recruitment Scam Solicitations:**
   - Any message stating or implying: *"Contact @admin on Telegram for early TCS joining letter"* or *"Pay Rs 2,000 for TCS verification clearance"* is permanently banned on first sight.
2. **Unofficial Fee Collection:**
   - TCS never charges training or document verification fees. Any post suggesting fees are required will be quarantined immediately.
3. **Sharing Internal NextStep / TCS Intranet Credentials:**
   - Users are prohibited from requesting or sharing login credentials, session cookies, or proprietary TCS portal API keys.
4. **Offensive or Abusive Language:**
   - Discussions must remain constructive, respectful, and professional.

---

# 3. User Reporting Architecture

Candidates are the first line of defense in identifying policy violations. The reporting workflow is designed to be accessible, intuitive, and shielded against abuse.

```
  USER REPORTING PIPELINE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Candidate    │ ---> │ Click "Report" Icon     │ ---> │ Select Violation Reason │
  │ Browsing     │      │ on Post or Comment Card │      │ + Optional Context Note │
  └──────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                      │
                                                                      ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Backend API Processing (`POST /api/v1/reports/`):                           │
  │ 1. Authenticate Candidate (Anonymous users cannot report)                   │
  │ 2. Check Throttling (Max 10 reports / hour / user)                          │
  │ 3. Verify Target Exists & Is Not Already Deleted                            │
  │ 4. Prevent Duplicate Reporting (Unique per reporter + target while pending) │
  │ 5. Insert `Report` record with status `PENDING`                             │
  │ 6. Return HTTP 201 Created ("Report submitted successfully")                 │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3.1 Report Reasons & Metadata

The system defines 7 standardized report reasons:

| Reason Code | Label Shown to Candidate | Description & Target Violations |
|---|---|---|
| `SPAM` | Spam or Commercial Promotion | Promotional links, crypto schemes, affiliate links, repetitive flooding |
| `HARASSMENT` | Harassment or Abuse | Targeted insults, bullying, personal hostility, hate speech |
| `MISINFORMATION`| False Information / Rumors | Unverified claims of batch cancellations, fake joining date rumors |
| `ABUSIVE_CONTENT`| Profanity or Vulgarity | Offensive language, inappropriate imagery, disrespectful conduct |
| `PERSONAL_INFO` | Private Personal Information | Sharing candidate emails, phone numbers, employee IDs, doxxing |
| `SCAM` | Fraud / Fee Solicitation | Paid joining letter scams, paid Telegram groups, fake HR contacts |
| `OTHER` | Other Reason | Policy violations not categorized above; requires descriptive text |

---

## 3.2 Database Schema: The `Report` Model (`moderation/models.py`)

The `Report` model enforces a database-level invariant: **A report must target exactly one post OR exactly one comment, but never both, and never neither.**

```python
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Report(models.Model):
    class ReportReason(models.TextChoices):
        SPAM = 'SPAM', 'Spam or Commercial Promotion'
        HARASSMENT = 'HARASSMENT', 'Harassment or Abuse'
        MISINFORMATION = 'MISINFORMATION', 'False Information / Rumors'
        ABUSIVE_CONTENT = 'ABUSIVE_CONTENT', 'Profanity or Vulgarity'
        PERSONAL_INFORMATION = 'PERSONAL_INFORMATION', 'Private Personal Information'
        SCAM = 'SCAM', 'Fraud or Fee Solicitation'
        OTHER = 'OTHER', 'Other Violation'

    class ReportStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        REVIEWED = 'REVIEWED', 'Reviewed'
        RESOLVED = 'RESOLVED', 'Resolved (Action Taken)'
        DISMISSED = 'DISMISSED', 'Dismissed (No Violation)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_reports',
        db_index=True
    )
    post = models.ForeignKey(
        'community.Post',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    comment = models.ForeignKey(
        'community.Comment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    reason = models.CharField(
        max_length=32,
        choices=ReportReason.choices,
        default=ReportReason.SPAM,
        db_index=True
    )
    description = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Optional context provided by the reporting candidate"
    )
    status = models.CharField(
        max_length=16,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderator_notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['post', 'status']),
            models.Index(fields=['comment', 'status']),
        ]
        constraints = [
            # Exactly one target constraint (XOR)
            models.CheckConstraint(
                check=(
                    models.Q(post__isnull=False, comment__isnull=True) |
                    models.Q(post__isnull=True, comment__isnull=False)
                ),
                name='report_exactly_one_target'
            ),
        ]

    def clean(self):
        if bool(self.post) == bool(self.comment):
            raise ValidationError("A report must target either a post or a comment, not both or neither.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
```

---

## 3.3 Duplicate Report Handling & Anti-Brigading

To prevent malicious users from flooding the moderation queue (report brigading):

1. **Active Pending Check:** A candidate cannot submit a second report against the same post or comment while an earlier report from that candidate is in `PENDING` status.
   ```python
   # Application-level deduplication query:
   existing = Report.objects.filter(
       reporter=request.user,
       status=Report.ReportStatus.PENDING
   )
   if post_id:
       existing = existing.filter(post_id=post_id)
   elif comment_id:
       existing = existing.filter(comment_id=comment_id)

   if existing.exists():
       return Response(
           {"error": {"code": "DUPLICATE_REPORT", "message": "You already have a pending report for this content."}},
           status=status.HTTP_400_BAD_REQUEST
       )
   ```
2. **Rate Limiting:** Report submissions are throttled to a maximum of **10 reports per hour per candidate** via `ReportRateThrottle`.

# 4. Moderation Workflows & Lifecycle

Content moderation follows a disciplined state machine designed to resolve reports promptly while preserving an auditable chain of evidence.

```
  REPORT RESOLUTION STATE MACHINE
  ┌───────────────────┐
  │ Candidate Submits │
  │ Report (`PENDING`)│
  └─────────┬─────────┘
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Moderation Queue Triage                                     │
  │ • Priority 1 (Urgent): `SCAM`, `PERSONAL_INFORMATION`       │
  │ • Priority 2 (High):   `HARASSMENT`, `MISINFORMATION`       │
  │ • Priority 3 (Normal): `SPAM`, `ABUSIVE_CONTENT`, `OTHER`   │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Moderator Reviews Content in Context:                       │
  │ ┌─────────────────────────────────────────────────────────┐ │
  │ │ ACTION: `DISMISS`                                       │ │
  │ │ Content is compliant. Report status -> `DISMISSED`.     │ │
  │ ├─────────────────────────────────────────────────────────┤ │
  │ │ ACTION: `REMOVE_CONTENT`                                │ │
  │ │ Offending post/comment soft-deleted (`is_deleted=True`).│ │
  │ │ Report status -> `RESOLVED`. Notification to author.    │ │
  │ ├─────────────────────────────────────────────────────────┤ │
  │ │ ACTION: `LOCK_POST`                                     │ │
  │ │ Thread frozen (`is_locked=True`). New comments blocked. │ │
  │ ├─────────────────────────────────────────────────────────┤ │
  │ │ ACTION: `WARN_USER`                                     │ │
  │ │ Policy warning dispatched to author's notification feed.│ │
  │ ├─────────────────────────────────────────────────────────┤ │
  │ │ ACTION: `BAN_USER`                                      │ │
  │ │ Account suspended (`is_active=False`). Sessions revoked.│ │
  │ └─────────────────────────────────────────────────────────┘ │
  └─────────────────────────────────────────────────────────────┘
```

---

## 4.1 Queue Prioritization Algorithm

To ensure scam attempts and doxxing emergencies are resolved within minutes, reports are sorted dynamically by severity weight and report velocity.

### Severity Weight Matrix:
```python
REPORT_SEVERITY_WEIGHTS = {
    'SCAM': 100,                  # Urgent: immediate financial harm
    'PERSONAL_INFORMATION': 90,  # Urgent: immediate privacy/safety risk
    'HARASSMENT': 60,            # High: hostile behavior
    'MISINFORMATION': 50,        # High: rumor spreading
    'SPAM': 30,                  # Normal: commercial noise
    'ABUSIVE_CONTENT': 30,       # Normal: profanity
    'OTHER': 10,                 # Normal: miscellaneous
}
```

- **Report Velocity Multiplier:** If multiple distinct candidates report the same post within 1 hour, its priority score multiplies by `log2(report_count + 1)`, escalating the item to the top of the moderator queue.

---

## 4.2 Detailed Moderator Action Specifications

### 4.2.1 Action: `DISMISS`
- **Application:** Used when reported content does not violate community guidelines (e.g., a candidate expressing benign frustration about long wait times).
- **Effect:**
  - `Report.status` set to `DISMISSED`.
  - `Report.reviewed_by` and `Report.reviewed_at` updated.
  - Offending content remains publicly visible and untouched.
  - Reporter receives no negative sanction; no notification dispatched.

### 4.2.2 Action: `REMOVE_CONTENT` (Soft Deletion)
- **Application:** Used when a post or comment violates community policies.
- **Effect:**
  - Offending model field `is_deleted` set to `True`.
  - `Report.status` set to `RESOLVED`.
  - In-app notification dispatched to the content author:
    *"Your post/comment was removed by a moderator for violating community guidelines (Reason: {reason})."*

### 4.2.3 Action: `LOCK_POST`
- **Application:** Used when a discussion thread devolves into flame wars, brigading, or off-topic arguments, but the original post has value.
- **Effect:**
  - `Post.is_locked` set to `True`.
  - New comment submissions return `HTTP 403 Forbidden` (`POST_LOCKED`).
  - An amber banner renders on the post detail screen in the UI.

### 4.2.4 Action: `WARN_USER`
- **Application:** Used for first-time or minor infractions (e.g., posting referral links or mild incivility).
- **Effect:**
  - Dispatches a formal moderation warning notification to the candidate.
  - Increments candidate's internal infraction count in moderation logs.

### 4.2.5 Action: `BAN_USER`
- **Application:** Used for critical violations (scams, fee solicitation, doxxing, severe harassment, or repeated warnings).
- **Effect:**
  - `User.is_active` set to `False`.
  - All outstanding JWT refresh tokens bulk-blacklisted in Redis and DB.
  - All active `Device` FCM registrations deactivated.
  - User cannot log in, create posts, write comments, or vote.

---

# 5. Soft Deletion & Content Preservation Architecture

Hard deletion (`DELETE FROM community_post ...`) is strictly prohibited for user-generated content in the production environment.

```
  SOFT DELETION & TOMBSTONE ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────┐
  │ Database Row (`community_post` / `community_comment`)       │
  ├─────────────────────────────────────────────────────────────┤
  │ • id: UUIDv4                                                │
  │ • author_id: UUIDv4                                         │
  │ • title: "Original Post Title"                              │
  │ • body: "Original Post Body (Preserved for audit/legal)"    │
  │ • is_deleted: True <------------------- FLAG FLIPPED        │
  │ • created_at / updated_at                                   │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ DRF Serializer Layer (Public Community Consumption):        │
  │ If `obj.is_deleted`:                                        │
  │   title = "[This post has been removed by a moderator]"     │
  │   body  = "[This content is no longer available.]"          │
  │   author = None                                             │
  └─────────────────────────────────────────────────────────────┘
```

### Why Soft Deletion is Mandatory:
1. **Thread Continuity:** In hierarchical discussions, hard-deleting a parent comment would either cascade-delete all legitimate child replies or orphan replies, breaking UI navigation.
2. **Audit & Legal Evidence:** Retaining the original text in the database allows administrators to review moderation disputes and maintain compliance with legal notices.
3. **Reversal of Errors:** If content is mistakenly removed, a moderator can easily restore it by flipping `is_deleted = False`.

---

# 6. User Suspension & Ban Protocol

```
  USER BAN ENFORCEMENT TIMELINE
  ┌─────────────────────────────────────────────────────────────┐
  │ Moderator Triggers Ban Action in Admin Dashboard            │
  ├─────────────────────────────────────────────────────────────┤
  │ 1. Transaction BEGIN                                        │
  │    • `User.is_active = False`                               │
  │    • Create `AuditLog` entry (Moderator ID, Reason, IP)     │
  │ 2. Transaction COMMIT                                       │
  ├─────────────────────────────────────────────────────────────┤
  │ 3. Celery Task: Revoke Active Sessions                      │
  │    • Blacklist all user refresh tokens in DB & Redis        │
  │    • Mark all `Device.is_active = False` (Halt push alerts) │
  ├─────────────────────────────────────────────────────────────┤
  │ 4. Immediate Client State on Next API Request               │
  │    • Access token rejected (`USER_INACTIVE`) -> HTTP 401    │
  │    • UI displays: "Your account has been suspended."        │
  └─────────────────────────────────────────────────────────────┘
```

---

## 6.1 Temporary vs Permanent Bans

| Ban Level | Duration | Typical Violation | Restoration Path |
|---|---|---|---|
| **Warning Only** | 0 days | Mild off-topic spam, wrong category | Account remains active |
| **Temporary Suspension** | 7 Days | Aggressive tone, minor rumor spreading | Auto-reinstated after 7 days |
| **Permanent Ban** | Indefinite | Paid job scams, doxxing, fake TCS HR | Admin manual review only |

---

## 6.2 Banned User Experience & Edge Cases

When a banned user attempts to interact with the API:
- **Authentication Attempt (`POST /api/v1/auth/login/`):**
  ```json
  {
    "error": {
      "code": "ACCOUNT_SUSPENDED",
      "message": "This account has been suspended for violating community guidelines."
    }
  }
  ```
- **Authenticated Request with Unexpired Access Token:**
  - The JWT authentication class checks `user.is_active` on every request.
  - Returns `HTTP 401 Unauthorized` (`code: USER_INACTIVE`).
- **Public Browsing:**
  - A banned user may browse public community discussions as an unauthenticated visitor, but cannot log in or participate.

# 7. Administrator Announcement Management

Announcements allow platform administrators to broadcast critical updates, scam warnings, and community advisories directly to candidates.

```
  ANNOUNCEMENT LIFECYCLE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Admin Drafts │ ---> │ Admin Publishes         │ ---> │ 1. In-App Banner Active │
  │ Announcement │      │ `is_published = True`   │      │ 2. Top of Community Feed│
  └──────────────┘      └─────────────────────────┘      │ 3. Celery Broadcasts    │
                                                         │    FCM Push to All      │
                                                         └────────────┬────────────┘
                                                                      │
                                                         ┌────────────┴────────────┐
                                                         ▼                         ▼
                                                    Pinned Alert              Expires At:
                                                  (Sticky Top Bar)        Auto-Unpublished
```

---

## 7.1 Database Model: `Announcement` (`community/models.py`)

```python
import uuid
from django.db import models
from django.conf import settings

class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements'
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_published = models.BooleanField(default=False, db_index=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-published_at']
        indexes = [
            models.Index(fields=['is_published', 'is_pinned', '-published_at']),
        ]

    def __str__(self):
        return self.title
```

---

## 7.2 Push Broadcast Integration

When an announcement is published with `is_published = True`, a post-save signal or service call triggers:
```python
from notifications.tasks import broadcast_announcement_task

if announcement.is_published:
    broadcast_announcement_task.delay(str(announcement.id))
```

---

# 8. Anti-Spam, Automation & Automated Heuristics

To shield the human moderation queue from sheer volume, automated heuristics filter and flag low-hanging spam before it appears in public feeds.

```
  AUTOMATED SPAM & FRAUD FILTER PIPELINE
  ┌────────────────────────────────────────────────────────┐
  │ Incoming Post or Comment Submission                    │
  └───────────────────────────┬────────────────────────────┘
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │ 1. Rate Limiting Check (Redis)                         │
  │    • Max 5 posts / hour, Max 30 comments / hour        │
  ├────────────────────────────────────────────────────────┤
  │ 2. Blacklisted Keyword Heuristics                      │
  │    • Regex patterns targeting paid Telegram scams,     │
  │      fee extortion, or fake HR contact numbers         │
  ├────────────────────────────────────────────────────────┤
  │ 3. Repetition & Gibberish Detection                    │
  │    • Duplicate post detection within 60 minutes        │
  │    • Excessive character repetition (e.g. "aaaaa...")  │
  └───────────────────────────┬────────────────────────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
      [Clean Content]                   [Flagged Content]
      Published Instantly               • Block Submission OR
                                        • Create Automatic Report
                                          with reason `SPAM`
```

---

## 8.1 Automated Keyword Heuristics

Configured in `moderation/heuristics.py`:

```python
import re

SCAM_PATTERNS = [
    re.compile(r'(pay|fee|charge|money|rs\.?|inr)\s*(\d+|thousand)?\s*(for|to)\s*(joining|jl|offer)', re.I),
    re.compile(r'(telegram|whatsapp)\s*(group|contact|channel|link)?\s*(@|https?://|t\.me/|\+91)', re.I),
    re.compile(r'(guaranteed|direct|immediate)\s*(joining|placement|selection)', re.I),
    re.compile(r'(nextstep|ultimatix)\s*(password|login|credentials|otp)', re.I),
]

def evaluate_content_safety(title: str, body: str) -> dict:
    """
    Scans text against known malicious scam and phishing patterns.
    Returns flagged status and matched reason.
    """
    full_text = f"{title} {body}"
    for pattern in SCAM_PATTERNS:
        if pattern.search(full_text):
            return {
                "flagged": True,
                "reason": "SCAM_PATTERN_MATCH",
                "matched_pattern": pattern.pattern
            }
    return {"flagged": False, "reason": None}
```

---

## 8.2 Duplicate Submission Defense

A candidate cannot post identical titles or bodies within 60 minutes. An MD5 hash of `(author_id + title.strip().lower())` is stored in Redis with a 3600-second TTL. If a matching key exists, the request returns `HTTP 400 Bad Request` (`code: DUPLICATE_POST`).

---

# 9. Administrative Tools & Django Admin Interface

For the MVP, Django Admin serves as the primary control center for staff and community moderators, eliminating the need for a custom frontend admin portal.

```
  DJANGO ADMIN MODERATION INTERFACE
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Django Administration: Moderation Reports                                   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ Filter by: [Status: PENDING ▼]  [Reason: ALL ▼]  [Date: Last 7 Days ▼]      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ Action: [Resolve and Soft-Delete Content ▼] [Go] (3 selected)               │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ [ ] ID      | Target  | Reason | Status  | Reporter | Reported At | Actions │
  │ [x] #104    | POST    | SCAM   | PENDING | Cand #18 | 10 mins ago | [Review]│
  │ [ ] #103    | COMMENT | SPAM   | PENDING | Cand #42 | 45 mins ago | [Review]│
  │ [ ] #102    | POST    | OTHER  | PENDING | Cand #09 | 2 hours ago | [Review]│
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9.1 Custom Admin Configurations (`moderation/admin.py`)

```python
from django.contrib import admin
from django.utils import timezone
from .models import Report
from community.models import Post, Comment

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'target_type', 'reason', 'status', 'reporter', 'created_at', 'reviewed_by']
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['reporter__email', 'description', 'post__title', 'comment__body']
    readonly_fields = ['id', 'reporter', 'post', 'comment', 'created_at', 'updated_at']
    actions = ['dismiss_reports', 'soft_delete_and_resolve']

    def target_type(self, obj):
        return "POST" if obj.post else "COMMENT"
    target_type.short_description = "Target"

    @admin.action(description="Dismiss selected reports (No violation)")
    def dismiss_reports(self, request, queryset):
        queryset.update(
            status=Report.ReportStatus.DISMISSED,
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )

    @admin.action(description="Resolve reports and soft-delete reported content")
    def soft_delete_and_resolve(self, request, queryset):
        for report in queryset:
            if report.post:
                report.post.is_deleted = True
                report.post.save(update_fields=['is_deleted', 'updated_at'])
            elif report.comment:
                report.comment.is_deleted = True
                report.comment.save(update_fields=['is_deleted', 'updated_at'])
            report.status = Report.ReportStatus.RESOLVED
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save()
```

---

## 9.2 Protected Staff REST API Endpoints

In addition to Django Admin, staff members can resolve reports via standard REST APIs:
- `GET /api/v1/moderation/reports/?status=PENDING`: Lists pending reports.
- `POST /api/v1/moderation/reports/{id}/review/`: Executes `DISMISS`, `REMOVE_CONTENT`, `WARN_USER`, or `BAN_USER`.
- `POST /api/v1/moderation/users/{id}/ban/`: Suspends user and revokes tokens.
- `POST /api/v1/moderation/users/{id}/unban/`: Reinstates suspended account.

# 10. Data Retention, Privacy & Legal Compliance

Moderation data requires strict data governance to comply with global privacy standards while ensuring the platform maintains evidence of enforcement actions.

```
  MODERATION RETENTION & PRIVACY ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────┐
  │ Active Moderation Logs & Reports                            │
  ├─────────────────────────────────────────────────────────────┤
  │ Day 0 to Day 90:                                            │
  │ • Retain full `Report` record including reporter UUID       │
  │ • Retain original reported post/comment content             │
  │ • Retain moderator identity and review timestamps           │
  ├─────────────────────────────────────────────────────────────┤
  │ Day 90+: AUTOMATED DATA MINIMIZATION                        │
  │ • Anonymize `Report.reporter` (set to system dummy user)    │
  │ • Retain aggregate violation metrics (e.g. "SCAM", resolved)│
  │ • Permanently purge raw IP addresses associated with report │
  └─────────────────────────────────────────────────────────────┘
```

---

## 10.1 Intermediary Liability & Legal Safe Harbor

As an independent community forum hosting user-generated content:
1. **Notice-and-Takedown Protocol:** The platform operates on a reactive notice-and-takedown standard. When an authenticated user reports content for copyright violation, doxxing, or fraud, the report enters the priority queue with a target SLA of review within 24 hours.
2. **Third-Party Immunity:** The platform acts as an intermediary; user submissions represent the opinions of individual candidates and not the platform operators or Tata Consultancy Services.

---

# 11. Telemetry, Monitoring & Moderation Metrics

To maintain community safety and verify moderator responsiveness, the platform tracks four primary moderation Key Performance Indicators (KPIs):

```
  MODERATION TELEMETRY METRICS
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ Metric Name                     │ Type & Operational Goal                   │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `reports_submitted_total`       │ Counter: Reports created by category      │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `reports_pending_gauge`         │ Gauge: Current size of moderation backlog │
  │                                 │ (Goal: < 20 pending items)                │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `report_resolution_time_seconds`│ Histogram: Time from creation to action   │
  │                                 │ (Target SLA: Median < 6 hours)            │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ `action_distribution_total`     │ Counter: Breakdown by action taken        │
  │                                 │ (`DISMISS`, `REMOVE`, `LOCK`, `BAN`)      │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 11.1 Structured Logging for Moderation Events

Every resolution emits an auditable JSON log entry:

```json
{
  "timestamp": "2026-09-19T15:10:00Z",
  "logger": "moderation",
  "level": "NOTICE",
  "event": "MODERATION_ACTION_TAKEN",
  "moderator_id": "c1a2b3c4-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "report_id": "7b8e1f2a-9c3d-4e5f-a1b2-3c4d5e6f7a8b",
  "target_type": "POST",
  "target_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",
  "action": "REMOVE_CONTENT",
  "reason": "SCAM",
  "notes": "Paid Telegram joining letter link removed."
}
```

---

# 12. Testing Strategy & Automated Test Suite

All moderation endpoints, database constraints, and permission boundaries are tested using `pytest` and `pytest-django`.

```
  AUTOMATED TEST SUITE
  ┌─────────────────────────────────────────────────────────────┐
  │ tests/moderation/                                           │
  │ ├── test_report_creation_and_constraints.py                 │
  │ ├── test_duplicate_report_prevention.py                     │
  │ ├── test_moderation_permissions.py                          │
  │ ├── test_soft_deletion_serializer_masking.py                │
  │ └── test_user_ban_and_session_revocation.py                 │
  └─────────────────────────────────────────────────────────────┘
```

---

## 12.1 Automated Test Examples (`pytest-django`)

### 12.1.1 Testing XOR Target Constraint on `Report` Model
```python
import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from moderation.models import Report

@pytest.mark.django_db
def test_report_fails_if_both_post_and_comment_are_set(candidate_user, sample_post, sample_comment):
    with pytest.raises((ValidationError, IntegrityError)):
        report = Report.objects.create(
            reporter=candidate_user,
            post=sample_post,
            comment=sample_comment,
            reason=Report.ReportReason.SPAM
        )
```

### 12.1.2 Testing Regular Candidates Blocked from Moderation Queue
```python
from rest_framework import status

@pytest.mark.django_db
def test_regular_candidate_cannot_access_moderation_queue(authenticated_client):
    # Attempt to query pending reports as non-staff user
    res = authenticated_client.get("/api/v1/moderation/reports/")
    assert res.status_code == status.HTTP_403_FORBIDDEN
```

### 12.1.3 Testing Content Soft-Deletion Masks Body in Public Feed
```python
from rest_framework import status

@pytest.mark.django_db
def test_soft_deleted_post_displays_tombstone(api_client, sample_post):
    sample_post.is_deleted = True
    sample_post.save()

    res = api_client.get(f"/api/v1/posts/{sample_post.id}/")
    assert res.status_code == status.HTTP_200_OK
    assert res.data["is_deleted"] is True
    assert "removed" in res.data["body"].lower()
```

### 12.1.4 Testing Duplicate Pending Report Blocked
```python
from rest_framework import status

@pytest.mark.django_db
def test_duplicate_pending_report_returns_bad_request(authenticated_client, sample_post):
    # Submit first report
    res1 = authenticated_client.post("/api/v1/reports/", {
        "post_id": str(sample_post.id),
        "reason": "SPAM"
    }, format="json")
    assert res1.status_code == status.HTTP_201_CREATED

    # Submit second report on same target while first is PENDING
    res2 = authenticated_client.post("/api/v1/reports/", {
        "post_id": str(sample_post.id),
        "reason": "SPAM"
    }, format="json")
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert res2.data["error"]["code"] == "DUPLICATE_REPORT"
```

# 13. Implementation Checklist & Definition of Done

The moderation system is complete and production-ready when all of the following criteria are validated:

- [ ] **Database Constraints:** `report_exactly_one_target` XOR constraint active and enforced in PostgreSQL.
- [ ] **Report Model Created:** `Report` model with UUID, reporter FK, post/comment FKs, status, and reason choices.
- [ ] **Deduplication Active:** Active pending report check prevents duplicate submissions by the same user.
- [ ] **Throttling Active:** Report creation throttled to 10 requests per hour per user.
- [ ] **Soft Deletion Implemented:** `Post.is_deleted` and `Comment.is_deleted` implemented and masked in serializers.
- [ ] **Locking Mechanism Verified:** `Post.is_locked` prevents new comments with HTTP 403 response.
- [ ] **User Ban Workflow:** Banning an account sets `is_active=False`, blacklists refresh tokens, and disables FCM push alerts.
- [ ] **Django Admin Configured:** `ReportAdmin` equipped with bulk actions (Dismiss, Soft-Delete) and custom list filters.
- [ ] **Announcement Model Created:** `Announcement` model supports draft, published, and pinned states.
- [ ] **Heuristics Active:** Pre-save scanner checks against regex patterns for paid job scams and phishing links.
- [ ] **Audit Logging Active:** Structured logging captures all moderation enforcement actions with moderator IDs.
- [ ] **Automated Tests Pass:** 100% pass rate on pytest moderation test suite.
- [ ] **Legal Disclaimers Present:** Clear non-affiliation statements present across public boundaries.

---

# 14. AI Agent Implementation Directives for Moderation

When generating, updating, or refactoring moderation-related code, AI coding agents must strictly obey these directives:

1. **Never Hard Delete Content:** Always set `is_deleted = True`. Never call `.delete()` on `Post` or `Comment` instances in moderation views.
2. **Never Permit Dual Targets:** In `Report` creation, enforce that exactly one of `post` or `comment` is populated. Never allow both to be set.
3. **Always Check Staff Permissions:** Moderation review endpoints (`/api/v1/moderation/*`) must be strictly protected by `IsAdminUser` / `is_staff`. Never grant regular candidates access to the queue.
4. **Always Revoke Tokens on Ban:** When setting `user.is_active = False`, always blacklist outstanding JWT refresh tokens and deactivate `Device` records.
5. **Never Expose Internal Moderator Notes:** Moderator notes, reporter identities, and internal review timestamps must never be serialized to regular candidate endpoints.
6. **Protect Against Impersonation:** Block any candidate from registering or updating their display name to include "TCS", "HR", "Admin", or "Moderator".
