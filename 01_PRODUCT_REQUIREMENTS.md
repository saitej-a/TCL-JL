# TCS Joining Tracker — Product Requirements Document

**Document:** 01_PRODUCT_REQUIREMENTS.md  
**Product:** TCS Joining Tracker  
**Version:** 1.0 — MVP  
**Status:** Development Specification  

---

# 1. Product Overview

## 1.1 Product Name

**TCS Joining Tracker**

A community-driven web application for candidates who are waiting for their TCS joining letter, joining date, onboarding communication, or related updates.

## 1.2 Product Purpose

The application helps TCS candidates:

- Track their own recruitment and joining timeline.
- See how other candidates are progressing.
- Share joining-related updates.
- Discuss offer letters, joining letters, locations, onboarding, and related topics.
- Understand community-reported trends without relying on scattered WhatsApp, Telegram, Reddit, or social-media discussions.
- Receive notifications when relevant community activity occurs.

The product is **not an official TCS platform** and must clearly communicate that it is an independent community platform.

---

# 2. Problem Statement

Candidates who have completed TCS recruitment processes often have difficulty understanding what is happening after selection or offer issuance.

Information is commonly distributed across:

- WhatsApp groups
- Telegram groups
- Reddit
- LinkedIn
- YouTube comments
- Personal contacts
- Different candidate groups

This information is fragmented, difficult to search, and often lacks structured timelines.

Candidates need a centralized place where they can:

1. Record their recruitment timeline.
2. Compare their progress with voluntarily submitted community data.
3. Discuss updates.
4. Discover whether other candidates with similar profiles have received joining-related communication.
5. Receive important community updates.

---

# 3. Product Vision

Build a trusted community-powered platform where a TCS candidate can answer:

> "Where am I in the joining process, and what are other candidates experiencing?"

The platform should combine:

- Personal Timeline
- Community Discussions
- Anonymous Aggregated Data
- Notifications

---

# 4. MVP Goals

The MVP must provide:

## 4.1 Candidate Accounts

Users can:

- Register.
- Log in.
- Log out.
- Verify their email.
- Reset their password.
- Create a candidate profile.
- Edit their candidate information.
- Choose how their identity is displayed publicly.

## 4.2 Candidate Timeline

Users can record:

- Interview
- Selection
- Offer Letter
- Joining Readiness Survey
- Joining Letter
- Joining Date
- Joined
- Other

Example:

```text
Interview                 ✓
23 April 2026

Selection                 ✓
05 May 2026

Joining Readiness Survey ✓
15 May 2026

Joining Letter            ⏳
Pending

Joining Date              ⏳
Pending
```

Users must be able to update their timeline as their status changes.

---

# 5. Candidate Profile

Potential fields:

- Display name
- Batch
- Hiring type
- Interview date
- Interview center
- Region
- Joining location
- Current status
- Offer letter date
- Expected joining date
- Other timeline information

Initial hiring categories:

- Prime
- Digital
- Ninja
- Other

The implementation must allow categories to be extended later.

---

# 6. Privacy and Identity

Privacy is a core product requirement.

Users must not be required to expose their real identity publicly.

Public identity modes:

### Anonymous

```text
Anonymous Candidate
2025 • Digital
Hyderabad
```

### Display Name

```text
Sai T.
2025 • Digital
Hyderabad
```

The application must never publicly expose:

- Email address
- Phone number
- Password
- IP address
- FCM token
- Authentication credentials

unless explicitly required for an authenticated system operation.

---

# 7. Community

The application provides a community discussion system.

Initial categories:

- GENERAL
- JOINING_LETTER
- OFFER_LETTER
- JOINING_DATE
- LOCATION
- INTERVIEW
- DOCUMENTS
- DISCUSSION
- OTHER

Categories should be extensible.

---

# 8. Community Posts

A post contains:

- Author
- Title
- Body
- Category
- Created date
- Updated date
- Vote count
- Comment count
- Moderation status

Example:

```text
Anyone from 2025 Digital Hyderabad
received their JL?

Digital • 2025

Has anyone from Hyderabad who completed
the readiness survey received their joining
letter?

↑ 42       💬 18
```

---

# 9. Comments

Users can comment on posts and reply to comments.

Users can:

- Create comments.
- Reply to comments.
- Delete their own comments where permitted.
- Report inappropriate comments.

---

# 10. Voting

Users can vote on community posts.

The MVP supports:

- Upvote
- Remove vote

A user must not be able to create multiple votes for the same post.

The database must enforce this with an appropriate uniqueness constraint.

---

# 11. Community Timeline Analytics

The application aggregates voluntarily submitted candidate data.

Example:

```text
2025 Batch

Candidates tracked: 1,248

Interview completed       1,248
Offer Letter received    1,180
Readiness survey           940
Joining Letter             210
Joining Date                87
Joined                      42
```

These figures must be clearly identified as:

> **Community-reported data**

They must never be represented as official TCS statistics.

---

# 12. Timeline Filtering

Users should eventually be able to filter community data by:

- Batch
- Hiring type
- Region
- Interview center
- Joining location
- Status
- Time period

The MVP should implement only filters that can be supported reliably by available data.

---

# 13. Community Statistics

The dashboard may display:

- Total candidates tracked
- Candidates waiting for JL
- Candidates reporting JL received
- Candidates reporting joining date
- Candidates reporting joined
- Number of timeline updates
- Number of community posts
- Number of active candidates

All statistics must include appropriate context regarding their source and limitations.

---

# 14. Dashboard

After login, the candidate should see a personal dashboard.

Example:

```text
TCS Joining Tracker

Welcome back, Candidate

YOUR TIMELINE

Interview             ✓
Selection             ✓
Offer Letter          ✓
Readiness Survey      ✓
Joining Letter        ⏳
Joining Date          ⏳

COMMUNITY

1,248 candidates tracked
210 report receiving JL

LATEST UPDATES

Anyone from Hyderabad received JL?
Anyone got joining location?
New update from 2025 Digital candidates
```

---

# 15. Community Feed

The community feed provides:

- Latest posts
- Trending posts
- Most discussed posts
- Category filtering

Possible tabs:

- All
- Latest
- Trending
- JL Updates
- OL Updates
- Locations
- 2025

---

# 16. Search

The MVP supports basic search across:

- Post titles
- Post content
- Categories

Example:

```text
Search: "Hyderabad JL"
```

Advanced full-text search is not required for the first version.

---

# 17. Notifications

The MVP should support:

- Comment on your post
- Reply to your comment
- Vote on your post
- Mention where supported
- Important community announcement
- Timeline-related reminder

The system should be designed so browser push notifications can be supported.

---

# 18. Browser Push Notifications

The application may use Firebase Cloud Messaging for browser notifications.

Architecture:

```text
User
 ↓
Browser
 ↓
FCM Token
 ↓
Django
 ↓
Celery
 ↓
Firebase Cloud Messaging
 ↓
Browser Notification
```

A user may have multiple registered devices.

FCM tokens must not be stored as a single field on the main user record.

---

# 19. Announcements

Administrators can create important announcements.

Announcements can be:

- Published
- Unpublished
- Pinned
- Expired

---

# 20. Moderation

Users can report:

- Posts
- Comments

Initial report reasons:

- SPAM
- ABUSE
- HARASSMENT
- MISINFORMATION
- PERSONAL_INFORMATION
- SCAM
- OTHER

Administrators can:

- Review reports
- Delete posts
- Delete comments
- Lock posts
- Ban users
- Unban users
- Remove inappropriate content

---

# 21. Anti-Spam

The MVP should include:

- Rate limiting on post creation.
- Rate limiting on comment creation.
- Rate limiting on authentication endpoints.
- Server-side input validation.
- Maximum content length.
- Basic abuse protection.

Advanced anti-spam systems are out of scope.

---

# 22. Admin Dashboard

Administrators need a basic dashboard.

The admin should be able to view:

- Users
- Candidates
- Posts
- Comments
- Reports
- Announcements
- Timeline statistics

Django Admin may be used initially instead of creating a custom admin interface.

---

# 23. User Status

Initial statuses:

- WAITING
- JL_RECEIVED
- JOINING_DATE_RECEIVED
- JOINED
- WITHDRAWN
- UNKNOWN

The system should allow additional statuses later.

---

# 24. Timeline Event Model

Timeline events should be represented independently from the candidate profile.

Conceptually:

```text
Candidate
    │
    ├── Timeline Event
    ├── Timeline Event
    ├── Timeline Event
    └── Timeline Event
```

Each event contains:

- Event type
- Event date
- Optional description
- Created timestamp
- Updated timestamp

---

# 25. Data Accuracy

The platform is based on voluntarily submitted community data.

Therefore:

- User-submitted information must not automatically be treated as verified.
- Community statistics must be labeled accordingly.
- The application must not claim that community data represents all TCS candidates.
- The application must not imply that TCS has endorsed or provided the platform.
- Official TCS communication should only be represented as official when it comes from an identifiable official source or is clearly labeled as such.

---

# 26. Important Disclaimer

The website should contain:

> **TCS Joining Tracker is an independent community platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS). Information displayed on the platform is primarily user-submitted and may not represent official TCS information.**

This disclaimer should appear on:

- Footer
- About page
- Registration/onboarding flow where appropriate

---

# 27. Security Requirements

Required:

- Password hashing using Django's authentication system.
- CSRF protection.
- Authentication and authorization.
- Server-side validation.
- Secure cookies.
- Environment variables for secrets.
- No credentials committed to Git.
- File upload validation.
- Rate limiting.
- Protection against unauthorized object access.
- Proper permission checks on all APIs.

Sensitive user information must not be exposed through public APIs.

---

# 28. File Uploads

If posts support attachments, the MVP may allow limited:

- Images
- PDF documents

Restrictions:

- Maximum file size.
- Allowed MIME types.
- Allowed extensions.
- Server-side validation.
- Secure storage.

Executable files must never be accepted.

---

# 29. Mobile Responsiveness

The website must be fully responsive across:

- Mobile
- Tablet
- Desktop

The mobile experience is particularly important.

---

# 30. PWA

The application should be designed so it can eventually function as a Progressive Web App.

MVP PWA capabilities may include:

- Installable website
- App icon
- Responsive UI
- Service worker
- Browser notifications

Offline-first functionality is not required.

---

# 31. Performance Requirements

Initial target:

```text
~2,000 registered users
~500 daily active users
~20 concurrent users
```

The architecture should scale beyond these numbers without requiring a complete rewrite.

Requirements:

- Pagination for posts and comments.
- Database indexes for frequently queried fields.
- Efficient ORM queries.
- Avoid N+1 queries.
- Caching where useful.
- Background processing for notifications and expensive tasks.

---

# 32. Recommended MVP Architecture

The application should initially be a modular Django monolith.

Suggested structure:

```text
tcs_joining_tracker/

    config/

    accounts/
    candidates/
    timeline/
    community/
    notifications/
    moderation/
    analytics/

    manage.py
```

Backend:

- Python
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery

Frontend may use:

- React + Tailwind CSS

or a Django-based frontend if faster development is preferred.

The architecture should avoid unnecessary microservices.

---

# 33. Core Data Entities

The MVP should contain approximately:

```text
User
CandidateProfile
TimelineEvent
Device

Post
Comment
PostVote

Notification
Report
Announcement
```

The exact implementation belongs in:

`03_DATABASE_DESIGN.md`

---

# 34. MVP User Journey

```text
Landing Page
      ↓
Register
      ↓
Verify Email
      ↓
Create Candidate Profile
      ↓
Add Recruitment Timeline
      ↓
Dashboard
      ↓
View Community Updates
      ↓
Create / Read Posts
      ↓
Update Timeline
      ↓
Receive Notifications
```

The user should reach the dashboard quickly without completing unnecessary profile information.

---

# 35. Landing Page

Suggested messaging:

```text
Waiting for your TCS joining letter?

Track your journey.
See community-reported updates.
Connect with candidates in the same situation.

[Create Account]

[Explore Community]
```

The landing page may show community-level numbers where available. These must be identified as community data.

---

# 36. MVP Pages

Required pages:

```text
/
                Landing

/register
/login
/forgot-password

/dashboard

/profile
/profile/timeline

/community
/community/post/{id}
/community/create

/notifications

/about
/privacy
/terms
```

Admin:

```text
/admin/
```

The exact URL structure may change during implementation.

---

# 37. MVP Features — Must Have

```text
✓ User registration
✓ Login/logout
✓ Email verification
✓ Candidate profile
✓ Recruitment timeline
✓ Candidate status
✓ Community posts
✓ Categories
✓ Comments
✓ Comment replies
✓ Upvotes
✓ Basic search
✓ Community statistics
✓ Notifications
✓ Device/FCM token management
✓ Reporting
✓ Admin moderation
✓ Responsive UI
✓ Security protections
✓ Privacy controls
✓ Independent-platform disclaimer
```

---

# 38. MVP Features — Should Have

```text
○ Trending posts
○ Pinned posts
○ Announcements
○ Timeline filters
○ Advanced community analytics
○ PWA installation
○ Browser push notifications
○ Dark mode
```

---

# 39. MVP Features — Not Required

Do not implement initially:

```text
✗ Private messaging
✗ Global real-time chat
✗ Voice/video calls
✗ Native Android application
✗ Native iOS application
✗ Payments
✗ Subscription system
✗ Microservices
✗ Kubernetes
✗ Elasticsearch
✗ AI chatbot
✗ Automated TCS scraping
✗ Automatic email parsing
✗ Complex recommendation engine
✗ Job marketplace
```

---

# 40. Success Criteria

A new candidate must be able to:

1. Create an account.
2. Verify their email.
3. Create their candidate profile.
4. Add their recruitment timeline.
5. View their dashboard.
6. Browse community posts.
7. Create a post.
8. Comment on a post.
9. Reply to a comment.
10. Upvote a post.
11. Search posts.
12. Update their timeline.
13. Receive application notifications.
14. Report inappropriate content.
15. Control their public identity.

An administrator must be able to:

1. View users.
2. View candidates.
3. Moderate posts.
4. Moderate comments.
5. Review reports.
6. Ban users.
7. Publish announcements.
8. View basic statistics.

---

# 41. Product Principles

### Community first

The application exists to help candidates share useful information.

### Privacy first

Users should never need to expose sensitive personal information to participate.

### Data transparency

Clearly distinguish community-reported information from official information.

### Simplicity

Do not add complex features that do not directly improve the core experience.

### Mobile first

The majority of users should be able to comfortably use the application from a phone.

### Scalable foundation

The MVP should be simple but structured well enough to support future growth.

### No false certainty

Incomplete community reports must not be presented as definitive claims about TCS hiring or joining processes.

---

# 42. Future Product Direction

Possible post-MVP features:

- Private messaging
- Real-time community chat
- Advanced timeline analytics
- Regional communities
- Batch-specific communities
- Verified update system
- Official-source update aggregation
- Email notifications
- Telegram/WhatsApp integrations
- Native mobile applications
- Advanced moderation
- AI-powered search
- Community reputation system

These are outside the initial MVP scope.

---

# 43. Final MVP Definition

The MVP is a:

> **Privacy-conscious, community-driven TCS joining tracker that allows candidates to maintain their recruitment timeline, participate in discussions, and explore aggregated community-reported joining trends.**

The product should prioritize:

```text
Personal Timeline
        ↓
Community
        ↓
Aggregated Data
        ↓
Notifications
```

over secondary features such as real-time chat or private messaging.

The initial release should be a modular Django application with PostgreSQL as the primary database, Redis/Celery for background tasks, and browser/PWA support for notifications.

All user-generated statistics must be explicitly labeled as community-reported and must not be presented as official TCS information.
