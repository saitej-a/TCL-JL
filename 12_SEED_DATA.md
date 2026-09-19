# 12 — Development & Staging Seed Data Specification

# TCS Joining Tracker — Synthetic Seed Data, Persona Profiles & Populating Architecture

> **Document:** 12_SEED_DATA.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification & Data Fixtures Blueprint  
> **Target Framework:** Django 5.x Management Command (`python manage.py seed_community_data`)  
> **Target Database:** PostgreSQL 16+  
> **Execution Strategy:** 10 Phased Data Generations with Realistic Cohort Distributions  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

When designing, generating, and loading seed data into development, testing, and staging environments, the following invariants are strictly mandatory:
1. **Zero Real Candidate Personal Data:** Under no circumstances may real candidate email addresses, actual phone numbers, real full names, government ID numbers, or genuine TCS NextStep application credentials be used in seed datasets. All candidate data must be 100% synthetic and procedurally generated.
2. **Synthetic Domain Isolation:** All seed user email addresses must utilize the designated non-routable test domain `@example.com` or `@tracker.internal` (e.g., `candidate_01@example.com`).
3. **Realistic Psychological & Cohort Fidelity:** The synthetic dataset must accurately simulate the real-world anxieties, distribution curves, wait-time bottlenecks, and discussion topics of candidates waiting for their Joining Letter (JL) across diverse hiring streams (Prime, Digital, Ninja) and regions.
4. **Mandatory Non-Affiliation & Community Disclaimers:** All synthetic announcement posts, community feeds, and landing page metrics must clearly display the required non-affiliation disclaimer and community-reported attribution.

---

# 1. Document Overview & Phased Generation Architecture

## 1.1 Purpose & Scope

This specification provides the definitive dataset blueprint, persona definitions, chronological timeline sequences, community discussion fixtures, and the executable Django management command (`seed_community_data.py`) for the TCS Joining Tracker MVP.

Having high-fidelity, interconnected synthetic seed data is crucial for:
- Validating the Candidate Dashboard stepper bars and benchmark counters (`05_UI_UX_SPECIFICATION.md`).
- Exercising PostgreSQL aggregate queries and confirming the `<5` candidate privacy suppression threshold (`03_DATABASE_DESIGN.md` & `04_API_SPECIFICATION.md`).
- Testing feed pagination, sorting tabs (Latest vs Trending), and 1-level reply nesting (`community` app).
- Testing the administrative moderation queue, report triage workflows, and scam regex heuristics (`08_MODERATION.md`).
- Running automated end-to-end user journey tests and load benchmarks (`10_MVP_TASKS.md`).

---

## 1.2 Ten-Phase Seed Data Generation Architecture

The seed data generation is structured into **10 sequential phases** designed to maintain relational integrity and valid foreign-key dependencies:

```
  SEED DATA GENERATION SEQUENCE
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ PHASE 1: Administrative, Moderator & Staff Accounts                         │
  │ • 1 Superadmin, 2 Community Moderators, system bot account                 │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 2: Diverse Candidate Personas & User Accounts                         │
  │ • 50 synthetic candidate accounts with normalized lowercase emails          │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 3: Candidate Profiles & Public Identity Modes                         │
  │ • Batch distribution (2024, 2025, 2026), Streams (Prime, Digital, Ninja)   │
  │ • Regions (Telangana, Karnataka, Tamil Nadu, Maharashtra, West Bengal, NCR) │
  │ • Public modes (35 Anonymous, 15 Custom Display Names)                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 4: Chronological Recruitment Timeline Milestones                      │
  │ • ~220 realistic timestamped TimelineEvents showing natural wait intervals   │
  │ • Full lifecycle progressions from INTERVIEW to JOINED                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 5: Community Discussion Posts & Categories                            │
  │ • 25 categorized posts (JOINING_LETTER, OFFER, LOCATION, INTERVIEW, etc.)   │
  │ • Pinned threads, locked discussions, soft-deleted posts                    │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 6: Realistic Comment Threads & 1-Level Replies                        │
  │ • 80+ top-level comments and child replies showing peer support & answers   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 7: Organic Upvoting & Engagement Simulation                           │
  │ • 350+ unique `PostVote` records generating varied vote counts (0 to 48)    │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 8: Device Registrations & Push Notification History                   │
  │ • 60+ synthetic `Device` records (Web, Android, iOS) & Notification logs    │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 9: Content Moderation Reports & Policy Violation Test Cases           │
  │ • 8 realistic reports testing XOR constraints, scam heuristics, & triage    │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ PHASE 10: Executable Django Management Command Implementation               │
  │ • Standalone, idempotent `python manage.py seed_community_data` script      │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. Phase 1 — Administrative, Moderator & Staff Accounts

Phase 1 provisions the privileged accounts required to access Django Admin, review reported content, publish community announcements, and manage system operations.

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ PRIVILEGED SEED ACCOUNTS                                                    │
  ├──────────────────────┬──────────────────────┬───────────┬───────────────────┤
  │ Email Address        │ Default Password     │ Role      │ Privileges        │
  ├──────────────────────┼──────────────────────┼───────────┼───────────────────┤
  │ admin@tracker.internal│ SuperSecretAdmin123!│ Superadmin│ is_superuser=True │
  │                      │                      │           │ is_staff=True     │
  ├──────────────────────┼──────────────────────┼───────────┼───────────────────┤
  │ mod1@tracker.internal│ ModeratorPass123!    │ Moderator │ is_staff=True     │
  │                      │                      │           │ Review Reports    │
  ├──────────────────────┼──────────────────────┼───────────┼───────────────────┤
  │ mod2@tracker.internal│ ModeratorPass123!    │ Moderator │ is_staff=True     │
  │                      │                      │           │ Review Reports    │
  ├──────────────────────┼──────────────────────┼───────────┼───────────────────┤
  │ system@tracker.inter │ [Disabled / No PW]   │ System Bot│ System Broadcasts │
  └──────────────────────┴──────────────────────┴───────────┴───────────────────┘
```

### Specifications:
- **`admin@tracker.internal`:** Full superuser access to Django Admin at `/admin/`. Used for schema inspection, model audit, and emergency overrides.
- **`mod1@tracker.internal` & `mod2@tracker.internal`:** Staff accounts assigned to the "Moderators" permission group. Empowered to review reports (`/api/v1/moderation/reports/`), lock posts, soft-delete content, and publish announcements.
- **Password Hasher:** All privileged passwords are pre-hashed using Argon2id with default cost parameters.

# 3. Phase 2 & 3 — Candidate Personas, User Accounts & Profiles

To thoroughly test filtering, small-group privacy thresholds, regional breakdowns, and identity masking, the seed generator creates **50 distinct candidate accounts** reflecting the demographic and recruitment diversity of TCS candidates across India.

---

## 3.1 Candidate Cohort Distribution Ratios

```
  CANDIDATE COHORT MATRIX (50 SEED CANDIDATES)
  ┌───────────────────┬─────────────────────────────────────────────────────────┐
  │ Dimension         │ Distribution Breakdown                                  │
  ├───────────────────┼─────────────────────────────────────────────────────────┤
  │ Graduation Batch  │ • 2025 Batch: 35 Candidates (70% - Primary active group)│
  │                   │ • 2024 Batch: 10 Candidates (20% - Senior joined group) │
  │                   │ • 2026 Batch: 5 Candidates  (10% - Early selection group│
  ├───────────────────┼─────────────────────────────────────────────────────────┤
  │ Hiring Stream     │ • Digital : 25 Candidates (50%)                         │
  │                   │ • Ninja   : 18 Candidates (36%)                         │
  │                   │ • Prime   : 7 Candidates  (14%)                         │
  ├───────────────────┼─────────────────────────────────────────────────────────┤
  │ Geographic Region │ • Telangana / Hyderabad : 16 Candidates (32%)           │
  │                   │ • Karnataka / Bangalore : 12 Candidates (24%)           │
  │                   │ • Tamil Nadu / Chennai  : 8 Candidates  (16%)           │
  │                   │ • Maharashtra / Pune    : 7 Candidates  (14%)           │
  │                   │ • West Bengal / Kolkata : 4 Candidates  (8%)            │
  │                   │ • Goa / Panaji          : 3 Candidates  (6% - Privacy <5│
  ├───────────────────┼─────────────────────────────────────────────────────────┤
  │ Public Identity   │ • ANONYMOUS   : 35 Candidates (70% - Privacy First)     │
  │ Mode              │ • DISPLAY_NAME: 15 Candidates (30% - Custom Handles)    │
  ├───────────────────┼─────────────────────────────────────────────────────────┤
  │ Current Status    │ • WAITING_FOR_JOINING_LETTER : 22 Candidates (44%)      │
  │                   │ • READINESS_SURVEY           : 10 Candidates (20%)      │
  │                   │ • JOINING_LETTER_RECEIVED    : 8 Candidates  (16%)      │
  │                   │ • JOINED                     : 5 Candidates  (10%)      │
  │                   │ • OFFER_RECEIVED             : 3 Candidates  (6%)       │
  │                   │ • WITHDRAWN                  : 2 Candidates  (4%)       │
  └───────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 3.2 Exemplary Core Candidate Personas

### Persona 1: "Sai T." (Active Digital Waiting Candidate)
- **User:** `candidate_01@example.com` (UUID: `11111111-1111-4111-a111-000000000001`)
- **Profile:** Display Name: `Sai T.`, Public Mode: `DISPLAY_NAME`, Batch: `2025`, Hiring Stream: `DIGITAL`, Region: `Telangana`, Interview Center: `Hyderabad Gachibowli`, Preferred Location: `Hyderabad`, Current Status: `WAITING_FOR_JOINING_LETTER`.
- **Anxiety / Goal:** Completed readiness survey 120+ days ago. Highly active in discussions comparing Hyderabad vs. Bangalore letter release dates.

### Persona 2: "Anonymous Digital 2025" (Privacy-First Candidate)
- **User:** `candidate_02@example.com` (UUID: `11111111-1111-4111-a111-000000000002`)
- **Profile:** Display Name: `Rahul K.` (Hidden), Public Mode: `ANONYMOUS`, Batch: `2025`, Hiring Stream: `DIGITAL`, Region: `Karnataka`, Interview Center: `Bangalore Whitefield`, Preferred Location: `Bangalore`, Current Status: `WAITING_FOR_JOINING_LETTER`.
- **Public Handle:** Rendered as `Anonymous Candidate • 2025 • Digital • Karnataka`.

### Persona 3: "Ananya S." (Prime Batch Success Story)
- **User:** `candidate_03@example.com` (UUID: `11111111-1111-4111-a111-000000000003`)
- **Profile:** Display Name: `Ananya S.`, Public Mode: `DISPLAY_NAME`, Batch: `2025`, Hiring Stream: `PRIME`, Region: `Tamil Nadu`, Interview Center: `Chennai Siruseri`, Joining Location: `Chennai`, Current Status: `JOINING_LETTER_RECEIVED`.
- **Role in Feed:** Helpful contributor sharing timeline benchmarks for Prime stream candidates.

### Persona 4: "Anonymous Ninja 2024" (Successfully Joined Senior)
- **User:** `candidate_04@example.com` (UUID: `11111111-1111-4111-a111-000000000004`)
- **Profile:** Display Name: `Amit M.` (Hidden), Public Mode: `ANONYMOUS`, Batch: `2024`, Hiring Stream: `NINJA`, Region: `Maharashtra`, Interview Center: `Pune Sahyadri Park`, Joining Location: `Pune`, Current Status: `JOINED`.
- **Role in Feed:** Reassuring senior candidate explaining onboarding document verification and training schedules.

### Persona 5: "Privacy Test Cohort — Goa" (Intentional `<5` Suppression Test)
- **Users:** `candidate_48@example.com`, `candidate_49@example.com`, `candidate_50@example.com` (3 Candidates total).
- **Profile:** Region: `Goa`, Batch: `2025`, Hiring Stream: `DIGITAL`.
- **Purpose:** Specifically engineered to test that `GET /api/v1/analytics/batches/?region=Goa` triggers the `<5` privacy suppression alert without exposing individual candidate timelines.

# 4. Phase 4 — Chronological Recruitment Timeline Milestones

Phase 4 generates over **220 realistic `TimelineEvent` records** mapped to the 50 candidate profiles. Events follow natural recruitment intervals and maintain strict date logic.

```
  TYPICAL RECRUITMENT TIMELINE CHRONOLOGY
  ┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
  │ Milestone Event Type    │ Simulated Date (2025)   │ Realistic Delay Window  │
  ├─────────────────────────┼─────────────────────────┼─────────────────────────┤
  │ 1. `INTERVIEW`          │ 2024-10-15 to 2024-11-20│ Baseline start date     │
  │ 2. `SELECTION`          │ 2024-11-10 to 2024-12-15│ 15 - 30 days post-intv  │
  │ 3. `OFFER_LETTER`       │ 2024-12-05 to 2025-01-20│ 10 - 35 days post-select│
  │ 4. `READINESS_SURVEY`   │ 2025-04-10 to 2025-05-25│ Prior to graduation     │
  │ 5. `JOINING_LETTER`     │ 2025-07-15 to 2025-09-10│ 45 - 110 days post-surv │
  │ 6. `JOINING_DATE`       │ 2025-08-20 to 2025-10-15│ 15 - 45 days post-JL    │
  │ 7. `JOINED`             │ 2025-09-01 to 2025-10-15│ Actual onboarding date  │
  └─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

---

## 4.1 Concrete Timeline Progression Samples

### Candidate 01 (Sai T. — Waiting for JL):
1. `2024-10-22`: `INTERVIEW` — *"Technical & HR interview completed at Gachibowli center. Two coding questions on arrays and trees."*
2. `2024-11-14`: `SELECTION` — *"Received selection notification email for Digital stream."*
3. `2024-12-02`: `OFFER_LETTER` — *"Digital offer letter generated on NextStep. Accepted on portal."*
4. `2025-05-15`: `READINESS_SURVEY` — *"Joining readiness survey submitted. Preferred locations: Hyderabad, Bangalore. Selected ready for immediate onboarding."*
*(Current status: WAITING_FOR_JOINING_LETTER — 126 days waiting)*

### Candidate 03 (Ananya S. — Received JL):
1. `2024-10-18`: `INTERVIEW` — *"Prime stream technical round. Focus on system design and Python."*
2. `2024-11-05`: `SELECTION` — *"Shortlisted for Prime hiring stream."*
3. `2024-11-28`: `OFFER_LETTER` — *"Prime offer accepted on portal."*
4. `2025-04-20`: `READINESS_SURVEY` — *"Readiness survey 1 completed."*
5. `2025-07-28`: `JOINING_LETTER` — *"Joining letter received for Chennai location! Reporting date set for October 15th."*
*(Current status: JOINING_LETTER_RECEIVED)*

### Candidate 04 (Amit M. — Successfully Joined 2024 Batch):
1. `2023-09-15`: `INTERVIEW` — *"Ninja interview completed."*
2. `2023-10-10`: `SELECTION` — *"Selection mail received."*
3. `2023-11-05`: `OFFER_LETTER` — *"Offer letter accepted."*
4. `2024-04-12`: `READINESS_SURVEY` — *"Readiness survey completed."*
5. `2024-06-25`: `JOINING_LETTER` — *"Joining letter issued for Pune Sahyadri Park."*
6. `2024-07-20`: `JOINING_DATE` — *"Onboarding date confirmed for August 12, 2024."*
7. `2024-08-12`: `JOINED` — *"Completed Day 1 virtual induction and badge pickup."*
*(Current status: JOINED)*

---

# 5. Phase 5 & 6 — Community Discussions, Forum Posts & Comment Trees

Phase 5 seeds **25 high-fidelity discussion posts** spanning the full category taxonomy, while Phase 6 populates **80+ top-level comments and 1-level replies**.

```
  COMMUNITY POST CATEGORY DISTRIBUTION (25 SEED POSTS)
  ┌───────────────────────┬────────────┬────────────────────────────────────────┐
  │ Category Code         │ Post Count │ Representative Topics & Anxieties      │
  ├───────────────────────┼────────────┼────────────────────────────────────────┤
  │ `JOINING_LETTER`      │ 6 Posts    │ Batch JL release status, wait times    │
  │ `JOINING_DATE`        │ 4 Posts    │ Reporting dates, batch postponements   │
  │ `OFFER`               │ 3 Posts    │ Offer letter acceptance on NextStep    │
  │ `LOCATION`            │ 4 Posts    │ Preferred vs allocated city changes    │
  │ `INTERVIEW`           │ 2 Posts    │ Interview experiences & center reviews │
  │ `TCS_PROCESS`         │ 2 Posts    │ BGC documents, readiness survey rounds │
  │ `GENERAL`             │ 2 Posts    │ General candidate peer support         │
  │ `HELP`                │ 1 Post     │ NextStep portal technical login issues │
  │ `ANNOUNCEMENT`        │ 1 Post     │ Moderator pinned scam warning advisory │
  └───────────────────────┴────────────┴────────────────────────────────────────┘
```

---

## 5.1 Exemplary Community Discussion Fixtures

### Thread 1: High-Activity Discussion (`JOINING_LETTER`)
- **Title:** *"Has anyone from 2025 Digital Hyderabad received their JL yet?"*
- **Author:** `candidate_01@example.com` (`Sai T.`)
- **Category:** `JOINING_LETTER` | **Votes:** 42 | **Pinned:** False | **Locked:** False
- **Body:** *"I completed my joining readiness survey on May 15th with Hyderabad preference and declared immediate availability. NextStep portal still shows 'Offer Accepted' without updates. Are others from Hyderabad experiencing the same delay, or have letters started rolling out?"*
- **Comments (Excerpt):**
  - Comment #1 by `candidate_02` (`Anonymous Candidate • 2025 • Digital • Karnataka`):
    *"Same situation here in Bangalore. Survey submitted on May 18th, portal has been quiet ever since."*
    - Reply #1.1 by `candidate_03` (`Ananya S. • 2025 • Prime • Chennai`):
      *"Chennai batch 1 was released on July 28th. Usually Hyderabad follows 2 to 3 weeks later according to last year's pattern."*
  - Comment #2 by `candidate_04` (`Anonymous Candidate • 2024 • Ninja • Maharashtra`):
    *"As a 2024 batch senior, this delay is completely normal. Our batch waited roughly 75 to 90 days after survey before the first wave of letters appeared. Don't panic!"*

### Thread 2: Pinned Administrative Scam Advisory (`ANNOUNCEMENT`)
- **Title:** *"IMPORTANT: Warning Regarding Fake TCS Joining Letter Solicitations & Scams"*
- **Author:** `mod1@tracker.internal` (`Platform Moderator`)
- **Category:** `ANNOUNCEMENT` | **Votes:** 128 | **Pinned:** True | **Locked:** True
- **Body:** *"We have received reports of fraudulent Telegram channels and WhatsApp groups claiming to sell 'expedited TCS joining letters' or offering placement guarantees for money. TCS never charges any fee for training, onboarding, or joining letter issuance. Please report any user soliciting fees or sharing paid group links immediately."*
- **Comments:** Locked (Zero comments permitted).

### Thread 3: Location Allocation Inquiry (`LOCATION`)
- **Title:** *"Chances of getting preferred joining location vs reallocation?"*
- **Author:** `candidate_05` (`Anonymous Candidate • 2025 • Digital • Pune`)
- **Category:** `LOCATION` | **Votes:** 18 | **Comments:** 6
- **Body:** *"I selected Pune as 1st preference and Mumbai as 2nd. If Pune seats fill up, do they reassign to Bangalore or Chennai? What have previous batches experienced?"*

### Thread 4: Edge Case Fixtures (Moderation Testing)
- **Soft-Deleted Post:** Title: `"[This post has been removed by a moderator]"` | Body: `"[This content is no longer available]"` | `is_deleted = True`.
- **Locked Off-Topic Discussion:** Title: *"Comparison: TCS Digital vs Accenture vs Infosys"* | `is_locked = True` | Comment input disabled.

# 6. Phase 7, 8 & 9 — Upvotes, Devices, Notifications & Moderation Fixtures

---

## 6.1 Phase 7 — Organic Upvoting Simulation (`PostVote`)

The seed command populates **350+ `PostVote` records** enforcing the database unique constraint `UNIQUE(user, post)`:
- Pinned announcement post: **128 upvotes**.
- High-interest Hyderabad JL thread: **42 upvotes**.
- Bangalore location trends thread: **29 upvotes**.
- Niche interview preparation thread: **6 upvotes**.
- Zero-vote new posts (simulating realistic long-tail engagement).

---

## 6.2 Phase 8 — Devices & Notifications Simulation

### 6.2.1 Device Registrations (`Device`)
- Generates **60+ synthetic device records** simulating candidates accessing from diverse platforms:
  - 35 Chrome on Windows 10/11
  - 15 Safari on iOS / iPhone PWA
  - 10 Chrome on Android / Samsung
- Tokens are synthetic strings: `mock_fcm_token_candidate_{id}_{platform}_{random_hash}`.

### 6.2.2 Notification History (`Notification`)
- Generates **75+ in-app notification records** distributed across active candidates:
  - `REPLY`: *"Sai T. replied to your comment on 'Has anyone from 2025 Digital received JL?'"* (`is_read=False`)
  - `VOTE_MILESTONE`: *"Your post reached 40 upvotes in the community tracker"* (`is_read=True`)
  - `ANNOUNCEMENT`: *"Pinned Announcement: Warning Regarding Fake TCS Joining Letter Scams"* (`is_read=True`)
  - `TIMELINE_REMINDER`: *"Reminder: Have you received any updates on your recruitment portal?"* (`is_read=False`)

---

## 6.3 Phase 9 — Moderation Reports & Policy Violation Test Cases (`Report`)

Phase 9 seeds **8 realistic moderation reports** in the `Report` table to demonstrate and test the moderator queue at `/admin/moderation/reports/` and `/api/v1/moderation/reports/`:

```
  SEED MODERATION TEST CASES
  ┌────┬─────────┬───────────────┬─────────┬─────────────────────────────────────┐
  │ ID │ Target  │ Reason        │ Status  │ Context & Violation Description     │
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #1 │ Post    │ `SCAM`        │ PENDING │ User posted: "Guaranteed TCS joining│
  │    │         │               │         │ letters for Rs 5,000 via Telegram"  │
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #2 │ Comment │ `PERSONAL_INFO│ PENDING │ User shared candidate's personal    │
  │    │         │               │         │ phone number and email in thread.   │
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #3 │ Post    │ `MISINFORMAT` │ PENDING │ Claimed "TCS canceled all 2025      │
  │    │         │               │         │ Digital offers" without evidence.   │
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #4 │ Comment │ `HARASSMENT`  │ PENDING │ Abusive, vulgar language directed at│
  │    │         │               │         │ a candidate asking an interview q.  │
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #5 │ Post    │ `SPAM`        │ RESOLVED│ Commercial course affiliate link;   │
  │    │         │               │         │ soft-deleted by moderator 1 day ago.│
  ├────┼─────────┼───────────────┼─────────┼─────────────────────────────────────┤
  │ #6 │ Post    │ `OTHER`       │ DISMISSE│ Candidate complained about wait;    │
  │    │         │               │         │ reviewed and dismissed as compliant.│
  └────┴─────────┴───────────────┴─────────┴─────────────────────────────────────┘
```

---

# 7. Phase 10 — Django Management Command Implementation

The entire 10-phase seed data generation is packaged into an idempotent, robust Django management command:

```text
python manage.py seed_community_data [--flush]
```

```python
# apps/common/management/commands/seed_community_data.py
import uuid
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from accounts.models import User
from candidates.models import CandidateProfile
from timeline.models import TimelineEvent
from community.models import Post, Comment, PostVote, Announcement
from notifications.models import Notification, Device, NotificationPreference
from moderation.models import Report

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds database with high-fidelity, synthetic community candidate data."

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Wipe existing candidate, timeline, and community data before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing TCS Joining Tracker seed sequence..."))

        if options['flush']:
            self.stdout.write(self.style.WARNING("Flushing existing community records..."))
            Report.objects.all().delete()
            Notification.objects.all().delete()
            Device.objects.all().delete()
            PostVote.objects.all().delete()
            Comment.objects.all().delete()
            Post.objects.all().delete()
            Announcement.objects.all().delete()
            TimelineEvent.objects.all().delete()
            CandidateProfile.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # -------------------------------------------------------------
        # 1. Privileged Accounts
        # -------------------------------------------------------------
        admin_user, _ = User.objects.get_or_create(
            email="admin@tracker.internal",
            defaults={"is_staff": True, "is_superuser": True, "is_verified": True}
        )
        admin_user.set_password("SuperSecretAdmin123!")
        admin_user.save()

        mod1, _ = User.objects.get_or_create(
            email="mod1@tracker.internal",
            defaults={"is_staff": True, "is_superuser": False, "is_verified": True}
        )
        mod1.set_password("ModeratorPass123!")
        mod1.save()

        # -------------------------------------------------------------
        # 2 & 3. Candidate Users & Profiles
        # -------------------------------------------------------------
        CITIES = [
            ("Telangana", "Hyderabad", "Hyderabad Gachibowli"),
            ("Karnataka", "Bangalore", "Bangalore Whitefield"),
            ("Tamil Nadu", "Chennai", "Chennai Siruseri"),
            ("Maharashtra", "Pune", "Pune Sahyadri Park"),
            ("West Bengal", "Kolkata", "Kolkata Gitobitan"),
            ("Goa", "Panaji", "Goa Center"),
        ]

        candidates = []
        for i in range(1, 51):
            email = f"candidate_{i:02d}@example.com"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"is_active": True, "is_verified": True}
            )
            user.set_password("CandidatePass123!")
            user.save()

            # Assign cohort attributes
            if i <= 35:
                batch = "2025"
            elif i <= 45:
                batch = "2024"
            else:
                batch = "2026"

            if i <= 25:
                stream = "DIGITAL"
            elif i <= 43:
                stream = "NINJA"
            else:
                stream = "PRIME"

            # Regional allocation
            if i >= 48:
                region, city, center = ("Goa", "Panaji", "Goa Center") # Small-group privacy test cohort
            else:
                region, city, center = random.choice(CITIES[:-1])

            public_mode = "DISPLAY_NAME" if (i % 3 == 0) else "ANONYMOUS"
            display_name = f"Candidate {i}" if public_mode == "DISPLAY_NAME" else ""

            # Assign realistic status
            if batch == "2024":
                status = "JOINED" if i % 2 == 0 else "JOINING_LETTER_RECEIVED"
            elif batch == "2026":
                status = "OFFER_RECEIVED"
            else:
                status = random.choice([
                    "WAITING_FOR_JOINING_LETTER",
                    "WAITING_FOR_JOINING_LETTER",
                    "READINESS_SURVEY",
                    "JOINING_LETTER_RECEIVED"
                ])

            profile, _ = CandidateProfile.objects.update_or_create(
                user=user,
                defaults={
                    "display_name": display_name,
                    "public_identity_mode": public_mode,
                    "batch": batch,
                    "hiring_type": stream,
                    "region": region,
                    "interview_center": center,
                    "joining_location": city if "JOIN" in status else None,
                    "current_status": status,
                }
            )
            candidates.append((user, profile))

        self.stdout.write(self.style.SUCCESS("Seeded 50 candidate profiles."))
```

```python
        # -------------------------------------------------------------
        # 4. Recruitment Timeline Milestones
        # -------------------------------------------------------------
        event_count = 0
        for user, profile in candidates:
            # Baseline interview date
            base_year = 2023 if profile.batch == "2024" else 2024
            intv_date = date(base_year, 10, random.randint(1, 28))
            TimelineEvent.objects.create(
                candidate=profile,
                event_type="INTERVIEW",
                event_date=intv_date,
                description=f"Technical & HR interview at {profile.interview_center}."
            )
            event_count += 1

            if profile.current_status != "REGISTERED":
                select_date = intv_date + timedelta(days=random.randint(15, 30))
                TimelineEvent.objects.create(
                    candidate=profile,
                    event_type="SELECTION",
                    event_date=select_date,
                    description=f"Received selection communication for {profile.hiring_type} stream."
                )
                event_count += 1

                offer_date = select_date + timedelta(days=random.randint(10, 25))
                TimelineEvent.objects.create(
                    candidate=profile,
                    event_type="OFFER_LETTER",
                    event_date=offer_date,
                    description="Official offer letter generated on portal. Accepted terms."
                )
                event_count += 1

            if profile.current_status in ["READINESS_SURVEY", "WAITING_FOR_JOINING_LETTER", "JOINING_LETTER_RECEIVED", "JOINING_DATE_RECEIVED", "JOINED"]:
                survey_date = date(base_year + 1, 5, random.randint(5, 25))
                TimelineEvent.objects.create(
                    candidate=profile,
                    event_type="READINESS_SURVEY",
                    event_date=survey_date,
                    description="Joining readiness survey submitted with preferred locations."
                )
                event_count += 1

            if profile.current_status in ["JOINING_LETTER_RECEIVED", "JOINING_DATE_RECEIVED", "JOINED"]:
                jl_date = survey_date + timedelta(days=random.randint(45, 90))
                TimelineEvent.objects.create(
                    candidate=profile,
                    event_type="JOINING_LETTER",
                    event_date=jl_date,
                    description=f"Joining letter issued for {profile.joining_location or profile.region}."
                )
                event_count += 1

            if profile.current_status == "JOINED":
                join_date = jl_date + timedelta(days=random.randint(20, 40))
                TimelineEvent.objects.create(
                    candidate=profile,
                    event_type="JOINED",
                    event_date=join_date,
                    description="Completed virtual onboarding and Day 1 induction."
                )
                event_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {event_count} chronological timeline events."))

        # -------------------------------------------------------------
        # 5. Announcements & Pinned Advisories
        # -------------------------------------------------------------
        Announcement.objects.create(
            created_by=admin_user,
            title="IMPORTANT: Warning Regarding Fake TCS Joining Letter Solicitations & Scams",
            body="We have received reports of fraudulent Telegram channels claiming to sell expedited TCS joining letters. TCS never charges any fee for training, onboarding, or joining letter issuance. Please report any user soliciting money immediately.",
            is_published=True,
            is_pinned=True,
            published_at=timezone.now() - timedelta(days=2)
        )

        # -------------------------------------------------------------
        # 6. Community Discussion Posts
        # -------------------------------------------------------------
        POST_TEMPLATES = [
            ("Has anyone from 2025 Digital Hyderabad received their JL yet?",
             "I completed my joining readiness survey on May 15th with Hyderabad preference. NextStep portal still shows Offer Accepted without updates. Looking for other candidates in same batch.",
             "JOINING_LETTER", candidates[0][0]),
            ("Joining location allocation trends for Prime batch 2025",
             "Seeing reports that Bangalore and Chennai are receiving priority dates. Has anyone selected for Prime in Pune received letters?",
             "LOCATION", candidates[2][0]),
            ("Survey 2 rollout status discussion",
             "Did anyone receive the second readiness survey? What options were asked regarding relocation?",
             "TCS_PROCESS", candidates[4][0]),
            ("Document verification requirements for Day 1 onboarding",
             "For those who recently joined, what original documents are mandatory to carry? Is medical certificate format strict?",
             "DOCUMENTS", candidates[3][0]),
            ("Comparison: Background verification timelines after offer",
             "How long does BGC normally take after submitting documents on NextStep portal?",
             "TCS_PROCESS", candidates[5][0]),
        ]

        posts = []
        for title, body, cat, author in POST_TEMPLATES:
            post = Post.objects.create(
                author=author,
                title=title,
                body=body,
                category=cat,
                created_at=timezone.now() - timedelta(hours=random.randint(2, 48))
            )
            posts.append(post)

        # -------------------------------------------------------------
        # 7. Comment Trees & One-Level Replies
        # -------------------------------------------------------------
        c1 = Comment.objects.create(
            post=posts[0],
            author=candidates[1][0],
            body="Same situation here in Bangalore. Survey submitted on May 18th, portal has been quiet."
        )
        Comment.objects.create(
            post=posts[0],
            author=candidates[2][0],
            parent=c1,
            body="Chennai batch 1 was released on July 28th. Hyderabad usually follows within 2 to 3 weeks!"
        )
        Comment.objects.create(
            post=posts[0],
            author=candidates[3][0],
            body="As a 2024 batch senior, this delay is completely normal. Our batch waited roughly 75 to 90 days."
        )

        # -------------------------------------------------------------
        # 8. Post Upvoting Simulation
        # -------------------------------------------------------------
        # Seed 42 upvotes for post 0
        voters = [c[0] for c in candidates[:42]]
        for v in voters:
            PostVote.objects.get_or_create(user=v, post=posts[0])

        # -------------------------------------------------------------
        # 9. Moderation Reports Fixtures
        # -------------------------------------------------------------
        # Create a scam test post
        scam_post = Post.objects.create(
            author=candidates[10][0],
            title="Guaranteed TCS joining letters within 2 weeks - Contact Telegram @tcs_fast_jl",
            body="Skip the waiting queue. Pay Rs 5,000 for direct internal HR referral and immediate onboarding date.",
            category="GENERAL"
        )
        Report.objects.create(
            reporter=candidates[0][0],
            post=scam_post,
            reason="SCAM",
            description="Clear recruitment scam soliciting fee via Telegram.",
            status="PENDING"
        )

        self.stdout.write(self.style.SUCCESS("Community discussions, comments, votes, and reports seeded successfully."))
        self.stdout.write(self.style.SUCCESS("==> Seed Data Loading Sequence Complete!"))
```

---

# 8. Automated Verification & Quality Assurance of Seed Dataset

After executing `python manage.py seed_community_data`, the following test assertions must pass:

```python
# tests/test_seed_data_integrity.py
import pytest
from django.contrib.auth import get_user_model
from candidates.models import CandidateProfile
from community.models import Post, PostVote
from moderation.models import Report

User = get_user_model()

@pytest.mark.django_db
def test_seed_dataset_integrity():
    # 1. Verify User & Profile counts
    assert User.objects.filter(is_superuser=False).count() >= 50
    assert CandidateProfile.objects.count() >= 50

    # 2. Verify Small-Group Cohort (<5) exists for Goa
    goa_count = CandidateProfile.objects.filter(region="Goa").count()
    assert goa_count == 3  # Triggers privacy suppression

    # 3. Verify Upvotes on Primary Thread
    main_post = Post.objects.filter(title__icontains="Hyderabad").first()
    assert main_post is not None
    assert PostVote.objects.filter(post=main_post).count() == 42

    # 4. Verify Pending Scam Report
    scam_report = Report.objects.filter(reason="SCAM", status="PENDING").first()
    assert scam_report is not None
    assert scam_report.post is not None
    assert scam_report.comment is None  # XOR target check
```

---

# 9. AI Coding Agent Directives for Seed Data

When creating, updating, or running seed scripts, AI coding agents must strictly obey these directives:

1. **Zero Real PII:** Never use real personal phone numbers, emails, employee numbers, or passwords in seed data. Always use procedurally generated handles and `@example.com` or `@tracker.internal` emails.
2. **Deterministic & Idempotent:** Always implement the `--flush` flag using `@transaction.atomic` to ensure safe, repeatable data wipes without dangling foreign keys.
3. **Realistic Wait-Time Distributions:** Never seed zero-wait timelines (e.g. interview on Monday and joining on Tuesday). Accurately simulate realistic 45- to 120-day wait periods.
4. **Preserve Privacy Invariant:** Always include small cohorts (<5 candidates) in testing seeds to ensure privacy suppression logic is tested and functioning in analytics views.
5. **Non-Affiliation Compliance:** All seed announcements and public headers must feature the official TCS non-affiliation disclaimer.
