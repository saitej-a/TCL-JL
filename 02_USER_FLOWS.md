# TCS Joining Tracker — User Flows

**Document:** 02_USER_FLOWS.md  
**Product:** TCS Joining Tracker  
**Version:** 1.0 — MVP  
**Status:** Development Specification  

---

# 1. Purpose

This document defines the primary user journeys and application flows for the TCS Joining Tracker MVP.

The purpose is to give developers and AI coding agents a precise understanding of:

- How users move through the application.
- What actions are available at each stage.
- Which pages are involved.
- What authentication is required.
- What happens after each action.
- What edge cases should be handled.

The flows in this document should be implemented consistently across the frontend and backend.

---

# 2. User Roles

The MVP has three logical user roles.

## 2.1 Visitor

A user who is not authenticated.

Can:

- View landing page.
- View public product information.
- View public community content where enabled.
- Search public community posts where enabled.
- Register.
- Login.
- View About, Privacy, and Terms pages.

Cannot:

- Create posts.
- Comment.
- Vote.
- Create a candidate profile.
- Modify timeline data.
- Access private notifications.

---

## 2.2 Candidate

An authenticated user.

Can:

- Manage candidate profile.
- Manage recruitment timeline.
- View dashboard.
- Create posts.
- Comment.
- Reply.
- Upvote.
- Search community content.
- Report content.
- Manage notification preferences.
- Register browser/device notifications.
- Control public identity.
- View community statistics.

---

## 2.3 Administrator

An authenticated administrator.

Can:

- Manage users.
- Manage candidate data where required for moderation.
- Moderate posts.
- Moderate comments.
- Review reports.
- Ban/unban users.
- Lock posts.
- Publish announcements.
- View platform statistics.

The initial implementation may use Django Admin rather than a custom administration interface.

---

# 3. Global Navigation Flow

## 3.1 Visitor Navigation

```text
Landing
   │
   ├── Register
   │
   ├── Login
   │
   ├── Community
   │
   ├── About
   │
   ├── Privacy
   │
   └── Terms
```

---

## 3.2 Authenticated Candidate Navigation

```text
Dashboard
   │
   ├── My Timeline
   │
   ├── Profile
   │
   ├── Community
   │     ├── Feed
   │     ├── Post Detail
   │     └── Create Post
   │
   ├── Notifications
   │
   └── Account Settings
```

---

# 4. First-Time User Journey

The primary onboarding flow is:

```text
Landing Page
      ↓
Register
      ↓
Email Verification
      ↓
Candidate Profile Setup
      ↓
Timeline Setup
      ↓
Dashboard
```

The onboarding process should be short and should not require unnecessary information.

---

# 5. Landing Page Flow

## 5.1 Entry

User opens:

```text
/
```

The landing page displays:

- Product name.
- Short description.
- Primary call-to-action.
- Community statistics where available.
- Explanation that the platform is independent from TCS.
- Links to login and registration.

Example:

```text
Waiting for your TCS joining letter?

Track your journey.
See community-reported updates.
Connect with candidates in the same situation.

[Create Account]
[Explore Community]
```

---

## 5.2 Visitor Actions

### Create Account

```text
Landing
   ↓
Register
```

### Login

```text
Landing
   ↓
Login
```

### Explore Community

```text
Landing
   ↓
Community
```

### Learn More

```text
Landing
   ↓
About
```

---

# 6. Registration Flow

## 6.1 Registration

User selects:

```text
Create Account
```

System displays registration form.

Required information should be minimal.

Suggested fields:

- Email
- Password
- Password confirmation

Optional onboarding information can be collected later.

---

## 6.2 Validation

Backend validates:

- Email format.
- Email uniqueness.
- Password requirements.
- Password confirmation.
- Rate limits.

If invalid:

```text
Registration Form
      ↓
Validation Error
      ↓
Show Field Errors
      ↓
User Corrects Form
```

If valid:

```text
Registration
      ↓
Create User
      ↓
Send Verification Email
      ↓
Show Verification Required Page
```

---

# 7. Email Verification Flow

User receives verification email.

```text
Verification Email
        ↓
Verification Link
        ↓
Backend validates token
        ↓
Email verified
        ↓
Continue onboarding
```

If the token is:

- Valid → verify account.
- Expired → show expired-token message.
- Invalid → show invalid-token message.
- Already used → show already-verified state.

The user should have an option to request a new verification email.

---

# 8. Login Flow

```text
Login
  ↓
Enter Email + Password
  ↓
Validate Credentials
  ↓
Authenticated
  ↓
Dashboard
```

If credentials are invalid:

```text
Login
  ↓
Invalid Credentials
  ↓
Display Generic Error
```

Do not reveal whether a specific email address exists.

If the user has not verified their email:

```text
Login
  ↓
Verification Required
  ↓
Resend Verification
```

---

# 9. Logout Flow

```text
Authenticated User
       ↓
Logout
       ↓
Invalidate Session / Token
       ↓
Landing Page
```

All authenticated-only pages must require authentication again after logout.

---

# 10. Password Reset Flow

```text
Login
   ↓
Forgot Password
   ↓
Enter Email
   ↓
Send Reset Email
   ↓
Open Reset Link
   ↓
Set New Password
   ↓
Password Updated
   ↓
Login
```

The system should show a generic response after requesting a reset so that account existence is not unnecessarily exposed.

---

# 11. Candidate Profile Setup

After email verification, a new candidate is directed to profile setup.

```text
Email Verified
      ↓
Profile Setup
```

Suggested information:

```text
Display Name
Batch
Hiring Type
Region
Interview Center
Interview Date
Current Status
```

Fields should be categorized as:

- Required
- Optional

The user should be able to skip non-essential information and complete it later.

---

# 12. Public Identity Selection

During onboarding, users select how they appear publicly.

Options:

```text
Anonymous
Display Name
```

Default:

```text
Anonymous
```

Example:

```text
Anonymous Candidate
2025 • Digital
Hyderabad
```

or:

```text
Sai T.
2025 • Digital
Hyderabad
```

Private account information remains hidden regardless of the selected display mode.

---

# 13. Timeline Setup Flow

After profile setup:

```text
Profile Setup
      ↓
Timeline Setup
```

The user can add known recruitment events.

Example:

```text
Interview
23 Apr 2026

Selection
05 May 2026

Offer Letter
05 May 2026

Joining Readiness Survey
15 May 2026
```

Events that have not happened should not be required.

The user can save partial information.

---

# 14. Adding a Timeline Event

```text
My Timeline
    ↓
Add Event
    ↓
Select Event Type
    ↓
Enter Date
    ↓
Optional Description
    ↓
Save
```

Event types:

```text
INTERVIEW
SELECTION
OFFER_LETTER
READINESS_SURVEY
JOINING_LETTER
JOINING_DATE
JOINED
OTHER
```

After saving:

```text
Save
 ↓
Validate
 ↓
Create TimelineEvent
 ↓
Update Candidate Status if applicable
 ↓
Return to Timeline
```

---

# 15. Editing a Timeline Event

```text
Timeline
   ↓
Select Event
   ↓
Edit
   ↓
Update Fields
   ↓
Save
   ↓
Timeline Updated
```

The user can edit their own timeline events.

Users cannot edit another candidate's timeline.

---

# 16. Deleting a Timeline Event

```text
Timeline
   ↓
Select Event
   ↓
Delete
   ↓
Confirmation
   ↓
Delete Event
   ↓
Refresh Timeline
```

A confirmation step should be used to prevent accidental deletion.

---

# 17. Candidate Status Update

The candidate's current status can be updated.

Initial statuses:

```text
WAITING
JL_RECEIVED
JOINING_DATE_RECEIVED
JOINED
WITHDRAWN
UNKNOWN
```

Example:

```text
Waiting for Joining Letter
        ↓
JL Received
        ↓
Joining Date Received
        ↓
Joined
```

Status changes should optionally create corresponding timeline events.

The exact automatic relationship between status and timeline events should be defined in the database/API specification.

---

# 18. Dashboard Flow

After successful login:

```text
Login
  ↓
Dashboard
```

Dashboard contains:

```text
Candidate Status
Timeline
Community Summary
Latest Community Posts
Notifications
```

Example:

```text
Your Status
WAITING FOR JOINING LETTER

Timeline
✓ Interview
✓ Selection
✓ Offer Letter
✓ Readiness Survey
⏳ Joining Letter
⏳ Joining Date

Community
1,248 candidates tracked
210 reported JL received

Latest Updates
...
```

---

# 19. Community Feed Flow

Candidate selects:

```text
Community
```

Flow:

```text
Community
    ↓
Load Posts
    ↓
Apply Optional Filters
    ↓
Display Paginated Feed
```

Users can browse:

- Latest
- Trending
- Category
- Search results

Posts should be paginated.

---

# 20. Creating a Post

```text
Community
   ↓
Create Post
   ↓
Enter Title
   ↓
Select Category
   ↓
Enter Body
   ↓
Optional Attachment
   ↓
Submit
```

Backend:

```text
Validate Authentication
        ↓
Validate Input
        ↓
Validate Attachment
        ↓
Apply Rate Limit
        ↓
Create Post
        ↓
Return Post
        ↓
Redirect to Post Detail
```

---

# 21. Post Validation

Before publishing:

- Title must not be empty.
- Body must not be empty.
- Content length must be within limits.
- Category must be valid.
- Attachment must satisfy allowed type and size.
- User must not exceed posting rate limits.

If validation fails:

```text
Create Post
    ↓
Validation Errors
    ↓
Display Errors
```

The entered content should be preserved where practical.

---

# 22. Viewing a Post

```text
Community Feed
      ↓
Select Post
      ↓
Post Detail
```

Post detail displays:

- Title
- Body
- Category
- Author display identity
- Created date
- Vote count
- Comments
- Replies
- Report option

---

# 23. Upvote Flow

```text
Post
 ↓
Click Upvote
 ↓
Backend checks authentication
 ↓
Check existing vote
 ↓
Create or remove vote
 ↓
Return updated count
```

A user can have at most one active vote per post.

If the user clicks again:

```text
Existing Vote
     ↓
Remove Vote
```

---

# 24. Comment Flow

```text
Post Detail
     ↓
Write Comment
     ↓
Submit
     ↓
Validate
     ↓
Create Comment
     ↓
Display Comment
```

The comment author can delete their own comment where permitted.

---

# 25. Reply Flow

```text
Comment
   ↓
Reply
   ↓
Enter Reply
   ↓
Submit
   ↓
Create Child Comment
   ↓
Display Reply
```

Replies should maintain the relationship to the parent comment.

---

# 26. Comment Notification Flow

When a user comments on another user's post:

```text
New Comment
     ↓
Identify Post Owner
     ↓
Create Notification
     ↓
Queue Push Notification if enabled
```

When a user replies to a comment:

```text
New Reply
     ↓
Identify Parent Comment Owner
     ↓
Create Notification
```

Users should not receive unnecessary notifications for their own actions.

---

# 27. Search Flow

```text
Community
   ↓
Search Box
   ↓
Enter Query
   ↓
Submit
   ↓
Backend Search
   ↓
Paginated Results
```

Search initially covers:

- Post title
- Post body
- Category where appropriate

If no results:

```text
No matching posts found.
```

---

# 28. Category Filter Flow

```text
Community
   ↓
Select Category
   ↓
Request Filtered Posts
   ↓
Display Results
```

Example:

```text
[All]
[Joining Letter]
[Offer Letter]
[Location]
[Interview]
[Documents]
```

Filters should work together with pagination and search where technically appropriate.

---

# 29. Trending Posts Flow

If enabled:

```text
Community
   ↓
Trending
   ↓
Backend calculates ranking
   ↓
Display trending posts
```

The ranking algorithm should remain simple for MVP.

Possible signals:

- Recent activity
- Votes
- Comment count

Do not build a complex recommendation system.

---

# 30. Community Statistics Flow

The dashboard or analytics page requests aggregated candidate data.

```text
Statistics Page
      ↓
Select Filters
      ↓
Backend Aggregation
      ↓
Return Aggregated Results
      ↓
Render Charts / Counters
```

Example filters:

```text
Batch: 2025
Hiring Type: Digital
Region: Telangana
```

Results must clearly state:

> Community-reported data based on available user submissions.

---

# 31. Statistics Privacy Flow

The analytics system must avoid exposing individual candidates.

Do not return:

```text
Candidate A received JL
Candidate B is waiting
Candidate C joined
```

Instead return aggregates:

```text
Waiting: 720
JL Received: 210
Joining Date Received: 87
Joined: 42
```

For very small filtered populations, the system should consider suppressing or broadening results to reduce the risk of identifying individuals.

---

# 32. Notification Center Flow

Candidate selects:

```text
Notifications
```

System displays:

- Unread notifications.
- Read notifications.
- Notification timestamp.
- Related object where applicable.

Example:

```text
Sai T. replied to your comment
5 minutes ago

New community announcement
2 hours ago
```

Selecting a notification should navigate to the relevant page where appropriate.

---

# 33. Mark Notification as Read

```text
Notification
   ↓
Open
   ↓
Mark as Read
   ↓
Navigate to Related Content
```

The user may also have:

```text
Mark all as read
```

---

# 34. Browser Push Registration Flow

When browser notifications are enabled:

```text
Candidate
   ↓
Enable Notifications
   ↓
Browser Permission
   ↓
Permission Granted
   ↓
Generate / Retrieve FCM Token
   ↓
Send Token to Django
   ↓
Register Device
```

Backend stores the device separately from the user.

Conceptually:

```text
User
 ├── Device
 ├── Device
 └── Device
```

If permission is denied, the application should continue functioning normally.

---

# 35. Device Token Refresh Flow

FCM tokens can change.

```text
Browser
   ↓
Token Changed
   ↓
Send New Token
   ↓
Update Device Record
```

Inactive or invalid tokens should eventually be disabled.

---

# 36. Report Post Flow

```text
Post
 ↓
Report
 ↓
Select Reason
 ↓
Optional Details
 ↓
Submit
 ↓
Create Report
 ↓
Show Confirmation
```

Example reasons:

```text
SPAM
ABUSE
HARASSMENT
MISINFORMATION
PERSONAL_INFORMATION
SCAM
OTHER
```

Users should not be able to create unlimited duplicate reports for the same content.

---

# 37. Report Comment Flow

Same basic process:

```text
Comment
 ↓
Report
 ↓
Select Reason
 ↓
Submit
 ↓
Create Report
```

---

# 38. Moderation Flow

Administrator:

```text
Admin
 ↓
Reports
 ↓
Select Report
 ↓
Review Content
 ↓
Choose Action
```

Possible actions:

```text
Dismiss
Delete Content
Lock Post
Warn User
Ban User
```

The final MVP can initially implement:

- Dismiss
- Delete
- Lock
- Ban

---

# 39. User Ban Flow

```text
Admin
 ↓
User
 ↓
Ban
 ↓
Confirmation
 ↓
User Status = BANNED
```

A banned user should not be able to:

- Create posts.
- Comment.
- Vote.
- Perform other restricted community actions.

Authentication behavior for banned accounts should be defined consistently.

---

# 40. Announcement Flow

Administrator:

```text
Admin
 ↓
Create Announcement
 ↓
Enter Title
 ↓
Enter Content
 ↓
Optional Expiry
 ↓
Publish
```

Published announcement:

```text
Announcement
 ↓
Visible to users
 ↓
Optional notification
```

Pinned announcements can appear prominently in the community.

---

# 41. Profile Editing Flow

```text
Profile
 ↓
Edit
 ↓
Update Fields
 ↓
Validate
 ↓
Save
 ↓
Profile Updated
```

Users can modify:

- Display name
- Public identity mode
- Batch
- Hiring type
- Region
- Interview center
- Joining location
- Other supported fields

Sensitive authentication information should have separate flows.

---

# 42. Privacy Settings Flow

```text
Profile / Settings
       ↓
Privacy
       ↓
Choose Public Identity
       ↓
Save
```

The user should be able to switch between:

```text
Anonymous
Display Name
```

The change should apply to future and existing public content according to the product's privacy policy.

---

# 43. Account Deletion Flow

MVP should provide a safe account deletion process.

```text
Settings
   ↓
Delete Account
   ↓
Warning / Confirmation
   ↓
Confirm
   ↓
Account Deletion / Anonymization
   ↓
Logout
   ↓
Landing Page
```

The exact retention/anonymization rules should be defined in the Privacy requirements.

Community content should not accidentally expose deleted users' private information.

---

# 44. Public Community Access

Visitors may be allowed to browse public community content without an account.

If public access is enabled:

```text
Visitor
 ↓
Community
 ↓
View Posts
```

But actions requiring identity must redirect to authentication:

```text
Visitor
 ↓
Comment / Vote / Create Post
 ↓
Login / Register
```

The final implementation should choose one consistent public-access policy.

---

# 45. Unauthorized Access Flow

If an unauthenticated user accesses a protected endpoint:

```text
Protected Endpoint
       ↓
Authentication Check
       ↓
Not Authenticated
       ↓
401 / Redirect to Login
```

If an authenticated user attempts to access another user's private resource:

```text
Authorization Check
       ↓
Permission Denied
       ↓
403
```

The API must not leak whether unauthorized private resources exist.

---

# 46. Error Handling Flow

All major flows should handle:

- Network errors.
- Validation errors.
- Authentication errors.
- Permission errors.
- Rate-limit errors.
- Server errors.

Frontend should display user-friendly messages.

Do not expose raw Django/Python stack traces to users.

---

# 47. Empty States

Every list should have an appropriate empty state.

Examples:

### No posts

```text
No community posts yet.

Be the first to start a discussion.
[Create Post]
```

### No notifications

```text
You're all caught up.
```

### No timeline events

```text
Your timeline is empty.

Add your first recruitment event.
[Add Event]
```

### No search results

```text
No posts found for your search.
```

---

# 48. Loading States

The frontend should provide loading feedback for:

- Dashboard
- Community feed
- Post detail
- Comments
- Notifications
- Statistics
- Profile
- Timeline

Use skeletons/spinners where appropriate.

Avoid blank screens during API requests.

---

# 49. Mobile Flow

The primary mobile flow should be:

```text
Open Website
      ↓
Landing
      ↓
Login/Register
      ↓
Dashboard
      ↓
Timeline / Community
```

Navigation should remain accessible on small screens.

A bottom navigation pattern may be considered:

```text
Home | Community | Timeline | Notifications | Profile
```

---

# 50. PWA Installation Flow

If PWA support is implemented:

```text
User visits website
       ↓
Browser detects installable PWA
       ↓
Show install prompt / UI
       ↓
User installs
       ↓
Application available from device home screen
```

Installation must remain optional.

---

# 51. Complete New Candidate Flow

The primary happy path is:

```text
                    LANDING
                       │
                       ▼
                  CREATE ACCOUNT
                       │
                       ▼
                EMAIL VERIFICATION
                       │
                       ▼
                PROFILE SETUP
                       │
                       ▼
                TIMELINE SETUP
                       │
                       ▼
                    DASHBOARD
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
       TIMELINE     COMMUNITY    NOTIFICATIONS
          │            │
          │            ├── View Post
          │            ├── Create Post
          │            ├── Comment
          │            ├── Reply
          │            └── Vote
          │
          └── Update Events
```

---

# 52. Complete Returning Candidate Flow

```text
Login
  ↓
Dashboard
  ↓
Check Timeline
  ↓
Check Community
  ↓
Read Updates
  ↓
Update Personal Timeline
  ↓
Receive / Read Notifications
```

---

# 53. Important Edge Cases

The implementation must consider:

## Registration

- Existing email.
- Invalid email.
- Weak password.
- Expired verification link.
- Already verified account.
- Excessive registration attempts.

## Login

- Wrong credentials.
- Unverified account.
- Banned account.
- Rate limiting.

## Posts

- Empty title.
- Empty body.
- Excessive content.
- Invalid attachment.
- Oversized attachment.
- User is banned.
- Rate limit exceeded.

## Comments

- Empty comment.
- Excessive content.
- Post deleted.
- Post locked.
- User banned.
- Rate limit exceeded.

## Voting

- Already voted.
- Vote removed.
- Post deleted.
- Unauthorized request.

## Timeline

- Invalid event type.
- Invalid date.
- Duplicate event if duplicates are not allowed.
- Event belongs to another user.
- Deleted candidate account.

## Notifications

- Invalid device token.
- Expired token.
- Permission denied.
- Notification target deleted.

---

# 54. AI Agent Implementation Rules for User Flows

When implementing these flows, the AI coding agent must:

1. Follow the flows in this document.
2. Do not invent new product behavior without documenting it.
3. Keep frontend and backend behavior consistent.
4. Validate permissions on the backend.
5. Never rely solely on frontend validation.
6. Never expose private user data through APIs.
7. Use reusable components for repeated UI patterns.
8. Use consistent error handling.
9. Implement loading and empty states.
10. Write tests for important happy paths and edge cases.
11. Keep business logic out of presentation components where possible.
12. Do not introduce unnecessary dependencies.
13. Do not implement features explicitly marked out of scope.
14. Update the relevant documentation when behavior changes.

---

# 55. MVP Completion Flow

The MVP is ready for initial release when this complete journey works:

```text
Visitor
   ↓
Register
   ↓
Verify Email
   ↓
Create Candidate Profile
   ↓
Create Timeline
   ↓
Dashboard
   ↓
Browse Community
   ↓
Create Post
   ↓
Receive Comment
   ↓
Reply
   ↓
Receive Notification
   ↓
Update Timeline
   ↓
View Community Statistics
   ↓
Manage Profile / Privacy
```

At the same time, administrators must be able to:

```text
Admin Login
    ↓
View Users
    ↓
Review Reports
    ↓
Moderate Content
    ↓
Ban / Unban Users
    ↓
Publish Announcements
    ↓
View Basic Statistics
```

---

# 56. Definition of Done

A user flow is considered complete only when:

- The UI exists.
- The backend endpoint exists.
- Authentication/authorization is enforced.
- Validation exists.
- Error states are handled.
- Loading states are handled where applicable.
- Empty states are handled where applicable.
- Database changes are implemented.
- Tests cover the important path.
- The behavior matches this document.

The AI agent must not mark a feature complete merely because the UI has been created.

---

# 57. Related Documents

This document should be used together with:

```text
01_PRODUCT_REQUIREMENTS.md
03_DATABASE_DESIGN.md
04_API_SPECIFICATION.md
05_UI_UX_SPECIFICATION.md
06_AUTH_SECURITY.md
07_NOTIFICATION_SYSTEM.md
08_MODERATION.md
09_PROJECT_ARCHITECTURE.md
10_MVP_TASKS.md
11_AI_AGENT_RULES.md
12_SEED_DATA.md
```

These documents together form the MVP implementation specification.
