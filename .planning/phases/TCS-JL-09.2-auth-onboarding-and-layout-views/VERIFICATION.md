# VERIFICATION — Phase 9.2: Auth, Onboarding & Layout Views

**Phase:** 9.2 · **Verified:** 2026-09-23 · **Plan:** `09.2-01-PLAN.md` (6 tasks, wave 1)
**Requirements:** UI-01 (layout shells), UI-04 (disclaimer placements)
**Verdict:** ✅ **PASS** — every plan task is built, all gates are green on a clean tree, the backend
suite grew 788 → 790 with the deliberate D1 fix, and independent live drills re-proved the phase's
done-when ("layout adapts across breakpoints with the disclaimer present") plus the full auth →
onboarding → dashboard journey. The verification pass also **caught and fixed one real defect** the
execution had pinned in place (wrong announcements URL).

---

## 1. Evidence re-derived (not trusted from execution)

| Gate | Result |
|---|---|
| `npm run lint` | 0 errors (7 benign fast-refresh warnings) |
| `npm run typecheck` | clean |
| `npm run test:run` | **98/98** across 19 files |
| `npm run build` | `dist/` produced, `index.html` present |
| Backend `pytest -q` | **790 passed** (788 baseline + 2 new gate-flag tests) |
| `git diff config/settings/` | empty — no settings drift left behind |
| Drill scaffolding | announcements deleted; only the documented `live-proof-92` dev account remains |

## 2. Wire drills (curl, real API)

- **V1 — the gate flag is truthful:** login → `GET /me/` → `profile_completed: true` for the
  wizard-completed account (and the test suite pins False for no-profile and partial-profile).
- **V2 — single-hop enforcement (the execution finding, re-confirmed):** `PATCH /profile/
  {"current_status": "JOINED"}` from `OFFER_RECEIVED` → **400**. The side-channel is single-hop;
  the wizard's timeline-event path is the correct multi-hop write.
- **V3 — milestone fabrication blocked:** `POST /timeline/` with a 2030 event date → rejected
  (`"event_date cannot be more than 730 days in the future."`). The wizard cannot backdate the
  future.
- **V4 — login error codes on the wire:** `INVALID_CREDENTIALS` → 401; after 6 failures the limiter
  answers **429 with `Retry-After: 25`** — exactly the pair the LoginPage maps to its countdown UI.
  A request the client sends with no Bearer (logins) can never trigger refresh — bypass premise holds.

## 3. Browser drills (real Chromium, dev server on :5173)

- **Banner end-to-end (D3):** created a published announcement server-side → banner appeared with
  📣, title, **Read update** link; dismiss (×) removed it and wrote the announcement **ID** to
  `tjt.dismissed_announcements`; hard reload → still dismissed; created a **second** announcement →
  banner showed the new item (per-ID dismissal semantics hold); drill rows then deleted.
- **Guard:** anonymous visit to `/notifications?filter=unread` → `/login?next=%2Fnotifications%3Ffilter%3Dunread`
  (path + query preserved).
- **Breakpoints + disclaimer (the done-when):** 1440px → sidebar + center + 320px rail + "+ Post",
  tab bar `display: none`; 400px → sidebar/rail hidden, top app bar + 5-tab bar visible, disclaimer
  present at **both** widths (screenshots captured; DOM-asserted via computed styles).
- **Landing:** hero, live pulse pill, CTAs, and the stats band fed by the real `/public/stats/`
  (22 / 21 / 67) with the "Community-reported data" caption and the §5.6 footer disclaimer.

## 4. Defect found and fixed during verification

**O-92-1 (MEDIUM, fixed in-pass): the banner called a nonexistent URL.** Execution wired the banner
to `/api/v1/community/announcements/` — a guessed prefix. The live resolver (and 04 §72) put the
public read at **`/api/v1/announcements/`**. Consequence: the banner silently never rendered in
production traffic paths (its failure mode is silent by design — which is also why execution's
happy-path smoke missed it; the AppShell tests had pinned the same wrong URL). Fixed in
`api/announcements.ts` + `AppShell.test.tsx`; suite re-run green. *Lesson recorded: a component
whose failure mode is silence needs a live-data drill, not only mocked tests.*

## 5. Visual comparison vs the Stitch screens (standing directive §4)

Implementation was driven by the 10 mockups (project `3852118218307261541`, design system
`assets/9887579562818178405`). Compared live:

| Screen | Match | Notes / deliberate divergences |
|---|---|---|
| App Shell (dark, desktop) | ✅ | Sidebar pills, "+ Post", 320px rail, disclaimer all present. Rail shows a placeholder card — 9.3 fills it. |
| Mobile Shell | ✅ | Top app bar + 5-tab bottom bar + disclaimer. Dashboard content cards (Status Summary / Community Pulse) are 9.3 scope, absent by boundary. |
| Landing | ✅ | Pulse pill, hero copy, CTAs, microcopy, stats band + caption. Mockup's 4 aspirational counters → **3 real ones** (the API's shape); product-preview card not built (decorative). |
| Login | ✅ | Brand row, copy, eye toggle, Forgot link, or-divider, error/success strips (test-pinned). |
| Wizard steps 1–3 | ✅ | Progress header with % + labels, radio-card list, review rows + Edit + confirm + success strip. Status list **differs by design**: mockup's 6 picks → 7 chain-legal event-backed picks (INTERVIEW/SELECTION added; "Not sure/other" dropped — OTHER/WITHDRAWN have no event semantics and stay PATCH-only). |

## 6. Acceptance criteria matrix

| Criterion (plan/roadmap) | Evidence | Verdict |
|---|---|---|
| Layout adapts across breakpoints with the disclaimer present (done-when) | Drill §3: computed-style assertions + screenshots at 1440/400 | ✅ |
| `profile_completed` truthful, tests pin both directions | test_me 6/6; V1 wire check | ✅ |
| Gate: incomplete profile → /onboarding; exempt from itself; releases on finish | Unit tests + execution's live journey; V1 confirms released flag | ✅ |
| Six §7.2 screens wired to real endpoints; 3 error codes mapped distinctly | Unit tests (401/429+Retry-After/403); V4 wire | ✅ |
| §7.3 wizard persists per-step; step 2 walk-the-chain event | Unit tests assert `POST /timeline/` body; V2/V3 wire | ✅ |
| §5.5 banner: latest un-dismissed, per-ID persistence, silent degradation | Drill §3 end-to-end; unit tests | ✅ |
| D2: no staff navigation | AppShell test pins absence | ✅ |
| UI-04 disclaimer from the single content module | Rendered on shell/landing/auth/wizard; live-asserted | ✅ |

## 7. Observations carried forward

1. **O1 (`/admin` path collision)** — unchanged, still deferred with staff UI (D2).
2. **`/community/create` nav affordance** — the shell's "+ Post" links there; the stub is fine for
   now, but 9.3's feed phase owns making it real.
3. **Banner ordering** — the API returns published rows; the banner picks the first un-dismissed.
   If pinned-vs-newest ordering ever matters, confirm the server's ordering contract (04 §72) in
   the feed phase.
4. **Wizard resume edge** — resume logic keys off `offer_letter_date`/`REGISTERED`; a user who
   completes step 1 but abandons before step 2 resumes at step 2 correctly, but a user stuck at
   REGISTERED with a completed-looking profile can never exist (offer date required) — no dead-end
   found. Re-examine only if onboarding fields change.

**Tracking updated:** STATE.md → phase-verified; REQUIREMENTS.md UI-01/UI-04 wording confirmed.
