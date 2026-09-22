# VERIFICATION 05-02 — Feed, Comments & Voting Endpoints

**Phase:** 5.2 · **Verified:** 2026-09-22 · **Requirements:** COMM-01, COMM-02, COMM-06, COMM-07, COMM-08 (endpoint halves of COMM-03/04/05)
**Verdict:** ❌ **FAIL** — the automated gate is green (441 tests, ruff clean, no migration drift) and most
of the surface is correct, but **independent live-HTTP probing found two acceptance-criteria defects the
phase's own suite does not catch**, plus two response-shape deviations from 04. One of the two defects
(P9 feed/search exclusion) is masked by a **vacuous regression test** that passes whether or not the bug
is present — proven by mutation. STATE/REQUIREMENTS already mark 5.2 and Phase 5 COMPLETE; that claim is
**not** supported by this verification.
**Verification is independent of execution:** a separate probe script (`verify_probe_05_02.py`, not the
phase's `drill_05_02.py`) attacked the running stack over real HTTP with real JWTs, and two controlled
mutations established which tests are load-bearing and which are not.

## Evidence sources

| Source | Scope | Result |
|---|---|---|
| Independent adversarial HTTP probe (`verify_probe_05_02.py`, real JWTs, gunicorn) | 8 checks: P9 feed/search exclusion, tombstone masking, 04 §30/§43 shapes, COMM-02 throttle, trending exclusion | **3 pass / 5 fail** |
| Full automated suite `pytest` | 441 tests | **441 passed** |
| `ruff check` + `ruff format --check` | `apps/ config/` | clean (112 files) |
| `manage.py makemigrations --check --dry-run` | drift | No changes detected — **no migration**, as planned |
| Mutation probes (temporary, reverted) | test-suite strength | see below — one test vacuous, one load-bearing |

The phase's own `drill_05_02.py` (33/33) **passed while both defects were live**, because it never asserts
that a deleted post leaves the *default* feed (it checks tombstone detail only) and never exercises the
post-create throttle. Green drill ≠ correct phase.

## Roadmap success criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Paginated feed filtered by category, search, and sort order | ⚠️ **PARTIAL** | Category/search/tab/ordering all function and paginate (20, un-overridable). **But soft-deleted posts are not excluded from the default feed or from `?search=`** (probe V2/V4) — the listing shows tombstone cards that P9 says must leave. |
| 2 | Comment replies strictly capped at 1-level depth | ✅ PASS | 5.1 `validate_reply_depth` on the `create_comment` path; probe-confirmed `nested_reply` 400 (drill #21) and `test_reply_depth.py` (11 tests). |
| 3 | Upvoting enforces `UNIQUE(user, post)`, no duplicates | ✅ PASS | DB constraint `unique_user_post_vote` is the guarantee; duplicate POST → 409 `already_voted` inside a savepoint (no 500 on race); `test_vote_constraint.py` (7). |
| 4 | Soft-deleted content displays clean tombstones without breaking reply hierarchies | ⚠️ **PARTIAL** | Tombstone text renders correctly and originals are masked (probe V3 — no text leak); reply trees survive (`parent` SET_NULL). **But the feed-exclusion half of the design (5.1 D4 / P9 / 03 §28) is unmet** — deleted posts remain listed. |
| 5 | Feed querysets use `select_related()`/`.annotate()` to eliminate N+1 | ✅ PASS | `select_related("author__candidate_profile")`, `distinct=True` counts, filtered `Prefetch` for `has_voted`; `test_query_budgets.py` asserts feed/trending/thread budgets; the multiplication trap test is **load-bearing** (mutation: removing `distinct=True` → `assert 6 == 3` fails). |

## Requirements

| Item | Verdict | Notes |
|---|---|---|
| COMM-01 (browse feed: category/search/sort) | ⚠️ Partial | Mechanically complete; **fails the deleted-post exclusion** the same requirement's design (P9) carries. |
| COMM-02 (create posts, **rate-limited 5/hr**) | ❌ **Not met** | **Post creation is unthrottled.** `PostListCreateView` declares no `throttle_classes`; probe V7 fired 8 rapid creates → `[201×8]`, no 429. The `community_writes` 30/min scope exists but is wired only to detail/vote/comment/lock/pin — **not** to the one endpoint COMM-02/T5.7 names. REQUIREMENTS.md's "community_writes 30/min" claim is inaccurate for the create path. |
| COMM-06 (staff lock/pin; locked rejects comments) | ✅ Complete | `IsModerator` (is_staff) on lock/unlock/pin/unpin; author cannot lock own thread (403 `moderator_only`); locked post → 400 `post_locked`; `/unlock/` + `/unpin/` reversibility additions present. |
| COMM-07 (public handles, deterministic avatars, cohort tags) | ✅ Complete | `CommunityAuthorSerializer` = 3.2 redaction + `avatar_seed`; HMAC over candidate id with server-side `AVATAR_SEED_SECRET` (non-derivable, stable); cohort tags (batch/hiring_type/region) present; no email (probe + `test_avatar_seed.py`). |
| COMM-08 (no N+1) | ✅ Complete | See criterion 5. |

## Known/recorded deviations (by design — report, do not "fix")

- **D3 — tombstones keep the author handle** (deliberate deviation from 08 §406's `author = None`). Confirmed in code and probe; anonymity-safe via 3.2. Recorded in CONTEXT/PLAN.
- **Rate-limit value 30/min `community_writes` vs spec 5/hr** — recorded in REQUIREMENTS as a deviation. *Separate from COMM-02 above:* even the deviated 30/min is **not applied to create**, so this is a wiring defect, not just a value choice.
- **`invalid_category` returns 404, not 400** (PLAN said 400; `_InvalidCategory.status_code = 404`). Internally consistent and tested, but unconventional for a bad query-param value and off-plan.
- **Routes/shapes drifted from PLAN:** `/api/v1/community/posts/` (PLAN: `posts/`), `?tab=trending` (PLAN: `?ordering=trending`), flat `/community/comments/{id}/` (PLAN: nested), vote POST → 201 (PLAN: 200), unlock via `DELETE` (PLAN: `POST /unlock/`). These are coherent and drilled; they are PLAN-doc drift, not bugs.

## Response-shape deviations from 04 (newly found)

- **04 §30 feed card — `body_preview` missing.** The feed returns the **full `body`** (probe V5: keys include `body`, no `body_preview`). PLAN P3 pinned a 200-char `body_preview` on the card with full body only on detail; the implementation uses one `PostCardSerializer` (full body) for both. Payload-size and spec-shape regression.
- **04 §43 vote shape — `voted` missing.** Vote responses return `{id, vote_count, is_pinned, is_locked}` (probe V6), not `{"voted": bool, "vote_count": int}`. Clients cannot read the toggle state from the vote response.

## Test-suite strength (mutation evidence)

| Mutation | Expected | Observed |
|---|---|---|
| Added the missing `is_deleted=False` filter to `feed_queryset` | If `test_deleted_posts_absent_from_feed` were load-bearing it would pass *only* with the fix | `test_feed_api.py` **9 passed both with and without the fix** — the test is **vacuous**: it asserts `"gone" not in titles`, but a deleted post's title is masked to `"This content has been removed."`, so the literal never appears regardless. The suite was green while the bug was live. |
| Removed `distinct=True` from both feed counts | The multiplication-trap test fails | `test_counts_exact_under_multiplication` **failed (`assert 6 == 3`)** — genuinely load-bearing. |

Both mutations were reverted; `git diff` on `views_services.py` is clean and `distinct=True` is restored.

## Findings

### F1 — Soft-deleted posts remain in the default feed and in search — **HIGH**
`apps/community/views_services.py::feed_queryset` never filters `is_deleted=False` (while
`trending_queryset` does). Result: a deleted post is returned by `GET /community/posts/` and by
`?search=`, rendered as a tombstone card. Violates P9 ("deleted posts leave the feed and search"),
5.1 D4, and 03 §28; undercuts roadmap criteria 1 and 4. Original text is **not** leaked (masking holds,
probe V3), so this is a correctness/design defect, not a disclosure one. **Guarded only by a vacuous
test** (see mutation evidence). Fix: add `.filter(is_deleted=False)` in `feed_queryset` (trending already
does) **and** repair the test to assert on the post's *id*, not its masked title.

### F2 — Post creation is not rate-limited — **HIGH**
COMM-02/T5.7 require rate-limited creation (spec 5/hr). `PostListCreateView` has no `throttle_classes`,
and there is no global `DEFAULT_THROTTLE_CLASSES`, so `POST /community/posts/` is unbounded (probe V7:
8 rapid creates, all 201). The `community_writes` throttle guards every *other* community write but the
create path — the exact one the spec names. Fix: attach a scoped throttle to the create view (and decide
the 5/hr-vs-30/min value deliberately). REQUIREMENTS.md's COMM-02 "Complete" line should be corrected.

### F3 — Feed card returns full `body`, not `body_preview` — **MEDIUM**
04 §30 / PLAN P3 pin a truncated `body_preview` on the card; the shipped `PostCardSerializer` returns the
full body on both list and detail. Larger payloads and a spec-shape miss. Fix: add a `body_preview`
(200-char, display-masked) field for the list shape, or document the deviation as intentional.

### F4 — Vote response omits `voted` — **LOW**
04 §43's shape is `{"voted": bool, "vote_count": int}`; the response carries `vote_count` but no `voted`.
Two-line serializer fix (`VoteSerializer`).

### F5 — `invalid_category` is 404, not 400 — **LOW** *(product/contract call)*
A bad `?category=` value returns 404 (off-plan; PLAN said 400). 400 is the conventional status for a
malformed query parameter. Consistent and tested, so flagging only for an explicit decision.

### F6 — Dead permission classes — **LOW** *(hygiene)*
`permissions.py` defines `IsAuthorOrReadOnly` and `CommunityAccess`, but the views use an inline
`_require_author()` helper and `[IsAuthenticated, IsActive, IsVerified]` directly. The two classes are
unused. Either wire them in (single source for the author gate) or delete them.

### F7 — `?tab=trending` ignores `category`/`search`; comment-create unthrottled — **LOW** *(accepted-risk / by-design)*
The trending branch builds its queryset without the category/search filters, so those params are silently
dropped when `tab=trending`. Comment creation has no throttle (04 §90 omits it; PLAN accepted the risk).
Both are defensible but should be documented as known limits.

## Residual risk

- **F1 + F2 mean Phase 5 was closed prematurely.** STATE.md (`stopped_at`, `last_activity`) and
  REQUIREMENTS.md (COMM-01/02 rows, sub-phase 5.2 → Complete) and ROADMAP.md (05-02/05-03 checked,
  Phase 5 → 3/3) all assert completion. Two acceptance-criteria defects are live and one regression test
  is vacuous, so the "441 green / 33-33 drill" evidence over-states correctness. The docs should not
  carry a Phase 5 COMPLETE claim until F1/F2 are fixed and re-probed.
- The 5.1 D4 / P9 "deleted leaves the feed" invariant is now demonstrably unenforced end-to-end; any
  Phase 9 UI built on this feed will render tombstone cards the design says should not exist.
- `AVATAR_SEED_SECRET` defaults to `SECRET_KEY`; rotating `SECRET_KEY` silently recolours every anonymous
  avatar (documented trade-off, not a defect). Pin the secret before launch if avatar stability matters.

## Required before close

1. **F1** — filter `is_deleted=False` in `feed_queryset`; fix `test_deleted_posts_absent_from_feed` to
   assert on post id (and add a search-exclusion assertion). Re-run probe V2/V4.
2. **F2** — throttle `POST /community/posts/`; correct the COMM-02 line in REQUIREMENTS.md. Re-run probe V7.
3. **F3/F4** — restore `body_preview` on the card and `voted` on the vote response, or record an explicit
   decision to deviate from 04 §30/§43.
4. Re-run the full gate + this probe; only then update STATE/REQUIREMENTS/ROADMAP to COMPLETE.

## Sign-off

5.2's models-level guarantees (vote uniqueness, reply depth, tombstone masking, N+1 discipline, avatar
non-derivability, staff moderation gating) hold under independent probing. Its **feed-exclusion and
rate-limiting acceptance criteria do not**, and the suite's green result rests partly on a test that
cannot fail. **Verdict: FAIL — not closed.** The defects are small, localized fixes (one queryset filter,
one throttle, two serializer fields, one test assertion), but they are real and block a Phase 5 COMPLETE
claim.
