# PLAN 05-01 — Forum Models & Deletion Semantics

**Phase:** 5.1 · **Roadmap:** COMM-03, COMM-04, COMM-05 · **Status:** ✅ Executed (2026-09-22) · **Written:** 2026-09-22
**Inputs:** `CONTEXT.md` in this directory (decisions D1–D4 + pins P1–P6); 03 §9 (Post), §10 (Comment + reply structure), §11 (PostVote), §17 (indexes), §18 (UUIDs), §19 (FK delete strategy), §20 (soft deletion), §26/§38 (validation + constraints), §29/§30 (no denormalized counters); 04 §33 (create-post body), §42 (the five comment rules); 08 §390–§415 (tombstone architecture, preserved originals, reversibility); 10_MVP T5.1–T5.3
**Scope discipline:** Models + validators + services + tombstone helpers + tests only. **No serializers, views, URLs, permissions, throttles, or feed querysets** (all 5.2). No `Announcement` (Phase 8 / T8.6, same app later). No notifications, no analytics, no seed data. New `apps/community` app ⇒ **one new migration expected**; drift check runs *after* generation.
**Pre-condition:** 4.2 executed & committed (`b232158`); stack healthy; 319-test suite green (92 accounts + 125 candidates + 102 timeline).

## Goal (roadmap "done when")

> Duplicate votes are impossible at DB level; tombstones preserve reply trees.

## Decisions carried from CONTEXT.md

| # | Decision | Consequence |
|---|----------|-------------|
| D1 | **Categories = merged union of three disagreeing specs**, settings-driven, `OFFER` folded into `OFFER_LETTER` | 12 keys shipped; extensible without a deploy (01 §7); vocabulary aligns with `TimelineEvent` for Phase 7 analytics |
| D2 | **`author` required, `PROTECT`** — the retained anonymized user row (2.2) is the tombstone | No NULL-author branch anywhere; 3.2's `AuthorPublicSerializer` already renders the anonymized row safely; hard user deletion refused, which is what makes the F1 profile-deletion fix the coherent one |
| D3 | **One neutral tombstone copy** for author- and moderator-deletion alike | Neither path makes a false attribution claim; originals stay in the row (08 §390); Phase 8 owns moderator wording |
| D4 | **Deleted posts leave the feed; detail returns a masked tombstone** | 03 §28 literal; criterion 4 met by tombstoned comments remaining in their threads + T5.8's masked detail |

**Planner resolutions (CONTEXT open items 1–4):**

- **R1 — The depth rule is enforced on the real write path, not just declared.** `Model.clean()` is *not* called by `save()`, so shipping a validator alone would leave the invariant unenforced until 5.2. 5.1 therefore ships `create_post()` / `create_comment()` service functions that validate, and 5.2's serializers delegate to them (the 3.1/3.2 split: service owns the invariant, serializer owns shape). `clean()` mirrors the same validators for admin/forms. **Documented limitation:** `bulk_create()` and raw SQL bypass both — no production path uses them, and the Phase 10 seed must go through the services.
- **R2 — Tombstones are pure module functions in `apps/community/tombstones.py`**, not model methods: one `TOMBSTONE_TEXT` constant plus `display_title(post)` / `display_body(obj)`. Keeps a display concern out of the model and gives 5.2 exactly one copy source (D3).
- **R3 — Field details the specs leave open:** `title` is `CharField(max_length=200)` (specs state only "String, Required"); `body` is `TextField`; whitespace-only title/body are rejected; `Post.Meta.ordering = ["-is_pinned", "-created_at"]` (pinned first, then newest — matches 03 §17's `(is_pinned, created_at)` index and 9.10's "pinned announcements" in the feed) and `Comment.Meta.ordering = ["created_at"]` (conversation order). Ordering is pinned now because 5.2's pagination must be stable.
- **R4 — Error vocabulary:** `Model.clean()` raises Django's `ValidationError` with codes; the services translate to `InvalidPostError` / `InvalidCommentError` (plain `ValueError` subclasses carrying `.code`, exactly 3.1's `InvalidTransitionError` pattern) so 5.2 renders the project envelope with a stable code.
- **R5 — Test matrix** below (~52 tests; suite 319 → ~371).

## Pinned design

### Category vocabulary (D1) — `config/settings/base.py`

```python
POST_CATEGORIES = [
    ("GENERAL", "General"), ("JOINING_LETTER", "Joining Letter"),
    ("OFFER_LETTER", "Offer Letter"), ("JOINING_DATE", "Joining Date"),
    ("LOCATION", "Location"), ("INTERVIEW", "Interview"),
    ("DOCUMENTS", "Documents"), ("DISCUSSION", "Discussion"),
    ("TCS_PROCESS", "TCS Process"), ("HELP", "Help"),
    ("ANNOUNCEMENT", "Announcements"), ("OTHER", "Other"),
]
```

Read **at call time** (3.1 D3's `BATCH_YEARS` pattern): `category` is a `CharField` **without** `choices`, so extending the list never produces a migration. Keys + labels come from this one structure, which is also what 5.2's `GET /posts/categories/` (T5.4) serves — one source of truth for both the field and the endpoint.

### Comment write-path rules (04 §42, T5.2, 03 §10)

`validate_reply_depth(comment)` enforces all three model-level rules from 04 §42's list, each with a distinct code:

```text
nested_reply            parent is itself a reply  (parent.parent_id is not None)   ← T5.2's exact rule
parent_post_mismatch    parent belongs to a different post
parent_deleted          parent is soft-deleted — a removed comment accepts no new replies
```

Resolved from ids (never by walking ancestors), so the check is O(1) and safe on unsaved instances. The remaining two rules from 04 §42 — *post is not locked* and *user has permission* — are **request-context** concerns and stay in 5.2's view; `Post.is_locked` ships here so the check has a field to read.

### Deletion semantics (D3/D4, 03 §20, 08 §390–§415)

- `soft_delete_post(post)` / `soft_delete_comment(comment)` flip `is_deleted = True` and save with `update_fields` (including `updated_at`). **Idempotent** — a second call is a no-op. **Never** deletes a row; reversal is literally `is_deleted = False` (08 §415's "Reversal of Errors"), documented in the docstrings so no later phase invents a hard-delete path.
- The original `title`/`body` stay untouched in the row (08 §390: preserved for audit/legal). Masking happens only in `tombstones.display_*`, which 5.2's serializers call.
- A tombstoned **comment** keeps its `parent_id`, so replies still resolve and the thread shape survives the flag flip (D4 / criterion 4). A tombstoned **post** keeps its comments — nothing cascades on a flag.

### File layout

```text
apps/community/
├── apps.py            # CommunityConfig + INSTALLED_APPS registration
├── models.py          # Post, Comment, PostVote (+ clean() mirroring the validators)
├── validators.py      # validators for category / blank content / reply depth
├── services.py        # create_post, create_comment, soft_delete_post, soft_delete_comment
├── tombstones.py      # TOMBSTONE_TEXT + display_title/display_body
├── migrations/0001_initial.py
└── tests/             # conftest + 5 files
```

## Stage 1 — Build & automated gate

**Gate:** full pytest green (319 pre-existing untouched) + `ruff check`/`format` clean + `makemigrations --check` clean *after* generating the new migration. No live drill until this passes.

### 1.1 App scaffold + settings
- New `apps/community/` per the layout above; add `"apps.community"` to `INSTALLED_APPS` (3.1/4.1 pattern). `POST_CATEGORIES` added to `config/settings/base.py`. No other settings changes.

### 1.2 `apps/community/models.py`
- **`Post`** (03 §9 + T5.1): `id` UUIDv4 PK; `author` FK(`AUTH_USER_MODEL`, `on_delete=PROTECT`, `related_name="community_posts"`); `title` CharField(200); `body` TextField; `category` CharField(20) + `validate_post_category` (no `choices`, per D1); `is_pinned`/`is_locked`/`is_deleted` BooleanField(default=False); `created_at`/`updated_at`.
  `Meta.ordering = ["-is_pinned", "-created_at"]`; indexes `idx_post_category_created (category, created_at)`, `idx_post_created (created_at)`, `idx_post_pinned_created (is_pinned, created_at)` (03 §17).
- **`Comment`** (03 §10 + T5.2): `id`; `post` FK(`Post`, `CASCADE`, `related_name="comments"`); `author` FK(`AUTH_USER_MODEL`, `PROTECT`, `related_name="community_comments"`); `parent` FK(`"self"`, `null=True, blank=True`, **`SET_NULL`**, `related_name="replies"` — P1); `body` TextField; `is_deleted` BooleanField(default=False); timestamps.
  `Meta.ordering = ["created_at"]`; indexes `idx_comment_post_created (post, created_at)`, `idx_comment_parent_created (parent, created_at)` (03 §17).
- **`PostVote`** (03 §11 + T5.3): `id`; `user` FK(`AUTH_USER_MODEL`, `CASCADE`, `related_name="post_votes"`); `post` FK(`Post`, `CASCADE`, `related_name="votes"`); `created_at`.
  `Meta.constraints = [UniqueConstraint(fields=["user", "post"], name="unique_user_post_vote")]` — **the phase's one hard database guarantee** (roadmap criterion 3). The FK also gives PostgreSQL an index on `post` for 5.2's `annotate(Count("votes"))`.
- `clean()` on `Post` and `Comment` runs the same validators (admin/forms get the rules too). **No `vote_count`/`comment_count` fields** (03 §9/§29/§30).
- Docstrings record the *asymmetry* plainly: votes are DB-enforced, depth is application-enforced because a cross-row rule cannot be a PostgreSQL `CHECK` (P4).

### 1.3 `apps/community/validators.py`
`validate_post_category(value)` (code `invalid_category`, reads the setting at call time); `validate_not_blank(value)` (code `blank_content`); `validate_title_length(value)` (code `title_too_long`, boundary 200/201); `validate_reply_depth(comment)` → the three codes above. All raise Django `ValidationError` (R4).

### 1.4 `apps/community/services.py`
- `InvalidPostError(ValueError)` / `InvalidCommentError(ValueError)`, each carrying `.code` (R4).
- `create_post(author, *, title, body, category) -> Post` — validates, then saves; the single post-write path (R1).
- `create_comment(post, author, *, body, parent=None) -> Comment` — validates depth + blank body, then saves; the single comment-write path (R1).
- `soft_delete_post(post)` / `soft_delete_comment(comment)` — see semantics above.
- No `@transaction.atomic` (each is a single-row write); no locked-post or permission logic (5.2's request context).

### 1.5 Migration
`0001_initial`: three tables, UUID PKs, the three FKs per §1.2, the five named indexes, and `unique_user_post_vote`. Names/columns confirmed in the file; DB-level verified in Stage 2.

### 1.6 Tests — `apps/community/tests/`

Conftest: local `make_user` (verified)/`make_post`/`make_comment`/`make_vote` helpers (apps' conftests are not shared — 3.2 precedent); `make_post` goes through `create_post` so tests exercise the real path, with a direct-ORM escape hatch for constraint tests.

| File | Proves |
|---|---|
| `test_community_models.py` (12) | UUIDv4 PKs auto-assigned on all three; boolean defaults (`is_pinned`/`is_locked`/`is_deleted` all False); `related_name`s (`post.comments`, `post.votes`, `user.community_posts`, `user.community_comments`); pinned Meta ordering for Post and Comment; all five named indexes present in `0001_initial` with the right columns; **no `vote_count`/`comment_count` fields exist** on `Post`; `author` is `PROTECT` — hard-deleting a user with content raises `ProtectedError` (D2's enforcement, not just its documentation); hard-deleting a post CASCADEs its comments and votes |
| `test_vote_constraint.py` (7) | **DB-level** duplicate rejection: a second `PostVote.objects.create` for the same `(user, post)` raises `IntegrityError` (inside `transaction.atomic()`, with the rollback asserted) — proving the guarantee is the database's, not a serializer's; two users may vote the same post; one user may vote two posts; constraint name is exactly `unique_user_post_vote`; soft-deleting a post does **not** delete its votes (rows retained); vote counts are derivable by `annotate(Count("votes"))` with no denormalized field |
| `test_reply_depth.py` (11) | Top-level comment accepted; a reply to a top-level comment accepted (depth 1); **reply-to-a-reply rejected** with code `nested_reply` and nothing persisted; parent from another post → `parent_post_mismatch`; parent soft-deleted → `parent_deleted`; a legal reply to a tombstoned *post*'s live comment still works (only the parent's state matters); `Comment.clean()`/`full_clean()` raises the same codes via admin/forms; depth check resolves ids (an unsaved reply whose parent is unsaved-but-top-level still validates); `parent.parent_id` is the only ancestor read (O(1), no walk); **SET_NULL promotion**: hard-deleting a parent promotes its reply to top-level with its body intact (P1 — content is never destroyed) |
| `test_deletion_semantics.py` (13) | `soft_delete_post` flips the flag and **retains title/body in the row** (08 §390 audit requirement, asserted by re-reading the raw field, not the masked one); idempotent (double delete is a no-op); `soft_delete_comment` the same; `display_title`/`display_body` mask only when deleted, and pass through untouched when not; the same for comments; a tombstoned comment keeps `parent_id` so its replies still resolve (criterion 4); a tombstoned post keeps its comments; **reversal restores display** (`is_deleted = False` — 08 §415); masked copy is exactly the `TOMBSTONE_TEXT` constant (D3) and makes no moderator claim; `Post.objects.count()` is unchanged by soft delete (no row is ever removed) |
| `test_validators.py` (9) | `validate_post_category` accepts every key in `POST_CATEGORIES`, rejects unknown/lowercase/blank with `invalid_category`; **`override_settings` extension applies without a migration** (01 §7's extensibility, proven at call time); blank and whitespace-only titles/bodies rejected with `blank_title`/`blank_body`; title boundary 200 accepted / 201 rejected with `title_too_long`; `create_post` surfaces the same codes as `InvalidPostError` (R4); `create_comment` surfaces `blank_body`; a whitespace-only body on a reply is rejected | 

### 1.7 Execution order (Stage 1)
1. 1.1 scaffold + settings → 1.2 models → 1.3 validators → 1.4 services → 1.5 `makemigrations community` + inspect
2. 1.6 tests → `docker compose run --rm web sh -c "pip install -q -r requirements-dev.txt && python -m pytest"`
3. **Gate:** pytest green · `ruff check apps config` · `ruff format --check apps config` · `makemigrations --check --dry-run`

## Stage 2 — Live verification round *(executed 2026-09-22: 23/23 checks green)*

- [x] Stack restart; `/health/` + `/health/ready/` 200 after boot
- [x] `community.0001_initial` applied (`showmigrations` shows `[X]`; it had already been applied
  by the entrypoint's migrate on the `docker compose run` invocations, confirmed rather than assumed)
- [x] DB-level schema proof via psql: all three tables, all five named indexes present
  (`idx_post_category_created`, `idx_post_created`, `idx_post_pinned_created`,
  `idx_comment_post_created`, `idx_comment_parent_created`), and
  `unique_user_post_vote UNIQUE CONSTRAINT, btree (user_id, post_id)` — the roadmap criterion
  proven at the layer that holds it
- [x] **ORM drill** (`manage.py shell`, 23 checks): `create_post` persists a UUIDv4 → blank title and
  unknown category rejected with stable codes → depth-1 reply accepted, **nested reply rejected with
  nothing persisted** → duplicate vote raises `IntegrityError` while a second user's vote succeeds and
  the aggregate count agrees → `soft_delete_comment` keeps the original body in the row while
  `display_body` masks it and the reply tree still resolves → `soft_delete_post` keeps its comments
  and votes → **hard-deleted parent promotes its reply with the body intact (SET_NULL)** → author
  deletion refused with `ProtectedError` (PROTECT) → post hard delete cascades comments + votes
  without raising on a two-level thread
- [x] Full pytest re-run green (**375 passed**, was 319); ruff check + format clean;
  `makemigrations --check` clean — **no further migration**, as planned
- [x] Prod compose validates (`docker compose --env-file .env.prod -f docker-compose.prod.yml
  config -q`, deploy-injected env interpolated from the shell); docs updated: `.planning/STATE.md`,
  `REQUIREMENTS.md` (COMM-03/04/05 → Complete + sub-phase row), `ROADMAP.md` (05-01 checked,
  Phase 5 → 1/3 In progress), PLAN gate checkboxes

## Out of scope (Phase 5.2+)

- Serializers, views, URLs, permissions, throttles, feed querysets, search, `?ordering=`, and the categories endpoint — plans 05-02/05-03 (T5.4–T5.13)
- **Recorded for 5.2 so nothing is lost:** 08 §406 renders a deleted post's author as `None`/unattributed — the author-nulling rule for *deleted posts* (and whether a tombstoned comment keeps its author handle) is a serializer decision in 5.2. `AuthorPublicSerializer` (3.2) is the only author shape to use.
- Rate limiting for post creation (5 posts/hour, T5.7); locked-post comment rejection (403 `POST_LOCKED`, T5.10); staff lock/pin endpoints (T5.12); notification hooks on comments/replies (Phase 6); `Announcement` (Phase 8, T8.6, same app); seed data (Phase 10)

## Security notes (ASVS L1)

- **Authorship is never client-supplied:** `author` is a required FK taken from the caller, never a request body (06 §4.5's rule, enforced at the model layer where it cannot be bypassed by a new endpoint).
- **Two different integrity guarantees, honestly labelled:** duplicate votes are impossible at the database level (criterion 3, `unique_user_post_vote`); the 1-level depth rule is application-level because PostgreSQL cannot express a cross-row `CHECK`. The plan's tests prove *both* claims separately rather than implying both are DB-enforced.
- **Deletion is a flag, never a destructive operation** — no model hook, cascade, or admin action in 5.1 physically removes community content, so moderation history and reply trees survive by construction (08 §390–§415).
- **Tombstones make no false claims** (D3): masking text is neutral for both removal paths, so the platform never tells a reader that a moderator acted when the author chose to delete, or vice versa.
- **Retained originals are a deliberate trade-off:** soft-deleted bodies stay readable to anyone with database or admin access (08 §390 requires this for audit/legal). Nothing in 5.1 exposes them through an API path; 5.2's serializers must always go through `tombstones.display_*`.
