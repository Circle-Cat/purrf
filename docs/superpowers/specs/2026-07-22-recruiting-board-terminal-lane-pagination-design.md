# Recruiting board — terminal-lane pagination

**Date:** 2026-07-22
**Ticket:** PUR-505 (recruiting)
**Status:** Design in review (incorporates independent review round 1)

## 1. Problem & scope

`GET /recruiting/jobs/{job_id}/board` (`BoardService.get_board`) loads a job's
**latest application per user** with no limit — `ApplicationRepository.list_by_job`
is an unbounded `SELECT` joined to `users`, and the response returns every card
grouped by stage in one payload. The frontend Kanban (`BoardPage.jsx`) renders
one lane per pipeline stage plus two terminal lanes (`hired`, `rejected`).

The terminal lanes `rejected` and `hired` are **append-only** — they only grow.
Active pipeline stages (`recruiter_screening`, `tech`, …) are bounded by how
many applicants are concurrently in flight, so they stay small. As a job
accumulates history, the terminal lanes dominate the query, the payload, and the
render.

**In scope:** keep the Kanban layout; active stages stay full-load; the terminal
lanes (`rejected`, `hired`) return a first page of N cards + a total, with a
"Load more" control at the bottom of the lane that pages through the rest via
offset/limit.

**Out of scope (YAGNI):** paginating active stages; cursor/keyset pagination
(the real fix for paging drift — see §7); frontend virtualization; search/filter
within the terminal lanes.

## 2. Key decisions

- **Terminal lanes handled symmetrically.** `rejected` and `hired` use the exact
  same mechanism — same endpoint, same ordering, same page size. When a lane has
  few cards, `has_more` is `false` and the "Load more" button does not render, so
  the lane looks identical to today. This avoids a special-case branch for
  `hired` (which is smaller but still unbounded).
- **Pagination is offset/limit + total**, matching the existing codebase
  convention (`notification_repository`, `users_repository` search). No
  cursor/keyset — terminal-lane paging depth is bounded in practice, and offset
  is fast enough at that depth. Accepted tradeoff: paging drift (§7, mitigated by
  frontend dedupe).
- **Terminal lanes are ordered by stage-entry time, newest-first**
  (`stage_entered_at DESC, application_id DESC` as a stable tiebreaker) — the
  moment the application entered `rejected` / `hired`, most recent at the top.
  **Active stages keep `application_id ASC`** ("first applied, first handled"),
  unchanged from today.
- **New column `application.stage_entered_at`** is the single source of truth for
  that ordering — the timestamp the application entered its *current* stage.
  Added `NOT NULL` **with `server_default=func.now()`** so every INSERT path
  (including grandfather scripts, §3) is safe; stage-*change* UPDATE sites set it
  explicitly to `now()`. **No historical backfill** — the feature is not
  launched, so existing rows simply get the migration-time `now()` via the
  server default; terminal-lane ordering of pre-existing rows is not
  meaningful and isn't a design concern (§3). `updated_timestamp`
  is unusable here: later non-stage writes (e.g. a blacklist tag backfill) move it
  and would corrupt the order. Deriving the time from `application_activity` at
  query time was rejected — it can't use a plain index and works against the goal
  of scaling the terminal lanes.
- **Page size N = 20** (matches `notification_repository` default), clamped to a
  max (≤ 100) on the endpoint.
- **The board response structure changes (breaking).** The board endpoint has a
  single verified consumer (`BoardPage.jsx`, no frontend test references it), so
  the response is restructured directly with no backward-compat shim.
- **"Latest application per user" semantics are preserved** everywhere — both the
  active-stage query and the terminal-lane page query build on the existing
  `max(application_id) GROUP BY user_id` subquery, with the `stage` filter applied
  in the **outer** query (§4.1). The board never shows a prior rejected attempt of
  a user who has since re-applied.

## 3. Schema change (Alembic)

Add `application.stage_entered_at` (`TIMESTAMP WITH TIME ZONE`, `NOT NULL`,
`server_default=func.now()`). Follow the standard flow: `tools/make_migration` →
review the generated revision → `tools/migrate_db`.

**Write sites** — set `stage_entered_at = now()` wherever `application.stage` is
assigned. All six in the codebase (the first four are runtime paths; the last two
are the grandfather backfill script):

1. `ApplicationService.submit` — row creation (`application_service.py:307`);
   equals `created_datetime`, and correctly reflects an auto-screen straight into
   `rejected`/`hired`. (INSERT — covered by `server_default`, but set explicitly.)
2. `BoardService.change_stage` (`board_service.py:992`) — manual advance/reject/hire. (UPDATE — must set explicitly.)
3. `BoardService` single blacklist (`board_service.py:1406`). (UPDATE — set explicitly.)
4. `BoardService` blacklist sweep (`board_service.py:1444`). (UPDATE — set explicitly.)
5. `backfill_activity_application_gate.py:69` — promote existing app to HIRED
   (UPDATE, writes no activity). Must set `stage_entered_at=now()` explicitly.
6. `backfill_activity_application_gate.py:82` — INSERT new HIRED row. `server_default`
   covers it, but set explicitly for clarity.

**No historical backfill.** The column is added in one step —
`NOT NULL` with `server_default=func.now()` — so Postgres populates every
existing row with the migration-time `now()` in the same statement that adds
the column; there is no separate backfill UPDATE. This is a deliberate
simplification: the feature is not launched, so there is no real traffic to
preserve accurate history for, and terminal-lane ordering of pre-existing rows
is not meaningful. Going forward, the runtime write sites above are what make
the column trustworthy for newly-created and newly-transitioned rows.

**Index:** `(job_id, stage, stage_entered_at DESC, application_id DESC)` on
`application`, covering the terminal page's `WHERE job_id=? AND stage=?` +
`ORDER BY stage_entered_at DESC, application_id DESC`.

**Performance caveat to validate.** The terminal page/count queries still wrap the
`max(application_id) GROUP BY user_id` latest-per-user subquery, which aggregates
**all** of a job's applications on every request — cost is O(all apps for the job),
not O(page); the index above does not fix that. Consider a supporting index
`(job_id, user_id, application_id)` for the subquery, and **validate the final plan
with `EXPLAIN` on realistic data** (confirm no extra Sort node) before assuming the
scaling win.

## 4. Backend

### 4.1 Repository (`backend/repository/application_repository.py`)

All build on the existing latest-per-user subquery; the `stage` filter goes in the
**outer** query, never inside the subquery.

- `list_by_job(session, job_id, exclude_stages=None)` — existing method gains an
  `exclude_stages` param. `get_board` passes `{REJECTED, HIRED}` so the main query
  returns only active-stage cards. `ORDER BY application_id ASC` unchanged.
- `list_by_job_and_stage(session, job_id, stage, limit, offset)` — latest app per
  user, filtered to one stage, newest-entry-first:
  ```sql
  SELECT application.*, users.*
  FROM application JOIN users ON users.user_id = application.user_id
  WHERE application.job_id = :job_id
    AND application.stage = :stage
    AND application.application_id IN (
      SELECT max(application_id) FROM application
      WHERE job_id = :job_id GROUP BY user_id)
  ORDER BY application.stage_entered_at DESC, application.application_id DESC
  LIMIT :limit OFFSET :offset
  ```
  Returns `list[tuple[ApplicationEntity, UsersEntity]]`.
- **`count_latest_by_job_and_stage(session, job_id, stage) -> int`** — count using
  the *identical* WHERE (outer `stage` filter + latest-per-user subquery), so
  `total` matches what `items` would enumerate. **New name deliberately avoids the
  existing `count_by_job_and_stage`** (`application_repository.py:77`, used by
  `audit_service.py:60` — a `GROUP BY stage` with no latest-per-user semantics; do
  not reuse or shadow it).

### 4.2 Service (`backend/recruiting/board_service.py`)

- `get_board` — active stages via `list_by_job(..., exclude_stages={REJECTED, HIRED})`,
  full-load. For each terminal stage, fetch the first N via
  `list_by_job_and_stage(..., limit=N, offset=0)` plus `count_latest_by_job_and_stage`.
  The existing batched resolution (assignments, reviewer names, contact emails) is
  applied across all cards being returned (active + terminal first page).
- `get_board_stage_page(session, current_user, job_id, stage, limit, offset)` — new.
  Same owner authorization as `get_board` (`_require_owner(..., allow_read_all=True)`);
  maps the page's rows to `BoardCardDto`s via the same batched helpers. Returns
  items + total + has_more.

### 4.3 Controller / endpoint (`backend/recruiting/board_controller.py`)

- New route: `GET /recruiting/jobs/{job_id}/board/applications?stage={stage}&limit={limit}&offset={offset}`
  → `{ "items": BoardCardDto[], "total": int, "has_more": bool }`.
- `limit` defaults to 20, clamped to ≤ 100; `offset` defaults to 0, must be ≥ 0.
- Invalid `stage` (not a valid `ApplicationStage`) or out-of-range params → 400.
- Non-owner → existing 403 path via `_require_owner`.

## 5. Board response structure (breaking change)

Today: `dict[str, list[BoardCardDto]]` — no room for `total`/`has_more`.

New shape wraps each stage:

```jsonc
{
  "stages": {
    "recruiter_screening": { "items": [/* all */], "total": 12,   "has_more": false },
    "tech":                { "items": [/* all */], "total": 3,    "has_more": false },
    "rejected":            { "items": [/* first N */], "total": 1240, "has_more": true  },
    "hired":               { "items": [/* first N */], "total": 84,   "has_more": true  }
  }
}
```

- Every stage uses the same object shape. Active stages always have
  `has_more == false` and `total == len(items)` — the frontend does not branch on
  stage type.
- Stages with zero cards remain absent keys; the frontend keeps its
  `.get(stage, default)` pattern, adapted to the new shape.

## 6. Frontend (`frontend/src/pages/Recruiting/board/BoardPage.jsx`)

- `loadBoard` adapts to the wrapped shape: `board.stages[lane.stage]?.items ?? []`;
  store `total` and `has_more` per lane.
- Terminal lanes render a "Load more" button when `has_more` is true. Clicking
  calls the new endpoint with the next `offset` (current loaded count) and appends
  the returned cards, **deduping by `application_id`** so paging drift (§7) can't
  render the same card twice. Lane header shows the count, e.g. `Rejected (1240)`.
- The existing round-shrink filter (`BoardPage.jsx:196`) and other lane logic are
  preserved.
- Add `RECRUITING_JOB_BOARD_STAGE` endpoint constant
  (`frontend/src/constants/ApiEndpoints.js`) and an api function alongside
  `getJobBoard`.

## 7. Known limitations (accepted)

- **Paging drift.** With `stage_entered_at DESC` (newest at top) + offset paging, a
  new terminal-lane entry during a browsing session inserts at the head and shifts
  the window, so a later "Load more" at `offset = loadedCount` can re-return
  already-seen rows. Terminal lanes are low-churn and append-only, so this is rare;
  the frontend dedupes by `application_id` (§6) to keep it harmless. A keyset cursor
  is the real fix and is intentionally out of scope.
- **count/page snapshot skew.** `total` and the page are separate statements; under
  READ COMMITTED a commit landing between them can make `total`/`has_more`
  transiently off by one. Cosmetic; accepted (can be tightened to one
  repeatable-read transaction if it ever matters).

## 8. Error handling & testing

**Error handling**

- Invalid `stage` / out-of-range `limit`/`offset` → 400 (validated in controller).
- Non-owner caller → 403 (existing `_require_owner` path).
- Frontend: a failed "Load more" surfaces a toast and leaves already-loaded cards
  intact (does not clear the lane).

**Tests**

- Migration (DB-backed): inserting an `application` row without specifying
  `stage_entered_at` gets the `server_default` (`now()`); the
  `ix_application_job_stage_entered` index exists.
- Repository: `list_by_job_and_stage` ordering (`stage_entered_at DESC`, id
  tiebreaker), limit/offset windows, **latest-per-user with outer stage filter** (a
  user whose latest app is active but who has an older rejected row does NOT appear
  in the rejected lane; `total` from `count_latest_by_job_and_stage` matches
  `items`), `list_by_job(exclude_stages=...)` excludes terminal stages. A regression
  asserting the existing `count_by_job_and_stage` (audit) still resolves to the
  4-arg version. DB-backed tests use the Neon test `DATABASE_URL`.
- Service: owner authorization on `get_board_stage_page`; `get_board` returns active
  stages full + terminal first page of N + correct `total`/`has_more`; every
  stage-write path (incl. the two blacklist paths) sets `stage_entered_at`.
- Controller: param validation (bad stage, negative offset, limit clamp), response
  shape.
- Frontend (`//tests/frontend_test:frontend_unit_tests`): terminal lane renders
  first page + count; "Load more" appends the next page and dedupes by
  `application_id`; button hidden when `has_more` is false; failed load keeps
  existing cards + shows toast.

## 9. Migration / rollout

One Alembic migration (add column `NOT NULL` with `server_default` + index, no
backfill; §3). Backend and frontend ship together because the board response shape
changes; the board endpoint has a single frontend consumer, so there is no external
contract to version. Deploy runs the migration before the new code (migrate-before-deploy
convention).
