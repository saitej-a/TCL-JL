# Phase 4.2 — Discussion Record: Timeline API, IDOR Defense & Dashboard

Date: 2026-09-22
Scope: Roadmap plan 04-02 (T4.4–T4.9) — API layer over 4.1's model + services:
`GET/POST /api/v1/timeline/`, `PATCH/DELETE /api/v1/timeline/{event_id}/`,
`IsTimelineOwner` IDOR defense, and `GET /api/v1/dashboard/`.
Requirements covered: TIME-03, TIME-04 (API-enabling half), TIME-05.

## Decisions locked (user)

- **D1 — Dashboard ships complete-shaped now; community is real, notifications is a
  placeholder.** The community benchmark is derivable *today* from `CandidateProfile`
  status counts, so 4.2 computes it for real rather than stubbing it. The two 04 §28
  dependencies that do not yet exist are handled as follows:
  - `community_waiting_count` — **computed for real** from existing profile data
    (status distribution + waiting-state total), labeled COMMUNITY_REPORTED.
  - `unread_notifications` — returns **0** as an explicit not-yet-wired placeholder,
    documented in code + PLAN as wired in Phase 6 (Notifications model does not exist).
  Rationale: the 04 §28 response key contract is stable from day one, so Phase 9.3's
  dashboard UI never churns when Phases 6/7 land — they fill values, not keys.
- **D2 — Benchmark block = waiting total + status distribution, threshold-suppressed.**
  TIME-05's "benchmarks" (plural) is met with per-status counts across all candidates
  plus a waiting-state total, each suppressed per 04 §53's privacy threshold
  (server-side setting; small cohorts must not be exposed) and explicitly labeled
  `data_source: "COMMUNITY_REPORTED"` (04 §65 item 20 / 01 §1007: never presented as
  official TCS information). Micro-cohort leakage is the risk being managed: a raw
  count of 1 in a niche batch is personal data.
- **D3 — Future-dated events: bounded horizon for all types, plus JOINING_LETTER is
  present-or-past.** POST/PATCH reject `event_date` beyond *today + 24 months*
  (settings-driven, not hardcoded) and absurd past years; this bound applies to every
  event type. Additionally, `JOINING_LETTER` may only be dated today or earlier —
  a letter is *issued*, not planned ahead. `JOINING_DATE` is explicitly allowed in the
  future within that horizon (a candidate legitimately records an upcoming joining
  date), as is `OTHER` (offers/dates shared informally).
  *Interpretation note:* the user's answer combined "bounded horizon, all types" with
  the free-text refinement "joining date can be for future but joining letter will be
  issued in present or past" — read here as horizon-for-all + a single
  present/past-only carve-out for JOINING_LETTER. Veto at plan review if the intent was
  instead to exempt JOINING_DATE from the type list entirely.

## Spec invariants carried (no decision)

- **Endpoints per 04 §24–§28 + T4.4–T4.8.** List is paginated, owner-scoped, and
  chronological (newest first, `-event_date` with a `-created_at` tiebreak); 04 §9
  page-number pagination with default size 20 and a controlled maximum of 50 — no
  client-supplied arbitrary `page_size`. Optional `?event_type=` filter per 04 §3277.
- **IDOR semantics are 404, not 403.** 06 §4.2 rule 2 and roadmap success criterion 3
  both mandate HTTP 404 for another candidate's event (prevents enumeration, matching
  06 §4.2's "No Match: HTTP 404 (Not 403)" pipeline). `IsTimelineOwner` per 06 §4.3.3
  (`obj.candidate.user == request.user`) is the object-level class; the *query* is
  scoped to `request.user` as well — never `TimelineEvent.objects.get(id=...)` — so
  even a mistake in permission wiring cannot leak. `PATCH`/`DELETE` on a foreign or
  nonexistent UUID are indistinguishable: both 404 with the project envelope.
- **POST/PATCH compose 4.1's services; no service changes expected.**
  `record_timeline_event` (D1 walk-the-chain, `auto_update_status=True` default),
  `update_timeline_event` (forward-only D2 re-sync on `event_type` change),
  `delete_timeline_event`. A blocked chain surfaces 4.1's `InvalidTransitionError` as
  a **400** carrying the machine's transition code — the 3.2 view pattern already
  established this rendering via `_TransitionRejected`.
- **Write gating mirrors 3.2:** `IsAuthenticated + IsActive + IsVerified` for all
  timeline routes (timeline writes are candidate writes; unverified/inactive users
  never own timeline content). Error bodies keep 2.2's project envelope
  (`{"error": {code, message}}`) via the accounts exception handler — no bespoke shapes.
- **`is_verified` is read-only in every serializer.** It is a moderation/verification
  flag (Phase 8 territory); clients cannot set it via POST or PATCH.
- **Missing profile follows 3.2's precedent:** an authenticated, verified user with no
  `CandidateProfile` gets the 404 `profile_not_found` envelope on timeline routes
  (3.2's `ProfileView._get_profile` shape) rather than an empty timeline or a 500.
- **TIME-04 is split across phases.** Its API-enabling half lands here (owners can
  list, edit, delete their own milestones); the *interactive chronological roadmap UI*
  with edit/delete controls is Phase 9.3 (UI-03, plan 09-03). TIME-04 is therefore
  marked partial at 4.2 close, not Complete.
- No model changes, no migrations expected — `makemigrations --check` must stay clean.

## Inputs already in place

- 4.1 shipped and committed (`38e1a07`): `apps/timeline` with `TimelineEvent`
  (UUIDv4, CASCADE FK, 8 event types, both compound indexes), `record_timeline_event`,
  `update_timeline_event`, `delete_timeline_event`, `CHAIN_ORDER`,
  `EVENT_TYPE_TO_STATUS`, and a 30-test suite.
- 3.2's API conventions to reuse verbatim: `apps/candidates/views.py`
  (`SpecErrorMixin`, `_TransitionRejected`, `_ProfileExists`, `_ProfileNotFound`),
  `permissions.py` (`IsActive`, `IsProfileOwner`), the
  `query-from-request.user` ownership discipline, and `apps/candidates/urls.py`
  included from `config/urls.py` under `/api/v1/`.
- DRF config already global: `JWTAuthentication`, `PageNumberPagination`,
  `PAGE_SIZE = 20`, project exception handler.
- 3.1's status machine + `CandidateProfile.current_status` (11 values) — the data the
  dashboard's progression and community blocks read.
- 238-test green suite, ruff gates, migration-drift checks from Phases 1–4.1.

## Open items for planning (4.2 PLAN.md)

1. `completion_percentage` (04 §28) exists **only** in the spec example — no helper,
   no field, no prior art in code. Planner must define the metric: which
   `CandidateProfile` fields count as "filled", field weights, and whether it is a
   service-layer computation or a serializer method. Pinned as a small, documented,
   tested rule.
2. Dashboard route home: `apps/timeline/` (timeline-adjacent) vs a new
   `apps/dashboard/` app vs `apps/candidates/`. The endpoint aggregates across domains
   (profile + timeline + community), so the choice affects where Phases 6/7 hook in.
3. Community benchmark suppression threshold: 04 §53 says "configured server-side"
   with a recommended initial value — planner pins the constant/setting name and the
   suppression response shape (`suppressed: true` + message per §53, vs omitting keys).
4. `auto_update_status` exposure: 4.1's service takes a parameter, but the API is a
   user-facing surface where silently declining to sync would desync status from the
   timeline. Planner decides whether POST hardcodes `True` (no client control) and
   whether PATCH/`?auto_update_status=` is ever accepted.
5. Ordering + pagination test matrix, IDOR matrix (foreign UUID on GET-list / PATCH /
   DELETE → 404 with row intact and no status change), date-boundary tests (exactly
   horizon, one day past, JOINING_LETTER tomorrow → 400), and dashboard aggregation
   tests (latest milestone with zero events, community counts with a single candidate,
   suppression firing).
