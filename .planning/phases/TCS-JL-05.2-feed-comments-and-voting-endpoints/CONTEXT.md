# Phase 5.2 — Discussion Record: Feed, Comments & Voting Endpoints

Date: 2026-09-22
Scope: Roadmap plans 05-02 and 05-03 (T5.4–T5.13) — the whole community API on top
of 5.1's models: categories, feed listing (category filter, search, ordering,
pagination), post detail/creation (rate-limited)/edit/soft-delete, comments
list/create, vote add/remove, and staff lock/pin. Requirements covered: COMM-01,
COMM-02, COMM-06, COMM-07, COMM-08 (COMM-03/04/05 model halves shipped in 5.1).
No model changes expected beyond the settings-driven bits below; model/schema
decisions stay as 5.1 pinned them.

## Decisions locked (user)

- **D1 — "Trending" is a windowed activity score.** 04 §31 whitelists only
  `created_at`/`vote_count` orderings and never defines Trending, but 05 §1016's
  feed has three tabs — Latest, **Trending (Most Active)**, Top Voted — and 02 §29
  says the ranking should "remain simple", with recent activity, votes, and comment
  count as signals. So: `ordering=trending` ranks by
  `vote_count + comment_count` restricted to posts created within a settings-held
  window (default 14 days), newest-first as the tiebreak. Stale threads age out of
  the tab instead of occupying it forever, and there is no time-decay math or
  recommendation machinery (02 §29's explicit limit).
  *Consequence:* `ordering` accepts exactly
  `-created_at` (default), `created_at`, `-vote_count`, `vote_count`, `trending` —
  a deliberate, documented extension of 04 §31's list, because 05's UI mandates a
  third mode that §31 does not name. Anything else → 400 (`invalid_ordering`).
- **D2 — Search uses on-the-fly PostgreSQL search vectors.** An annotate of
  `SearchVector("title", "body")` matched with `websearch_to_tsquery`, composed in
  the same query as the feed filters and scoped to non-deleted posts. Satisfies
  T5.6's "search vectors" and 04 §32's "use PostgreSQL search capabilities" with
  **no new column, no migration, and no staleness risk** — 03 §32 frames full-text
  search as something to evaluate before adding dependencies, and a stored
  `SearchVectorField` + GIN index remains a purely additive escalation if the
  forum outgrows a scan.
- **D3 — Tombstoned content keeps its author handle; only the text is masked.**
  ⚠️ **This is a deliberate deviation from 08 §406**, whose diagram renders a
  removed post's author as `None`. Chosen because a reader keeps the thread's
  "who was here" context, and because the handle is already anonymity-safe: 3.2's
  `AuthorPublicSerializer` resolves ANONYMOUS candidates (the default) to
  "Anonymous Candidate" and never exposes email or real names, while 5.1 D3's
  neutral copy means removal never implies moderation. *Residual exposure, stated
  plainly:* a candidate who deletes their own post still has their chosen
  pseudonym attached to the tombstone; account deletion is unaffected because 2.2
  anonymizes the user row, which renders as anonymous anyway. 08 §406's
  `author = None` is therefore **not implemented** — the verification record must
  report this as a known deviation, not discover it as a bug.
- **D4 — `comment_count` counts tombstones too.** Tombstoned comments stay visible
  in their thread (5.1 D4), so the feed's number matches what a reader actually
  finds: 7 visible entries means 7. Excluding them would make the count disagree
  with the thread, which is the mismatch users read as a bug.

## Planner resolutions (pinned here; veto at plan review)

- **P1 — Anonymous avatars get a server-derived, non-forgeable seed.**
  05 §60/§6.5 asks for a "deterministic, pleasant pastel" for ANONYMOUS mode based
  on an "internal random salt so discussions remain followable without revealing
  names". The author payload therefore gains one key, **`avatar_seed`**: an HMAC of
  the candidate's id with a server-side secret, reduced to a fixed palette index
  (client picks the pastel). Deterministic per candidate, **not computable by any
  client** from public data — a UUID- or name-derived colour would let anyone
  compute any candidate's avatar and would link a person across threads even after
  a display-name change, which is precisely what the spec's salt exists to avoid.
  No schema change, no backfill. DISPLAY_NAME mode stays purely client-side
  (2-letter initials + colour hashed from the display name) exactly as 05 §6.5
  states. This extends 04 §30's `{id, display_name}` example by one key.
- **P2 — Ordering maps to the UI's three tabs, and pinned-first is server-side.**
  Latest → `-created_at` (default); Trending → `trending` (D1); Top Voted →
  `-vote_count`. Pinned posts are ordered first **regardless** of the requested
  ordering, per 04 §31's "implement that server-side rather than trusting the
  client" — the client never sends a pinned flag.
- **P3 — `body_preview` is a display-derived truncation.** 04 §30 shows
  `body_preview` and full `body` only on detail. Pin: first 200 characters of the
  **displayed** body (so a deleted post previews as the tombstone, not its original
  text), single-line, no HTML. Constant in the community module, not a setting.
- **P4 — Lock and unlock are symmetric.** 04 §37 defines `POST /lock/` and §38
  defines `/pin/` and `/unpin/` but no `/unlock/`. Pin: `/lock/` sets
  `is_locked=True` and **`/unlock/` sets `False`** — added because leaving a
  moderator unable to undo a lock is a one-way door, and 08's reversal principle
  (mistakes must be correctable) plus §38's own pin/unpin symmetry argue for it.
  Flagged as an addition beyond §37.
- **P5 — Permissions and gating.** Reads (feed, detail, comments, categories):
  `IsAuthenticated` + `IsActive` + `IsVerified` (community is the authenticated
  tier of 06 §6; an unverified account cannot participate). Writes: same gate plus
  object-level `IsAuthorOrModerator` (06 §4.3.2) for post/comment edit and delete.
  Lock/pin/unlock/unpin: `is_staff` only (COMM-06, T5.12).
- **P6 — 403, not 404, for someone else's post.** 4.2's 404-not-403 rule exists to
  prevent *enumeration of private* resources (06 §4.2.2). Community posts are
  readable by every authenticated candidate, so the post's existence is already
  public and a 403 leaks nothing; copying 4.2's rule here would only confuse
  clients. Pin: `PATCH`/`DELETE` by a non-author, non-moderator → **403**
  (`not_post_author`), with the same treatment for comments. Genuinely missing ids
  are 404 (`post_not_found`).
- **P7 — Rate limiting follows 2.2's pattern.** A new `community_post_create` scope
  at **5/hour** (T5.7, COMM-02) added to `DEFAULT_THROTTLE_RATES` with
  `ScopedRateThrottle`, so a 429 renders the project envelope with `Retry-After`
  through the accounts handler. Comment creation gets no scope — 04 §90 does not
  list it — recorded as accepted risk, revisitable in Phase 8/10.
- **P8 — The two-annotation trap is pinned explicitly (COMM-08).** Counting votes
  and comments in one queryset joins two different reverse FKs and **multiplies
  rows**: a post with 3 votes and 2 comments reports 6 for each. Pin:
  `Count("votes", distinct=True)` and `Count("comments", distinct=True)` in a single
  `annotate`, with the feed using `select_related("author__candidate_profile")`, and
  a test asserting exact counts on a post that has both.
- **P9 — Deleted posts leave the feed and search, but detail stays reachable.**
  5.1 D4 at the query layer: feed and `?search=` both filter `is_deleted=False`;
  `GET /posts/{id}/` still returns a 200 with the masked tombstone (04 T5.8), never
  404 — a linked post must be able to explain itself.
- **P10 — `total_comments` resolves the one-number problem.** Threads must not
  display two different sizes: the feed card (which shows D4's all-levels count)
  and the comments endpoint would otherwise disagree, because comments paginate
  **top-level** comments with replies nested (04 §40: one level only, "avoid
  unlimited nested structures"). Pin the comments response as: `count`/`next`/
  `previous` follow DRF semantics for the paginated set (top-level comments —
  honest, so a client computing pages from `count` cannot mis-paginate),
  `results[]` carries replies nested, and a top-level **`total_comments`** field
  reports the D4 all-levels number so the card and the thread agree. One added key,
  no invented pagination semantics.
- **P11 — Categories endpoint serves 5.1's settings list.**
  `GET /posts/categories/` → `{"results": [{"value", "label"}]}` (04 §46 shape) read
  from `POST_CATEGORIES`, so the model validator and the endpoint can never drift.
- **P12 — No notification wiring in this phase.** Comment/reply creation "may
  asynchronously create a notification" (04 §41) — that hook belongs to Phase 6,
  which owns the Notification model. 5.2 leaves the call site documented rather
  than inventing a stub.

## Spec invariants carried (no decision)

- **Response shapes** per 04: feed items carry `id, title, body_preview, category,
  author{id, display_name, avatar_seed}, vote_count, comment_count, is_pinned,
  is_locked, created_at`; post detail carries full `body`; comments carry
  `id, body, author, parent, replies[], created_at`; vote endpoints return
  `{"voted": bool, "vote_count": int}`.
- **Explicit vote verbs** (04 §45): `POST /posts/{id}/vote/` adds,
  `DELETE /posts/{id}/vote/` removes — no toggle endpoint. 5.1's
  `unique_user_post_vote` remains the real guarantee; the API must translate a
  duplicate into a clean response rather than surfacing an `IntegrityError`.
- **Filters compose:** `?category=`, `?search=`, `?ordering=`, `?page=` work
  together (04 §30/§32); unknown `category` → 400 (`invalid_category`), unknown
  `ordering` → 400 (`invalid_ordering`).
- **Locked posts reject new comments** with **403 `POST_LOCKED`** (T5.10, 04 §37's
  "a locked post cannot receive new comments").
- **04 §42's remaining rules** were split in 5.1: the three model-level parent rules
  live in `validate_reply_depth`; *post not locked* and *user has permission* are
  request-context rules and are 5.2's to enforce at the view layer.
- **Comment/thread creation goes through 5.1's services** (`create_post`,
  `create_comment`, `soft_delete_*`) so the reply-depth and category rules keep
  exactly one enforcement point; bodies render through `tombstones.display_body` /
  `display_title` (5.1 D3/P2) and never read the raw field on the way out.
- **Error bodies** keep 2.2/3.2's project envelope via the accounts exception
  handler; serializer field errors keep DRF's field shape; `InvalidPostError` /
  `InvalidCommentError` codes pass through verbatim (5.1 R4).
- **No `Announcement`** (Phase 8, T8.6); no notification delivery (Phase 6); no
  analytics reads (Phase 7); no seed data (Phase 10); no frontend (Phase 9).

## Inputs already in place

- **5.1 (shipped, pushed in `a7f170a`)**: `Post`/`Comment`/`PostVote` with the
  `unique_user_post_vote` DB constraint, `is_locked`/`is_pinned`/`is_deleted` flags,
  `create_post`/`create_comment`/`soft_delete_*`, `validate_reply_depth` and its
  three codes, `tombstones.TOMBSTONE_TEXT` + `display_title`/`display_body`, and a
  56-test suite.
- **3.2**: `AuthorPublicSerializer` — the only community author shape; already
  resolves ANONYMOUS/DISPLAY_NAME, the anonymized (2.2) row, and profile-less
  users, with redaction tests. It supplies the batch/hiring-type/region cohort tags
  05 §6.5 asks for; `avatar_seed` (P1) is additive to it.
- **4.2**: the error-envelope + permission-class pattern (`SpecErrorMixin`,
  `_TransitionRejected`, `IsActive`, `IsVerified`), DRF pagination config
  (`PageNumberPagination`, `PAGE_SIZE=20`, no client page-size override), and the
  "single serializer shape per direction" discipline.
- **2.2**: throttle infrastructure (`DEFAULT_THROTTLE_RATES`, scoped throttles, 429
  envelope with `Retry-After`) to extend with P7's scope.
- 375-test green suite, ruff gates, migration-drift checks from Phases 1–5.1.

## Open items for planning (5.2 PLAN.md)

1. Trending window: setting name + default (14 days) and whether a minimum-activity
   threshold is needed so an empty result set renders as an empty tab rather than a
   wall of zero-activity posts.
2. Avatar seed details: palette size, the secret's settings name, and the guarantee
   that the value is stable across requests but not derivable from `id` (test-pinned).
3. Whether search ranks by relevance or falls back to the requested ordering (pin:
   compose with `ordering`, defaulting to `-created_at`, so results are predictable).
4. Division between the two plans (05-02: T5.4–T5.9 feed/detail/create/edit/delete +
   categories; 05-03: T5.10–T5.13 comments/votes/lock-pin plus the shared test
   matrix), since this sub-phase ships two plans.
5. Test matrix: the multiplicative-annotation trap (P8) with exact counts,
   query-count assertions for the feed and comment list (COMM-08's "done when: no
   N+1"), ordering whitelist accept/reject incl. `trending`, pinned-first under
   every ordering, category + search composition, search excluding deleted posts,
   tombstone rendering across feed/detail/comments (D3/D4), locked-post 403,
   429 envelope on post creation, 403-vs-404 ownership split (P6), and
   `avatar_seed` stability + non-derivability (P1).
