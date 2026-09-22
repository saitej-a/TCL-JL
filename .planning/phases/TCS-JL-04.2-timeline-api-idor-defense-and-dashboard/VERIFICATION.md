# VERIFICATION 04-02 — Timeline API, IDOR Defense & Dashboard

**Phase:** 4.2 · **Verified:** 2026-09-22 · **Requirements:** TIME-03, TIME-04 (API half), TIME-05
**Verdict:** ✅ **PASS** — all four roadmap success criteria and both in-scope requirements hold under
independent adversarial probing. One **cross-phase defect** was found in the Phase 2.2 deletion
service (F1) that 4.2 inherits but does not cause; it blocks a 06 §4.2 compliance claim and inflates
the dashboard's community cohort.
**Verification is independent of execution:** a separate probe script (not the phase's own test
suite) attacked the running stack over real HTTP with real JWTs, and two controlled mutations
confirmed the IDOR tests are load-bearing rather than vacuous.

## Evidence sources

| Source | Scope | Result |
|---|---|---|
| Independent adversarial HTTP probe (`manage.py shell`, real JWTs, gunicorn via nginx) | 61 checks across C1–C4, TIME-02, D2/D3, privacy, pagination, surface, integration seam | **59 pass / 2 fail** (both F1) |
| Full automated suite `pytest` | 319 tests | **319 passed** (238 pre-existing + 81 new) |
| `ruff check` + `ruff format --check` | `apps/ config/` | clean (85 files) |
| `manage.py makemigrations --check --dry-run` | drift | No changes detected — **no migration**, as planned |
| Mutation probes (temporary, reverted) | test-suite strength | both mutations caught |

Probe method was deliberately harsher than the phase's own tests: it asserts *field-level* error
provenance (a rejected date must fail on `event_date`, never be confused with a status block),
compares **raw response bytes** across foreign vs nonexistent identifiers, and searches aggregate
payloads for other candidates' identifiers.

## Roadmap success criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Candidate can record milestones (Interview, Selection, Offer, Survey, JL, Date, Joined) with date and notes | ✅ PASS | All **8** types (incl. `OTHER`) returned 201 with the submitted `description` persisted |
| 2 | Recording a JL event atomically updates status in the same transaction | ✅ PASS | Seven-step API sequence kept status exactly on-mapping after every call; a late backward milestone returned `400 status_terminal` with the event count and the status both provably unchanged |
| 3 | Timeline queries scope to `request.user` and return 404 on unauthorized access | ✅ PASS | Foreign PATCH/DELETE → `404 timeline_event_not_found` with **byte-identical** bodies to a nonexistent UUID; `?event_type=` filter cannot widen scope; anonymous → 401, unverified → 403 |
| 4 | Dashboard aggregates status progression, latest milestone, community benchmarks | ✅ PASS | Exact 04 §28 keys; progression + latest milestone both present; benchmarks labeled `COMMUNITY_REPORTED`, suppressed below threshold, 11-key distribution, waiting total verified against a direct DB count |

## Requirements and decisions

| Item | Verdict | Notes |
|---|---|---|
| TIME-03 (IDOR 404) | ✅ Complete | Two independent layers proven separately: query scoping (8 checks) and `IsTimelineOwner` (4 unit checks) |
| TIME-04 (interactive roadmap) | ⚠️ **Partial, by plan** | API half complete (list/edit/delete own milestones); roadmap UI remains Phase 9.3 (UI-03) |
| TIME-05 (dashboard) | ✅ Complete | Includes the D1 placeholder `unread_notifications: 0` and the D2 suppressed benchmark block |
| TIME-02 (atomic sync) | ✅ Re-verified at the API | The 4.1 invariant holds through the HTTP layer, not just the service layer |
| D1 (dashboard key contract) | ✅ | All four top-level blocks present with the Phase-6 placeholder explicitly `0` |
| D2 (suppression + labeling) | ✅ | Mechanism asserted against the live cohort vs `ANALYTICS_MIN_COHORT_SIZE`; counts omitted (not zeroed) when suppressed; no individual identifiers or emails in the payload |
| D3 (date bounds) | ✅ | Exactly +730 days accepted, +731 rejected on `event_date`; 1999 rejected; future `JOINING_LETTER` rejected with the **carve-out** message (distinguishable from the horizon error); `JOINING_DATE` today and +6 months accepted |
| R4 (`auto_update_status` not client-controlled) | ✅ | `is_verified` and `candidate` in a body are both ignored on POST *and* PATCH; ownership/verification cannot be self-asserted |
| D2 forward-only | ✅ | Type edit syncs forward; deletion never regresses; a *backward* mapped edit persists the type while leaving status put; `OTHER` notes remain recordable even after `JOINED` |

## Test-suite strength (mutation evidence)

| Mutation | Expected | Observed |
|---|---|---|
| Removed `candidate__user=request.user` from both querysets | IDOR/scoping tests fail | **9 failed** — every foreign-access and cross-tenant test caught it |
| Removed `IsVerified` from the list + dashboard permission classes | unverified tests fail | **2 failed** — both `test_unverified_is_rejected` caught it |

Both mutations were reverted in the same command that applied them; the restored tree re-ran
**319 passed / ruff clean / no drift**. The IDOR tests are demonstrably load-bearing.

## Findings

### F1 — Account deletion does not cascade to the profile or its timeline events — **HIGH**

`apps/accounts/services.py::anonymize_delete_account` anonymizes the `User` row (unusable password,
`deleted_<uuid>@tracker.internal`, `is_active=False`) and stops there. It never deletes the
`CandidateProfile` or its `TimelineEvent` rows, which 06 §4.2 step 4 requires
("Delete CandidateProfile and private TimelineEvents (`CASCADE`)") and 06 §2.7 promises as
"Zero Orphaned PII". Verified empirically: after `anonymize_delete_account`, the profile row and its
milestone rows both survive, and the survived profile still carries `display_name`, `batch`,
`hiring_type`, `region`, and `current_status`.

This is a **Phase 2.2 defect**, not a 4.2 regression — 4.1's plan and 4.2's plan both *assumed* the
deletion flow was in place, and the FK is correctly `CASCADE` (nothing ever triggers it). 4.2 is
where the consequence becomes visible.

Blast radius: (a) private timeline events of deleted candidates are retained indefinitely;
(b) the public `/api/v1/candidates/{id}/` surface can still serve a deleted candidate's chosen
`display_name`; (c) the dashboard's community cohort counts deactivated accounts — observed
21 profiles of which 2 were anonymized. Aggregates are not individually identifying, so this is a
retention/accuracy defect rather than a disclosure one, but it undermines the deletion guarantee
the product makes to anxious candidates.

**Recommendation:** fix in a dedicated follow-up (delete the profile inside the same atomic
transaction, letting the FK cascade remove events), then extend 4.2's dashboard to exclude
`user__is_active=False` profiles — or document an explicit decision that anonymized profiles remain
part of the community cohort. Needs a user decision, since it edits a shipped phase's contract.

### F2 — Dashboard cohort counts deactivated/anonymized profiles — **MEDIUM**

Direct consequence of F1. `_analytics_block` uses `CandidateProfile.objects.count()` with no
`user__is_active` filter, so benchmarks include candidates who left and are used as the suppression
denominator. Fix once F1's disposition is decided.

### F3 — Malformed identifiers bypass the project error envelope — **LOW**

`GET /api/v1/timeline/not-a-uuid/` returns HTTP 404 with a **non-JSON** body: the route
(`<uuid:pk>`) never matches, so no view handles it and the DRF/accounts envelope never runs.
Independently, `?event_type=interview` (lowercase) returns 400 — filtering is case-sensitive against
the choice values. Neither leaks existence information, and the same property exists in 3.2's
`/candidates/<uuid:pk>/`. Worth one shared fix (a project-wide JSON 404 handler) or an explicit
acceptance note.

### F4 — 405 responses omit the `Allow` header — **LOW** *(code-level observation, not probed)*

The custom `http_method_not_allowed` raises `MethodNotAllowed` with an envelope body but no
`Allow` header, so RFC 9110's requirement to advertise permitted methods is unmet. No spec
requirement covers it; adding `headers={"Allow": "PATCH, DELETE"}` is a two-line improvement.

### F5 — `completion_percentage` treats `WITHDRAWN` as progress — **LOW** *(product call)*

The metric's "status advanced past REGISTERED" item fires for `WITHDRAWN`, so a candidate who left
the process scores **higher** than one who never began. Defensible (they did engage) but arguably
misleading on a completeness meter. A one-line change if the product intent is otherwise.

### F6 — Timeline writes are unthrottled — **LOW** *(accepted risk, by plan)*

04 §90 does not list timeline among throttled categories, and 4.2's plan recorded that explicitly, so
an authenticated candidate can POST milestones without bound. No abuse signal observed. Revisit in
Phase 8 (anti-spam) or Phase 10 (hardening) if it matters.

## Residual risk

- Suppression protects the *dashboard* cohort count, but the threshold is global: a batch/hiring-type
  breakdown with a cohort of 1 would leak — that breakdown is deliberately deferred to Phase 7,
  whose own suppression rules must apply the same floor per bucket, not just globally.
- `F1`/`F2` mean every community benchmark figure reported today is slightly inflated by
  deleted accounts. Acceptable for a pre-launch dataset; must be resolved before launch claims.
- The public candidate surface (3.2) inherits F1's `display_name` retention — outside 4.2's scope,
  but the finding should be carried to whichever phase fixes the deletion flow.

## Sign-off

4.2's deliverables meet their acceptance criteria with independently reproduced evidence, and no
finding originates in the code this phase added. **Not** closed on the strength of the phase's own
tests alone: the mutation probes and the adversarial probe are the basis for that claim.
