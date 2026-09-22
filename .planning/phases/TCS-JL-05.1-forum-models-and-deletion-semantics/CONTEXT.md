# Phase 5.1 — Discussion Record: Forum Models & Deletion Semantics

Date: 2026-09-22
Scope: Roadmap plan 05-01 (T5.1–T5.3) — model layer only: `Post`, `Comment`, and
`PostVote` in a new `apps/community` app, with soft-deletion semantics, strict
1-level reply validation, and the `UNIQUE(user, post)` vote constraint.
Feed/search endpoints are Phase 5.2 (05-02, 05-03). Requirements covered:
COMM-03, COMM-04, COMM-05.

## Decisions locked (user)

- **D1 — Categories: the merged union of all three spec lists, settings-driven.**
  Three documents define post categories and none agree: 01 §7 (product, 9 —
  GENERAL, JOINING_LETTER, OFFER_LETTER, JOINING_DATE, LOCATION, INTERVIEW,
  DOCUMENTS, DISCUSSION, OTHER) and 03 §9 + T5.1 (10 — the same set minus
  LOCATION/DOCUMENTS, plus TCS_PROCESS, HELP, ANNOUNCEMENT). The union ships as
  **12 categories**, with `OFFER` folded into `OFFER_LETTER` (01 §7's product
  name, and the spelling `TimelineEvent` already uses — cross-feature vocabulary
  consistency matters because Phase 7 analytics will filter both):

  ```text
  GENERAL, JOINING_LETTER, OFFER_LETTER, JOINING_DATE, LOCATION, INTERVIEW,
  DOCUMENTS, DISCUSSION, TCS_PROCESS, HELP, ANNOUNCEMENT, OTHER
  ```

  Held in settings like `BATCH_YEARS`/`RESERVED_DISPLAY_NAME_TOKENS`, so 01 §7's
  "categories should be extensible" is satisfied without a deploy.
  *Carried caution:* because `ANNOUNCEMENT` is user-selectable, a candidate can
  post a self-labeled announcement, which brushes against 01 §1007's "never
  presented as official TCS information" and §14's rule that announcements are
  admin-controlled and must be clearly distinguishable. Removing it later is a
  one-line settings edit with no migration — that flexibility is part of why this
  decision was made this way. Announcement *the model* is Phase 8 (T8.6).
- **D2 — `author` stays required and is never nulled; the retained anonymized
  user row is the tombstone.** 06 §4.2 step 5's "set author to NULL or a
  designated Deleted Candidate" is satisfied by the *second* clause: 2.2 anonymizes
  the User row (`deleted_<uuid>@tracker.internal`, unusable password,
  `is_active=False`) and never deletes it, and 3.2's shipped
  `AuthorPublicSerializer` + redaction tests already render exactly that row as
  anonymous with no email. Consequence: no serializer, `select_related`, or
  `annotate` path anywhere in the project needs a NULL-author branch, and
  moderation/audit can still attribute content. The FK is declared `PROTECT` so
  the no-hard-delete assumption is enforced rather than merely documented.
  *Cross-link to F1 (4.2 verification):* this makes the F1 fix a **profile**
  deletion, not a user deletion — coherent, and a hard user delete would now be
  refused rather than silently destroying attribution.
- **D3 — One neutral tombstone copy for both removal paths.** COMM-05 lets authors
  *and* moderators soft-delete, but the schema has a single `is_deleted` flag, so
  the flag cannot distinguish them. 08 §406 mandates
  "[This post has been removed by a moderator]" while 03 §20 offers the neutral
  "This content has been removed." — the neutral wording ships for **both** posts
  and comments, so an author's own deletion never displays a false moderation
  claim and a moderator's action never masquerades as the author's choice. The
  original title/body stay in the row (08 §390: "Preserved for audit/legal");
  masking is a display concern, and Phase 8 owns moderator-specific messaging.
- **D4 — Soft-deleted posts leave the feed; direct detail returns a masked
  tombstone.** 03 §28's feed query is explicit (`filter(is_deleted=False)`), and a
  removed post should not consume feed space or push live content down. Roadmap
  success criterion 4 ("soft-deleted content displays clean tombstones without
  breaking reply hierarchies") is satisfied by the parts that *are* trees —
  tombstoned **comments stay in their thread** so replies keep their parent — plus
  04 T5.8's masked detail response, which is why detail returns 200-with-tombstone
  rather than 404.

## Planner resolutions (pinned here; veto at plan review)

- **P1 — `Comment.parent` is `null=True, blank=True, on_delete=SET_NULL`,
  `related_name="replies"`.** 03 §19 specifies `Post → Comment` CASCADE but is
  silent on the self-FK, and soft delete is the only removal path this project
  has, so this only matters if something hard-deletes a comment by accident.
  SET_NULL is chosen because it **never destroys content**: a reply whose parent
  vanished is promoted to a top-level comment instead of being wiped. `PROTECT`
  was rejected as actively harmful here — combined with `Post → Comment` CASCADE
  it would raise `ProtectedError` and make hard-deleting a post impossible
  whenever a thread had two levels.
- **P2 — `User → PostVote` is CASCADE** (03 §19): votes are aggregates with no
  audit value, and 2.2 never hard-deletes users anyway.
- **P3 — Indexes exactly per 03 §17, repo naming style:** `idx_post_category_created`,
  `idx_post_created`, `idx_post_pinned_created`, `idx_comment_post_created`,
  `idx_comment_parent_created`. **No denormalized `vote_count`/`comment_count`
  columns** (03 §9, §29, §30) — Phase 5.2 aggregates with `annotate()`.
- **P4 — The 1-level reply rule cannot be a database constraint.** "No nested
  replies" is a **cross-row** invariant (`parent.parent IS NOT NULL`), and
  PostgreSQL `CHECK` constraints cannot see another row; Django has no
  `UniqueConstraint`-style expression for it either. So it is enforced in the
  model's `clean()` plus a reusable validator that 5.2's serializer calls — and
  the plan must state plainly that the vote rule has a **hard DB guarantee** while
  the depth rule has an application-level one, rather than implying both are
  database-enforced (03 §38 says exactly this; §39's "database is the final
  integrity boundary" claim is therefore qualified for this one rule).
- **P5 — Repo-convention vocabularies:** `category` is a `CharField` +
  settings-reading validator (3.1 D3's `BATCH_YEARS` pattern) rather than Django
  `choices`, so extending the list never produces a migration. Labels for 5.2's
  categories endpoint come from the same settings structure.
- **P6 — New `apps/community` app owns exactly the three models.** `Announcement`
  lands here in Phase 8 (T8.6) — not 5.1.

## Spec invariants carried (no decision)

- **Fields exactly per 03 §9/§10/§11 + T5.1–T5.3.** `Post`: `id` (UUIDv4 PK),
  `author`, `title`, `body`, `category`, `is_pinned`, `is_locked`, `is_deleted`,
  `created_at`, `updated_at`. `Comment`: `id`, `post`, `author`, `parent`
  (nullable), `body`, `is_deleted`, timestamps. `PostVote`: `id`, `user`, `post`,
  `created_at`.
- **UUIDv4 primary keys** on all three (03 §18).
- **`UNIQUE(user, post)` on `PostVote`** (03 §11, §38; T5.3) as a named
  `UniqueConstraint` — duplicate votes must be impossible at the database level,
  not merely rejected by a serializer (roadmap criterion 3).
- **Soft delete only, no hard deletes in 5.1's code paths** (03 §20, 08 §390).
  Rows are retained; the flag is flipped. Deletion is reversible (`is_deleted =
  False` restores content — 08 §415).
- **Strict 1-level replies** (03 §10, §38; T5.2): a reply's parent must be a
  top-level comment.
- **No API surface in this phase** — no serializers, views, URLs, permissions,
  rate limits, or querysets (all 5.2). Tombstone rendering *helpers* ship here so
  5.2 has a single copy source instead of inventing a second wording.

## Inputs already in place

- 3.2's `AuthorPublicSerializer` in `apps/candidates/serializers.py` — the single
  community-facing author shape (D2 depends on it), with redaction tests already
  covering the anonymized-user and profile-less-user cases.
- 2.2's `anonymize_delete_account`: retains the User row as the tombstone seam
  (D2's foundation).
- Repo conventions to reuse verbatim: settings-driven vocabularies read at call
  time (3.1 D3), app registration pattern (3.1/4.1), named compound indexes with
  descending support (4.1), and the Stage 1/Stage 2 gate discipline.
- 319-test green suite, ruff gates, and migration-drift checks from Phases 1–4.2.
- F1 from the 4.2 verification is **open**: account deletion does not yet delete
  the `CandidateProfile` or its timeline events. D2 above is compatible with
  fixing it by deleting profiles.

## Open items for planning (5.1 PLAN.md)

1. Where the depth check actually runs on the write path once 5.2 exists
   (`Model.clean()` is not called by `save()`): planner pins whether 5.1 ships a
   service-level guard or leaves the call site to 5.2, without letting the rule
   go unenforced in between.
2. Whether tombstone helpers are model methods (e.g. `post.display_title`) or pure
   module functions in a small `tombstones.py` — planner pins, avoiding
   overbuilding a display concern inside the model.
3. Field shape details the specs leave open: `title`/`body` `max_length` (03 §9
   just says "String, Required"), whether whitespace-only titles/bodies are
   rejected, and `Comment`/`Post` `Meta.ordering` (needed for 5.2's stable
   pagination).
4. Test matrix: unique-constraint enforcement at the DB level (including the
   `IntegrityError` path, not just serializer validation), depth validator for
   legal/illegal/nested-reply-parent cases, soft-delete masking helpers, row
   retention after soft delete, cascade behaviour on post hard-delete, `SET_NULL`
   promotion of a reply whose parent is hard-deleted, category validator against
   the settings list, and index presence verified in the generated migration.
