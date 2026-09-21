# Phase 3.2 — Discussion Record: Profile API & Privacy Boundaries

Date: 2026-09-21
Scope: Roadmap plan 03-02 (T3.4–T3.8) — `/api/v1/profile/` CRUD, public candidate endpoint,
private/public serializer segregation, impersonation blocker, pytest suite.
Requirements covered: PROF-04. (PROF-01..03 completed at the model layer in 3.1; this phase
makes them reachable through the API and adds the public redaction boundary.)

## Decisions locked (user)

- **D1 — POST honors a requested `current_status` via the transition chain, atomically.**
  Creation itself pins REGISTERED (machine default). If the request supplies
  `current_status != REGISTERED`, run `transition_status(REGISTERED → requested)` inside the
  creation transaction. Illegal edges — including 04 §20's own example body
  (`WAITING_FOR_JOINING_LETTER`) — yield a 400 field error on `current_status` with the
  machine's code, and the creation is rolled back: no profile survives a failed POST.
- **D2 — Public endpoint built now:** `GET /api/v1/candidates/{id}/` (04 §23), read-only,
  keyed by CandidateProfile UUID, returning exactly the §23 safe shape (id, resolved
  display_name, batch, hiring_type, region, current_status). `CandidatePublicSerializer`
  is the single redaction boundary; Phase 5 community feeds reuse it (and
  `AuthorPublicSerializer`) rather than re-deriving redaction.
- **D3 — Impersonation blocker: case-insensitive substring match.** Reserved tokens live in
  settings (`RESERVED_DISPLAY_NAME_TOKENS`, default: TCS, Tata, HR, Admin, Official,
  Moderator) so additions need no deploy. Substring match on the cleaned `display_name`
  blocks lookalikes (`TCSOfficial`, `hr_team`); rare false positives accepted.
  `display_name` is validated regardless of `public_identity_mode` — flipping to
  DISPLAY_NAME later cannot smuggle a reserved name past validation.
- **D4 — `DELETE /api/v1/profile/` → 405** with the project error envelope pointing to
  `DELETE /api/v1/account/` (04 §22's preferred MVP; account deletion owns profile removal
  via the 2.2 tombstone flow).

## Spec invariants carried (no decision)

- GET/PATCH response shapes exactly 04 §19/§21. PATCH: "only fields permitted for candidate
  self-editing may be changed" — `current_status` changes route through 3.1's
  `transition_status` (single mutation point; `InvalidTransitionError` → 400 with
  `status_terminal`/`status_invalid_transition`). Mixed PATCHes (fields + status) wrap the
  field save and the transition in one transaction so a rejected status leaves nothing saved.
  Phase 4.1 TIME-02 will wrap the same service atomically with timeline events.
- Profile create/update gated on **active + verified** users (tightens T3.4's
  "authenticated"; per 3.1 D4 note — tombstoned users never own profiles).
- Duplicate profile creation rejected (T3.4); `IsCandidateProfileOwner`-style ownership —
  the only private route is self (T3.5).
- Redaction zero-exposure set (04 §23 + 06 §5.3): email, phone, FCM token, password,
  private notes, internal moderation state — never in any public serializer.
- `AuthorPublicSerializer` per 06 §5.1/§5.2 shape (resolved display name via
  `candidate_profile`, batch/hiring_type/region) — user-sourced, defined in the candidates
  app so Phase 5 forum serializers import it from the profile domain.
- Batch validator + display resolver from 3.1 apply automatically; error style follows the
  2.2-established DRF field-error envelope.

## Open items for planning (non-blocking)

- Duplicate-creation status code: plan pins **409** with code `profile_exists` (vs generic
  400) — confirm at plan review.
- Public endpoint auth: default **AllowAny** (it serves only the community-safe §23 shape) —
  revisit at plan review if scraping concerns outweigh MVP simplicity.
- Accessor naming for `user.candidate_profile` with null profile in serializer contexts
  (reuse 3.1's `resolve_public_display_name`; no new logic).
