# VERIFICATION — Phase 8.2: Admin Triage & Ban Workflow

**Phase:** 8.2 · **Verified:** 2026-09-23 (round 2) · **Plan:** `08.2-01-PLAN.md` (7 tasks, wave 1)
**Requirements:** MOD-05, MOD-06 (+ T8.6/T8.7/T8.8/T8.10 deliverables)
**Verdict:** ✅ **PASS** — all seven plan tasks are built, every gate is green, and an independent
live drill against the running stack proves the phase's two asynchronous contracts actually complete
(**bans really do sever sessions and devices; announcement broadcasts really do fan out**) end-to-end
through the broker and the worker. No blocking findings. Five observations are recorded, none of which
contradicts a phase requirement.

**Verification is independent of execution.** Round 1 verified execution at 2 of 7 tasks and returned
FAIL; that record is superseded by this file (its findings F1–F5 are re-checked below and all closed).
This run re-derived the evidence from the tree as it stands rather than trusting the execution
summaries: the full suite, the CI-equivalent repo-wide lint, migration drift, and a purpose-written
live drill (`drill_08_02.py`) that drives the real URLconf, database, Redis broker and Celery worker —
plus the Django Admin over real HTTP sessions, which no pytest suite in this phase exercises.

## Evidence sources

| Source | Scope | Result |
|---|---|---|
| Live drill `drill_08_02.py` (real HTTP, real URLs, real broker→worker, real Admin sessions) | 8 sections: reporting, the five actions, ban/severing/reinstate, announcement lifecycle, reserved wiring, §107 names, Admin triage, cleanup | ✅ **58/58 checks passed**, 5 observations |
| Full suite `python -m pytest -q` | 788 tests | ✅ **788 passed**, 0 failed, 3 warnings |
| Lint `ruff check .` (CI's own command, repo-wide) | whole repo incl. `.planning/*.py` | ✅ All checks passed (182 files formatted) |
| Format `ruff format --check .` | whole repo | ✅ 182 files already formatted |
| `manage.py makemigrations --check --dry-run` | drift | ✅ No changes detected |
| `manage.py check` | system checks | ✅ No issues (0 silenced) |
| Worker liveness | `celery_worker` + `celery_beat` restarted to pick up the new task modules, then real `.delay()` dispatches observed completing | ✅ DB effects polled, not assumed |

The drill is deliberately **not** the phase's own suite: it asserts observable *effects* of asynchronous
work (device rows flipped inactive, `BlacklistedToken` rows appearing, `ANNOUNCEMENT` notifications for a
whole user set) by polling the database after a real dispatch, which is the only way to catch the F1/F2
class of defect the earlier run found.

## Round-1 findings — all closed

| # | Finding (round 1) | Status now | Evidence |
|---|---|---|---|
| F1 (HIGH) | No beat entry scheduled `auto_reinstate_users`, so temporary bans never lapsed back | ✅ **Closed** | `config/celery.py` carries `reinstate-suspended-users-hourly` (`crontab(minute=25)`) → `moderation.tasks.auto_reinstate_users`. Drill: a lapsed 7-day ban is reinstated by a **real dispatched task**; the beat-entry resolver confirms the name maps to real code. |
| F2 (HIGH) | Announcements unbuilt; two reserved wiring points dangled (beat `community.tasks.clean_expired_announcements`, route `notifications.tasks.broadcast_announcement`) | ✅ **Closed** | Both tasks exist at byte-exact reserved names; drill resolves every beat entry and route to real code **and** proves both run (broadcast fans out; expiry unpublishes). |
| F3 (HIGH, MOD-05) | No `ReportAdmin`, no staff-safe User ban action — a bare Admin `is_active` edit could suspend without audit or severing | ✅ **Closed** | `apps/moderation/admin.py` (five bulk actions) + `apps/accounts/admin.py` (`ban_selected_users`/`unban_selected_users`), all delegating to `moderation.services`. Drill drives the Admin actions **over HTTP**: dismiss → `DISMISSED`, soft-delete → tombstoned, ban → suspended **and** device severed by the worker. |
| F4 (MEDIUM) | §107 test names missing; no Celery wiring test | ✅ **Closed** | The three triage names exist verbatim (`test_admin_can_review_report`, `test_regular_user_cannot_review_report`, `test_remove_content`) and are asserted by the drill with exact `def name(` matching; `test_celery_wiring.py` resolves every beat/route entry. The four report-creation names remain 8.1-inherited (O2). |
| F5 (MEDIUM) | Async severing verified only by calling the task function directly | ✅ **Closed (live)** | Drill: `POST .../review/ {"action":"BAN_USER"}` → 202 → the **worker** (not the test) blacklists the outstanding token and deactivates the device. See O3 for the pytest-side guard. |

## Roadmap success criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Moderators triage reports from Django Admin with bulk actions | ✅ PASS | Admin changelist 200 for staff, 302 for anonymous and non-staff; `dismiss_reports` and `soft_delete_and_resolve` executed over HTTP redirect and land the DB writes; `ban_selected_users` suspends and severs. |
| 2 | Triage REST surface (§68 queue, §69 review, §70 ban/unban) | ✅ PASS | Queue: staff-only (candidate 403), §68 field shape exact (7 keys, no moderator-only leakage), severity-ordered (SCAM before OTHER), `?status=BOGUS` → 400 `invalid_filter`. Review: all five actions with correct transitions; `LOCK_POST` on a comment report → 400 with the report left PENDING. Ban/unban: candidate 403, staff-target 400, 202/200. |
| 3 | Five review actions behave per 08 §4.2 | ✅ PASS | DISMISS → `DISMISSED` + `reviewed_by`/`reviewed_at`/`moderator_notes` written; WARN_USER → `RESOLVED`, content untouched, author notified; REMOVE_CONTENT → comment tombstoned + notified; LOCK_POST → `is_locked` set; BAN_USER → `RESOLVED` + suspension. |
| 4 | "Banned accounts lose sessions and device alerts atomically" | ✅ PASS *(with §6's own semantics)* | The user-facing transaction is atomic: flag + `banned_until` + §11.1 log line commit together, and the drill confirms the device is **still** active immediately after that response (as D1 specifies). The worker then completes §6's step 3. A lapsed temporary ban auto-reinstates without reviving the device (D2/D3). |
| 5 | Suspended users are told, non-suspended wrong-password attempts are not | ✅ PASS | Correct password on a suspended account → 403 `ACCOUNT_SUSPENDED`; wrong password → generic 401 `INVALID_CREDENTIALS` (anti-enumeration preserved — the 403 requires proven ownership). |
| 6 | T8.6/T8.10 announcement system | ✅ PASS | Model + `publish()` (idempotent False→True; second publish 200 no-op), staff-only draft CRUD with anonymous public read of published non-expired rows (§72 fields only, pinned-first), draft/expired invisibility, expiry task unpublishes a lapsed row, in-app rows ungated while the push stays preference-gated (D7). |
| 7 | Reserved Celery names honoured (the 7.2 route-mismatch lesson) | ✅ PASS | Every beat entry and declared route resolves to real code; both byte-exact reserved names land on queues the worker consumes; the drill dispatches each task and observes its effect. |

## Requirements

| Item | Verdict | Notes |
|---|---|---|
| **MOD-05** (Admin review with bulk actions) | ✅ **Complete** | `ReportAdmin` ships `dismiss_reports` / `soft_delete_and_resolve` / `lock_posts` / `warn_users` / `ban_users` plus the staff-safe `UserAdmin` ban/unban actions; Admin and REST share one services layer (**verified live**: the Admin actions produce identical DB effects to the REST review path). |
| **MOD-06** (ban suspends, blacklists tokens, halts device alerts) | ✅ **Complete** | `is_active=False` + `banned_until` + audit line commit together; the idempotent sever task blacklists outstanding refresh tokens and deactivates devices **under real dispatch**; login gating and one-way unban verified. |
| T8.6 / T8.7 / T8.8 / T8.10 | ✅ Delivered | Announcement model/broadcast/expiry; five-action review; suspension protocol; broadcast task — each with live or suite evidence above. |

## Decisions D1–D9 — as built
Verified against `8.2-CONTEXT.md`: **D1** two-step ban (transaction then task, `on_commit` dispatch, 202) ·
**D2** idempotent severing, one-way unban (devices stay revoked — drill-asserted) · **D3** temporary bans
with `banned_until`, `duration_days`, hourly auto-reinstate · **D4** five actions, `DISMISSED` vs `RESOLVED`,
notes internal · **D5** one ban service for both entry points · **D6** static severity weights, velocity
multiplier diverged · **D7** full announcement scope, in-app ungated / push gated, byte-exact names ·
**D8** 04 §71–§75 surface · **D9** §11.1 structured logging only. All confirmed in code, tests and/or the drill.

## Observations (none blocks a requirement)

- **O1 (LOW, one-line decision):** `community.tasks.clean_expired_announcements` has **no explicit route**, so
  hourly housekeeping runs on `CELERY_TASK_DEFAULT_QUEUE` (`default`) while its three peers sit on
  `maintenance`. This is precisely what the plan specified (the reserved name left byte-identical) and it is
  harmless — the drill dispatches it and observes it complete — but 7.2 D-07's own rationale ("periodic work
  nobody is waiting on must not compete with request-driven work") argues for routing it. A one-line settings
  addition either way; recorded rather than changed during verification.
- **O2 (LOW, inherited from 8.1):** four of 04 §107's moderation test names are absent —
  `test_report_post`, `test_report_comment`, `test_report_requires_one_target`, `test_duplicate_report_behavior`.
  Their behavior is covered by differently-named tests in 8.1's suite (`test_report_post_created`,
  `test_report_comment_created`, `test_both_targets_rejected`, `test_duplicate_pending_report_returns_400`).
  8.2's plan scoped §107 to the three triage names, and those exist verbatim. If §107 is read as an exact-name
  contract, the fix belongs to 8.1's surface (thin aliases or renames).
- **O3 (LOW, regression guard):** no pytest test asserts `ban_user`'s `on_commit → .delay` dispatch — the phase
  suite invokes `sever_banned_user_sessions(...)` directly. The dispatch is proven end-to-end by this drill
  (stronger evidence than a mock), but a code change that silently dropped the dispatch hook would only be
  caught by re-running the drill. A `mock.patch` on the dispatch seam would move that guard into CI.
- **O4 (INFO):** `8.2-CONTEXT.md`'s D3 prose says `community.tasks.auto_reinstate_users`; what shipped (and what
  the plan, the route table and the beat entry all agree on) is `moderation.tasks.auto_reinstate_users` — the
  task lives in the app that owns the model it touches. CONTEXT typo only; no code impact.
- **O5 (INFO):** the ban migration shipped as `0005_user_banned_until` (the plan guessed `0002`; accounts already
  carried `0001`–`0004`). Announcements shipped as `community 0002_announcement`. Two migrations total, as planned.

## Residual risk

- **The accepted D1 window is real and stays:** a crash between the ban commit and the sever task leaves a
  suspended account with live sessions until retry. Re-banning is idempotent and re-fires it, and the API path
  is already closed at the flag, so the exposure is limited to token/device continuance — deliberately accepted
  by D1, not an oversight.
- **The drill is not wired into CI** (`.github/workflows/ci.yml` runs pytest + ruff only). The two asynchronous
  contracts are therefore guarded in CI by the byte-exact name wiring test, not by the live probe. Re-run the
  drill manually after touching moderation/announcement async paths.
- **Unrelated and unchanged by this phase:** Phase 5's two HIGH defects and the `anonymize_delete_account`
  device-revocation placeholder remain live in the tree (STATE.md Pending Todos). They are adjacent to this
  phase's device-severing primitive but were explicitly out of 8.2's scope by user decision.

## Sign-off

Phase 8.2 is **verified**. The ban protocol's two-step contract holds under a real broker and worker, the
triage surface (REST *and* Django Admin) writes through one service layer that neither path can drift from,
and the announcement system that 6.2 deferred is live at its reserved names. `.planning/REQUIREMENTS.md`
(MOD-05/MOD-06) and `.planning/ROADMAP.md` (plan 08-03) may now carry the phase's completion, with the
O1–O3 observations tracked rather than silently dropped.

**No code was changed by this verification** — the drill, which is verification-only tooling, is the only file
it added.
