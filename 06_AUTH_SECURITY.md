# 06 — Authentication & Security Specification

# TCS Joining Tracker — Authentication, Authorization & Security Architecture

> **Document:** 06_AUTH_SECURITY.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification  
> **Target Framework:** Django 5.x + Django REST Framework 3.15+ + djangorestframework-simplejwt  
> **Target Database:** PostgreSQL 16+ (with `CITEXT` extension) + Redis 7+ (Rate limiting & Blacklisting)  
> **Cryptography Standards:** Argon2id / PBKDF2-SHA256, HMAC-SHA256, AES-256-GCM, TLS 1.3  

---

## Important Product Boundary & Non-Affiliation Mandate

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

From an information security and privacy perspective, this boundary enforces strict technical invariants:
1. **Zero Credential Association:** The application must **never** solicit, accept, store, validate, or proxy official TCS credentials, including NextStep portal passwords, Ultimatix credentials, Employee Numbers, or internal TCS intranet tokens.
2. **Anonymous Candidature Protection:** Candidates legitimately fear disciplinary action, offer revocation, or workplace prejudice if their active inquiries or timeline complaints are linked back to their official TCS recruitment record. Privacy and anonymity are **core safety guarantees**, not merely convenience features.
3. **Independent Security Boundary:** All user accounts, password hashes, session tokens, and discussion histories belong strictly to the independent TCS Joining Tracker database and must never interface with TCS corporate infrastructure.

---

# 1. Document Overview, Threat Environment, & Security Principles

## 1.1 Purpose & Scope

This specification defines the complete end-to-end security architecture for the TCS Joining Tracker MVP. It establishes the technical standards, protocols, cryptographic primitives, permission frameworks, rate-limiting policies, and mitigation recipes necessary to secure the backend API (`04_API_SPECIFICATION.md`), database entities (`03_DATABASE_DESIGN.md`), and frontend user interfaces (`05_UI_UX_SPECIFICATION.md`).

Every security rule defined herein is authoritative and must be strictly enforced on the server. Client-side checks are exclusively for user convenience and form UX; they provide **zero** security guarantees.

---

## 1.2 The Threat Landscape & Adversary Model

The application operates in a unique threat environment characterized by the following threat vectors:

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         THREAT LANDSCAPE & ACTORS                           │
  ├───────────────────────┬─────────────────────────────────────────────────────┤
  │ Threat Actor          │ Motivations, Capabilities & Attack Vectors          │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 1. Malicious Spammers │ • Spreading scam Telegram/WhatsApp recruitment links│
  │    & Fraudsters       │ • Promising fake "paid joining letter expediting"   │
  │                       │ • Automated credential stuffing & bulk bot posts    │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 2. Curious / Hostile  │ • De-anonymizing candidates to expose their identity│
  │    Third Parties      │ • Scraping candidate regions, batches, and wait times│
  │                       │ • Correlating anonymous handles with real candidates│
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 3. Disgruntled Users  │ • Vote manipulation & comment brigading             │
  │    & Trolls           │ • Harassing other candidates or spreading false dates│
  │                       │ • Attempting horizontal privilege escalation (IDOR) │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 4. Automated Crawlers │ • Scraping public API endpoints                     │
  │    & Botnets          │ • Exhausting application resources (DoS / DDoS)     │
  │                       │ • Harvesting candidate email addresses              │
  └───────────────────────┴─────────────────────────────────────────────────────┘
```

---

## 1.3 Core Security Principles

All engineering implementations must adhere to five fundamental security axioms:

1. **Zero Trust Architecture:** Every request is authenticated, authorized, validated, and rate-limited at the application gateway. Never trust client headers, client-submitted IDs, or internal network perimeters.
2. **Least Privilege (PoLP):** Users, API endpoints, background Celery workers, and database roles possess only the minimum permissions required to perform their discrete function.
3. **Defense in Depth:** Multiple independent security barriers (e.g., firewall -> Nginx rate limiting -> Django middleware -> DRF permission class -> Model clean -> Database constraint). If any single layer fails, subsequent layers prevent compromise.
4. **Fail Securely:** When an error, timeout, or exception occurs, the system fails into a safe, restricted state (e.g., denying access, closing database transactions, invalidating tokens) rather than failing open.
5. **Privacy by Default:** Sensitive personal identifiable information (PII) is never collected unless strictly necessary. Public serializers must default to complete redaction of private attributes.

---

# 2. Identity, Account Management, & Lifecycle

## 2.1 Custom User Model Security (`accounts/models.py`)

The platform rejects Django's default `django.contrib.auth.models.User` to eliminate architectural vulnerabilities (such as sequential integer ID enumeration and username/email ambiguity).

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                            CUSTOM USER ENTITY                               │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ • id: UUIDv4 (Primary Key, cryptographically pseudo-random)                 │
  │ • email: CITEXT / Normalized Case-Insensitive String (Unique Index)         │
  │ • password: Hashed String (Argon2id / PBKDF2-SHA256)                        │
  │ • is_verified: Boolean (Default: False)                                     │
  │ • is_active: Boolean (Default: True)                                        │
  │ • is_staff: Boolean (Default: False) — Administrative Portal Access         │
  │ • is_superuser: Boolean (Default: False)                                    │
  │ • date_joined: DateTime (UTC)                                               │
  │ • created_at: DateTime (UTC)                                                │
  │ • updated_at: DateTime (UTC)                                                │
  └─────────────────────────────────────────────────────────────────────────────┘
```

### Architectural Security Requirements:
1. **UUIDv4 Primary Keys:** All `User` records utilize randomly generated UUIDv4 keys. This stops sequential ID enumeration, horizontal account crawling, and competitor metrics harvesting.
2. **Separation of Authentication and Candidate Data:** The `User` model contains **only** credentials and authentication flags. Recruitment profile details (`batch`, `hiring_type`, `region`, `interview_date`) are strictly isolated in `CandidateProfile` with a 1-to-1 foreign key.
3. **Administrative Access Lockdown:** `is_staff` and `is_superuser` fields must never be included in any user-facing serializer or self-registration payload. They can only be toggled via Django CLI (`python manage.py createsuperuser`) or direct administrator action in Django Admin.

---

## 2.2 Case-Insensitive Email Handling & Normalization

Email addresses are the primary login credential and must be protected against canonicalization bypass attacks:

### Attack Vectors:
- **Duplicate Account Confusion:** `Candidate@example.com` vs `candidate@example.com`.
- **Unicode Spoofing:** Homoglyph characters designed to impersonate existing accounts.
- **Sub-addressing Spreading:** Unlimited account generation via `user+tag@gmail.com`.

### Technical Defense Specification:
1. **Normalization Pipeline:**
   - Strip leading and trailing whitespace.
   - Convert email domain and local part to lowercase: `email.strip().lower()`.
   - Validate syntax against RFC 5322 standard using Django's `EmailValidator`.
2. **Database Invariant:**
   - Utilize PostgreSQL's `CITEXT` column type or a PostgreSQL unique functional index:
     ```sql
     CREATE UNIQUE INDEX unique_user_email_idx ON accounts_user (LOWER(email));
     ```
   - Guarantees database-level enforcement of uniqueness regardless of ORM bypasses.

---

## 2.3 Password Security & Hashing Architecture

Plaintext passwords must never touch disk, logs, caches, or API responses.

```
  PASSWORD SUBMISSION & HASHING PIPELINE
  ┌──────────────┐      ┌────────────────────────┐      ┌─────────────────────────┐
  │ Candidate    │ ---> │ Django Password        │ ---> │ Argon2id / PBKDF2       │
  │ Plaintext PW │      │ Validation Pipeline    │      │ Cryptographic Hashing   │
  └──────────────┘      └────────────────────────┘      └─────────────────────────┘
                                   │                                 │
                                   ▼                                 ▼
                        Reject if weak / common           Store in PostgreSQL DB:
                        (Length, Entropy, Dictionaries)   `argon2$argon2id$v=19$...`
```

### 2.3.1 Password Hashing Configuration
Django's password hasher hierarchy is configured in `settings.py`:

```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]
```

- **Primary Algorithm:** `Argon2id` (winner of the Password Hashing Competition). Provides superior resistance to GPU/ASIC brute-force attacks via memory-hard computational complexity.
- **Parameters:** Memory cost: 64MB (65536 KB), Time cost (iterations): 3 rounds, Parallelism: 2 threads.
- **Fallback Algorithm:** `PBKDF2PasswordHasher` with minimum 600,000 iterations (OWASP recommended standard for 2024/2026).

### 2.3.2 Password Complexity & Entropy Validation
The application enforces strict validation rules via `AUTH_PASSWORD_VALIDATORS`:

```python
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {'user_attributes': ('email',)},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},  # Minimum 10 characters for robust entropy
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.CustomPasswordComplexityValidator',
    },
]
```

- **`CustomPasswordComplexityValidator` Requirements:**
  - Must contain at least one uppercase ASCII character (`A-Z`).
  - Must contain at least one lowercase ASCII character (`a-z`).
  - Must contain at least one numeric digit (`0-9`).
  - Must contain at least one special character (`!@#$%^&*()_+-=[]{}|;:,.<>?`).
  - Maximum password length: **128 characters** (prevents Long Password Denial of Service attacks on hashing algorithms).

---

## 2.4 Registration Security & Account Enumeration Defense

Registration endpoints (`POST /api/v1/auth/register/`) are frequently targeted for credential harvesting and account enumeration.

### Threat Defense Rules:
1. **Generic Responses on Collisions:**
   - If a registration request arrives for an existing email address, the API **must not** return an explicit error stating `"Email already exists"`.
   - **Recommended Response:** Dispatch an email to the existing address notifying them of the attempt, while returning a standard response:
     ```json
     {
       "message": "Registration successful. Please check your email to activate your account."
     }
     ```
   - *Alternative Controlled Response:* Return a standardized validation error with strict IP-based rate limiting (maximum 3 registrations per IP per hour) to prevent automated enumeration.
2. **Timing Attack Elimination:** Ensure database lookups execute in constant time by hashing a dummy string if the user lookup fails during authentication routines.

---

## 2.5 Email Verification Architecture

Email verification guarantees that candidate accounts correspond to reachable mailboxes and halts bulk bot creation.

```
  EMAIL VERIFICATION TIMELINE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Register     │ ---> │ Generate HMAC Token     │ ---> │ User Clicks Email Link  │
  │ Account      │      │ (24-Hour Expiration)    │      │ `GET /verify-email/:tk` │
  └──────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                      │
                                                                      ▼
                                                         Validate Token & Set:
                                                         `User.is_verified = True`
```

### Technical Token Specification:
1. **Cryptographic Signing:** Verification tokens are generated using Django's `django.core.signing.TimestampSigner` or a dedicated single-use cryptographically random token (minimum 32 bytes / 256 bits of CSPRNG entropy).
2. **Token Invalidation:**
   - Verification tokens expire after exactly **24 hours** (`86,400 seconds`).
   - Tokens are single-use: upon successful validation, the token is recorded as consumed or invalidated by changing the user's secret salt timestamp.
3. **Resend Endpoint Protection (`POST /api/v1/auth/verification/resend/`):**
   - Strictly rate-limited to **1 request per 60 seconds** per IP/Email.
   - Always returns a generic response: `"If an unverified account exists, a verification link has been sent."`

---

## 2.6 Account Lockout, Inactivity, and Suspension States

Account access states must be explicitly checked on every authenticated request:

| Account State Flag | Access Permitted | Token Issuance | Behavior on Protected Endpoints |
|---|---|---|---|
| `is_active = True`, `is_verified = True` | Full Candidate Access | Normal Access + Refresh JWTs | HTTP 200 OK |
| `is_active = True`, `is_verified = False`| Restricted / Onboarding | Access JWT issued; profile restricted | Redirect to verification reminder |
| `is_active = False` (Banned / Suspended) | Blocked Entirely | Tokens rejected / revoked | HTTP 401 Unauthorized (`USER_INACTIVE`) |
| Soft-Deleted Account | Anonymized / Blocked | Blacklisted | HTTP 401 Unauthorized (`ACCOUNT_DELETED`) |

---

## 2.7 Account Deletion & Data Anonymization Protocol (Right to Be Forgotten)

When a candidate requests account deletion (`DELETE /api/v1/account/`), the platform must balance candidate privacy against community discussion integrity.

```
  ACCOUNT DELETION & ANONYMIZATION PROTOCOL
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 1. Verify Candidate Password (Re-authentication required)                   │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ 2. Revoke all active FCM Device registrations (`Device.delete()`)           │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ 3. Blacklist all outstanding JWT Refresh tokens in Redis / DB               │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ 4. Delete CandidateProfile and private TimelineEvents (`CASCADE`)           │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ 5. Anonymize Community Contributions:                                       │
  │    • `Post.author` set to NULL or designated system "Deleted Candidate"     │
  │    • `Comment.author` set to NULL or designated system "Deleted Candidate"  │
  │    • Post bodies and comments preserved to avoid breaking reply trees       │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ 6. Purge Private Account Record:                                            │
  │    • Remove `User.email`, password hash, date of birth, IP logs             │
  │    • Replace email with randomized hash: `deleted_[uuid]@tracker.internal`  │
  │    • Set `User.is_active = False`                                           │
  └─────────────────────────────────────────────────────────────────────────────┘
```

### Architectural Guarantees:
- **Zero Orphaned PII:** No residual records link the deleted candidate's email address or device tokens to their past forum contributions.
- **Discussion Thread Preservation:** Threads remain readable to other candidates without broken conversation links or missing parent comments.

# 3. Authentication Architecture & Token Lifecycle

The application uses JSON Web Token (JWT) authentication implemented via `djangorestframework-simplejwt`.

```
  JWT AUTHENTICATION & ROTATION CYCLE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Client Login │ ---> │ DRF Simple JWT Issues:  │ ---> │ Client Attaches:        │
  │ Credentials  │      │ • Access Token (15 min) │      │ `Authorization: Bearer` │
  └──────────────┘      │ • Refresh Token (7 days)│      │ to protected requests   │
                        └─────────────────────────┘      └─────────────────────────┘
                                     │                                │
                                     ▼                                ▼
                        Token Expiration Encountered       Access Token Validated
                                     │                     Object Returned
                                     ▼
                        `POST /auth/token/refresh/`
                        Old Refresh Blacklisted ---> New Pair Issued
```

---

## 3.1 Token Specifications & Cryptographic Claims

### 3.1.1 Access Token Specifications
- **Signing Algorithm:** `HMAC-SHA256` (`HS256`) using a dedicated 256-bit cryptographically random secret key distinct from Django's core `SECRET_KEY`.
- **Token Lifetime:** **15 minutes** (`900 seconds`). Short lifetimes drastically limit the window of vulnerability if an access token is intercepted.
- **Payload Structure:**
  ```json
  {
    "token_type": "access",
    "exp": 1789906500,
    "iat": 1789905600,
    "jti": "b5a948e2-411a-4d76-88a3-2c1b9d4e5f60",
    "user_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",
    "is_staff": false,
    "is_verified": true
  }
  ```
- **Security Rule on Payload Data:** The access token payload **must never contain** PII such as email addresses, display names, candidate phone numbers, or candidate status. It contains strictly the non-enumerable UUIDv4 `user_id` and essential authorization claims.

### 3.1.2 Refresh Token Specifications
- **Token Lifetime:** **7 days** (`604,800 seconds`).
- **Rotation Enforcement (`ROTATE_REFRESH_TOKENS = True`):** Every call to `/api/v1/auth/token/refresh/` invalidates the submitted refresh token and generates a brand new refresh token alongside the new access token.
- **Blacklisting Enforcement (`BLACKLIST_AFTER_ROTATION = True`):** Rotated tokens are immediately inserted into the database blacklist table (`token_blacklist_blacklistedtoken`).
- **Reuse Detection & Automatic Revocation:** If an attacker attempts to replay an already-consumed refresh token, Simple JWT detects a token reuse attack, flags the incident, and immediately revokes all descendant tokens issued to that family, terminating the session.

---

## 3.2 Simple JWT Configuration Reference

In `tcs_joining_tracker/config/settings.py`:

```python
from datetime import timedelta
import os

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ.get('JWT_SECRET_KEY', SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUDIENCE': 'https://tracker.internal/api',
    'ISSUER': 'tcs-joining-tracker-auth',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}
```

---

## 3.3 Client Token Storage & XSS/CSRF Hardening

The frontend application stores and transmits tokens adhering to strict security constraints:

### Deployment Strategies:
1. **Header-Based Bearer Authentication (Standard SPA Mode):**
   - Access token stored in memory (React state / AuthContext).
   - Refresh token stored in secure `localStorage` or protected session storage.
   - Mitigates CSRF completely because browsers do not automatically attach Bearer headers to cross-site requests.
   - XSS protection is achieved through strict Content Security Policy (CSP), automated HTML escaping, and prohibiting `dangerouslySetInnerHTML`.
2. **HttpOnly Cookie Architecture (Enhanced Enterprise Mode):**
   - Access and refresh tokens stored in `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
   - JavaScript cannot read the token, eliminating token theft via XSS.
   - Requires Django CSRF middleware enabled on all state-changing endpoints with `X-CSRFToken` verification.

---

## 3.4 Token Revocation Workflows

Tokens must be explicitly invalidated across four critical lifecycle triggers:

```
  TOKEN REVOCATION MATRIX
  ┌───────────────────────┬─────────────────────────────────────────────────────┐
  │ Trigger Event         │ Revocation Action                                   │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 1. User Logout        │ Client submits refresh token to `/auth/logout/`.    │
  │                       │ Token added to `token_blacklist` table.             │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 2. Password Change /  │ All outstanding refresh tokens for the user account │
  │    Password Reset     │ are bulk-blacklisted. User must re-authenticate.    │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 3. Account Suspension │ Moderator bans user (`is_active = False`). All user │
  │    or Ban             │ tokens blacklisted; active access tokens rejected.  │
  ├───────────────────────┼─────────────────────────────────────────────────────┤
  │ 4. Device Revocation  │ Deleting a `Device` record invalidates associated   │
  │                       │ FCM tokens and prompts active session refresh.      │
  └───────────────────────┴─────────────────────────────────────────────────────┘
```

---

## 3.5 Password Reset Protocol

The password reset flow allows legitimate users to recover access while resisting account takeover, brute-force enumeration, and token sniffing.

```
  PASSWORD RESET PROTOCOL
  ┌───────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ POST /auth/       │ ---> │ Constant-Time Lookup    │ ---> │ Send Email with Secure  │
  │ password-reset/   │      │ Generic 200 OK Response │      │ Single-Use Reset Link   │
  └───────────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                           │
                                                                           ▼
                                                              User Submits New Password
                                                              • Hash verified in DB
                                                              • Old tokens blacklisted
                                                              • New password hashed
```

### Technical Reset Invariants:
1. **Zero Information Leakage:** Requesting a reset for a non-existent email address yields the identical HTTP 200 response as a valid email:
   ```json
   {
     "message": "If an account exists with this email, password reset instructions have been dispatched."
   }
   ```
2. **Cryptographic Token Construction:**
   - Generated using Django's `default_token_generator` (derived from HMAC of user's password hash, last login timestamp, and secret key).
   - Alternatively, a cryptographically secure random token (32 bytes) stored as an unsalted SHA-256 hash in a dedicated `PasswordResetToken` table.
3. **Strict Expiration:** Reset tokens expire after **60 minutes** (`3,600 seconds`).
4. **Single-Use Invalidation:** Upon password reset confirmation (`POST /api/v1/auth/password-reset/confirm/`), the user's password hash changes, which cryptographically invalidates all previously generated tokens instantly.

---

# 4. Authorization, Access Control, & Object-Level Permissions

Authentication confirms who the user is; authorization enforces what the user is permitted to do.

## 4.1 Role-Based Access Control (RBAC) Matrix

| Resource / Endpoint | Anonymous Visitor | Authenticated Candidate | Moderator / Staff | Superadmin |
|---|---|---|---|---|
| **Public Landing & Public Stats** | Read Only | Read Only | Read Only | Full Access |
| **Community Feed & Public Posts** | Read Only | Read Only | Read Only | Full Access |
| **Post Creation** | Denied (401) | Allowed (Rate-limited) | Allowed | Full Access |
| **Post Edit / Delete (Own)** | Denied (401) | Allowed | Allowed | Full Access |
| **Post Edit / Delete (Others)** | Denied (401) | Denied (403) | Allowed (Soft-delete) | Full Access |
| **Post Lock / Pin** | Denied (401) | Denied (403) | Allowed | Full Access |
| **Comment Creation** | Denied (401) | Allowed (Rate-limited) | Allowed | Full Access |
| **Comment Delete (Own)** | Denied (401) | Allowed (Soft-delete) | Allowed (Soft-delete) | Full Access |
| **Comment Delete (Others)** | Denied (401) | Denied (403) | Allowed (Soft-delete) | Full Access |
| **Post Upvoting / Un-voting** | Denied (401) | Allowed (1 per post) | Allowed | Full Access |
| **Own Candidate Profile CRUD** | Denied (401) | Full Access | Read / Audit | Full Access |
| **Other Candidate Private Data** | Denied (401) | Denied (403/404) | Denied (403/404) | Audit Only |
| **Personal Timeline Events CRUD**| Denied (401) | Full Access (Own only) | Read / Audit | Full Access |
| **Content Reporting** | Denied (401) | Allowed (1 per target) | Allowed | Full Access |
| **Moderation Queue Review** | Denied (401) | Denied (403) | Full Access | Full Access |
| **User Suspension / Ban** | Denied (401) | Denied (403) | Allowed | Full Access |
| **Announcements Management** | Denied (401) | Denied (403) | Full Access | Full Access |

---

## 4.2 Object-Level Permissions & IDOR Defense

Insecure Direct Object Reference (IDOR) vulnerabilities occur when an attacker accesses or manipulates another candidate's private resource by altering a URL identifier (e.g., `PATCH /api/v1/timeline/9a9f8d8b-7c1a...`).

```
  IDOR MITIGATION PIPELINE
  ┌────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Request to:            │ ---> │ Extract `request.user`   │ ---> │ Database Filter:        │
  │ `/timeline/{event_id}/`│      │ from Validated JWT      │      │ `TimelineEvent.objects. │
  └────────────────────────┘      └─────────────────────────┘      │ filter(id=id,           │
                                                                   │ candidate__user=user)`  │
                                                                   └─────────────────────────┘
                                                                                │
                                                                                ▼
                                                                   Match Found: Allowed
                                                                   No Match: HTTP 404 (Not 403)
```

### Concrete Defense Rules:
1. **Filter by Authenticated Context:** Never query models using raw client-supplied identifiers without scoping to `request.user`.
   ```python
   # VULNERABLE TO IDOR:
   event = TimelineEvent.objects.get(id=event_id)
   
   # SECURE IMPLEMENTATION:
   event = get_object_or_404(TimelineEvent, id=event_id, candidate__user=request.user)
   ```
2. **Return HTTP 404 Instead of HTTP 403:** When an unauthorized candidate requests another candidate's private resource, the API returns **HTTP 404 Not Found** rather than HTTP 403 Forbidden. This prevents resource enumeration (confirming whether a given UUID exists).

---

## 4.3 Custom DRF Permission Classes

The platform defines reusable, audit-tested permission classes in `tcs_joining_tracker/common/permissions.py`:

### 4.3.1 `IsCandidateProfileOwner`
```python
from rest_framework.permissions import BasePermission

class IsCandidateProfileOwner(BasePermission):
    # Ensures candidates can view or modify only their own profile.
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
```

### 4.3.2 `IsAuthorOrModerator`
```python
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAuthorOrModerator(BasePermission):
    # Allows read access to all authenticated users; write/delete access
    # restricted to the author or staff/moderator.
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.author == request.user
```

### 4.3.3 `IsTimelineOwner`
```python
from rest_framework.permissions import BasePermission

class IsTimelineOwner(BasePermission):
    # Restricts timeline event modifications strictly to the candidate owner.
    def has_object_permission(self, request, view, obj):
        return obj.candidate.user == request.user
```

---

## 4.4 Horizontal & Vertical Privilege Escalation Defense

### Horizontal Escalation Defense:
- Candidates cannot vote multiple times, edit other candidates' comments, or register FCM tokens to other accounts.
- Enforced through database constraints (`UNIQUE(user, post)` for votes) and service-layer validation.

### Vertical Escalation Defense:
- Regular candidates must never elevate their privileges to `is_staff` or `is_superuser`.
- DRF serializers for `User` and `CandidateProfile` explicitly exclude `is_staff`, `is_superuser`, and `groups` from `fields` and enforce `read_only_fields`.
- In Django views, `request.data` is never passed directly into `user.update(**request.data)` without serializer whitelisting.

---

## 4.5 Context-Aware User Resolution

Under **no circumstances** may an API endpoint accept a `user_id` or `author_id` in the request body to determine who created a post, cast a vote, or submitted a report.

```python
# FORBIDDEN (Vulnerable to spoofing):
post = Post.objects.create(author_id=request.data.get('author_id'), ...)

# MANDATORY (Author authoritative from token context):
post = Post.objects.create(author=request.user, ...)
```

# 5. Privacy Engineering & Data Protection

Privacy is the primary non-functional requirement of the TCS Joining Tracker platform. Candidates must be confident that participation cannot lead to identification.

```
  PUBLIC IDENTITY ISOLATION WALL
  ┌───────────────────────────────────────────────┐
  │ PRIVATE CREDENTIALS LAYER (Never Public):     │
  │ • User.email = candidate@example.com          │
  │ • User.password = $argon2id$...               │
  │ • Device.fcm_token = bk3RNwTe3H0:CI2k_HHBc5...│
  │ • Audit logs, IP addresses, session tokens    │
  └───────────────────────┬───────────────────────┘
                          │ (STRICT SERIALIZER BOUNDARY)
                          ▼
  ┌───────────────────────────────────────────────┐
  │ PUBLIC COMMUNITY PRESENTATION LAYER:          │
  │ ┌───────────────────────────────────────────┐ │
  │ │ If mode == 'ANONYMOUS':                   │ │
  │ │ "Anonymous Candidate • 2025 • Digital"    │ │
  │ ├───────────────────────────────────────────┤ │
  │ │ If mode == 'DISPLAY_NAME':                │ │
  │ │ "Sai T. • 2025 • Digital • Hyderabad"     │ │
  │ └───────────────────────────────────────────┘ │
  └───────────────────────────────────────────────┘
```

---

## 5.1 Public Identity Enforcement

The database model `CandidateProfile` defines `public_identity_mode`:
- `ANONYMOUS` (Default)
- `DISPLAY_NAME`

### Identity Rendering Invariants:
1. When a post, comment, or upvote is serialized for public consumption, the serializer resolves the author identity through a dedicated method field:
   ```python
   class AuthorPublicSerializer(serializers.ModelSerializer):
       display_name = serializers.SerializerMethodField()
       batch = serializers.CharField(source='candidate_profile.batch', read_only=True)
       hiring_type = serializers.CharField(source='candidate_profile.hiring_type', read_only=True)
       region = serializers.CharField(source='candidate_profile.region', read_only=True)

       class Meta:
           model = User
           fields = ['id', 'display_name', 'batch', 'hiring_type', 'region']

       def get_display_name(self, obj):
           profile = getattr(obj, 'candidate_profile', None)
           if not profile or profile.public_identity_mode == 'ANONYMOUS':
               return "Anonymous Candidate"
           return profile.display_name or "Anonymous Candidate"
   ```
2. **Deterministic Pseudonymity:** For the `ANONYMOUS` mode, avatar generation uses an internal hash of `(user.id + SECRET_KEY)` so that a user's comments within a single thread have consistent visual styling without exposing their true identity across global search.

---

## 5.2 Serializer Segregation Architecture

To prevent accidental data leaks through over-serialization, serializers are split into strict access boundaries:

```
  SERIALIZER BOUNDARY SEPARATION
  ┌─────────────────────────────┬──────────────────────────────────────────────┐
  │ Serializer Class            │ Exposed Fields & Target Audience             │
  ├─────────────────────────────┼──────────────────────────────────────────────┤
  │ `UserPrivateSerializer`     │ `id`, `email`, `is_verified`, `created_at`   │
  │                             │ (Authenticated user `/me/` endpoint only)    │
  ├─────────────────────────────┼──────────────────────────────────────────────┤
  │ `UserPublicSerializer`      │ `id`, `display_name`, `batch`, `hiring_type` │
  │                             │ (Public community author representation)     │
  ├─────────────────────────────┼──────────────────────────────────────────────┤
  │ `CandidatePrivateSerializer`│ All fields + `interview_date`, `offer_date`  │
  │                             │ (Profile owner `/api/v1/profile/` only)      │
  ├─────────────────────────────┼──────────────────────────────────────────────┤
  │ `CandidatePublicSerializer` │ Sanitized fields only (No email, no notes)   │
  │                             │ (Used if candidate profiles are viewed)      │
  ├─────────────────────────────┼──────────────────────────────────────────────┤
  │ `AdminUserSerializer`       │ Audit metadata, report logs, suspension state│
  │                             │ (Staff / Django Admin only)                  │
  └─────────────────────────────┴──────────────────────────────────────────────┘
```

---

## 5.3 Sensitive Data Classification & Zero-Exposure Policy

| Data Attribute | Classification | Permitted API Endpoints | Security Controls |
|---|---|---|---|
| **Password Hash** | Restrictive / Secret | **NONE** (Never returned in any API) | Salted Argon2id / PBKDF2; write-only |
| **Email Address** | Sensitive PII | `/api/v1/me/` (Self only) | Redacted from all community endpoints |
| **FCM Device Token**| Sensitive Infra Cred | **NONE** (Accepted on POST, never read) | Write-only endpoint; omitted from GET |
| **IP Address** | Sensitive PII / Log | Internal audit logs only | Anonymized / truncated; never exposed |
| **Password Reset Token**| Secret Credential | Internal email dispatch only | 60-min expiry; hashed in DB |
| **Verification Token**| Secret Credential | Internal email dispatch only | 24-hr expiry; single-use |
| **Moderation Notes** | Internal Admin | Staff moderation queue only | Excluded from regular candidate views |

---

## 5.4 Small-Group Privacy Suppression

A major privacy threat in community trackers is the **re-identification of individuals in small filter groups**.

*Example:* If only 1 candidate in "Digital • 2025 • Hubli" reports having received their joining letter, anyone in that recruitment cohort can easily deduce that individual's identity.

```
  SMALL-GROUP AGGREGATE PRIVACY SUPPRESSION
  ┌────────────────────────────────────────────────────────┐
  │ Filter Query: batch=2025 & stream=Digital & region=Goa │
  ├────────────────────────────────────────────────────────┤
  │ Aggregate Count: 3 candidates                          │
  ├────────────────────────────────────────────────────────┤
  │ Evaluation: 3 < MIN_ANALYTICS_GROUP_SIZE (5)           │
  ├────────────────────────────────────────────────────────┤
  │ Action: SUPPRESS DETAILED METRICS                      │
  │ Return HTTP 200:                                       │
  │ {                                                      │
  │   "data_source": "COMMUNITY_REPORTED",                 │
  │   "suppressed": true,                                  │
  │   "message": "Not enough community data to display     │
  │               breakdown (minimum 5 submissions req'd)."│
  │ }                                                      │
  └────────────────────────────────────────────────────────┘
```

- **Configuration:** `MIN_ANALYTICS_GROUP_SIZE = 5` (configured in `settings.py`).
- **Backend Enforcement:** Analytics services evaluate `queryset.count()` prior to generating breakdowns. If the cohort size is below the threshold, sub-metrics (`average_wait_days`, `status_distribution`) are completely suppressed.

---

# 6. Device & FCM Notification Security

The application supports browser push notifications via Firebase Cloud Messaging (FCM). FCM tokens are critical infrastructure identifiers that must be defended against hijacking and cross-account binding.

```
  FCM DEVICE REGISTRATION & NOTIFICATION PIPELINE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Browser      │ ---> │ POST /api/v1/devices/   │ ---> │ PostgreSQL:             │
  │ Obtains FCM  │      │ Token sent over TLS 1.3 │      │ Device(user=req.user,   │
  │ Token from   │      │ Bearer Auth Required    │      │        token=token,     │
  │ Firebase SDK │      │                         │      │        is_active=True)  │
  └──────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                      │
                                                                      ▼
                                                         Celery Worker Dispatches
                                                         Push to Firebase API
                                                         (Zero PII in Push Payload)
```

---

## 6.1 Device Registration Security

1. **Dedicated `Device` Entity:** FCM tokens are never stored directly on the `User` model. A user can own multiple active browsers/devices (`1-to-Many` relationship).
2. **Write-Only Serializer:**
   ```python
   class DeviceRegistrationSerializer(serializers.ModelSerializer):
       class Meta:
           model = Device
           fields = ['id', 'fcm_token', 'device_type', 'browser', 'is_active']
           extra_kwargs = {
               'fcm_token': {'write_only': True}  # NEVER returned in responses
           }
   ```
3. **Cross-Tenant Prevention:** When a token is registered, any pre-existing record containing the identical `fcm_token` belonging to another user account is deactivated or updated to the new authenticated user. This prevents notifications from routing to a previous user of a shared public workstation.

---

## 6.2 Push Notification Payload Security (Zero-PII Payload)

Push notifications are routed across third-party intermediaries (Google FCM servers, Apple APNs, browser notification daemons). 

### Security Rule:
**Push notification payloads must never contain private personal data or confidential timeline notes.**

- **Vulnerable Payload (Leaking PII):**
  ```json
  {"title": "Offer Letter", "body": "Candidate Sai Teja (ID: 1042) got Digital offer in Hyderabad"}
  ```
- **Secure Payload (Zero PII):**
  ```json
  {
    "notification": {
      "title": "New Community Reply",
      "body": "Someone replied to your comment on TCS Joining Tracker."
    },
    "data": {
      "type": "REPLY",
      "post_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",
      "click_action": "https://tracker.internal/community/posts/9a9f8d8b-7c1a-4e15-a1a8-111111111111"
    }
  }
  ```

---

## 6.3 Stale Token Invalidation & Housekeeping

1. When Firebase returns `messaging/registration-token-not-registered` or `messaging/invalid-registration-token`, the background Celery task marks `Device.is_active = False`.
2. A daily Celery cron task automatically deletes inactive devices older than 30 days.

---

# 7. Rate Limiting, Throttling, & Abuse Prevention

The application deploys Redis-backed rate limiting using Django REST Framework's throttling framework. Rate limiting defends against brute-force password cracking, credential stuffing, spam flooding, and denial-of-service (DoS) attempts.

```
  REDIS DISTRIBUTED THROTTLING PIPELINE
  ┌───────────────────────┐
  │ Incoming HTTP Request │
  └───────────┬───────────┘
              ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ Identify Throttle Bucket Key:                                               │
  │ • IP Bucket: `throttle_anon_<ip>`                                           │
  │ • User Bucket: `throttle_user_<user_id>`                                    │
  │ • Scoped Bucket: `throttle_scope_<scope>_<key>`                             │
  └───────────────────────────────────┬─────────────────────────────────────────┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                  Under Limit                Limit Exceeded
                 (Allow Request)            (HTTP 429 Too Many Requests)
                 Increment Redis            Return Header:
                 Sliding Window             `Retry-After: 42`
```

---

## 7.1 Throttling Tier Definitions & Scopes

Configured in `settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Global baseline rates
        'anon': '60/minute',
        'user': '300/minute',
        
        # Sensitive authentication scopes
        'auth_login': '5/minute',           # Prevents brute-force login
        'auth_register': '3/hour',          # Prevents bulk bot registrations
        'auth_password_reset': '3/hour',    # Prevents password reset flooding
        'auth_verify_resend': '1/minute',   # Prevents email spam
        
        # Community participation scopes
        'post_create': '5/hour',            # Prevents spam post flooding
        'comment_create': '30/hour',        # Prevents thread spamming
        'vote_toggle': '60/minute',         # Prevents vote gaming scripts
        'report_create': '10/hour',         # Prevents report queue sabotage
        
        # Device & notification scopes
        'device_register': '10/hour',
        
        # Public search & analytics scopes
        'public_search': '30/minute',
        'public_analytics': '60/minute',
    }
}
```

---

## 7.2 Custom Scoped Throttle Classes

Defined in `accounts/throttles.py`:

```python
from rest_framework.throttling import ScopedRateThrottle

class LoginRateThrottle(ScopedRateThrottle):
    scope = 'auth_login'

    def get_cache_key(self, request, view):
        # Combined IP + email bucket to prevent distributed credential stuffing
        email = request.data.get('email', '').strip().lower()
        ident = self.get_ident(request)
        return f"throttle_login_{ident}_{email}"

class PostCreateRateThrottle(ScopedRateThrottle):
    scope = 'post_create'

class CommentCreateRateThrottle(ScopedRateThrottle):
    scope = 'comment_create'

class ReportRateThrottle(ScopedRateThrottle):
    scope = 'report_create'
```

---

## 7.3 HTTP 429 Rate Limit Response Standards

When a client breaches a throttling limit, the API returns a predictable JSON response accompanied by standard RFC 6585 headers:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 42
```

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Request rate limit exceeded. Please wait before retrying.",
    "retry_after_seconds": 42
  }
}
```

# 8. Web Application Vulnerability Defenses (OWASP Top 10 Mitigation)

The application implements defense-in-depth mitigations against the full spectrum of the OWASP Top 10 web application vulnerabilities.

```
  OWASP TOP 10 DEFENSE MATRIX
  ┌─────────────────────────────────┬───────────────────────────────────────────┐
  │ OWASP Category                  │ Concrete Implementation in TCS Tracker    │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A01: Broken Access Control      │ Object permissions, IDOR defense, UUIDs   │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A02: Cryptographic Failures     │ Argon2id hashing, TLS 1.3, JWT HS256, HSTS│
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A03: Injection (SQLi, Command)  │ Django ORM parameterization, zero raw SQL │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A04: Insecure Design            │ Threat model, rate limiting, anon modes   │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A05: Security Misconfiguration  │ Strict headers, DEBUG=False, CORS allowlist│
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A06: Vulnerable Components      │ Automated pip-audit, pinned dependencies  │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A07: Auth & Identification      │ Simple JWT rotation, 15m expiry, blacklist│
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A08: Software & Data Integrity  │ Verification tokens, secure deserializer  │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A09: Logging & Monitoring Fail  │ Audit logs, PII redaction, Prometheus     │
  ├─────────────────────────────────┼───────────────────────────────────────────┤
  │ A10: Server-Side Request Forgery│ No arbitrary webhooks or remote URL fetch │
  └─────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 8.1 Injection Defense (SQLi & Command Injection)

1. **SQL Injection Defense:**
   - Django's Object-Relational Mapper (ORM) generates parameterized SQL queries automatically, eliminating SQL injection for standard queryset operations.
   - **Prohibition of Raw SQL:** Developers and AI coding agents are strictly forbidden from writing `cursor.execute()`, `Model.objects.raw()`, or passing string-concatenated variables into `.extra()`.
   ```python
   # STRICTLY FORBIDDEN (Vulnerable to SQLi):
   Post.objects.raw(f"SELECT * FROM community_post WHERE title = '{search_query}'")

   # MANDATORY (Parameterized Query):
   Post.objects.filter(title__icontains=search_query)
   ```
2. **Command Injection Defense:**
   - Under no circumstances may user inputs be passed to `os.system()`, `subprocess.Popen(..., shell=True)`, or `eval()`.
   - Any external system utility calls must use parameterized argument lists without shell interpretation (`shell=False`).

---

## 8.2 Cross-Site Scripting (XSS) Defense

Cross-Site Scripting attacks could allow an attacker to inject malicious JavaScript into community posts or comments, stealing session tokens or impersonating candidates.

### Mitigation Architecture:
1. **Plain-Text Community Content by Default:**
   - For the MVP, post bodies and comment inputs are stored, treated, and rendered strictly as **plain text** (`CharField` and `TextField`).
   - React automatically escapes string values embedded within JSX expressions (`<div>{post.body}</div>`), preventing execution of injected `<script>` or `<img onerror=...>` tags.
2. **Prohibition of Unsafe Sinks:**
   - Frontend developers and AI agents must **never** use `dangerouslySetInnerHTML`, `innerHTML`, `document.write()`, or `eval()`.
3. **Markdown Sanitization (If Enabled Post-MVP):**
   - If rich text/markdown is introduced, sanitization must occur **server-side** before storage using Python's `nh3` (Ammonia) or `bleach` with an explicit HTML tag whitelist:
     ```python
     import nh3

     ALLOWED_TAGS = {'b', 'i', 'strong', 'em', 'p', 'ul', 'ol', 'li', 'code', 'blockquote'}
     clean_body = nh3.clean(raw_input, tags=ALLOWED_TAGS, attributes={})
     ```
   - Never rely on client-side markdown sanitization alone.

---

## 8.3 Cross-Site Request Forgery (CSRF) Architecture

1. **Header-Based Bearer Token Protection:**
   - Standard API requests authenticate via `Authorization: Bearer <token>`.
   - Browsers do not attach Bearer tokens automatically to cross-origin requests, providing innate immunity to CSRF attacks for token-based endpoints.
2. **Cookie-Based Authentication Protection:**
   - If session cookies or HttpOnly JWT cookies are utilized, Django's `django.middleware.csrf.CsrfViewMiddleware` is enabled.
   - All state-changing methods (`POST`, `PUT`, `PATCH`, `DELETE`) require the `X-CSRFToken` request header.
   - CSRF cookies configured with `CSRF_COOKIE_HTTPONLY = False` (for frontend client reading), `CSRF_COOKIE_SECURE = True`, and `CSRF_COOKIE_SAMESITE = 'Lax'`.

---

## 8.4 Server-Side Request Forgery (SSRF) & File Upload Hardening

If post attachments are enabled (MVP post-launch extension):

```
  FILE UPLOAD HARDENING PIPELINE
  ┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ Uploaded     │ ---> │ 1. File Size Check      │ ---> │ 3. MIME / Magic Bytes   │
  │ Attachment   │      │    (Max 5MB)            │      │    Verification         │
  └──────────────┘      ├─────────────────────────┤      └─────────────────────────┘
                        │ 2. Extension Whitelist  │                   │
                        │    (.jpg, .png, .pdf)   │                   ▼
                        └─────────────────────────┘      Store in Isolated S3 Bucket
                                                         (No executable permissions)
```

### Upload Rules:
- **Strict Size Limitation:** Maximum **5 Megabytes** (`5,242,880 bytes`). Configured via `DATA_UPLOAD_MAX_MEMORY_SIZE`.
- **Extension & Magic Byte Whitelist:**
  - Allowed: `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`.
  - Prohibited: Executable extensions (`.exe`, `.sh`, `.py`, `.php`, `.js`, `.svg`, `.html`, `.xml`).
  - Validation requires reading the first 2048 bytes with `python-magic` to inspect the true file header rather than trusting the user-supplied filename.
- **Storage Isolation:** Files stored in an isolated S3/GCS bucket with direct download forced via `Content-Disposition: attachment`. Uploads are never served directly from the Django application root.

---

## 8.5 Clickjacking Defense

- **HTTP Header Enforcement:**
  ```text
  X-Frame-Options: DENY
  Content-Security-Policy: frame-ancestors 'none';
  ```
- Guaranteed via Django's `XFrameOptionsMiddleware`. Prevents the site from being framed within an invisible iframe on a malicious website to hijack user clicks.

---

## 8.6 Insecure Deserialization & Mass Assignment Defense

- **Prohibition of `pickle` and `yaml.load`:** Python's `pickle` library is strictly prohibited for any client-facing data processing or cache serialization.
- **Explicit DRF Serializer Whitelisting:**
  - `Meta.fields` must always be an explicit list of permitted field names.
  - **`fields = '__all__'` is strictly forbidden** in any model serializer to prevent Mass Assignment vulnerabilities.
  ```python
  # FORBIDDEN (Mass assignment risk):
  class Meta:
      model = User
      fields = '__all__'

  # MANDATORY (Explicit whitelist):
  class Meta:
      model = CandidateProfile
      fields = ['batch', 'hiring_type', 'region', 'interview_date']
  ```

---

# 9. Network, Transport, & HTTP Security Headers

In production environments, all communication between clients, CDNs, load balancers, and backend servers is encrypted and hardened via standard HTTP security headers.

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                       PRODUCTION HTTP SECURITY HEADERS                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ Strict-Transport-Security: max-age=31536000; includeSubDomains; preload     │
  │ X-Content-Type-Options: nosniff                                             │
  │ X-Frame-Options: DENY                                                       │
  │ Referrer-Policy: strict-origin-when-cross-origin                            │
  │ Cross-Origin-Opener-Policy: same-origin                                     │
  │ Cross-Origin-Resource-Policy: same-origin                                   │
  │ Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()   │
  │ Content-Security-Policy: default-src 'self'; ...                           │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9.1 HTTPS & Transport Security (HSTS)

Enforced in `settings.py`:

```python
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000  # 1 Full Year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## 9.2 Content Security Policy (CSP) Directives

Implemented via `django-csp`:

```python
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://www.gstatic.com", "https://*.firebaseio.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https://*.amazonaws.com")
CSP_CONNECT_SRC = ("'self'", "https://fcm.googleapis.com", "https://*.firebaseio.com")
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)
```

---

## 9.3 Cross-Origin Resource Sharing (CORS) Production Configuration

In `settings.py` via `django-cors-headers`:

```python
CORS_ALLOW_ALL_ORIGINS = False  # WILDCARDS STRICTLY FORBIDDEN IN PROD

CORS_ALLOWED_ORIGINS = [
    "https://tracker.internal",
    "https://app.tracker.internal",
]

CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
```

---

# 10. Secrets Management & Environment Security

## 10.1 Environment Variable Strategy

1. **Zero Credentials in Version Control:**
   - Secret keys, database passwords, Redis URLs, and Firebase service credentials must never be committed to Git.
   - `.gitignore` explicitly includes `.env`, `.env.local`, `*.pem`, `serviceAccountKey.json`.
2. **Environment Parsing:** Loaded via `django-environ` or `python-dotenv`:
   ```python
   import environ
   env = environ.Env(DEBUG=(bool, False))
   environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

   SECRET_KEY = env('DJANGO_SECRET_KEY')
   JWT_SECRET_KEY = env('JWT_SECRET_KEY')
   ```

---

## 10.2 Production Secret Key & JWT Key Rotation Strategy

- **Distinct Keys:** `DJANGO_SECRET_KEY` and `JWT_SECRET_KEY` must be completely distinct 256-bit cryptographically random strings.
- **Rotation Procedure:**
  1. Generate new 64-character secret.
  2. Deploy new key as primary signing key while maintaining old key in secondary verification list.
  3. Allow active access tokens (15-min lifetime) to naturally expire.
  4. Fully retire old key.

---

## 10.3 Firebase Admin SDK Credential Protection

- Firebase service account keys must reside outside the web server docroot.
- Loaded strictly through environment variable JSON string or secure cloud secret managers (AWS Secrets Manager / GCP Secret Manager / Vault).

# 11. Audit Logging, Security Monitoring, & Incident Response

Comprehensive observability ensures security anomalies are detected before they lead to data compromise.

```
  STRUCTURED SECURITY AUDIT LOGGING PIPELINE
  ┌───────────────────────┐
  │ Security Event Raised │
  └───────────┬───────────┘
              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ PII & Secret Redaction Filter:                              │
  │ • Strip passwords, JWT tokens, FCM tokens, raw emails       │
  │ • Retain UUIDs, timestamps, IP hashes, action codes         │
  └───────────────────────────┬─────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Structured JSON Output (stdout / Log Shipper):              │
  │ {                                                           │
  │   "timestamp": "2026-09-19T14:32:10Z",                     │
  │   "event_type": "AUTH_LOGIN_FAILED",                        │
  │   "ip": "203.0.113.42",                                     │
  │   "user_id": "9a9f8d8b-7c1a-4e15-a1a8-111111111111",       │
  │   "reason": "INVALID_PASSWORD"                              │
  │ }                                                           │
  └─────────────────────────────────────────────────────────────┘
```

---

## 11.1 Security Event Taxonomy

The platform records standardized security events:

| Event Code | Trigger Description | Log Level | Target Alert |
|---|---|---|---|
| `AUTH_LOGIN_SUCCESS` | Successful user authentication | INFO | None |
| `AUTH_LOGIN_FAILED` | Invalid credentials submitted | WARNING | Alert if > 10 from same IP/user |
| `AUTH_LOGOUT` | User session ended / blacklisted | INFO | None |
| `AUTH_PASSWORD_RESET_REQ` | Reset link requested | INFO | None |
| `AUTH_PASSWORD_RESET_DONE`| Password changed successfully | NOTICE | Invalidate old sessions |
| `AUTH_TOKEN_REUSE_DETECT` | Invalidation of compromised token family | CRITICAL | Security Alert immediate |
| `AUTH_ACCOUNT_LOCKED` | Rate limit breached on auth endpoint | WARNING | Temporary IP throttle |
| `IDOR_ATTEMPT_BLOCKED` | User attempted access to unauthorized UUID | WARNING | Audit review |
| `RATE_LIMIT_EXCEEDED` | Throttling limit triggered | WARNING | Metrics counter |
| `MODERATION_ACTION` | Moderator locked, pinned, or deleted content | NOTICE | Mod audit trail |
| `USER_BANNED` | User account suspended | CRITICAL | Admin audit log |
| `ACCOUNT_DELETED` | Candidate initiated full account deletion | NOTICE | Privacy audit log |

---

## 11.2 PII & Secret Redaction in Application Logs

A custom Django logging filter (`common.logging.SecurityRedactionFilter`) intercepts and scrubs sensitive fields prior to writing to standard output:

```python
import logging
import re

class SecurityRedactionFilter(logging.Filter):
    SENSITIVE_PATTERNS = [
        re.compile(r'("password"\s*:\s*)"[^"]+"', re.IGNORECASE),
        re.compile(r'("token"\s*:\s*)"[^"]+"', re.IGNORECASE),
        re.compile(r'("fcm_token"\s*:\s*)"[^"]+"', re.IGNORECASE),
        re.compile(r'(Bearer\s+)[a-zA-Z0-9_\-\.]+', re.IGNORECASE),
    ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern in self.SENSITIVE_PATTERNS:
                record.msg = pattern.sub(r'\1"[REDACTED]"', record.msg)
        return True
```

---

## 11.3 Incident Response Runbook for Compromised Credentials

In the event of suspected token compromise or credential leak:

1. **Step 1 — Immediate Session Severing:**
   - Execute Django management command to flush and bulk-blacklist all active refresh tokens for the compromised user:
     ```bash
     python manage.py revoke_user_sessions --user-id=<uuid>
     ```
2. **Step 2 — Deactivate Registered Devices:**
   - Delete all associated `Device` records to halt pending push notification delivery.
3. **Step 3 — Force Password Reset:**
   - Invalidate the current password hash and generate an administrative password reset request.
4. **Step 4 — Audit Trail Inspection:**
   - Query security logs for the past 7 days matching the affected `user_id` to evaluate unauthorized post creations or modified timeline events.

---

# 12. Security Testing Strategy & Automated Test Suite

Every security control defined in this specification must be backed by automated regression tests written in `pytest` with `pytest-django`.

```
  AUTOMATED SECURITY TEST SUITE
  ┌─────────────────────────────────────────────────────────────┐
  │ tests/security/                                             │
  │ ├── test_authentication_security.py                         │
  │ ├── test_idor_and_object_permissions.py                     │
  │ ├── test_rate_limiting_and_throttling.py                    │
  │ ├── test_privacy_and_serializer_leakage.py                  │
  │ ├── test_token_blacklisting_and_rotation.py                 │
  │ └── test_owasp_top10_defenses.py                            │
  └─────────────────────────────────────────────────────────────┘
```

---

## 12.1 Automated Test Examples (pytest-django)

### 12.1.1 Testing IDOR Protection on Timeline Events
```python
import pytest
from rest_framework import status

@pytest.mark.django_db
def test_candidate_cannot_modify_other_timeline_event(authenticated_client, other_user_timeline_event):
    # Attempt to PATCH an event belonging to another candidate
    url = f"/api/v1/timeline/{other_user_timeline_event.id}/"
    payload = {"description": "Malicious modification"}
    
    response = authenticated_client.patch(url, payload, format="json")
    
    # Must return 404 (Not Found) to prevent resource existence leakage
    assert response.status_code == status.HTTP_404_NOT_FOUND
    other_user_timeline_event.refresh_from_db()
    assert other_user_timeline_event.description != "Malicious modification"
```

### 12.1.2 Testing Refresh Token Rotation & Blacklisting
```python
@pytest.mark.django_db
def test_refresh_token_rotation_blacklists_old_token(api_client, test_user):
    login_res = api_client.post("/api/v1/auth/login/", {
        "email": test_user.email,
        "password": "StrongPassword123!"
    })
    initial_refresh = login_res.data["refresh"]

    # First refresh succeeds
    refresh_res = api_client.post("/api/v1/auth/token/refresh/", {"refresh": initial_refresh})
    assert refresh_res.status_code == status.HTTP_200_OK
    assert "access" in refresh_res.data

    # Replaying old refresh token MUST fail
    replay_res = api_client.post("/api/v1/auth/token/refresh/", {"refresh": initial_refresh})
    assert replay_res.status_code == status.HTTP_401_UNAUTHORIZED
```

### 12.1.3 Testing Zero Exposure of Email in Public Post Serializer
```python
@pytest.mark.django_db
def test_public_post_serializer_never_leaks_author_email(api_client, public_post):
    res = api_client.get(f"/api/v1/posts/{public_post.id}/")
    assert res.status_code == status.HTTP_200_OK
    
    response_json = res.content.decode("utf-8")
    assert public_post.author.email not in response_json
    assert "email" not in res.data["author"]
```

---

## 12.2 Static Analysis & Dependency Vulnerability Auditing

The CI/CD pipeline enforces automated security scans before any code merges to main:

1. **Bandit (Python AST Security Linter):**
   ```bash
   bandit -r apps/ config/ -ll -ii
   ```
   Fails pipeline on high/medium severity findings (raw SQL, insecure random, hardcoded secrets).
2. **Pip-Audit (Known CVE Vulnerability Scanner):**
   ```bash
   pip-audit --strict --requirement requirements.txt
   ```
   Halts build if any package has an unpatched advisory.

---

# 13. Django Production Security Configuration Reference

Consolidated production settings in `config/settings/production.py`:

```python
import os
from .base import *

DEBUG = False
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'tracker.internal').split(',')

# TLS & Transport Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Framing & Sniffing
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')

# Database Connection Security
DATABASES['default']['CONN_MAX_AGE'] = 600
DATABASES['default']['OPTIONS'] = {
    'sslmode': 'require',
}
```

---

# 14. Security Verification Checklist & Definition of Done

The security layer is verified and ready for production only when all of the following criteria are validated:

- [ ] **Custom User Model:** Uses UUIDv4 primary keys and normalized case-insensitive email.
- [ ] **Argon2id Hashing:** Verified as primary password hasher with high memory/time costs.
- [ ] **JWT Rotation & Blacklisting:** Refresh token rotation and blacklisting active in DB.
- [ ] **Zero PII Exposure:** Email, password hash, FCM token, and IP address verified absent from all public serializers.
- [ ] **Strict IDOR Mitigation:** All timeline, profile, and comment endpoints enforce authenticated user ownership.
- [ ] **Small-Group Suppression:** Cohorts with < 5 candidates suppressed in analytics endpoints.
- [ ] **Throttling Active:** Redis-backed throttling limits tested on login, register, posts, and comments.
- [ ] **Security Headers Enforced:** HSTS, CSP, X-Frame-Options DENY, and nosniff validated via security scanner.
- [ ] **Automated Tests Passing:** Security test suite passes with 100% success on pytest.
- [ ] **Static Scans Clean:** Bandit and pip-audit report zero high/medium vulnerabilities.
- [ ] **Disclaimer Invariant:** Non-affiliation statement rendered on public boundaries.

---

# 15. AI Agent Implementation Directives for Security & Auth

When implementing, modifying, or reviewing code for this product, AI coding agents must adhere to these inviolable directives:

1. **Never Bypass Permissions:** Never remove or weaken a permission class (`IsAuthenticated`, `IsCandidateProfileOwner`) for convenience or rapid prototyping.
2. **Never Return PII:** Never add `email`, `password`, `fcm_token`, or `user_id` to public serializers.
3. **Never Query Models Without Context:** Always filter candidate-specific objects by `candidate__user=request.user` or `author=request.user`.
4. **Never Use Raw SQL:** Always use Django ORM parameterized querysets.
5. **Enforce Rate Limits:** Always attach appropriate throttle classes to sensitive endpoints.
6. **Preserve Non-Affiliation Boundary:** Never implement scraping tools, unofficial API proxies, or credential harvesting targeting official TCS systems.
