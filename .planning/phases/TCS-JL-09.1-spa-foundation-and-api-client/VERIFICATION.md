# VERIFICATION — Phase 9.1: SPA Foundation & API Client

**Phase:** 9.1 · **Verified:** 2026-09-23 · **Plan:** `09.1-01-PLAN.md` (5 tasks, wave 1)
**Requirements:** UI-02 (complete), UI-01 (foundation half; layout shells are 9.2–9.4)
**Verdict:** ✅ **PASS** — all five plan tasks are built, every frontend gate is green on a clean
tree, the backend suite is unchanged at 788, and independent live drills against the running stack
prove the phase's defining contract under conditions the unit suite alone cannot create: **a real
double-fetch 401 storm produces exactly ONE refresh POST and two successful replays**, and the wire
itself demonstrates why that matters (a reused refresh token revokes the whole token family). Two
observations are recorded (one HIGH-visibility path-collision note, one spec-vs-shipped naming
note); neither contradicts a phase requirement, and neither was introduced by this phase.

**Verification is independent of execution.** Evidence was re-derived from the tree as it stands:
fresh gate runs, the backend suite re-executed in the container, static contract greps, a
curl-level HTTP drill against the real API (login → rotation → reuse → family revocation), and a
browser drill through the actual SPA (scripted XHR instrumentation, no test doubles) driven to a
5-second access-token lifetime so the 401 storm happens for real. All temporary drill scaffolding
(5s `ACCESS_TOKEN_LIFETIME`, scratch double-fetch button) was reverted; `git diff` on
`config/settings/local.py` is empty and the frontend suite was re-run green afterward.

## Evidence sources

| Source | Scope | Result |
|---|---|---|
| Frontend gates (clean tree, re-run) | lint / typecheck / 14 test files / build → `dist/` | ✅ **0 lint errors** (7 fast-refresh warnings, cosmetic) · ✅ tsc clean · ✅ **76/76 tests** · ✅ build 2.4s |
| Static contract greps (T-09.1-02/-05/-06) | storage, absolute-host, single-source vocabularies | ✅ only `theme` + refresh token persisted · ✅ no absolute API host in `src/` · ✅ disclaimer strings exist only in `src/content/disclaimer.ts` |
| Backend suite `python -m pytest -q` (in `web` container) | 788 tests | ✅ **788 passed**, 0 failed, 3 warnings — phase touched no Python |
| HTTP drill B (curl over the real wire) | login → Bearer auth → rotation → **reuse-detection** → family revocation | ✅ 6/6 checks (below) |
| Browser drill C (real Chromium, SPA loaded from Vite) | double-fetch 401 storm with 5s access lifetime | ✅ **2× 401 → exactly 1 refresh POST → 2× 200 replay**, user stayed signed in |
| Browser drill D (real Chromium) | route guards, `next=` round-trip, PublicOnly bounce, history-mode deep links | ✅ 4/4 checks (below) |

## Drill B — the wire proves why single-flight is mandatory (curl, real API)

| # | Check | Result |
|---|---|---|
| B1 | `POST /auth/login/` issues access + refresh (one family) | ✅ 200, both tokens returned |
| B2 | `GET /me/` with `Authorization: Bearer <access>` | ✅ 200 |
| B3 | `POST /auth/token/refresh/` with refresh R1 rotates (blacklists R1, mints R2) | ✅ 200, `{access, refresh}` both present |
| B4 | **Replay R1** (reuse-detection trigger) | ✅ **401** |
| B5 | **R2 — the legitimate child — is also dead** (whole family revoked) | ✅ **401** |
| B6 | Old access token remains valid until its own expiry (revocation touches refresh tokens, not outstanding accesses) | ✅ 200 |

B4+B5 are the destructive behavior the client's single-flight queue exists to prevent: a naive
interceptor that fires two refreshes under concurrent 401s would land in exactly this state and log
the user out everywhere.

## Drill C — the done-when, observed live (real browser, 5s access lifetime)

Temporary setup: `ACCESS_TOKEN_LIFETIME = timedelta(seconds=5)` in `config/settings/local.py`
(reverted after), `web` restarted and lifetime confirmed via Django settings; a temporary
double-fetch button fired two concurrent `getMe()` calls through the shipped client after the
access token had expired.

```
GET  /api/v1/me/                 -> 401   (fetch A — expired access)
GET  /api/v1/me/                 -> 401   (fetch B — same expired access)
POST /api/v1/auth/token/refresh/ -> 200   (exactly ONE — single-flight queue)
GET  /api/v1/me/                 -> 200   (replay A, new Bearer)
GET  /api/v1/me/                 -> 200   (replay B, new Bearer)
```

Assertions captured: `refreshPOSTs: 1`; both callers received `{email: …}` responses; the app
remained on `/dashboard` (no redirect to `/login`, no visible error); the rotated refresh token was
persisted in `localStorage` after the storm (`tjt.refresh_token` present). A second, unplanned
natural occurrence during setup (a stalled evaluation run collided with a token expiry) also
produced a successful single-flight recovery, corroborating the scripted run.

## Drill D — routing and guards live (real browser)

| # | Check | Result |
|---|---|---|
| D1 | Anonymous visit to `/notifications?filter=unread` redirects with the full attempted path | ✅ landed on `/login?next=%2Fnotifications%3Ffilter%3Dunread` |
| D2 | History-mode deep links serve the SPA shell (dev server behavior; production still needs the D4 fallback) | ✅ 200 on `/dashboard`, `/timeline`, `/community`, `/settings`, unknown paths → SPA 404 page |
| D3 | Sign-in while sitting on `/login`, reload → PublicOnly bounces the authenticated user to `/dashboard` | ✅ path `/dashboard`, h1 "Dashboard", session intact |
| D4 | The same reload re-proves the boot path: a signed-in user is never bounced to `/login` while `booting` | ✅ (D3's reload would have exposed any such bounce) |

## Roadmap done-when and plan acceptance criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| **"401 responses transparently refresh and replay the original request"** (Phase 9.1 done-when) | ✅ PASS | Drill C (live, concurrent) + 19 API tests incl. the call-count concurrency proof + drill B showing the alternative is family revocation. |
| UI-02: centralized axios client, silent JWT refresh on 401 | ✅ PASS | `src/api/client.ts` single instance + interceptors; errors normalized to `ApiError` (04 §10 envelope, `Retry-After` on 429) — no axios error escapes. |
| 05 §4 tokens byte-exact, Tailwind v4 `@theme`, class-strategy dark mode | ✅ PASS | `index.css` brand scale (#4F46E5 anchor) + semantic aliases + `.dark` overrides; compiled CSS in `dist/` carries the variables; 14 test files pin vocabularies. |
| Bootable shell: every 05 §3.1 path, guards, Error Boundary | ✅ PASS | Drill D; 404 catch-all; booting renders skeleton (tested), never a redirect. |
| T9.3 + Disclaimer/EmptyState/IdentityPill | ✅ PASS | Component tests 36/36; disclaimer strings stored once (`src/content/disclaimer.ts`) and pinned byte-for-byte. |
| Backend non-regression | ✅ PASS | 788 passed after all frontend work; `config/settings/local.py` diff empty. |
| D1–D10 decisions as built | ✅ PASS | D1 storage split (memory/localStorage, greps) · D2 single-flight (drill C) · D3 proxy, one `VITE_API_BASE_URL` reader (grep) · D4 history mode + fallback recorded in README · D5 tokens (dist CSS) · D6 strict TS, no `any` (tsc + lint rule) · D7 no query/UI/mocking libs (package.json) · D8 Vitest+RTL adapter technique · D9 route table (drill D) · D10 library + single-source disclaimers. |

## Requirements impact

| Item | Verdict | Notes |
|---|---|---|
| **UI-02** | ✅ **Complete** | Contract shipped and proven at three levels: unit (adapter-driven), wire (drill B context), browser (drill C). Formal UAT predicate: UI-02's acceptance criteria are all directly observable in the shipped tree and were re-executed during this verification. |
| **UI-01** | ◐ In progress | Foundation half delivered (workspace, tokens, component library, route stubs). Layout shells, responsive 3-col/2-col/tab-bar, and every real view belong to 9.2–9.4. Deliberately **not** marked complete. |

## Observations (none blocks a requirement)

- **O1 (MEDIUM — pre-existing topology fact surfaced by verification, decision owed in 9.2 planning):**
  The D3 dev proxy reserves `/admin` for the Django admin, so 05 §3.1's staff routes
  `/admin/moderation/reports` and `/admin/announcements` cannot reach the SPA at those URLs in dev —
  `http://localhost:5173/admin/moderation/reports` answers **302 → Django admin login** (drill D2).
  The routes exist in the SPA's router and work in any topology that does not reserve `/admin`, but
  as long as the proxy owns that prefix, staff-page development and any production reverse-proxy
  that proxies `/admin` will collide. Options for 9.2: (a) relocate the UI staff pages (e.g.
  `/moderation/reports`), (b) split the proxy so `/admin/api` goes to Django and `/admin/*` to the
  SPA, or (c) accept Django-admin ownership of `/admin` and drop the UI paths from §3.1 (recorded
  spec change). This phase correctly built §3.1's routes verbatim; the collision is a topology
  decision, not a code defect — but it must be decided before 9.2 builds staff navigation.
- **O2 (LOW — spec-vs-shipped naming, cosmetic):** The plan's example proof URL
  `/api/v1/announcements/` 404'd on first probe during execution because the running `web` container
  predated the 8.2 code (gunicorn had not reloaded the URLconf); after a container restart the route
  answers 200 through the proxy (drill A3), and the route's real home per 04 §71 wiring is
  `/api/v1/announcements/` — verified live. Recorded so the earlier 404 is not misread as a missing
  endpoint. Relatedly, drill A2 confirms `GET /api/v1/public/stats/` returns the attributed payload
  (`data_source: COMMUNITY_REPORTED` + disclaimer) through the SPA origin.

## Tooling notes (for future verifications in this repo)

- The bundled ripgrep binary is unavailable in this environment; `code_search` fails. Use
  `grep`/`sed` via the terminal instead.
- npm 11 blocks esbuild postinstall scripts by policy; Vite/build work via platform binary
  packages, and the two `postinstall` warnings during `npm install` are expected.
- Browser drill instrumentation: SPA XHR traffic (axios) is not visible to `fetch` wrappers —
  wrap `XMLHttpRequest.prototype.open/send` instead. Plan evaluate calls to stay under the 10s
  preview limit (timeouts mid-run can double-fire clicks and rotate tokens unexpectedly).

**Verdict recap:** ✅ **PASS** — UI-02 complete and observed live under concurrency; UI-01
foundation delivered; no blocking findings; O1 recorded as a 9.2 planning input.
