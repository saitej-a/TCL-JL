# PLAN 05-02+05-03 — Feed, Comments & Voting Endpoints

**Phase:** 5.2 · **Roadmap:** COMM-01, COMM-02, COMM-06, COMM-07, COMM-08 (endpoint halves of COMM-03/04/05) · **Status:** ✅ Executed 2026-09-22 (441 tests green, ruff clean, no migration; 33/33 live HTTP checks; D2 search shipped as planned websearch SearchVector) · **Written:** 2026-09-22
**Covers two roadmap plans:** 05-02 (T5.4–T5.9: categories, feed, detail, create/edit/delete) and 05-03 (T5.10–T5.13: comments, votes, lock/pin, N+1 discipline) — one sub-phase, one execution unit; both boxes tick at close.
**Inputs:** `CONTEXT.md` here (D1–D4, P1–P12); 04 §30–§38, §42–§46 (shapes, rules, verbs); 03 §17/§28–§32 (indexes, query strategy, search); 05 §60/§1016 (tabs, identity pills); 06 §4.3.2 (`IsAuthorOrModerator`), §6 (tiers); 08 §406 (tombstone — **D3 deviates, see below**); 10_MVP T5.4–T5.13
**Scope discipline:** API layer over 5.1's models. **No model changes, no migrations expected** (`makemigrations --check` stays clean). No announcement model (Phase 8), no notification wiring beyond a documented call site (Phase 6), no analytics (Phase 7), no frontend (Phase 9).
**Pre-condition:** 5.1 executed & pushed (`a7f170a`); stack healthy; 375-test suite green.

## Goal (roadmap "done when")

> Feed queries show no N+1; moderation controls restrict correctly.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | **Trending = windowed activity** (`vote_count + comment_count` within `COMMUNITY_TRENDING_WINDOW_DAYS`, default 14), newest-first tiebreak | Stale threads age out; `?ordering=trending` is a documented extension of 04 §31's whitelist, driven by 05 §1016's third tab |
| D2 | **Search = on-the-fly `SearchVector` + websearch query** | No column, no migration, no staleness; stored GIN index remains an additive upgrade |
| D3 | **Tombstones keep the author handle; only text is masked** | ⚠️ **Documented deviation from 08 §406** (`author = None` not implemented); verification must report this as known, not as a bug |
| D4 | **`comment_count` includes tombstones** | Feed card number == what the thread renders |

**Planner resolutions (CONTEXT open items 1–5):**

- **R1 — Trending window & threshold.** Setting `COMMUNITY_TRENDING_WINDOW_DAYS = 14`, read at call time. **No minimum-activity threshold**: a zero-activity in-window post still appears under the newest-first tiebreak — an empty tab means genuinely nothing happened, and a threshold would be one more knob to explain. The window **filters** (out-of-window posts are absent from `trending`, not ranked 0).
- **R2 — Avatar seed mechanics.** `avatar_seed` = `hmac_sha256(AVATAR_SEED_SECRET, str(candidate.id))[0] % 10` → palette index **0–9** (client maps to the ten pastel pairs 05 §6.5 lists). Setting `AVATAR_SEED_SECRET` **defaults to `settings.SECRET_KEY`** so it works with zero config, but can be pinned independently — rotating `SECRET_KEY` would otherwise silently re-colour every anonymous avatar, and "discussions remain followable" is exactly the property rotation would break. Exposed for **all** authors (anonymous and display-name alike; display-name mode may ignore it client-side). Profile-less user → `null`. Test-pinned: stable across requests, changes when the secret changes, never derivable without the secret.
- **R3 — Search composes with ordering; no relevance rank.** `?search=` filters; `?ordering=` (default `-created_at`) still orders. Predictable pagination beats a relevance sort that would fight the §31 whitelist.
- **R4 — Plan split.** One execution unit (this file) building both plans; Stage 2 ticks both roadmap boxes, and STATE counts **+2 plans** (27-plan total is roadmap-derived).
- **R5 — Test matrix** below (~70 tests; suite 375 → ~445).

## Pinned design

### Routes (`apps/community/urls.py`, included from `config/urls.py` under `/api/v1/`)

| Route | View | Verbs |
|---|---|---|
| `posts/categories/` | `PostCategoriesView` | GET (declared beside the others; `<uuid:pk>` cannot match the literal) |
| `posts/` | `PostListCreateView` | GET (feed), POST (rate-limited) |
| `posts/<uuid:post_id>/` | `PostDetailView` | GET, PATCH, DELETE |
| `posts/<uuid:post_id>/comments/` | `CommentListCreateView` | GET, POST |
| `posts/<uuid:post_id>/comments/<uuid:comment_id>/` | `CommentDetailView` | PATCH, DELETE (04 §43–§44) |
| `posts/<uuid:post_id>/vote/` | `PostVoteView` | POST (add), DELETE (remove) — explicit verbs per §45, no toggle |
| `posts/<uuid:post_id>/lock/` + `unlock/` | `PostLockView` | POST each — `/unlock/` added (P4: 04 §37 defines only lock; a one-way lock contradicts 08's reversibility) |
| `posts/<uuid:post_id>/pin/` + `unpin/` | `PostPinView` | POST each (04 §38) |

### Queryset construction (COMM-08; 5.1 P3 index choices pay off here)

```python
def annotated_posts():                                    # module helper in views.py
    return Post.objects.select_related("author__candidate_profile").annotate(
        vote_count=Count("votes", distinct=True),         # P8: distinct or the two
        comment_count=Count("comments", distinct=True),   # reverse FKs multiply rows
    )

# feed (P9): annotated_posts().filter(is_deleted=False)   → tombstones leave feed AND search
# ordering (P2 — pinned first always, server-side):
#   -created_at  → ["-is_pinned", "-created_at"]          (default = Latest tab)
#    created_at  → ["-is_pinned",  "created_at"]
#   -vote_count  → ["-is_pinned", "-vote_count"]          (Top Voted tab)
#    vote_count  → ["-is_pinned",  "vote_count"]
#    trending    → filter(created_at__gte=window_start)
#                  .annotate(activity=Count("votes", distinct=True) + Count("comments", distinct=True))
#                  → ["-is_pinned", "-activity", "-created_at"]   (Trending tab, D1)
# search (D2): .annotate(search=SearchVector("title", "body"))
#              .filter(search=SearchQuery(term, search_type="websearch"))   — composes with ordering
```

Unknown `ordering` → 400 `invalid_ordering`; unknown `category` → 400 `invalid_category`. `?page_size=` remains un-overridable (global paginator, 4.2 precedent).

### Serializers (`apps/community/serializers.py`)

- **`CommunityAuthorSerializer(AuthorPublicSerializer)`** — adds `avatar_seed` (R2) to 3.2's shape; **3.2's own serializer is untouched** (its shape tests pin exact keys). Reads the candidate profile via the same source; profile-less → `null`. This is the only author shape on every community response (COMM-07's cohort tags come free from 3.2: batch/hiring-type/region per 05 §6.5).
- **`PostFeedSerializer`** — `id, title, body_preview, category, author, vote_count, comment_count, is_pinned, is_locked, created_at` (04 §30). `body_preview` = P3: first **200 chars** of `tombstones.display_body`, newlines collapsed, trailing ellipsis `…` when truncated — a deleted post previews as the tombstone, never its original text.
- **`PostDetailSerializer`** — same plus full `body` (display-masked; D4/D3 semantics identical on detail). Deleted post → 200 with tombstone (P9, T5.8).
- **`PostWriteSerializer`** — `title, body, category` only; `is_pinned`/`is_locked` are moderator-only and **absent**; delegates to `create_post`/`update_post` so 5.1's codes surface verbatim.
- **`CommentSerializer`** — `id, body (display-masked), author, parent, replies[], created_at` (04 §40): one level, replies nested; **tombstoned comments keep their author** (D3) and show the masked body.
- **`CommentWriteSerializer`** — `body`, optional `parent_id` (04 §42).

### Services added to `apps/community/services.py` (write path stays single)

`update_post(post, data)` (validates via 5.1 validators), `add_vote(user, post) -> (PostVote, bool)` / `remove_vote(user, post) -> bool` (constraint is the guarantee; `IntegrityError` → `DuplicateVoteError` → 409, never surfaced raw), `set_post_lock(post, locked)` / `set_post_pinned(post, pinned)`. Comment soft-delete reuses 5.1's `soft_delete_comment`.

### Error contract (envelope; DRF field errors stay DRF-shaped)

```text
400 invalid_category | invalid_ordering | <5.1 post/comment codes> (blank_title, nested_reply, …)
401 anonymous          403 verification_required (IsVerified) | not_post_author | not_comment_author
                       | moderator_only | POST_LOCKED (locked post, T5.10)
404 post_not_found | comment_not_found | vote_not_found
409 already_voted (duplicate POST /vote/)
429 RATE_LIMITED + Retry-After (community_post_create, 5/hour — T5.7/COMM-02)
```

**403-vs-404 split (P6):** ownership failures are 403 (existence is public to every authenticated candidate — 06 §4.2.2's enumeration rationale doesn't apply); *missing* ids are 404. **Writes to a tombstoned post are 404 `post_not_found`** (it's no longer a valid target); only `GET detail` and `GET comments` stay 200 (P9 — a linked thread can still explain itself). Mechanism: community views map `PermissionDenied` → envelope using a per-view `permission_denied_code` attribute, so `IsAuthorOrModerator` (06 §4.3.2, verbatim semantics: staff → allow, author → allow, SAFE_METHODS → allow) stays the real guard while codes stay stable.

### Gating (P5)

All routes: `IsAuthenticated + IsActive + IsVerified`. Object writes: + `IsAuthorOrModerator`. Lock/pin/unlock/unpin: `IsStaff` (new tiny class, `user.is_staff` — COMM-06/T5.12; **staff, not "moderator group"** — groups arrive with Phase 8's moderation tooling).

### Throttle (P7)

`community_post_create: "5/hour"` in `DEFAULT_THROTTLE_RATES`; `PostCreateRateThrottle(ScopedRateThrottle)` on POST only. Comment creation **unthrottled** (04 §90 omits it — accepted risk, revisit Phase 8/10).

### Documented non-goals inside the surface

- `PATCH /posts/{id}/` does **not** accept `is_pinned`/`is_locked` from anyone (moderator routes only).
- No comment-count cache, no Redis (03 §29/§30), no announcement endpoints.
- Notification hook: `create_comment` call site carries a `# Phase 6 hook:` comment (04 §41 "may asynchronously create") — no stub service invented.

## Stage 1 — Build & automated gate

**Gate:** full pytest green (375 untouched) + `ruff check`/`format` clean + `makemigrations --check` clean (**no migration expected**).

### 1.1 Settings
`COMMUNITY_TRENDING_WINDOW_DAYS = 14`, `AVATAR_SEED_SECRET = SECRET_KEY` (read via `getattr` at call time), `community_post_create: "5/hour"` added to `DEFAULT_THROTTLE_RATES`.

### 1.2 `apps/community/serializers.py`, `permissions.py` (`IsAuthorOrModerator`, `IsStaff`), `throttles.py`, `urls.py` + `config/urls.py` include

### 1.3 `apps/community/views.py` (+ module-level `annotated_posts()` helper)
`PostCategoriesView`, `PostListCreateView`, `PostDetailView`, `CommentListCreateView` (paginated **top-level** with nested replies; top-level `total_comments` key = D4's all-levels count so card and thread agree — P10), `CommentDetailView`, `PostVoteView`, `PostLockView`, `PostPinView`. Shared `PermissionDenied`→envelope mapping via `permission_denied_code`.

### 1.4 Services per above; `BODY_PREVIEW_LENGTH = 200` constant (P3, not a setting)

### 1.5 Tests — `apps/community/tests/` (conftest additions: `staff_user`, `api`/`auth_api` reuse pattern from 4.2, `make_tombstoned_post/comment` sugar)

| File | Proves |
|---|---|
| `test_categories.py` (3) | `{"results": [{value, label}]}` exactly mirrors `POST_CATEGORIES`; auth required; no drift between endpoint and validator vocabulary |
| `test_post_list.py` (16) | §30 shape keys; pagination + un-overridable page size; category filter + unknown → 400 `invalid_category`; search matches title **and** body, websearch operators don't crash, **deleted posts absent from search**; ordering whitelist (5 accepted incl. `trending`, unknown → 400 `invalid_ordering`); **pinned-first under every ordering**; trending excludes out-of-window posts (override the window setting) and ranks by activity; **the multiplication trap**: post with 3 votes + 2 comments shows 3/2, not 6/6 (P8); `body_preview` truncation at 200 + tombstone preview on a deleted post; author payload carries `avatar_seed` + cohort tags; deleted post absent from feed (P9); anonymous 401 / unverified 403 |
| `test_post_detail_create.py` (14) | detail full body + counts; **deleted detail → 200 tombstone, never 404** (P9/T5.8); create 201 via service (author from request; `is_pinned`/`is_locked` in body are ignored); create surfaces 5.1 codes (400 `blank_title` / `invalid_category`); **429 envelope + `Retry-After` after the 5th post in the hour** (T5.7); PATCH by author 200; PATCH by staff 200; **PATCH by other candidate → 403 `not_post_author`** (P6); PATCH validation codes; DELETE by author → 204 and **row retained with `is_deleted=True`**; DELETE by moderator 204; DELETE by other → 403; missing id → 404 `post_not_found` |
| `test_comments.py` (16) | list shape incl. top-level `total_comments`; top-level pagination with replies nested one level; **`total_comments` counts tombstones** (D4) and disagrees-with-thread scenario is impossible; create 201; reply via `parent_id`; **nested reply → 400 `nested_reply`**; `parent_post_mismatch`; **parent tombstoned → 400 `parent_deleted`**; tombstoned comment renders masked body **with author kept** (D3); **locked post → 403 `POST_LOCKED`** (T5.10); comment on tombstoned post → 404 `post_not_found` (write rule); PATCH own comment; DELETE own comment → soft, row retained; PATCH/DELETE by other → 403 `not_comment_author`; missing comment → 404; **query budget: list ≤ 8 queries, feed ≤ 8** (`assert_num_queries` — COMM-08's "no N+1" as a regression guard, not a hope) |
| `test_votes.py` (9) | POST → 200 `{"voted": true, "vote_count": n}`; **duplicate POST → 409 `already_voted`** and still one row; DELETE → `{"voted": false}`; DELETE without vote → 404 `vote_not_found`; constraint still the backstop (ORM duplicate raises); vote on tombstoned post → 404; counts move on the feed after voting; unverified 403; anonymous 401 |
| `test_moderation.py` (8) | lock by staff → §37 shape `{"id", "is_locked": true}`; **unlock** → false (P4's symmetry); pin/unpin → §38 shapes; non-staff → 403 `moderator_only`; unverified staff-gated check; lock state actually blocks comments (cross-file invariant restated); pin ordering surfaces first in feed (integration with P2); actions on tombstoned post → 404 |
| `test_avatar_seed.py` (4) | present on every author payload; **stable across requests**; **changes when `AVATAR_SEED_SECRET` is overridden** (non-derivability probe); `null` for a profile-less user |

### 1.6 Execution order
1. Settings → serializers/permissions/throttles → services → views/urls → tests
2. `docker compose run --rm web sh -c "pip install -q -r requirements-dev.txt && python -m pytest"`
3. **Gate:** pytest · ruff check · ruff format --check · `makemigrations --check --dry-run`

## Stage 2 — Live verification round

- [ ] Stack restart; `/health/` + `/health/ready/` 200
- [ ] Real-HTTP JWT drill (4.2 pattern, two candidates + one staff): categories → create posts (mind the 5/hour cap: run the **429 test deliberately last** for that user; extra fixture posts via ORM) → feed filters (`?category=`, `?search=`, each ordering incl. `trending` with pinned-first) → detail vs tombstone detail → PATCH own / 403 foreign → DELETE soft → comments (reply, nested 400, tombstoned parent 400, **locked 403**) → votes (add, **duplicate 409**, remove, feed count moves) → staff lock/unlock/pin/unpin + 403 as non-staff → `total_comments` agreement between card and thread
- [ ] Full pytest re-run green; ruff clean; `makemigrations --check` clean (expect **no** migration)
- [ ] `EXPLAIN` the feed query: index use on `idx_post_category_created` for the filtered path (5.1's indexes doing their job)
- [ ] Prod compose validates (4.1/4.2 flow); docs updated: STATE, REQUIREMENTS (COMM-01/02/06/07/08 + sub-phase row 5.2 → Complete), ROADMAP (05-02 **and** 05-03 checked, Phase 5 → 3/3 Complete), PLAN gate checkboxes; **VERIFICATION note: D3's deviation from 08 §406 stated up front**

## Out of scope (later phases)

- Notification dispatch on comments/replies (Phase 6 — call site documented); `Announcement` model + broadcast (Phase 8, T8.6); moderator *group* semantics (Phase 8 — 5.2 uses `is_staff`); comment-create throttling (accepted risk); relevance-ranked search & stored vectors (escalation path only); frontend (Phase 9); seed data via the services (Phase 10).

## Security notes (ASVS L1)

- **Authorship and moderator state are never client-supplied** — `author` from the request context, `is_pinned`/`is_locked` absent from every write serializer (06 §4.4/§4.5).
- **Avatar seed is non-forgeable** (P1/R2): a public-UUID-derived colour would let anyone track a pseudonym across threads — the property 05 §60's "internal random salt" protects. Secret is server-side; seed exposes only a palette index.
- **Removed content stays masked on every path out** — preview, detail, comments, and search all read through `tombstones.display_*`; no route returns an original title/body of tombstoned content.
- **Ownership failures are 403, existence is public** (P6): community reads are the authenticated tier, so 4.2's enumeration logic doesn't transfer; missing ids remain 404.
- **Rate-limited creation** blunts feed spam (T5.7); the 429 renders the project envelope with `Retry-After` so clients can back off properly.
- **D3 residual, restated:** a self-deleted post keeps its pseudonym on the tombstone — removal hides the words, not the participation. Account deletion anonymizes the row and thereby the handle (2.2).
