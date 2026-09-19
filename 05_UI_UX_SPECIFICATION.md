# 05 — UI/UX Specification

# TCS Joining Tracker — User Interface & User Experience Specification

> **Document:** 05_UI_UX_SPECIFICATION.md  
> **Product:** TCS Joining Tracker  
> **Version:** 1.0 — MVP  
> **Status:** Development Specification  
> **Target Frontend Stack:** React (TypeScript) + Tailwind CSS + Lucide React (Icons) + Headless UI / Radix Primitives + Service Worker (PWA)  
> **Target Backend Stack:** Django + Django REST Framework + PostgreSQL + Redis / Celery (from `03_DATABASE_DESIGN.md` and `04_API_SPECIFICATION.md`)

---

## Important Product Boundary & Legal Disclaimer

**TCS Joining Tracker is an independent, community-driven platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS).**

All UI screens, components, aggregated counters, charts, export artifacts, and informational pages must strictly respect the following presentation constraints:
1. Every public page footer, landing screen, registration modal, and analytics view must prominently display the official non-affiliation disclaimer.
2. All analytics figures, timelines, and trend metrics must be explicitly captioned as **"Community-reported data"** or **"Based on voluntary candidate submissions"**. They must **never** be titled or implied to be "Official TCS Statistics" or "TCS Corporate Data".
3. Visual branding must avoid replicating proprietary TCS corporate trademarks, logos, or typography to prevent candidate confusion or legal misrepresentation. The visual identity is that of a modern, clean, supportive peer-community tool.

---

# 1. Document Overview & Goals

This document provides the definitive, comprehensive UI/UX specification for the TCS Joining Tracker MVP. It bridges the product requirements (`01_PRODUCT_REQUIREMENTS.md`), candidate journeys (`02_USER_FLOWS.md`), relational database models (`03_DATABASE_DESIGN.md`), and backend REST endpoints (`04_API_SPECIFICATION.md`) into a pixel-precise, state-aware frontend architecture.

### Primary UI/UX Objectives:
- **Clarity & Anxiety Reduction:** Candidates waiting for months for their Joining Letter (JL) experience uncertainty and stress. The UI must present timeline milestones with reassuring clarity, honest progress states, and clear community benchmarks.
- **Privacy by Default:** Candidates fear repercussions if their participation is linked to their official TCS candidature. The UI must emphasize anonymous participation, customizable display handles, and strict separation between private auth credentials and public posts.
- **Mobile-First Ergonomics:** Over 75% of candidate visits occur via smartphones (Android/iOS) while on the move or checking emails. The layout, navigation, touch targets, and typography must provide a native-app feel on mobile devices.
- **Information Density vs. Readability:** Provide actionable timeline data and vibrant community discussions without sensory overload. Employ clean cards, generous whitespace, scannable badges, and structured tabs.
- **Zero Ambiguity States:** Every component must have explicitly defined states: default, hover, focus-visible, active, loading/skeleton, empty, disabled, error, and optimistic updates.

---

# 2. Design Philosophy & Core Principles

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                     CORE DESIGN PRINCIPLES                      │
  ├───────────────┬───────────────┬────────────────┬────────────────┤
  │ 1. Community  │ 2. Privacy    │ 3. Mobile-     │ 4. Truth in    │
  │    First      │    First      │    First       │    Data        │
  │ Peer support  │ Default anon; │ Thumb-friendly │ Distinctly     │
  │ & transparent │ no identity   │ bottom tabs &  │ community-     │
  │ discussion.   │ leaks ever.   │ 44px targets.  │ reported data. │
  └───────────────┴───────────────┴────────────────┴────────────────┘
```

### 2.1 Community First
Candidates turn to WhatsApp, Telegram, and Reddit groups where conversations get buried. The application surfaces high-value community signals:
- Structured discussion threads categorized by topic (`JOINING_LETTER`, `OFFER`, `LOCATION`, etc.).
- Upvoting mechanism to elevate verified or widely acknowledged timeline updates.
- Pinned administrative announcements to warn candidates of common scams, offer letter verification tips, and onboarding instructions.

### 2.2 Privacy First (Public Identity Modes)
Candidates can toggle their public display mode at any time without disrupting historical data integrity:
- **`ANONYMOUS` (Default):** Rendered as `Anonymous Candidate • [Batch] • [Hiring Type] • [Region]` (e.g., `Anonymous Candidate • 2025 • Digital • Hyderabad`). Generates a deterministic, pleasant pastel avatar based on an internal random salt so discussions remain followable without revealing names.
- **`DISPLAY_NAME`:** Rendered using the user-chosen public handle (e.g., `Sai T. • 2025 • Digital • Hyderabad`).
- **Absolute Privacy Barrier:** The frontend must never render email addresses, phone numbers, FCM device tokens, IP addresses, internal user IDs, or password reset tokens.

### 2.3 Mobile-First Ergonomics
- Base designs are drafted for a 375px viewport (common iPhone / Android width) and scale upwards to tablet (768px) and desktop (1024px, 1280px+).
- Critical navigation is housed within an ergonomic **Mobile Bottom Tab Bar** positioned inside the natural thumb-sweep zone.
- Minimum interactive touch target is **44 × 44 pixels** (conforming to Apple HIG and WCAG 2.1 AA).

### 2.4 Data Transparency & Truth-in-Labeling
- Aggregated numbers must never claim false authority.
- When filters produce fewer than **5 candidates**, data suppression is activated: *"Not enough community data to display this breakdown (minimum 5 submissions required to protect candidate anonymity)."*
- Disclaimers appear alongside metric cards and chart legends.

### 2.5 Simplicity & Focused Velocity
- Zero superfluous UI clutter. No complex nested comment trees (strictly capped at 1-level child replies).
- Fast page loads via server-assisted pagination (20 items per page), lightweight SVG icons (Lucide React), and optimized client-side state caching.

### 2.6 Accessibility (WCAG 2.1 Level AA)
- High-contrast color pairings meeting minimum 4.5:1 ratio for normal text and 3:1 for large text/graphic elements.
- Full keyboard operability (tab navigation, visible 2px focus rings, Escape key dismissal of overlays).
- Proper ARIA live regions for asynchronous updates (toasts, upvote toggles, submission errors).

---

# 3. Information Architecture & Navigation Hierarchy

```
                                GLOBAL SITEMAP
                                      │
     ┌────────────────────────────────┴────────────────────────────────┐
     ▼                                                                 ▼
[VISITOR / PUBLIC ROUTES]                           [AUTHENTICATED CANDIDATE ROUTES]
  │                                                   │
  ├── / (Landing Page)                                ├── /dashboard (Candidate Overview)
  ├── /login                                          ├── /timeline (Recruitment Roadmap)
  ├── /register                                       │     ├── [Modal: Add Event]
  ├── /verify-email-pending                           │     └── [Modal: Edit Event]
  ├── /verify-email/:token                            ├── /community (Discussion Feed)
  ├── /forgot-password                                │     ├── /community/create (New Post)
  ├── /reset-password/:token                          │     ├── /community/posts/:id (Detail & Comments)
  ├── /community (Public Feed View)                   ├── /analytics (Community Trends)
  ├── /community/posts/:id (Public Post)              ├── /notifications (Notification Center)
  ├── /about (Platform Purpose)                       └── /settings (Account & Profile Settings)
  ├── /privacy (Data Policy)                                ├── /settings/profile (Profile Info)
  └── /terms (Terms of Service)                             ├── /settings/privacy (Identity Mode)
                                                            ├── /settings/security (Password)
                                                            ├── /settings/devices (FCM Devices)
                                                            └── /settings/danger (Delete Account)
```

## 3.1 Route Access Control Matrix

| Route | Path | Allowed Roles | Unauthenticated Behavior |
|---|---|---|---|
| Landing Page | `/` | All (Visitor, Candidate, Admin) | Renders full landing page with CTAs |
| Login Screen | `/login` | Unauthenticated Visitors | Redirects authenticated users to `/dashboard` |
| Registration Screen | `/register` | Unauthenticated Visitors | Redirects authenticated users to `/dashboard` |
| Verification Pending | `/verify-email-pending` | Unauthenticated (post-register) | Accessible; resend verification token link |
| Verification Action | `/verify-email/:token` | Unauthenticated / All | Validates token, redirects to `/onboarding/profile` |
| Forgot Password | `/forgot-password` | Unauthenticated Visitors | Accessible |
| Reset Password | `/reset-password/:token` | Unauthenticated Visitors | Validates reset token; displays new password form |
| Dashboard | `/dashboard` | Candidate, Admin | Redirects unauthenticated to `/login?next=/dashboard` |
| Personal Timeline | `/timeline` | Candidate, Admin | Redirects unauthenticated to `/login?next=/timeline` |
| Community Feed | `/community` | All (Public Read) | Visitors can read posts; clicking "Create", "Upvote", or "Comment" prompts Login Modal |
| Post Detail | `/community/posts/:id` | All (Public Read) | Visitors can read; writing comments or voting triggers Login Modal |
| Create Post | `/community/create` | Candidate, Admin | Redirects unauthenticated to `/login?next=/community/create` |
| Community Analytics | `/analytics` | All (Public Read) | Aggregate community statistics, trends, and charts |
| Notifications | `/notifications` | Candidate, Admin | Redirects unauthenticated to `/login?next=/notifications` |
| Profile & Settings | `/settings` | Candidate, Admin | Redirects unauthenticated to `/login?next=/settings` |
| Admin Reports Queue | `/admin/moderation/reports` | Administrator Only (`is_staff`) | Returns 403 Forbidden / redirects to `/dashboard` for non-staff |
| Admin Announcements | `/admin/announcements` | Administrator Only (`is_staff`) | Returns 403 Forbidden / redirects to `/dashboard` for non-staff |
| Informational Pages | `/about`, `/privacy`, `/terms` | All | Accessible publicly |

---

# 4. Design Tokens & Visual Style Guide

The visual design system utilizes a modern, trust-inspiring palette grounded in professional slate neutrals, vibrant primary indigos, and unambiguous semantic status accents.

```
       COLOR SYSTEM PALETTE
  ┌─────────────────────────────────┐
  │ Primary Brand: Indigo / Blue    │  #4F46E5 (Indigo 600) / #3B82F6 (Blue 500)
  ├─────────────────────────────────┤
  │ Neutral Slate: Background & UI  │  #0F172A (Slate 900) to #F8FAFC (Slate 50)
  ├─────────────────────────────────┤
  │ Semantic Status:                │
  │ • Completed / Joined: Emerald   │  #10B981 (Emerald 500)
  │ • Waiting / Survey: Amber       │  #F59E0B (Amber 500)
  │ • Letter Received: Indigo/Sky   │  #0EA5E9 (Sky 500)
  │ • Error / Danger: Rose/Red      │  #EF4444 (Red 500)
  └─────────────────────────────────┘
```

## 4.1 Color Palette & Semantic System

### 4.1.1 Primary Brand Colors
- **`brand-50`:** `#EEF2FF` — Ultra-light tint for badge backgrounds, active item highlights.
- **`brand-100`:** `#E0E7FF` — Subtle border accents, interactive pill hover states.
- **`brand-500`:** `#6366F1` — Secondary brand button, interactive toggles.
- **`brand-600`:** `#4F46E5` — **Primary Brand Anchor**. Buttons, active tab underlines, key links.
- **`brand-700`:** `#4338CA` — Hover state for primary buttons and interactive brand elements.
- **`brand-800`:** `#3730A3` — Active/pressed state for primary buttons.
- **`brand-900`:** `#312E81` — Dark mode brand accents and highlighted surfaces.

### 4.1.2 Neutral Palette (Slate Spectrum)
- **`slate-50`:** `#F8FAFC` — App background (Light Mode), card hover fills.
- **`slate-100`:** `#F1F5F9` — Secondary container fill, card header stripes, input background.
- **`slate-200`:** `#E2E8F0` — Default border color (Light Mode), divider rules, skeleton shine.
- **`slate-300`:** `#CBD5E1` — Disabled button border, secondary icon glyphs.
- **`slate-400`:** `#94A3B8` — Placeholder text, helper hints, timestamp captions.
- **`slate-500`:** `#64748B` — Secondary body text, icon idle color, inactive tab labels.
- **`slate-600`:** `#475569` — Medium-contrast copy, table headings, subheaders.
- **`slate-700`:** `#334155` — High-contrast secondary text, card titles, borders (Dark Mode).
- **`slate-800`:** `#1E293B` — Surface containers (Dark Mode), navigation bars, dropdown menus.
- **`slate-900`:** `#0F172A` — App background (Dark Mode), primary body text (Light Mode).
- **`slate-950`:** `#020617` — Deepest contrast background, mobile status bar backdrop.

### 4.1.3 Semantic & Functional Accents
- **Success (`emerald`):**
  - Text/Icon: `#059669` (Light Mode) / `#34D399` (Dark Mode)
  - Surface Background: `#ECFDF5` (Light Mode) / `#064E3B` (Dark Mode)
  - Border: `#A7F3D0` (Light Mode) / `#047857` (Dark Mode)
  - *Usage:* Milestones completed (`JOINED`, `SELECTION`, `OFFER_LETTER`), verified status indicators, toast success alerts.
- **Warning / In-Progress (`amber`):**
  - Text/Icon: `#D97706` (Light Mode) / `#FBBF24` (Dark Mode)
  - Surface Background: `#FFFBEB` (Light Mode) / `#78350F` (Dark Mode)
  - Border: `#FDE68A` (Light Mode) / `#B45309` (Dark Mode)
  - *Usage:* Milestones pending (`WAITING_FOR_JOINING_LETTER`, `READINESS_SURVEY`), verification reminders, caution notices.
- **Information / Notice (`sky`):**
  - Text/Icon: `#0284C7` (Light Mode) / `#38BDF8` (Dark Mode)
  - Surface Background: `#F0F9FF` (Light Mode) / `#0C4A6E` (Dark Mode)
  - Border: `#BAE6FD` (Light Mode) / `#0369A1` (Dark Mode)
  - *Usage:* Milestone achieved (`JOINING_LETTER_RECEIVED`), informational banners, community notes.
- **Danger / Error (`rose` / `red`):**
  - Text/Icon: `#DC2626` (Light Mode) / `#F87171` (Dark Mode)
  - Surface Background: `#FEF2F2` (Light Mode) / `#450A0A` (Dark Mode)
  - Border: `#FECACA` (Light Mode) / `#991B1B` (Dark Mode)
  - *Usage:* Form validation errors, deleted post placeholders, account deletion, ban notices, report badges.

### 4.1.4 Community Category Badge Color Matrix
To facilitate rapid visual scanning in the community feed, each post category is bound to a consistent color combination:

| Category Code | Human Label | Badge Background | Badge Text | Border Accent |
|---|---|---|---|---|
| `JOINING_LETTER` | Joining Letter | `bg-indigo-50 dark:bg-indigo-950/50` | `text-indigo-700 dark:text-indigo-300` | `border-indigo-200 dark:border-indigo-800` |
| `JOINING_DATE` | Joining Date | `bg-sky-50 dark:bg-sky-950/50` | `text-sky-700 dark:text-sky-300` | `border-sky-200 dark:border-sky-800` |
| `OFFER` | Offer Letter | `bg-emerald-50 dark:bg-emerald-950/50` | `text-emerald-700 dark:text-emerald-300` | `border-emerald-200 dark:border-emerald-800` |
| `INTERVIEW` | Interview | `bg-purple-50 dark:bg-purple-950/50` | `text-purple-700 dark:text-purple-300` | `border-purple-200 dark:border-purple-800` |
| `TCS_PROCESS` | TCS Process | `bg-amber-50 dark:bg-amber-950/50` | `text-amber-700 dark:text-amber-300` | `border-amber-200 dark:border-amber-800` |
| `GENERAL` | General | `bg-slate-100 dark:bg-slate-800` | `text-slate-700 dark:text-slate-300` | `border-slate-200 dark:border-slate-700` |
| `DISCUSSION` | Discussion | `bg-blue-50 dark:bg-blue-950/50` | `text-blue-700 dark:text-blue-300` | `border-blue-200 dark:border-blue-800` |
| `HELP` | Help Needed | `bg-rose-50 dark:bg-rose-950/50` | `text-rose-700 dark:text-rose-300` | `border-rose-200 dark:border-rose-800` |
| `ANNOUNCEMENT` | Announcement | `bg-teal-50 dark:bg-teal-950/50` | `text-teal-700 dark:text-teal-300` | `border-teal-200 dark:border-teal-800` |
| `OTHER` | Other | `bg-zinc-100 dark:bg-zinc-800` | `text-zinc-700 dark:text-zinc-300` | `border-zinc-200 dark:border-zinc-700` |

---

## 4.2 Light Mode vs Dark Mode Theme Specification

The application supports explicit theme switching (`Light`, `Dark`, and `System Default`). State is persisted in `localStorage('theme')` and synchronized with the Tailwind CSS `dark` root class.

| UI Element / Surface | Light Mode Token | Dark Mode Token | CSS Variable / Tailwind Class |
|---|---|---|---|
| **App Canvas / Page Background** | `#F8FAFC` (`slate-50`) | `#0F172A` (`slate-900`) | `bg-background` (`bg-slate-50 dark:bg-slate-900`) |
| **Card / Surface Container** | `#FFFFFF` (`white`) | `#1E293B` (`slate-800`) | `bg-surface` (`bg-white dark:bg-slate-800`) |
| **Card Header / Elevated Surface** | `#F1F5F9` (`slate-100`) | `#334155` (`slate-700`) | `bg-surface-elevated` |
| **Primary Text (Headings/Titles)** | `#0F172A` (`slate-900`) | `#F8FAFC` (`slate-50`) | `text-primary` (`text-slate-900 dark:text-slate-50`) |
| **Secondary Text (Body/Descriptions)**| `#475569` (`slate-600`) | `#94A3B8` (`slate-400`) | `text-secondary` (`text-slate-600 dark:text-slate-400`) |
| **Muted / Placeholder Text** | `#94A3B8` (`slate-400`) | `#64748B` (`slate-500`) | `text-muted` (`text-slate-400 dark:text-slate-500`) |
| **Borders & Dividers** | `#E2E8F0` (`slate-200`) | `#334155` (`slate-700`) | `border-default` (`border-slate-200 dark:border-slate-700`) |
| **Input Background** | `#FFFFFF` (`white`) | `#0F172A` (`slate-900`) | `bg-input` (`bg-white dark:bg-slate-900`) |
| **Input Border (Idle)** | `#CBD5E1` (`slate-300`) | `#475569` (`slate-600`) | `border-input` (`border-slate-300 dark:border-slate-600`) |
| **Input Border (Focus Ring)** | `#4F46E5` (`brand-600`) | `#6366F1` (`brand-500`) | `ring-2 ring-brand-500` |
| **Top Navigation / Header Bar** | `rgba(255,255,255,0.85)` + blur | `rgba(30,41,59,0.85)` + blur | `backdrop-blur-md border-b` |
| **Bottom Mobile Tab Bar** | `rgba(255,255,255,0.95)` + blur | `rgba(15,23,42,0.95)` + blur | `backdrop-blur-lg border-t` |
| **Modal / Dialog Backdrop** | `rgba(15,23,42,0.60)` | `rgba(2,6,23,0.80)` | `bg-black/60 dark:bg-black/80` |
| **Skeleton Loader Shine** | `#E2E8F0` / `#F1F5F9` | `#334155` / `#1E293B` | `animate-pulse bg-slate-200 dark:bg-slate-700` |

---

## 4.3 Typography Scale & Font Hierarchy

- **Primary Typeface:** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- **Monospace Typeface (Tokens/IDs/Timestamps):** `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`

| Typographic Role | Font Size (px / rem) | Line Height | Weight | Tracking (Letter Spacing) | Tailwind Class |
|---|---|---|---|---|---|
| **Display / Hero Headline** | `36px / 2.25rem` | `44px / 2.75rem` | Bold (`700`) | `-0.025em` (`tracking-tight`) | `text-4xl font-bold tracking-tight` |
| **Page Title (H1)** | `28px / 1.75rem` | `36px / 2.25rem` | Bold (`700`) | `-0.02em` (`tracking-tight`) | `text-2xl sm:text-3xl font-bold` |
| **Section Header (H2)** | `22px / 1.375rem`| `28px / 1.75rem` | SemiBold (`600`)| `-0.015em` | `text-xl sm:text-2xl font-semibold` |
| **Card / Widget Title (H3)** | `18px / 1.125rem`| `24px / 1.50rem` | SemiBold (`600`)| `-0.01em` | `text-lg font-semibold` |
| **Subhead / Form Label** | `14px / 0.875rem`| `20px / 1.25rem` | Medium (`500`) | `0em` | `text-sm font-medium` |
| **Body Primary** | `15px / 0.9375rem`| `24px / 1.50rem` | Regular (`400`) | `0em` | `text-[15px] leading-relaxed` |
| **Body Secondary / Post Preview**| `14px / 0.875rem`| `20px / 1.25rem` | Regular (`400`) | `0em` | `text-sm leading-normal` |
| **Caption / Helper / Timestamp** | `12px / 0.75rem` | `16px / 1.00rem` | Regular (`400`) | `+0.01em` | `text-xs text-slate-500` |
| **Badge / Pill Tag** | `11px / 0.6875rem`| `14px / 0.875rem`| Medium (`500`) | `+0.02em` (`tracking-wide`) | `text-[11px] font-medium tracking-wide` |
| **Legal Disclaimer / Fine Print**| `11px / 0.6875rem`| `16px / 1.00rem` | Regular (`400`) | `0em` | `text-[11px] leading-normal` |

---

## 4.4 Spacing & Baseline Grid Scale

All UI layout follows a strict **4px / 8px baseline grid**.

```
  px   rem     Tailwind   Typical Application Usage
 ────  ──────  ─────────  ──────────────────────────────────────────
  2px  0.125rem  p-0.5     Focus offset ring, thin indicator pip
  4px  0.25rem   p-1       Tight icon button padding, badge internal gap
  8px  0.50rem   p-2       Button small padding, input vertical gap
 12px  0.75rem   p-3       Standard input padding, dropdown item padding
 16px  1.00rem   p-4       Card padding (mobile), standard column gap
 20px  1.25rem   p-5       Card padding (tablet/desktop)
 24px  1.50rem   p-6       Large container padding, modal body inset
 32px  2.00rem   p-8       Section separation, empty state container
 48px  3.00rem   p-12      Page header margin, landing hero vertical gap
 64px  4.00rem   p-16      Landing page major block separation
```

---

## 4.5 Elevation, Shadows, and Surface Layering

Depth is communicated through layered surfaces and diffused shadows to maintain modern visual crispness without muddy gradients:

- **`shadow-none`:** Flat inputs, embedded timeline cards, secondary table cells.
- **`shadow-xs` (`0 1px 2px 0 rgba(0, 0, 0, 0.05)`):** Form controls, idle button elements, category chips.
- **`shadow-sm` (`0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)`):** Standard content cards, post feed cards, stat widgets.
- **`shadow-md` (`0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)`):** Dropdown menus, popovers, mobile bottom navigation bar.
- **`shadow-lg` (`0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)`):** Slide-over drawers, sticky floating action buttons (FAB).
- **`shadow-xl` (`0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)`):** Modals, confirmation dialogs, report dialogs.

---

## 4.6 Border Radii & Border Widths

- **`rounded-none`:** 0px — Not used in primary UI.
- **`rounded-sm`:** 2px — Sub-badges, code tags.
- **`rounded-md`:** 6px — Form inputs, select controls, date pickers.
- **`rounded-lg`:** 8px — Standard buttons, dropdown menus, toast notifications.
- **`rounded-xl`:** 12px — Post cards, timeline cards, metric widgets.
- **`rounded-2xl`:** 16px — Modals, hero banner containers, mobile action sheets.
- **`rounded-full`:** 9999px — User avatar containers, category pills, voting pill buttons, icon action circles.
- **Standard Border Width:** 1px (`border`), used universally for clean card and divider demarcation. Focus indicators use 2px outline rings (`ring-2 ring-brand-500 ring-offset-2`).

---

## 4.7 Responsive Breakpoints & Viewport Grid System

| Breakpoint Name | Min Width | Target Devices | Grid Columns & Content Max-Width |
|---|---|---|---|
| **`xs` (Base)** | `< 640px` | Smart phones (iPhone 13/14/15, Galaxy S21, Pixel) | 1 Column stacked; full-width cards; 16px horizontal page margins. |
| **`sm`** | `640px` | Large phones in landscape, phablets | 1 Column; max-w-xl centered container. |
| **`md`** | `768px` | Tablets (iPad mini, Galaxy Tab) | 2 Columns; side navigation collapses to compact drawer; 24px margins. |
| **`lg`** | `1024px` | Laptops, desktop monitors | 3 Columns: 240px Left Nav + 680px Main Stream + 320px Right Rail. |
| **`xl`** | `1280px` | Wide desktop displays | 3 Columns: 260px Left Nav + 720px Main Stream + 360px Right Rail; max-w-7xl centered. |
| **`2xl`** | `1536px` | Ultra-wide monitors | Same 3 Columns, auto-centered with balanced side gutters. |

# 5. Layout Shells & Global Elements

## 5.1 Unauthenticated Visitor Shell

The visitor shell is designed for landing, static informational pages (`/about`, `/privacy`, `/terms`), and authentication screens (`/login`, `/register`, `/forgot-password`).

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ [LOGO] TCS Joining Tracker           [Community] [About]  [Login] [Register]│
  ├─────────────────────────────────────────────────────────────────────────────┤
  │                                                                             │
  │                           MAIN PAGE CONTENT AREA                            │
  │                                                                             │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ FOOTER:                                                                     │
  │ © 2026 TCS Joining Tracker • Community-Driven Platform                     │
  │ [About] • [Privacy Policy] • [Terms of Service] • [Explore Community]       │
  │                                                                             │
  │ DISCLAIMER:                                                                 │
  │ TCS Joining Tracker is an independent community platform and is not         │
  │ affiliated with, endorsed by, or operated by Tata Consultancy Services      │
  │ (TCS). Information displayed on the platform is primarily user-submitted    │
  │ and may not represent official TCS information.                             │
  └─────────────────────────────────────────────────────────────────────────────┘
```

### Layout Specifications:
- **Header Height:** `64px` (`h-16`). Sticky positioning (`sticky top-0 z-40`).
- **Surface:** `bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800`.
- **Branding:** Left-aligned. Stylized SVG timeline node glyph + text **"TCS Joining Tracker"** (semibold, tracking-tight).
- **Navigation Links:** Medium grey text (`text-slate-600 dark:text-slate-400`), hover to primary brand (`hover:text-brand-600`).
- **Call-to-Action (CTA):** Primary button **"Register"** (`bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2`).

---

## 5.2 Authenticated Candidate Desktop Shell (3-Column Layout)

For viewports >= 1024px (`lg`), the platform uses an optimized three-column architecture that keeps personal status, community feed, and community benchmarks concurrently visible.

```
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ [!] ANNOUNCEMENT: TCS 2025 Digital Joining Letters reported in Hyderabad region. [Read Update ×] │
  ├───────────────┬───────────────────────────────────────────────────┬──────────────────────────────┤
  │ [LOGO] Tracker│ TOP BAR: Search Community...            [+] Post  │  [🔔 3]  [Sai T. (Avatar) ▼] │
  ├───────────────┼───────────────────────────────────────────────────┼──────────────────────────────┤
  │ LEFT SIDEBAR  │ CENTRAL MAIN WORKSPACE (max-w-3xl)                │ RIGHT RAIL WIDGETS           │
  │ (240px Fixed) │                                                   │ (320px Fixed)                │
  │               │ [PAGE HEADER: Title & Primary Actions]            │                              │
  │ [📊 Dashboard]│                                                   │ ┌──────────────────────────┐ │
  │ [📍 Timeline] │ ┌───────────────────────────────────────────────┐ │ │ MY STATUS SUMMARY        │ │
  │ [💬 Community]│ │                                               │ │ │ WAITING FOR JOINING    │ │
  │ [📈 Analytics]│ │                                               │ │ │ LETTER (Since 15 May)  │ │
  │ [🔔 Alerts (3)│ │               ACTIVE VIEW                     │ │ └──────────────────────────┘ │
  │ [⚙️ Settings] │ │                                               │ │ ┌──────────────────────────┐ │
  │               │ │         (Feed / Timeline / Details)           │ │ │ COMMUNITY PULSE        │ │
  │ ───────────── │ │                                               │ │ │ 1,248 Candidates Tracked│ │
  │ [?] About     │ │                                               │ │ │ 210 Received JL        │ │
  │ [🔒] Privacy  │ └───────────────────────────────────────────────┘ │ │ *Community-reported data │ │
  │ [🚪] Logout   │                                                   │ └──────────────────────────┘ │
  ├───────────────┴───────────────────────────────────────────────────┴──────────────────────────────┤
  │ GLOBAL FOOTER & TCS NON-AFFILIATION DISCLAIMER                                                   │
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Column Constraints:
- **Left Sidebar:** `w-60` (240px), sticky (`sticky top-16 h-[calc(100vh-4rem)]`), vertical scrollable if overflow. Contains primary app navigation links with active state pills.
- **Center Stream:** Fluid flex column with `max-w-2xl` or `max-w-3xl` depending on route, centered with `px-6 py-6`.
- **Right Rail:** `w-80` (320px), sticky. Houses the Candidate Quick Status Widget, Community Aggregates counter, and Trending Topics list. Suppressed on smaller desktop widths if viewport shrinks below 1024px.

---

## 5.3 Authenticated Candidate Tablet Shell (2-Column Layout)

For viewports between 768px and 1023px (`md`):
- Right rail widgets collapse into a summary card placed at the top or bottom of the primary workspace.
- Left sidebar transitions to a slim navigation bar (icon-only or top tab strip) or an off-canvas slide-out drawer toggled via a hamburger menu icon.
- Content occupies full available width minus the 64px icon sidebar.

---

## 5.4 Authenticated Candidate Mobile Shell (Top App Bar + Bottom Tab Bar)

For viewports < 768px (`xs` / `sm`), navigation follows standard iOS/Android ergonomics.

```
  ┌─────────────────────────────────────────┐
  │ [LOGO] Tracker          [🔍] [🔔 3] [⚙️]│ <-- Top App Bar (56px)
  ├─────────────────────────────────────────┤
  │                                         │
  │                                         │
  │           MOBILE MAIN CONTENT           │
  │           (Full width, px-4)            │
  │                                         │
  │                                         │
  │                                         │
  ├─────────────────────────────────────────┤
  │  [🏠]      [📍]      [💬]      [📈]   [👤]│ <-- Bottom Tab Bar (60px)
  │  Home   Timeline  Community  Trends  You│
  └─────────────────────────────────────────┘
```

### Mobile Layout Specifications:
- **Top App Bar:** `h-14` (56px), sticky at top (`top-0 z-40`). Holds brand logo, quick search trigger icon, notification bell with unread badge counter, and settings cog.
- **Bottom Tab Bar:** `h-16` (64px), sticky at bottom (`fixed bottom-0 left-0 right-0 z-50`), `pb-safe` (supporting iOS Home Indicator bar).
  - 5 Tab Slots:
    1. **Home / Dashboard** (Home icon)
    2. **Timeline** (Milestone / Git-commit icon)
    3. **Community** (MessageSquare icon)
    4. **Analytics / Trends** (BarChart3 icon)
    5. **Profile / Settings** (User icon)
- **Active Tab Styling:** `text-brand-600 dark:text-brand-400 font-semibold`, indicator dot or top bar pip (`w-1 h-1 bg-brand-600 rounded-full`). Inactive tabs use `text-slate-400 dark:text-slate-500`.

---

## 5.5 Global System Announcement Banner

When an administrative announcement is published and marked `is_pinned = True` (or within expiration date), a prominent banner renders across the top of the viewport above the navbar:

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 📢 NOTICE: TCS Joining Readiness Survey 2025 has started rolling out for    │
  │    Digital batch. [Read Announcement →]                                 [×] │
  └─────────────────────────────────────────────────────────────────────────────┘
```

- **Styling:** `bg-indigo-600 text-white px-4 py-2.5 text-xs sm:text-sm font-medium flex items-center justify-between shadow-sm`.
- **Dismiss Interaction:** Clicking `[×]` stores `announcement_dismissed_{id}` in `localStorage` to prevent showing the banner on subsequent page navigations during the active session.

---

## 5.6 Mandatory Legal & Non-Affiliation Disclaimer Placement

To protect the platform legally and prevent candidate confusion, the disclaimer is permanently positioned in three distinct areas:

1. **Global Sticky Footer:** Placed on all pages (desktop and mobile).
   ```text
   TCS Joining Tracker is an independent community platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS). Information displayed on the platform is primarily user-submitted and may not represent official TCS information.
   ```
2. **Community Analytics Header Callout:**
   ```text
   Notice: All metrics shown below are calculated exclusively from voluntarily submitted candidate data. They do not represent official TCS corporate communications or hiring figures.
   ```
3. **Registration Screen Sub-caption:**
   ```text
   By creating an account, you acknowledge that this is a peer support community and not an official TCS human resources portal.
   ```

---

# 6. UI Component Library Specifications

## 6.1 Buttons

```
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │  Primary Button  │  │ Secondary Button │  │  Outline Button  │
  │  [Icon] Action   │  │  [Icon] Action   │  │  [Icon] Action   │
  └──────────────────┘  └──────────────────┘  └──────────────────┘
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │   Ghost Button   │  │  Danger Button   │  │  Loading Button  │
  │      Action      │  │  Delete Account  │  │   [Spin] Saving  │
  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

### 6.1.1 Button Variants
1. **Primary Button:**
   - Classes: `bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white font-medium rounded-lg shadow-sm focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 transition-colors`
   - Use: Main form submissions, "Create Post", "Add Event", "Register".
2. **Secondary Button:**
   - Classes: `bg-slate-100 hover:bg-slate-200 active:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-100 font-medium rounded-lg shadow-xs transition-colors`
   - Use: Secondary actions, "Cancel", "Save as Draft", "Filter".
3. **Outline Button:**
   - Classes: `border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium rounded-lg transition-colors`
   - Use: Upvoting pill, category selection chips, secondary CTAs.
4. **Ghost Button:**
   - Classes: `bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium rounded-lg transition-colors`
   - Use: Inline table actions, icon-only buttons, modal close `[×]`.
5. **Danger Button:**
   - Classes: `bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white font-medium rounded-lg shadow-sm focus-visible:ring-2 focus-visible:ring-rose-500 transition-colors`
   - Use: "Delete Post", "Delete Event", "Confirm Account Deletion", "Ban User".

### 6.1.2 Button Sizes & Specifications

| Size Token | Height | Padding (X / Y) | Font Size | Icon Size | Minimum Target |
|---|---|---|---|---|---|
| **`sm`** | `32px` (`h-8`) | `px-3 py-1.5` | `text-xs` (12px) | `14 × 14px` | Desktop compact |
| **`md` (Default)** | `40px` (`h-10`) | `px-4 py-2` | `text-sm` (14px) | `16 × 16px` | Standard buttons |
| **`lg`** | `48px` (`h-12`) | `px-6 py-3` | `text-base` (16px) | `20 × 20px` | Primary Mobile CTAs |

### 6.1.3 Interactive Button States
- **Hover:** Darkens background by 1 shade (e.g., `brand-600` to `brand-700`).
- **Active/Pressed:** Scale down slightly (`active:scale-[0.98]`), darkens background to `brand-800`.
- **Focus-Visible:** Accessible 2px offset ring (`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2`).
- **Disabled:** `opacity-50 cursor-not-allowed pointer-events-none`.
- **Loading:** Label replaced or paired with spinning circle icon (`animate-spin w-4 h-4 mr-2`), button remains disabled to prevent duplicate network submissions.

---

## 6.2 Form Inputs & Controls

```
  ┌────────────────────────────────────────────────────────┐
  │ Email Address *                                        │
  │ ┌────────────────────────────────────────────────────┐ │
  │ │ candidate@example.com                              │ │
  │ └────────────────────────────────────────────────────┘ │
  │ We'll never share your email address publicly.         │
  └────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────┐
  │ Password *                                  [👁️ Show] │
  │ ┌────────────────────────────────────────────────────┐ │
  │ │ ••••••••••••••                                     │ │
  │ └────────────────────────────────────────────────────┘ │
  │ [!] Password must be at least 8 characters long.       │ <-- Error state
  └────────────────────────────────────────────────────────┘
```

### 6.2.1 Input Field Types & Specifications
- **Text Input / Email Input:**
  - Container: `flex flex-col gap-1.5`
  - Label: `text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between`
  - Input: `w-full h-10 px-3.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-all`
  - Helper Text: `text-xs text-slate-500 dark:text-slate-400`
  - Error Text: `text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1 font-medium mt-0.5`
- **Password Input with Reveal Toggle:**
  - Includes right-aligned icon button (`h-8 w-8 text-slate-400 hover:text-slate-600`) switching `type="password"` to `type="text"` with `aria-label="Toggle password visibility"`.
- **Textarea with Character Counter:**
  - Used for Community Post Body (`max: 5000 chars`), Comments (`max: 2000 chars`), and Report Notes.
  - Features real-time character tally at bottom-right: `1,240 / 2,000 characters`.
  - Turns warning amber at 90% threshold (`amber-600`), and danger red when exceeding cap (`rose-600`).
- **Select / Dropdown Selector:**
  - Native select styling enhanced with custom SVG chevron arrow, or Radix UI select primitive for custom styling.
  - Heights match standard inputs (40px).
- **Date Picker:**
  - Native HTML5 `<input type="date">` optimized for mobile touch wheels, paired with calendar icon prefix. Fallback to ISO string formatting `YYYY-MM-DD`.

---

## 6.3 Badges, Chips, and Status Indicators

### 6.3.1 Candidate Recruitment Status Badges

| Status Choice | Visual Display Label | Badge Styling (Light / Dark) | Meaning |
|---|---|---|---|
| `REGISTERED` | Registered | `bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300` | Account created; profile pending |
| `INTERVIEWED` | Interviewed | `bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300` | Completed technical/HR interview |
| `SELECTED` | Selected | `bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300` | Selection mail received |
| `OFFER_RECEIVED` | Offer Received | `bg-teal-100 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300` | Official offer letter issued |
| `READINESS_SURVEY`| Survey Completed | `bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300`| Joining readiness survey submitted |
| `WAITING_FOR_JOINING_LETTER`| Waiting for JL | `bg-amber-100 text-amber-900 border border-amber-300 animate-pulse` | Actively waiting for joining letter |
| `JOINING_LETTER_RECEIVED` | JL Received | `bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300` | Joining letter issued |
| `JOINING_DATE_RECEIVED` | Joining Date Set | `bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300` | Onboarding date confirmed |
| `JOINED` | Joined TCS | `bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300`| Successfully onboarded |
| `WITHDRAWN` | Withdrawn | `bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300` | Candidate declined or withdrew |
| `OTHER` | Other | `bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300` | Custom recruitment state |

---

## 6.4 Cards & Surface Containers

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ [Category: JOINING_LETTER]                       Posted 2 hours ago   │
  │                                                                        │
  │ Has anyone from 2025 Digital Hyderabad received JL yet?                │
  │ Completed survey on May 15th, still showing pending on portal...       │
  │                                                                        │
  │ 👤 Anonymous Candidate • 2025 • Digital • Hyderabad                    │
  ├────────────────────────────────────────────────────────────────────────┤
  │ [▲ 42 Upvotes]       [💬 18 Comments]       [🔗 Share]       [⚑ Report] │
  └────────────────────────────────────────────────────────────────────────┘
```

- **Card Container:** `bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 sm:p-5 shadow-sm hover:border-slate-300 dark:hover:border-slate-600 transition-all`
- **Clickable Card Surface:** Entire post card functions as a link to `/community/posts/:id`, while internal buttons (Upvote, Share, Author profile) stop event propagation (`e.stopPropagation()`).

---

## 6.5 User Identity & Avatar Presentation

To fulfill the strict **Privacy-First** requirement, user identities are rendered uniformly using one of two standardized identity pills:

```
  ANONYMOUS MODE:
  ┌──────────────────────────────────────────────────────────────────┐
  │ (🎭) Anonymous Candidate • 2025 • Digital • Hyderabad             │
  └──────────────────────────────────────────────────────────────────┘

  DISPLAY NAME MODE:
  ┌──────────────────────────────────────────────────────────────────┐
  │ (ST) Sai T. • 2025 • Digital • Hyderabad                         │
  └──────────────────────────────────────────────────────────────────┘
```

### Identity Rendering Rules:
1. **Avatar Circle:** `36 × 36px` (`w-9 h-9 rounded-full flex items-center justify-center font-semibold text-xs`).
   - For `ANONYMOUS`: Displays a generic stylized mask or silhouette glyph with a randomized, deterministic pastel background (`bg-indigo-100 text-indigo-700`).
   - For `DISPLAY_NAME`: Displays the 2-letter uppercase initials (e.g., `ST` for "Sai Teja") with background color computed from the hash of the display name.
2. **Metadata Tagline:** Accompanied by three verified candidate attributes:
   - `[Batch]` (e.g., `2025`)
   - `[Hiring Type]` (e.g., `Digital`, `Prime`, `Ninja`)
   - `[Region / Interview Center]` (e.g., `Hyderabad`)
3. **No Private Leaks:** Under no circumstances may email addresses or real full names be exposed in public threads.

---

## 6.6 Dialogs, Modals, & Bottom Drawers

```
  ┌────────────────────────────────────────────────────────┐
  │ Delete Timeline Event?                             [×] │
  ├────────────────────────────────────────────────────────┤
  │ Are you sure you want to remove the "Offer Letter"     │
  │ milestone? This will recalculate your profile status   │
  │ and timeline analytics.                                │
  ├────────────────────────────────────────────────────────┤
  │                       [Cancel]   [Delete Event (Red)]  │
  └────────────────────────────────────────────────────────┘
```

- **Desktop Presentation:** Centered overlay dialog (`max-w-md w-full bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6 border border-slate-200 dark:border-slate-700`).
- **Mobile Presentation (< 640px):** Transitions smoothly into an ergonomic **Bottom Sheet Drawer** docked at the screen bottom with a tactile pull-handle bar (`w-12 h-1.5 bg-slate-300 rounded-full mx-auto mb-4`).
- **Focus Trap:** Focus is trapped inside the active dialog; pressing `Escape` closes the modal; clicking the backdrop (`bg-black/60 backdrop-blur-xs`) dismisses the overlay safely.

---

## 6.7 Feedback, Skeletons, and Toast Notifications

### 6.7.1 Toast Notification System
Toasts deliver asynchronous confirmation of user actions:

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ (✓) Joining letter milestone added to your timeline.              [×]  │
  └────────────────────────────────────────────────────────────────────────┘
```

- **Positioning:** Desktop: bottom-right (`fixed bottom-6 right-6 z-50 flex flex-col gap-2`). Mobile: top-center (`fixed top-4 left-4 right-4 z-50`).
- **Variants:**
  - `Success`: `bg-emerald-900/90 text-emerald-100 border border-emerald-700`
  - `Error`: `bg-rose-900/90 text-rose-100 border border-rose-700`
  - `Info`: `bg-slate-900/90 text-slate-100 border border-slate-700`
- **Auto-Dismiss:** Automatically fades out after **4,000 ms**; pauses timer on mouse hover or touch press.

### 6.7.2 Skeleton Shimmer Loaders
During API queries, screens render structural placeholders instead of generic spinner wheels to minimize perceived latency:

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ [████████ 120px]                                        [████ 60px]    │
  │ [██████████████████████████████████████████████████████████████]       │
  │ [████████████████████████████████████████]                             │
  │                                                                        │
  │ (O) [██████████ 180px]                                                 │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## 6.8 Voting Component (Upvote Pill)

The community post upvote button uses an explicit toggle state:

```
  IDLE / UNVOTED STATE:              ACTIVE / VOTED STATE:
  ┌───────────────────────┐          ┌───────────────────────┐
  │  ▲ Upvote   |   42    │          │  ▲ Upvoted  |   43    │  <-- Filled Brand Blue
  └───────────────────────┘          └───────────────────────┘
```

- **Classes (Idle):** `flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-xs font-semibold hover:bg-brand-50 hover:border-brand-300 hover:text-brand-600 transition-all`
- **Classes (Active / Voted):** `flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-50 dark:bg-brand-950/80 border border-brand-500 text-brand-600 dark:text-brand-400 text-xs font-semibold shadow-xs`
- **Micro-Interaction:** Clicking triggers an immediate **optimistic UI counter increment (+1)** and subtle scale pulse (`scale-110` for 150ms) before the API request completes. If the API fails with an error, the state smoothly rolls back to the original vote count with an error toast.

# 7. Detailed Page & Screen Specifications (Part 1)

## 7.1 Landing Page (`/`)

The landing page serves as the public gateway. Its goal is to convert anxious candidates into registered members while being transparent about its non-affiliation with TCS.

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ [LOGO] TCS Joining Tracker           [Community] [About]       [Login] [Register]│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                                                  │
  │   HERO SECTION:                                                                  │
  │   Waiting for your TCS Joining Letter?                                           │
  │   Track your recruitment journey, compare community-reported timelines,          │
  │   and connect with fellow candidates in the same batch.                          │
  │                                                                                  │
  │   [Create Free Account]              [Explore Community Feed]                    │
  │                                                                                  │
  │   🛡️ 100% Anonymous by Default • Voluntary Peer Data • Independent Platform     │
  │                                                                                  │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │   LIVE COMMUNITY BENCHMARKS (COMMUNITY-REPORTED DATA):                           │
  │   ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐  │
  │   │ 1,248            │ 210              │ 87               │ 42               │  │
  │   │ Candidates       │ Reported Joining │ Reported Joining │ Reported Joined  │  │
  │   │ Tracked          │ Letter Received  │ Date Confirmed   │ TCS              │  │
  │   └──────────────────┴──────────────────┴──────────────────┴──────────────────┘  │
  │   *Figures represent voluntary user submissions and are not official TCS metrics.│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │   CORE CAPABILITIES:                                                             │
  │   ┌────────────────────────┬────────────────────────┬────────────────────────┐   │
  │   │ 📍 Personal Timeline   │ 💬 Peer Discussions    │ 📊 Aggregate Trends    │   │
  │   │ Record your interview, │ Ask questions about    │ See average wait times │   │
  │   │ selection, and survey  │ batches, locations, and│ between survey and JL  │   │
  │   │ milestones in one place│ document verification. │ across hiring streams. │   │
  │   └────────────────────────┴────────────────────────┴────────────────────────┘   │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │   RECENT COMMUNITY DISCUSSIONS:                                                  │
  │   • "Has anyone from 2025 Digital Hyderabad received JL?" (42 upvotes • 18 cmts) │
  │   • "Readiness survey submitted on May 15 — what's next?" (29 upvotes • 12 cmts) │
  │   • "Joining locations discussion for Prime candidates"   (15 upvotes • 6 cmts)  │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │   FOOTER & MANDATORY TCS NON-AFFILIATION DISCLAIMER                              │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Landing Page UX Requirements:
1. **Hero Value Proposition:** Direct, empathetic, and clear. Explains the core purpose in under 5 seconds.
2. **Dual Call to Action:**
   - Primary: `[Create Free Account]` -> links to `/register`.
   - Secondary: `[Explore Community Feed]` -> links to `/community` (visitors can browse posts without logging in).
3. **Live Aggregate Counters:** Fetched from `/api/v1/public/stats/`. Displays animated count-up numbers on page load.
4. **Mandatory Disclaimer:** Prominently positioned directly under the stats cards and repeated in the global footer.

---

## 7.2 Authentication Screens

```
  REGISTRATION SCREEN (/register)               LOGIN SCREEN (/login)
  ┌─────────────────────────────────────┐       ┌─────────────────────────────────────┐
  │ [LOGO] TCS Joining Tracker          │       │ [LOGO] TCS Joining Tracker          │
  │ Create Candidate Account            │       │ Welcome Back                        │
  │ Track your timeline anonymously     │       │ Access your recruitment dashboard   │
  ├─────────────────────────────────────┤       ├─────────────────────────────────────┤
  │ Email Address *                     │       │ Email Address                       │
  │ [ candidate@example.com           ] │       │ [ candidate@example.com           ] │
  │                                     │       │                                     │
  │ Password *                 [👁️ Show]│       │ Password                   [👁️ Show]│
  │ [ •••••••••••••••••               ] │       │ [ •••••••••••••••••               ] │
  │ At least 8 characters with numbers  │       │                                     │
  │                                     │       │ [ ] Remember me   [Forgot Password?]│
  │ Confirm Password *                  │       │                                     │
  │ [ •••••••••••••••••               ] │       │ [  Log In                         ] │
  │                                     │       │                                     │
  │ [ Create Account                  ] │       │ Don't have an account? [Register]   │
  │                                     │       │                                     │
  │ Already have an account? [Log In]   │       │                                     │
  │                                     │       │                                     │
  │ ⚖️ Independent community platform   │       │ ⚖️ Independent community platform   │
  └─────────────────────────────────────┘       └─────────────────────────────────────┘
```

### 7.2.1 Registration Screen (`/register`)
- **Fields:** Email, Password, Password Confirmation.
- **Client-Side Validation:**
  - Email: Valid regex format, normalized to lowercase.
  - Password: Minimum 8 characters, containing at least one digit and one letter.
  - Confirmation: Matches password exactly in real time.
- **Security Microcopy:** *"We never share your email address with other candidates or external parties."*
- **Post-Submission:** On HTTP 201, navigates to `/verify-email-pending`.

### 7.2.2 Email Verification Pending Screen (`/verify-email-pending`)
- Displays an envelope graphic with the registered email address highlighted in bold.
- Instructions: *"We sent a verification link to your email. Please click the link to activate your account and set up your candidate profile."*
- Action: Secondary outline button **"Resend Verification Email"** with a 60-second cooldown timer.

### 7.2.3 Email Verification Confirm Screen (`/verify-email/:token`)
- Shows a loading state while validating the token with `POST /api/v1/auth/verification/verify/`.
- **Success State:** Displays checkmark animation + *"Email verified successfully! Let's set up your profile."* -> Auto-redirects to `/onboarding/profile` in 2 seconds.
- **Error State:** Displays warning banner if token is expired or invalid, with a direct button to request a fresh verification link.

### 7.2.4 Login Screen (`/login`)
- **Fields:** Email, Password.
- **Error Feedback:** Generic failure message (*"Invalid email or password"*) to prevent user enumeration attacks.
- **Unverified Account Flow:** If backend returns `is_verified: false`, UI displays an inline banner: *"Your email is not verified yet. [Resend Verification Email]"*.

### 7.2.5 Forgot Password Screen (`/forgot-password`)
- Single input for Email address + **"Send Reset Instructions"** button.
- Generic success state: *"If an account exists for this email, we have dispatched password reset instructions."*

### 7.2.6 Password Reset Confirm Screen (`/reset-password/:token`)
- Fields: New Password, Confirm New Password.
- On success: Displays confirmation alert and provides a direct CTA to **"Log In with New Password"**.

---

## 7.3 Candidate Onboarding Flow

Following email verification, the candidate is guided through a streamlined 3-step setup wizard that takes under 60 seconds.

```
  ONBOARDING WIZARD — STEP 1: CANDIDATE PROFILE DETAILS
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Step 1 of 3: Profile Details    [●──────○──────○]                 [Skip for Now] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Tell us about your TCS Candidature                                               │
  │ This helps match you with other candidates in the same situation.                │
  │                                                                                  │
  │ Batch Year *                         Hiring Stream *                             │
  │ [ 2025                       ▼ ]     [ Digital                           ▼ ]     │
  │                                      (Prime / Digital / Ninja / Other)           │
  │                                                                                  │
  │ Region / State *                     Interview Center (Optional)                 │
  │ [ Telangana                  ▼ ]     [ Hyderabad Gachibowli                ]     │
  │                                                                                  │
  │ Current Status *                                                                 │
  │ [ Waiting for Joining Letter                                                 ▼ ] │
  │                                                                                  │
  │ Expected / Preferred Joining Location (Optional)                                 │
  │ [ Hyderabad                                                        ]             │
  │                                                                                  │
  │                                                         [Continue to Step 2 →]   │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

```
  ONBOARDING WIZARD — STEP 2: PUBLIC IDENTITY MODE
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Step 2 of 3: Privacy & Identity [●──────●──────○]                                │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Choose How You Appear in Discussions                                             │
  │ You can change this setting at any time in your profile settings.                │
  │                                                                                  │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ (●) ANONYMOUS MODE (Recommended)                                             │ │
  │ │     Participate without showing your name. Your posts will display as:       │ │
  │ │     ┌────────────────────────────────────────────────────────┐               │ │
  │ │     │ (🎭) Anonymous Candidate • 2025 • Digital • Hyderabad   │               │ │
  │ │     └────────────────────────────────────────────────────────┘               │ │
  │ ├──────────────────────────────────────────────────────────────────────────────┤ │
  │ │ ( ) CUSTOM DISPLAY NAME                                                      │ │
  │ │     Choose a public handle or nickname:                                      │ │
  │ │     [ Sai T.                                                         ]       │ │
  │ │     ┌────────────────────────────────────────────────────────┐               │ │
  │ │     │ (ST) Sai T. • 2025 • Digital • Hyderabad               │               │ │
  │ │     └────────────────────────────────────────────────────────┘               │ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │                                                                                  │
  │ [← Back]                                                [Continue to Step 3 →]   │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

```
  ONBOARDING WIZARD — STEP 3: INITIAL TIMELINE SETUP
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Step 3 of 3: Your Timeline      [●──────●──────●]                 [Finish Later] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Record Known Recruitment Milestones                                              │
  │ Enter any recruitment dates you have already completed. Skip future dates.       │
  │                                                                                  │
  │ [✓] Technical / HR Interview Date                                                │
  │     Date: [ 2026-04-23 ]        Note: [ Cleared interview on first attempt ]     │
  │                                                                                  │
  │ [✓] Selection Mail Date                                                          │
  │     Date: [ 2026-05-05 ]        Note: [ Selected for Digital stream        ]     │
  │                                                                                  │
  │ [✓] Offer Letter Issued Date                                                     │
  │     Date: [ 2026-05-05 ]        Note: [ Accepted on TCS NextStep portal    ]     │
  │                                                                                  │
  │ [✓] Joining Readiness Survey Submitted Date                                      │
  │     Date: [ 2026-05-15 ]        Note: [ Ready for immediate joining        ]     │
  │                                                                                  │
  │ [ ] Joining Letter Received Date (Pending)                                       │
  │                                                                                  │
  │ [← Back]                                                [Complete Setup & Go →]  │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.4 Candidate Dashboard (`/dashboard`)

The dashboard is the central hub after logging in. It aggregates personal timeline progress, peer benchmarks, and trending community activity.

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ WELCOME HEADER:                                                                  │
  │ Hello, Candidate!                                          [Update Timeline]     │
  │ Status: WAITING FOR JOINING LETTER (Since 15 May 2026)      [Ask Question]       │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ YOUR RECRUITMENT PROGRESSION:                                                    │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ (✓) Interview  ── (✓) Selection ── (✓) Offer ── (✓) Survey ── (⏳) JL ── (⏳) Join│ │
  │ │   23 Apr 2026       05 May 2026     05 May 2026   15 May 2026    Pending Pending│ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  ├────────────────────────────────────────┬─────────────────────────────────────────┤
  │ HOW YOU COMPARE (2025 DIGITAL BATCH):  │ COMMUNITY PULSE:                        │
  │ • 1,248 total candidates tracked       │ • 210 candidates received JL            │
  │ • 940 completed readiness survey       │ • Most reported location: Bangalore     │
  │ • Your wait time: 126 days since survey│ • Average wait: 64 days from survey     │
  │ *Community-reported data.              │                                         │
  ├────────────────────────────────────────┴─────────────────────────────────────────┤
  │ LATEST DISCUSSIONS IN YOUR STREAM (DIGITAL):                                     │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ Anyone from Hyderabad got JL for August batch?                 [42 ▲] [18 💬] │
  │ │ Digital • Hyderabad • Posted 2 hours ago by Anonymous Candidate               │
  │ ├──────────────────────────────────────────────────────────────────────────────┤ │
  │ │ Survey 2 rollout status discussion                             [29 ▲] [12 💬] │
  │ │ Digital • General • Posted 5 hours ago by Sai T.                               │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │ [View All Community Discussions →]                                               │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Dashboard Widget Layout:
1. **Status Progression Bar:** Horizontal timeline stepper showing milestone nodes. Completed milestones feature green checkmark badges; pending milestones feature amber pulsing hourglass icons.
2. **Community Benchmark Card:** Calculates candidate's current waiting duration compared to the average duration reported by other community members in the same batch and hiring category.
3. **Stream-Filtered Discussions:** Direct query displaying the top 5 most discussed threads in the candidate's hiring stream.

---

## 7.5 Personal Recruitment Timeline (`/timeline`)

The timeline view is the candidate's definitive personal record. It uses an interactive vertical roadmap design.

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ MY RECRUITMENT TIMELINE                             [+ Add Milestone Event]      │
  │ Current Status: [ Waiting for Joining Letter ▼ ]                                 │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                                                  │
  │  (✓) 15 May 2026 ── JOINING READINESS SURVEY SUBMITTED      [Edit] [Delete]      │
  │   │                 Location preferences: Hyderabad, Bangalore.                  │
  │   │                 Declared immediate availability on portal.                   │
  │   │                                                                              │
  │  (✓) 05 May 2026 ── OFFER LETTER ISSUED                     [Edit] [Delete]      │
  │   │                 Digital stream offer accepted on TCS NextStep.               │
  │   │                                                                              │
  │  (✓) 05 May 2026 ── SELECTION COMMUNICATED                  [Edit] [Delete]      │
  │   │                 Received official selection email.                           │
  │   │                                                                              │
  │  (✓) 23 Apr 2026 ── TECHNICAL & HR INTERVIEW                [Edit] [Delete]      │
  │   │                 Conducted at Hyderabad TCS center.                           │
  │   │                                                                              │
  │  (⏳) PENDING     ── JOINING LETTER                         [Mark as Received]   │
  │   │                 Waiting for official letter issuance.                        │
  │   │                                                                              │
  │  (⏳) PENDING     ── JOINING DATE & ONBOARDING              [Set Date]           │
  │                     Waiting for onboarding batch allocation.                     │
  │                                                                                  │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

```
  ADD / EDIT TIMELINE EVENT MODAL
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Add Timeline Milestone Event                                                 [×] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Event Milestone Type *                                                           │
  │ [ Joining Letter (JOINING_LETTER)                                             ▼ ]│
  │                                                                                  │
  │ Date Occurred *                                                                  │
  │ [ 2026-09-19                         📅 ]                                        │
  │                                                                                  │
  │ Description / Notes (Optional)                                                   │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ Received joining letter email with onboarding date for October 15th.         │ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │ 120 / 500 characters                                                             │
  │                                                                                  │
  │ [✓] Automatically update my current status to "Joining Letter Received"          │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                  [Cancel]    [Save Milestone]    │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Timeline UX Interactions:
1. **Milestone Stepper Line:** A continuous vertical stroke (`w-0.5 bg-slate-200 dark:bg-slate-700`) connecting milestone circles.
2. **Interactive Node Statuses:**
   - Completed: `w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center` with checkmark icon.
   - Pending/Next: `w-8 h-8 rounded-full bg-amber-100 text-amber-600 border-2 border-amber-400 animate-pulse` with hourglass icon.
   - Future: `w-8 h-8 rounded-full bg-slate-100 text-slate-400 border border-slate-300` with circle outline.
3. **Inline Quick Actions:** Uncompleted events feature direct action triggers (e.g., `[Mark as Received]`), which open the pre-filled modal with today's date automatically populated.
4. **Status Synchronization:** When an event of type `JOINING_LETTER` is created, the system prompts to automatically advance `CandidateProfile.current_status` to `JOINING_LETTER_RECEIVED` within the same transaction.

# 7. Detailed Page & Screen Specifications (Part 2)

## 7.6 Community Feed (`/community`)

The community feed organizes discussions, timeline questions, and peer verification reports.

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ COMMUNITY DISCUSSIONS                                    [+ Create New Post]     │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ [🔍 Search posts by keyword, location, or batch...                             ] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ CATEGORIES:                                                                      │
  │ [All] [Joining Letter] [Offer Letter] [Joining Date] [Location] [Interview] [More]│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TABS: [Latest (Newest First)]       [Trending (Most Active)]     [Top Voted]     │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ 📌 PINNED ANNOUNCEMENT                                                           │
  │ Important Community Guidelines & Scam Prevention Advice                          │
  │ TCS never charges money for training, equipment, or joining letter issuance.     │
  │ 👤 Platform Moderator • Pinned • 2 days ago                       [128 ▲] [45 💬]│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ POST CARD:                                                                       │
  │ [JOINING_LETTER]                                              Posted 2 hours ago │
  │ Has anyone from 2025 Digital Hyderabad received their JL yet?                    │
  │ Completed the readiness survey on May 15th with Hyderabad preference. NextStep   │
  │ portal still shows "Offer Accepted". Looking for other candidates in same batch. │
  │                                                                                  │
  │ 👤 Anonymous Candidate • 2025 • Digital • Hyderabad                              │
  │ ┌───────────────────────┐                                                        │
  │ │  ▲ Upvote   |   42    │     💬 18 Comments       🔗 Share       ⚑ Report       │
  │ └───────────────────────┘                                                        │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ POST CARD:                                                                       │
  │ [LOCATION]                                                    Posted 5 hours ago │
  │ Joining location allocation trends for Prime batch                               │
  │ Seeing reports that Bangalore and Chennai are receiving priority dates...        │
  │                                                                                  │
  │ 👤 Sai T. • 2025 • Prime • Chennai                                               │
  │ ┌───────────────────────┐                                                        │
  │ │  ▲ Upvoted  |   29    │     💬 12 Comments       🔗 Share       ⚑ Report       │
  │ └───────────────────────┘                                                        │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ PAGINATION:                                                                      │
  │ Showing 1-20 of 125 posts            [← Previous]   Page [ 1 ] of 7   [Next →]   │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Feed UX Behavior:
1. **Instant Category Filtering:** Clicking a category pill immediately refetches the feed (`GET /api/v1/posts/?category=JOINING_LETTER`) without full-page reload. Active pill highlighted in `brand-600` fill.
2. **Debounced Search Input:** Search bar waits 300ms after keystroke before triggering `GET /api/v1/posts/?search={query}`.
3. **Optimistic Upvote Interaction:** Clicking `[▲ Upvote]` triggers immediate counter update and toggle styling.
4. **Empty State:** If a filter yields zero posts:
   ```text
   No discussions found in this category.
   Be the first candidate to share an update or question.
   [Create Post]
   ```

---

## 7.7 Create Community Post Screen / Modal (`/community/create`)

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Create Community Discussion Post                                             [×] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Title *                                                                          │
  │ [ Enter a concise, descriptive title...                                        ] │
  │ 54 / 200 characters                                                              │
  │                                                                                  │
  │ Category *                                                                       │
  │ [ Joining Letter Updates (JOINING_LETTER)                                     ▼ ]│
  │                                                                                  │
  │ Discussion Body *                                                                │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ Describe your question, update, or experience in detail...                   │ │
  │ │                                                                              │ │
  │ │                                                                              │ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │ 420 / 5,000 characters                                                           │
  │                                                                                  │
  │ Posting Identity Preview:                                                        │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ Posting as: (🎭) Anonymous Candidate • 2025 • Digital • Hyderabad            │ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │ To post with your display name instead, update your Privacy Settings.           │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                    [Cancel]    [Publish Post]    │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.8 Post Detail & Discussion Screen (`/community/posts/:id`)

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ [← Back to Community Feed]                                                       │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ [Category: JOINING_LETTER]                                  Posted 2 hours ago   │
  │                                                                                  │
  │ Has anyone from 2025 Digital Hyderabad received their JL yet?                    │
  │                                                                                  │
  │ I completed the TCS joining readiness survey on May 15th with immediate          │
  │ availability selected and Hyderabad as my preferred location. My NextStep portal │
  │ currently shows "Offer Accepted", but no joining letter has been generated.     │
  │                                                                                  │
  │ Are other candidates in the same batch experiencing similar delays?              │
  │                                                                                  │
  │ 👤 Anonymous Candidate • 2025 • Digital • Hyderabad                              │
  │                                                                                  │
  │ ┌───────────────────────┐                                                        │
  │ │  ▲ Upvote   |   42    │     💬 18 Comments       🔗 Share       ⚑ Report       │
  │ └───────────────────────┘                                                        │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ WRITE A COMMENT:                                                                 │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ Share your timeline update or reply to this candidate...                     │ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  │                                                            [Post Comment]        │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ COMMENTS & REPLIES (18):                                                         │
  │                                                                                  │
  │  👤 Anonymous Candidate • 2025 • Digital • Hyderabad          1 hour ago         │
  │  I am in the exact same boat! Survey completed on May 15th, still waiting.       │
  │  A friend from Chennai received theirs yesterday though.                         │
  │  [Reply]   [Report]                                                              │
  │                                                                                  │
  │      ┌── 👤 Sai T. • 2025 • Digital • Chennai                 30 mins ago        │
  │      │   Yes, Chennai batch 1 was released on June 10th. Hyderabad usually       │
  │      │   follows within 2 to 3 weeks according to last year's trends.           │
  │      │   [Report]                                                                │
  │                                                                                  │
  │  👤 Anonymous Candidate • 2025 • Ninja • Hyderabad            45 mins ago        │
  │  [This comment was deleted by author.]                                           │
  │                                                                                  │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### Comment & Reply Rules:
1. **Strict 1-Level Nesting:** Top-level comments can receive direct replies. Replies cannot receive further nested replies (`parent.parent == NULL` enforced by backend and UI).
2. **Inline Reply Form:** Clicking `[Reply]` inserts an indented input box directly beneath the target parent comment with autofocus.
3. **Deleted Comments:** If `is_deleted = True`, the card retains position in the thread hierarchy but displays the muted placeholder: `[This comment was removed]`.
4. **Locked Post State:** If `is_locked = True`, the comment input box is replaced by an amber banner:
   ```text
   🔒 This discussion is locked. New comments and replies are disabled.
   ```

---

## 7.9 Community Analytics & Trends Screen (`/analytics`)

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ COMMUNITY RECRUITMENT BENCHMARKS & ANALYTICS                                     │
  │ Community-Reported Data • Voluntary Candidate Submissions • Not Official TCS Data│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ FILTERS: Batch: [ 2025 ▼ ]   Stream: [ All Streams ▼ ]   Region: [ All India ▼ ] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ OVERVIEW KPI CARDS:                                                              │
  │ ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐    │
  │ │ 1,248            │ 412              │ 320              │ 85               │    │
  │ │ Total Candidates │ Waiting for JL   │ Reported JL Recvd│ Reported Joined  │    │
  │ └──────────────────┴──────────────────┴──────────────────┴──────────────────┘    │
  ├────────────────────────────────────────┬─────────────────────────────────────────┤
  │ BREAKDOWN BY HIRING STREAM:            │ CANDIDATE STATUS DISTRIBUTION:          │
  │ • Digital : 650 candidates (52%)       │ [████████████░░░░░░░░░░░░]              │
  │   - 240 waiting, 210 received JL       │ Waiting for JL: 412 (33%)               │
  │ • Ninja   : 420 candidates (34%)       │ JL Received: 320 (26%)                  │
  │   - 90 waiting, 80 received JL         │ Joining Date Received: 87 (7%)          │
  │ • Prime   : 178 candidates (14%)       │ Joined TCS: 42 (3%)                     │
  │   - 82 waiting, 30 received JL         │ Survey / Offer stage: 387 (31%)         │
  ├────────────────────────────────────────┴─────────────────────────────────────────┤
  │ AVERAGE COMMUNITY WAIT TIMES (SURVEY TO JOINING LETTER):                         │
  │ • 2025 Digital : Average 54 days (Range: 14 to 92 days)                          │
  │ • 2025 Ninja   : Average 68 days (Range: 21 to 110 days)                         │
  │ • 2025 Prime   : Average 38 days (Range: 10 to 60 days)                          │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ 🛡️ PRIVACY SUPPRESSION NOTICE:                                                   │
  │ To prevent identification of individual candidates, data breakdowns with fewer   │
  │ than 5 submissions are automatically suppressed.                                 │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.10 Notification Center (`/notifications`)

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ NOTIFICATIONS (3 UNREAD)                             [Mark All as Read]          │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TABS: [All Notifications]                           [Unread Only (3)]            │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ (●) UNREAD • 15 minutes ago                                                      │
  │ 💬 Sai T. replied to your comment on "Has anyone from 2025 Digital received JL?" │
  │    "Yes, Chennai batch 1 was released on June 10th..."                           │
  │                                                                                  │
  │ (●) UNREAD • 2 hours ago                                                         │
  │ ▲ Your post "Has anyone from 2025 Digital Hyderabad received JL?" reached 40 upvotes│
  │                                                                                  │
  │ (●) UNREAD • 5 hours ago                                                         │
  │ 📢 Pinned Announcement: Important update regarding joining readiness survey 2   │
  │                                                                                  │
  │ ( ) READ • Yesterday                                                             │
  │ 💬 Anonymous Candidate commented on your discussion post                         │
  │                                                                                  │
  │ ( ) READ • 3 days ago                                                            │
  │ 📍 Reminder: Don't forget to update your timeline if your portal status changed! │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

- **Interactive Behavior:** Clicking any notification row calls `POST /api/v1/notifications/:id/read/` to set `is_read = true`, then navigates directly to the target post, comment, or announcement anchor.
- **Empty State:**
  ```text
  You're all caught up!
  No new notifications at this time.
  ```

---

## 7.11 Candidate Profile & Settings (`/settings`)

Organized into 5 dedicated tabs:

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ ACCOUNT & PROFILE SETTINGS                                                       │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TABS: [1. Profile Info] [2. Privacy & Identity] [3. Security] [4. Devices] [5. Danger]│
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TAB 2: PRIVACY & IDENTITY SETTINGS                                               │
  │                                                                                  │
  │ Choose your public appearance in community threads:                              │
  │                                                                                  │
  │ (●) ANONYMOUS CANDIDATE                                                          │
  │     Your contributions will appear as:                                           │
  │     ┌────────────────────────────────────────────────────────┐                   │
  │     │ (🎭) Anonymous Candidate • 2025 • Digital • Hyderabad   │                   │
  │     └────────────────────────────────────────────────────────┘                   │
  │                                                                                  │
  │ ( ) CUSTOM DISPLAY NAME                                                          │
  │     Public Display Name:                                                         │
  │     [ Sai T.                                                         ]           │
  │     ┌────────────────────────────────────────────────────────┐                   │
  │     │ (ST) Sai T. • 2025 • Digital • Hyderabad               │                   │
  │     └────────────────────────────────────────────────────────┘                   │
  │                                                                                  │
  │                                                              [Save Preferences]  │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TAB 4: BROWSER NOTIFICATIONS & REGISTERED DEVICES                                │
  │                                                                                  │
  │ Browser Push Notifications: [ ENABLE PUSH NOTIFICATIONS ]                        │
  │ Receive real-time alerts when someone replies to your timeline post.             │
  │                                                                                  │
  │ Registered Active Devices:                                                       │
  │ • Chrome on Windows 10 (Last active: Today at 14:30)           [Revoke Device]   │
  │ • Safari on iPhone (Last active: Yesterday at 09:12)           [Revoke Device]   │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ TAB 5: DANGER ZONE (ACCOUNT DELETION)                                            │
  │                                                                                  │
  │ Delete Account & Candidate Profile:                                              │
  │ Permanently remove your candidate profile, device tokens, and private account    │
  │ credentials. Your community posts will be anonymized to preserve discussions.    │
  │                                                                                  │
  │ [Delete My Account Permanently (Red)]                                            │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.12 Content Reporting & Moderation UI

```
  REPORT INAPPROPRIATE CONTENT MODAL
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ Report Content to Moderators                                                 [×] │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Why are you reporting this post/comment?                                         │
  │                                                                                  │
  │ ( ) Spam or commercial solicitation                                              │
  │ ( ) Harassment, hate speech, or abuse                                            │
  │ (●) Misinformation / False claims about official TCS process                     │
  │ ( ) Exposure of private personal information (emails, phone numbers)            │
  │ ( ) Fraudulent scam or fee collection attempt                                    │
  │ ( ) Other reason                                                                 │
  │                                                                                  │
  │ Additional Context (Optional):                                                   │
  │ ┌──────────────────────────────────────────────────────────────────────────────┐ │
  │ │ This post claims joining letters are released for all batches, which is false│ │
  │ └──────────────────────────────────────────────────────────────────────────────┘ │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                  [Cancel]    [Submit Report]     │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

```
  ADMIN MODERATION QUEUE (/admin/moderation/reports)
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ MODERATION QUEUE (3 PENDING REPORTS)                                             │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ [Report #104] • Target: POST • Reason: MISINFORMATION • Reporter: Candidate #18 │
  │ Content: "Guaranteed TCS joining dates for Rs 5,000 via Telegram contact..."     │
  │ [Review Content]  [Dismiss Report]  [Soft-Delete Post]  [Ban Offending User]     │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.13 Informational & Legal Pages

- **`/about`:** Explains the community mission, origin story, independence from TCS corporate entity, and open-source contribution guidelines.
- **`/privacy`:** Detailed privacy policy: email hashing, zero third-party marketing trackers, FCM token isolation, and account anonymization procedures.
- **`/terms`:** Terms of service: rules against spam, impersonation, harassment, scam solicitations, and clear reiteration of the TCS non-affiliation statement.

# 8. Micro-Interactions, Motion, and Animation Guidelines

Smooth, purposeful animations provide cognitive continuity without impeding efficiency or triggering motion discomfort.

```
  TRANSITION TIMING & CURVE TOKENS
  ┌───────────────────┬───────────┬───────────────────────────────────────────┐
  │ Token Name        │ Duration  │ Cubic Bezier Curve                        │
  ├───────────────────┼───────────┼───────────────────────────────────────────┤
  │ `transition-fast` │ 150ms     │ `cubic-bezier(0.4, 0, 0.2, 1)` (ease-out) │
  │ `transition-base` │ 250ms     │ `cubic-bezier(0.4, 0, 0.2, 1)`            │
  │ `transition-slow` │ 350ms     │ `cubic-bezier(0.16, 1, 0.3, 1)` (spring)  │
  └───────────────────┴───────────┴───────────────────────────────────────────┘
```

### 8.1 Specific Component Motion Rules
1. **Upvote Button Pulse:**
   - On click, icon scales to `1.25` for 100ms and returns to `1.0` with `transition-transform duration-150`.
   - The counter increments instantly via optimistic UI.
2. **Timeline Milestone Achievement:**
   - When a new event is saved, the timeline node icon rings with an expanding emerald ripple pulse (`animate-ping duration-1000 iteration-1`).
3. **Dropdowns & Popovers:**
   - Scale and fade in: Starts at `opacity-0 scale-95` and transitions to `opacity-100 scale-100` in 150ms.
4. **Modal & Drawer Enter/Exit:**
   - Desktop Modals: Fade-in backdrop (200ms), modal scales up from `0.95` to `1.0` (250ms).
   - Mobile Drawers: Slide in from `translate-y-full` to `translate-y-0` (300ms cubic-bezier).
5. **Toast Stacking & Dismissal:**
   - Enters from bottom-right (Desktop) or top-center (Mobile) with slide + fade.
   - Auto-dismiss slides out horizontally with `opacity-0 translate-x-4` in 200ms.
6. **Accessibility Override (`prefers-reduced-motion`):**
   - When the user's OS has reduced motion enabled, all durations fall back to `0ms` or instant opacity transitions (`duration-0 motion-reduce:transition-none`).

---

# 9. Responsive & Mobile-First Design Specifications

```
  VIEWPORT ADAPTATION MATRIX
  ┌──────────────────┬─────────────────┬─────────────────┬────────────────────┐
  │ Feature          │ Mobile (<768px) │ Tablet (768-1024│ Desktop (>=1024px) │
  ├──────────────────┼─────────────────┼─────────────────┼────────────────────┤
  │ Navigation       │ Bottom Tab Bar  │ Collapsible Rail│ Left Sticky Sidebar│
  │ Right Rail Stats │ Collapsed Card  │ Stacked in Feed │ Persistent 320px   │
  │ Form Layout      │ 1-Col Stacked   │ 2-Col Grid      │ 2-Col Grid         │
  │ Post Cards       │ Full Width px-4 │ Card px-6       │ Card px-6          │
  │ Dialogs / Modals │ Bottom Sheet    │ Centered Modal  │ Centered Modal     │
  │ Touch Targets    │ Min 44 × 44px   │ Min 40 × 40px   │ Min 36 × 36px      │
  └──────────────────┴─────────────────┴─────────────────┴────────────────────┘
```

### 9.1 Mobile Ergonomics & Thumb Zone
- Primary destructive or critical submit buttons span `w-full` on mobile screens with a minimum height of `48px` (`h-12`).
- The bottom tab bar features safe-area padding (`pb-[env(safe-area-inset-bottom)]`) to avoid overlapping iOS home indicator bars.
- Pull-to-refresh gesture supported on mobile community feed and personal timeline lists.

---

# 10. Progressive Web App (PWA) User Experience

The application is structured to deliver a native app experience on mobile devices without requiring app store distribution.

```
  ┌────────────────────────────────────────────────────────┐
  │ Add TCS Joining Tracker to Home Screen             [×] │
  │ Install our lightweight app for fast offline access    │
  │ and timely joining letter push alerts.                 │
  │                                                        │
  │                      [Not Now]    [Install App]        │
  └────────────────────────────────────────────────────────┘
```

### 10.1 PWA Specifications:
- **Manifest Configuration:**
  - Name: `TCS Joining Tracker`
  - Short Name: `JL Tracker`
  - Theme Color: `#4F46E5` (Light) / `#0F172A` (Dark)
  - Background Color: `#FFFFFF` / `#0F172A`
  - Display: `standalone`
  - Orientation: `portrait-primary`
  - Icons: `192x192` and `512x512` maskable PNGs.
- **Smart Install Promotion:**
  - Avoid aggressive prompts on first landing visit.
  - Show installation banner only after a candidate has either:
    1. Successfully created an account and added at least 1 timeline milestone, or
    2. Visited the community feed on 2 distinct days.
- **Offline UX:**
  - Service worker caches core shell, static assets, and cached user timeline.
  - When offline, a subtle amber banner appears at the screen top:
    ```text
    ⚠️ Offline Mode. Showing cached data. Actions will sync when online.
    ```
- **Push Notification Permission Primer:**
  - Never trigger raw browser `Notification.requestPermission()` directly without context.
  - First show an in-app soft modal explaining value:
    *"Enable push notifications so you never miss when a candidate reports joining letter updates for your batch."*
  - Only when candidate clicks "Enable Alerts" does the browser trigger native permission prompt.

---

# 11. Accessibility (a11y) & Usability Standards

Full compliance with **WCAG 2.1 Level AA** standards is mandatory across all views.

```
  ACCESSIBILITY CHECKLIST
  ┌───┬───────────────────────────────┬────────────────────────────────────────┐
  │ # │ Requirement                   │ Technical Verification                 │
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 1 │ Contrast Ratios               │ Minimum 4.5:1 for body text (slate-700)│
  │   │                               │ Minimum 3:1 for large titles & icons   │
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 2 │ Keyboard Navigation           │ Full tab index order across forms,     │
  │   │                               │ buttons, cards, and modal dismissals   │
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 3 │ Focus Visible                 │ 2px offset brand ring on all active    │
  │   │                               │ interactive elements (`ring-brand-500`)│
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 4 │ ARIA Landmark Roles           │ `<header role="banner">`, `<main>`,    │
  │   │                               │ `<nav role="navigation">`, `<aside>`   │
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 5 │ Live Regions                  │ `aria-live="polite"` on toasts & counts│
  │   │                               │ `aria-live="assertive"` on form errors │
  ├───┼───────────────────────────────┼────────────────────────────────────────┤
  │ 6 │ Form Label Associations       │ Every `<input>` bound to `<label>` via │
  │   │                               │ explicit `id` and `htmlFor` props      │
  └───┴───────────────────────────────┴────────────────────────────────────────┘
```

---

# 12. Comprehensive Edge Cases & Error States

```
  HTTP 429 RATE LIMIT ERROR STATE               HTTP 404 NOT FOUND STATE
  ┌─────────────────────────────────────┐       ┌─────────────────────────────────────┐
  │ [⏳ Clock Glyph]                    │       │ [🔍 Magnifying Glass Glyph]         │
  │ Rate Limit Exceeded                 │       │ Page Not Found                      │
  │ You're posting comments too fast.   │       │ This discussion or milestone event  │
  │                                     │       │ no longer exists or was removed.    │
  │ Please wait 42 seconds before       │       │                                     │
  │ submitting another comment.         │       │ [ Return to Community Feed ]        │
  │                                     │       │ [ Go to Personal Dashboard ]        │
  │ [ Try Again in 42s (Disabled) ]     │       │                                     │
  └─────────────────────────────────────┘       └─────────────────────────────────────┘
```

### 12.1 Detailed Edge Case Handling Matrix

| Scenario / Error | User Interface Presentation | Recovery Action |
|---|---|---|
| **Network Loss (Offline)** | Sticky amber banner: *"No internet connection. Cached data shown."* | Auto-reconnects when browser signals `online` event. |
| **HTTP 401 (Auth Expired)** | Triggers silent JWT refresh via `POST /api/v1/auth/token/refresh/`. If refresh fails, opens a lightweight Login Modal without clearing dirty form drafts. | User re-enters password; original pending submit resumes. |
| **HTTP 403 (Locked Post)** | Inline banner above comments: *"This post has been locked by a moderator. New replies disabled."* Comment textarea disabled. | Read-only access preserved. |
| **HTTP 403 (Banned Account)**| Full-screen notification: *"Your account has been suspended for violating community rules. Contact support for assistance."* | Logout button provided. |
| **HTTP 404 (Resource Gone)** | Clean error card with direct links to `/community` and `/dashboard`. | Prevents dead-end navigation. |
| **HTTP 429 (Rate Limited)** | Displays countdown timer: *"Too many requests. Please wait {seconds}s."* Action button shows live countdown. | Button enables automatically when timer expires. |
| **HTTP 500 (Server Error)** | Friendly illustration: *"Something went wrong on our end. Our team has been alerted. Please try again in a moment."* | `[Retry Request]` button. |
| **Form Validation Error** | Inline red error text under erroneous input; auto-scrolls to first invalid field; focus set to field. | User corrects input. |
| **Empty Community Feed** | Illustration of chat bubble: *"No discussions yet in this category. Be the first to start a conversation!"* | `[+ Create Post]` button. |
| **Empty Timeline** | Roadmap illustration: *"Your recruitment timeline is empty. Record your first milestone to track your journey."* | `[+ Add Milestone Event]` button. |
| **Empty Notifications** | Checkmark circle illustration: *"You're all caught up! No unread notifications."* | Subtext confirms status. |
| **Small Group Privacy** | Replaces chart bars with alert box: *"Not enough community data to display this breakdown (minimum 5 candidates required to protect privacy)."* | Explains privacy rule clearly. |

---

# 13. Frontend Architecture & React Component Structure

The frontend is structured as a modular React (TypeScript) single-page application using Tailwind CSS for utility styling and Radix UI / Headless UI for accessible unstyled primitives.

```
src/
├── api/                           # Centralized REST client & endpoint modules
│   ├── client.ts                  # Axios/Fetch instance with JWT refresh interceptor
│   ├── auth.ts                    # Login, register, verify, reset password
│   ├── profile.ts                 # Candidate profile CRUD & privacy toggles
│   ├── timeline.ts                # Timeline events CRUD
│   ├── community.ts               # Posts, comments, replies, upvotes, categories
│   ├── analytics.ts               # Aggregated trends, batch/stream breakdowns
│   ├── notifications.ts           # In-app notifications & read states
│   └── devices.ts                 # FCM browser device registration
├── components/                    # Reusable design system components
│   ├── common/                    # Buttons, Inputs, Badges, Modals, Toasts
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Textarea.tsx
│   │   ├── Select.tsx
│   │   ├── Badge.tsx
│   │   ├── Modal.tsx
│   │   ├── Toast.tsx
│   │   └── Skeleton.tsx
│   ├── layout/                    # Page shells, sidebars, headers, footers
│   │   ├── Navbar.tsx
│   │   ├── Sidebar.tsx
│   │   ├── MobileTabBar.tsx
│   │   ├── AnnouncementBanner.tsx
│   │   └── Footer.tsx
│   ├── timeline/                  # Roadmap, event cards, milestone steppers
│   │   ├── TimelineRoadmap.tsx
│   │   ├── TimelineNode.tsx
│   │   └── AddEventModal.tsx
│   ├── community/                 # Post cards, comment trees, upvote buttons
│   │   ├── PostCard.tsx
│   │   ├── CommentItem.tsx
│   │   ├── UpvoteButton.tsx
│   │   └── CategoryPills.tsx
│   └── analytics/                 # Metric widgets, progress bars, disclaimers
│       ├── StatWidget.tsx
│       ├── BreakdownChart.tsx
│       └── PrivacyCallout.tsx
├── context/                       # Global React contexts
│   ├── AuthContext.tsx            # Authenticated user, tokens, login/logout
│   ├── ThemeContext.tsx           # Light / Dark / System theme state
│   └── NotificationContext.tsx    # Unread counter, toast dispatcher
├── hooks/                         # Custom hooks
│   ├── useAuth.ts
│   ├── useTimeline.ts
│   ├── usePosts.ts
│   ├── useNotifications.ts
│   ├── useDebounce.ts
│   └── usePWAInstall.ts
├── pages/                         # Route view components
│   ├── LandingPage.tsx
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── OnboardingPage.tsx
│   ├── DashboardPage.tsx
│   ├── TimelinePage.tsx
│   ├── CommunityFeedPage.tsx
│   ├── PostDetailPage.tsx
│   ├── AnalyticsPage.tsx
│   ├── SettingsPage.tsx
│   └── NotFoundPage.tsx
└── types/                         # TypeScript interfaces (matching API specs)
    ├── auth.ts
    ├── profile.ts
    ├── timeline.ts
    ├── post.ts
    └── notification.ts
```

---

# 14. Tailwind CSS Configuration & CSS Custom Properties

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#EEF2FF',
          100: '#E0E7FF',
          200: '#C7D2FE',
          500: '#6366F1',
          600: '#4F46E5', // Primary brand anchor
          700: '#4338CA',
          800: '#3730A3',
          900: '#312E81',
          950: '#1E1B4B',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
};
```

---

# 15. UI/UX Verification Checklist & Definition of Done

A UI/UX feature or screen is considered complete only when all the following criteria are validated:

- [ ] **Pixel Alignment:** Layout conforms to 4px/8px grid and designated typography scale.
- [ ] **Dual Theme Support:** Rendered and manually tested in both Light and Dark modes with zero unreadable text or low-contrast borders.
- [ ] **Mobile Touch Readiness:** All mobile touch targets measure at least 44 × 44px; bottom tab bar operates cleanly without obscuring content.
- [ ] **All Component States Implemented:**
  - [ ] Default / Idle
  - [ ] Hover
  - [ ] Focus-visible (with 2px outline ring)
  - [ ] Active / Pressed
  - [ ] Loading / Skeleton placeholder
  - [ ] Empty state (with helpful action CTA)
  - [ ] Error state (with inline human-readable copy)
- [ ] **Mandatory Non-Affiliation Disclaimers:** Displayed verbatim on all public headers/footers and analytics screens.
- [ ] **Truth in Data Labeling:** All aggregated counters explicitly labeled as "Community-reported data".
- [ ] **Privacy Preservation:** Anonymous display mode properly masks user identity; no email or FCM tokens rendered.
- [ ] **Accessibility (WCAG 2.1 AA):** Passes automated Axe/Lighthouse checks with contrast score >= 4.5:1. Keyboard tab navigation functions without focus traps.
- [ ] **PWA & Offline Behavior:** Service worker registers; install prompt respects user frequency caps; offline alert renders when network is lost.

---

# 16. AI Agent Implementation Rules for UI/UX Frontend Build

When an AI coding agent generates, updates, or refactors frontend code based on this specification, it must adhere strictly to these rules:

1. **Follow the Spec Verbatim:** Never invent arbitrary styling, non-standard colors, or unorthodox layouts that conflict with this document.
2. **Never Omit Non-Affiliation Disclaimers:** Every public page and analytics component must render the mandated TCS non-affiliation statement.
3. **Enforce Public Identity Separation:** Never expose `email`, `user_id`, or `fcm_token` in public UI components.
4. **Enforce 1-Level Reply Depth:** In comment components, do not permit recursive nesting beyond 1 level (`parent.parent == NULL`).
5. **Implement Loading Skeletons:** Never leave users looking at raw blank screens while waiting for network responses. Use designated structural shimmer components.
6. **Preserve Mobile Ergonomics:** Always verify that buttons and touch targets meet the 44px minimum height and width on viewports < 768px.
7. **Handle Form Errors Gracefully:** Map backend API validation errors (`code: VALIDATION_ERROR`) directly to the corresponding input field labels.
8. **Optimistic Updates with Safe Rollback:** When implementing upvotes or bookmark toggles, update the UI immediately and rollback gracefully if the API fails.
9. **Never Mock Success Silently:** If an API endpoint fails, display a clear user-facing error toast rather than pretending the mutation succeeded.
