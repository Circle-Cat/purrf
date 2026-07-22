# Recruiting Board Terminal-Lane Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paginate the recruiting board's append-only terminal lanes (`hired`, `rejected`) so the board stops loading every application at once as data grows.

**Architecture:** Active pipeline stages keep loading in full; the two terminal lanes return a first page of N cards + a total from the main board endpoint, and a new per-stage endpoint serves subsequent pages via offset/limit ordered by a new `application.stage_entered_at` column (newest-entry first). The board response is restructured to carry `{items, total, has_more}` per stage. The frontend renders a "Load more" button on terminal lanes and dedupes appended cards.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy async / Alembic / PostgreSQL (Neon); React (JSX) / Tailwind / Vitest; Bazel test; pytest.

## Global Constraints

- **Migrations use Alembic only:** `tools/make_migration` → review the generated revision → `tools/migrate_db`. Never `init_db` on a populated DB. (See spec §3.)
- **DB-backed backend tests** run against the Neon test DB; pass the URL through: `bazel test <target> --test_env=DATABASE_URL --test_output=errors` with `DATABASE_URL` exported to the test DB.
- **Backend test target** = file name without `.py`, e.g. `//tests/backend_test/repository_test:application_repository_test`. Each new `*_test.py` needs a `py_test` entry in its directory `BUILD` **and** must call `unittest.main()` at the bottom (a py_test without it silently runs 0 tests and PASSES).
- **Frontend tests:** `bazel test //tests/frontend_test:frontend_unit_tests`. Frontend uses **pnpm** (not npm). New styling uses **Tailwind utilities**, never `.css`. All user-facing strings are **English**.
- **Lint once, at the very end** (after all tasks): `bash lint.sh --fix all_files` (CI gates on prettier). Do not lint per-task.
- **Commits:** title format `[PUR-505] Capitalized message`, charset `[a-zA-Z0-9_. -]` only. End every commit message body with:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- **Never push / rebase / open a PR** — Yuji controls that. Commit locally only.
- **Terminal stages** are exactly `hired` and `rejected`. `BLACKLISTED` is a valid enum value but is never assigned as a row's stage (blacklist sets `REJECTED` + a `tags["blacklisted"]` flag).
- Page size **N = 20**, endpoint `limit` clamped to `≤ 100`, `offset ≥ 0`.

## File Structure

- `backend/entity/application_entity.py` — **modify**: add `stage_entered_at` column.
- `backend/recruiting/board_service.py` — **modify**: set `stage_entered_at` on 3 UPDATE stage-writes; rewrite `get_board`; add `get_board_stage_page`.
- `backend/recruiting/application_service.py` — **modify**: set `stage_entered_at` on the submit INSERT.
- `backend/backfill/backfill_activity_application_gate.py` — **modify**: set `stage_entered_at` on the promote UPDATE.
- `alembic_setup/versions/<rev>_add_stage_entered_at_to_application.py` — **create**: column (NOT NULL + server_default now()) + index. No backfill.
- `backend/repository/application_repository.py` — **modify**: `list_by_job(exclude_stages=)`; add `list_by_job_and_stage`, `count_latest_by_job_and_stage`.
- `backend/dto/board_dto.py` — **modify**: add `BoardStageDto`, `BoardStagePageDto`.
- `backend/common/api_endpoints.py` — **modify**: add `RECRUITING_JOB_BOARD_STAGE_ENDPOINT`.
- `backend/recruiting/board_controller.py` — **modify**: add the per-stage page route.
- `frontend/src/constants/ApiEndpoints.js` — **modify**: add `RECRUITING_JOB_BOARD_STAGE`.
- `frontend/src/api/recruitingApi.js` — **modify**: add `getJobBoardStagePage`.
- `frontend/src/pages/Recruiting/board/BoardPage.jsx` — **modify**: adapt to wrapped shape + "Load more" + dedupe.
- Tests: `application_repository_test.py`, `board_service_test.py`, `board_controller_test.py` (all exist — extend), plus a new migration test and BoardPage frontend test.

---

### Task 1: Add `stage_entered_at` column and set it on every stage-write

**Files:**
- Modify: `backend/entity/application_entity.py`
- Modify: `backend/recruiting/board_service.py` (change_stage ~`:992`; single blacklist ~`:1406`; sweep ~`:1444`)
- Modify: `backend/recruiting/application_service.py` (submit create ~`:307`)
- Modify: `backend/backfill/backfill_activity_application_gate.py` (`:69` promote; `:82` insert)
- Test: `tests/backend_test/recruiting_test/board_service_test.py`

**Interfaces:**
- Produces: `ApplicationEntity.stage_entered_at: datetime` (NOT NULL, `server_default=func.now()`), set to `datetime.now(timezone.utc)` at every runtime stage assignment.

- [ ] **Step 1: Add the column to the entity**

In `backend/entity/application_entity.py`, after the `current_round` column block (before `tags`), add:

```python
    # Timestamp the application entered its CURRENT stage. Single source of
    # truth for terminal-lane (rejected/hired) ordering, which needs "most
    # recently rejected/hired first" and cannot rely on updated_timestamp
    # (later non-stage writes, e.g. a blacklist tag backfill, would move it).
    # server_default covers INSERT paths; stage-change UPDATEs set it explicitly.
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

(`datetime`, `DateTime`, `func` are already imported in this file.)

- [ ] **Step 2: Write the failing test for the stage-write paths**

In `tests/backend_test/recruiting_test/board_service_test.py`, add a test that a stage change sets `stage_entered_at`. Follow the file's existing fixture/mock style for building a `BoardService` with mocked repositories; the assertion is what matters:

```python
async def test_change_stage_sets_stage_entered_at(self):
    service, mocks = self._build_service()  # existing helper style in this file
    app = self._application(stage=ApplicationStage.RECRUITER_SCREENING)
    mocks.application_repository.get_by_id.return_value = app
    # ... existing owner/job setup so change_stage reaches the stage assignment ...
    before = datetime.now(timezone.utc)
    await service.change_stage(session, owner_user, app.application_id,
                               StageChangeDto(to_stage=ApplicationStage.HIRED))
    saved = mocks.application_repository.update.call_args.args[1]
    self.assertIsNotNone(saved.stage_entered_at)
    self.assertGreaterEqual(saved.stage_entered_at, before)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_service_test --test_env=DATABASE_URL --test_output=errors`
Expected: FAIL — `saved.stage_entered_at` is `None` (not set yet).

- [ ] **Step 4: Set `stage_entered_at` at each runtime stage-write**

In `backend/recruiting/board_service.py`:

`change_stage` — right after `application.stage = dto.to_stage` (currently `:992`):
```python
        application.stage = dto.to_stage
        application.stage_entered_at = datetime.now(timezone.utc)
```

Single blacklist — after `application.stage = ApplicationStage.REJECTED` (`:1406`):
```python
        application.stage = ApplicationStage.REJECTED
        application.stage_entered_at = datetime.now(timezone.utc)
```

Sweep — inside the `if locked.stage != ApplicationStage.REJECTED:` block, after `locked.stage = ApplicationStage.REJECTED` (`:1444`):
```python
                locked.stage = ApplicationStage.REJECTED
                locked.stage_entered_at = datetime.now(timezone.utc)
```

(`datetime`, `timezone` are already imported in `board_service.py`.)

In `backend/recruiting/application_service.py`, the submit `ApplicationEntity(...)` (`:307`) — add the field so the value is explicit (also covered by server_default):
```python
            ApplicationEntity(
                job_id=dto.job_id,
                user_id=current_user.user_id,
                stage=stage,
                stage_entered_at=datetime.now(timezone.utc),
                sub_status=self._screened_sub_status(stage),
                tags=tags,
            ),
```
Ensure `from datetime import datetime, timezone` is present at the top of `application_service.py`; add `timezone` to the existing datetime import if missing.

In `backend/backfill/backfill_activity_application_gate.py`, the promote UPDATE (`:69`):
```python
                existing_application.stage = ApplicationStage.HIRED
                existing_application.stage_entered_at = datetime.now(timezone.utc)
```
and the INSERT (`:82`) — add `stage_entered_at=datetime.now(timezone.utc)` to the `ApplicationEntity(...)` kwargs. Ensure `from datetime import datetime, timezone` is imported in this file.

- [ ] **Step 5: Run the test to verify it passes**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_service_test --test_env=DATABASE_URL --test_output=errors`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/entity/application_entity.py backend/recruiting/board_service.py \
        backend/recruiting/application_service.py \
        backend/backfill/backfill_activity_application_gate.py \
        tests/backend_test/recruiting_test/board_service_test.py
git commit -m "[PUR-505] Add application.stage_entered_at and set on stage writes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Alembic migration — add column (NOT NULL + server_default), index

**Files:**
- Create: `alembic_setup/versions/<rev>_add_stage_entered_at_to_application.py`
- Test: `tests/backend_test/repository_test/stage_entered_at_migration_test.py` (create) + its `BUILD` entry

**Interfaces:**
- Consumes: `ApplicationEntity.stage_entered_at` from Task 1.
- Produces: the column materialized on the DB (existing rows populated via
  `server_default`, no historical backfill — the feature is not launched, so
  historical accuracy isn't needed); index `ix_application_job_stage_entered`.

- [ ] **Step 1: Generate the migration skeleton**

Run: `DATABASE_URL=$DATABASE_URL python tools/make_migration/make_migration.py "add stage_entered_at to application"`
(If the tool path differs, use the repo's documented `tools/make_migration` entry.) This autogenerates an `op.add_column` for the new column. Open the created file under `alembic_setup/versions/`.

- [ ] **Step 2: Replace `upgrade()`/`downgrade()` with a one-step add + index (no backfill)**

`server_default=now()` lets Postgres populate every existing row in the same
statement that adds the column, so there's no add-nullable → backfill →
set-not-null dance:

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "application",
        sa.Column(
            "stage_entered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_application_job_stage_entered",
        "application",
        ["job_id", "stage", sa.text("stage_entered_at DESC"), sa.text("application_id DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_application_job_stage_entered", table_name="application")
    op.drop_column("application", "stage_entered_at")
```

Keep the autogenerated `revision` / `down_revision` identifiers untouched.

- [ ] **Step 3: Write the failing migration test**

Create `tests/backend_test/repository_test/stage_entered_at_migration_test.py`. DB-backed (uses `DATABASE_URL`; follow `application_repository_test.py`'s session/setup style). No backfill to test — just confirm the column and its default, and the index:

```python
import unittest
# ... async test base used elsewhere in this dir ...

class StageEnteredAtMigrationTest(...):
    async def test_insert_without_stage_entered_at_gets_server_default(self):
        # Insert a job + user + application row WITHOUT specifying
        # stage_entered_at, re-select it fresh, assert it is not None
        # (the server_default populated it).
        ...
        self.assertIsNotNone(stage_entered_at)

    async def test_index_exists(self):
        # Query pg_indexes for 'ix_application_job_stage_entered'.
        ...
        self.assertIsNotNone(indexname)

if __name__ == "__main__":
    unittest.main()
```

Add a `py_test(name = "stage_entered_at_migration_test", srcs = [...], ...)` entry to `tests/backend_test/repository_test/BUILD` mirroring the existing `application_repository_test` entry (same deps + `DATABASE_URL` env passing).

- [ ] **Step 4: Run the migration test to verify it fails**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/repository_test:stage_entered_at_migration_test --test_env=DATABASE_URL --test_output=errors`
Expected: FAIL (column/index not applied to the test DB yet).

- [ ] **Step 5: Apply the migration to the test DB**

Run: `DATABASE_URL=$DATABASE_URL python tools/migrate_db/migrate_db.py`
Expected: migration applies cleanly; `application.stage_entered_at` exists, NOT NULL, `server_default=now()`, and the index exists.
(Confirm `DATABASE_URL` points at the **test** DB before running — never run against staging/prod.)

- [ ] **Step 6: Run the migration test to verify it passes**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/repository_test:stage_entered_at_migration_test --test_env=DATABASE_URL --test_output=errors`
Expected: PASS (both cases).

- [ ] **Step 7: Commit**

```bash
git add alembic_setup/versions/ tests/backend_test/repository_test/stage_entered_at_migration_test.py \
        tests/backend_test/repository_test/BUILD
git commit -m "[PUR-505] Migrate stage_entered_at column with index, no backfill

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Repository — exclude_stages + terminal-lane page/count queries

**Files:**
- Modify: `backend/repository/application_repository.py`
- Test: `tests/backend_test/repository_test/application_repository_test.py`

**Interfaces:**
- Consumes: `stage_entered_at` (Task 1/2).
- Produces:
  - `list_by_job(session, job_id, exclude_stages: set[ApplicationStage] | None = None) -> list[tuple[ApplicationEntity, UsersEntity]]`
  - `list_by_job_and_stage(session, job_id, stage: ApplicationStage, limit: int, offset: int) -> list[tuple[ApplicationEntity, UsersEntity]]`
  - `count_latest_by_job_and_stage(session, job_id, stage: ApplicationStage) -> int`

- [ ] **Step 1: Write the failing repository tests**

In `tests/backend_test/repository_test/application_repository_test.py`, add (follow the file's existing DB-backed setup/seed helpers):

```python
async def test_list_by_job_and_stage_orders_by_entry_desc_and_pages(self):
    # Seed 3 rejected apps (distinct users) with stage_entered_at t1<t2<t3.
    page = await repo.list_by_job_and_stage(session, job_id, ApplicationStage.REJECTED, limit=2, offset=0)
    self.assertEqual([a.application_id for a, _ in page], [id_t3, id_t2])  # newest first
    page2 = await repo.list_by_job_and_stage(session, job_id, ApplicationStage.REJECTED, limit=2, offset=2)
    self.assertEqual([a.application_id for a, _ in page2], [id_t1])

async def test_list_by_job_and_stage_excludes_reapplied_users_old_rejected_row(self):
    # user has an OLD rejected row + a NEWER active row (higher application_id).
    # The old rejected row must NOT appear in the rejected lane (latest-per-user).
    page = await repo.list_by_job_and_stage(session, job_id, ApplicationStage.REJECTED, limit=50, offset=0)
    self.assertNotIn(old_rejected_id, [a.application_id for a, _ in page])

async def test_count_latest_by_job_and_stage_matches_items(self):
    total = await repo.count_latest_by_job_and_stage(session, job_id, ApplicationStage.REJECTED)
    page = await repo.list_by_job_and_stage(session, job_id, ApplicationStage.REJECTED, limit=1000, offset=0)
    self.assertEqual(total, len(page))

async def test_list_by_job_exclude_stages_drops_terminal(self):
    rows = await repo.list_by_job(session, job_id,
                                  exclude_stages={ApplicationStage.REJECTED, ApplicationStage.HIRED})
    stages = {a.stage for a, _ in rows}
    self.assertNotIn(ApplicationStage.REJECTED, stages)
    self.assertNotIn(ApplicationStage.HIRED, stages)
```

- [ ] **Step 2: Run to verify they fail**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/repository_test:application_repository_test --test_env=DATABASE_URL --test_output=errors`
Expected: FAIL — `list_by_job_and_stage` / `count_latest_by_job_and_stage` don't exist; `list_by_job` has no `exclude_stages`.

- [ ] **Step 3: Implement the three methods**

In `backend/repository/application_repository.py`, modify `list_by_job` and add the two new methods. Add `set` typing import if needed (built-in `set` is fine). Note the shared latest-per-user subquery and the **outer** stage filter:

```python
    async def list_by_job(
        self,
        session: AsyncSession,
        job_id: int,
        exclude_stages: set[ApplicationStage] | None = None,
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """Return each user's latest application for a job, joined with its
        applicant, ordered by application_id (stable board card order).

        Args:
            exclude_stages: if given, latest rows in these stages are dropped
                (the board loads active stages here and paginates terminal
                stages separately).
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        stmt = (
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.application_id.in_(latest_ids),
            )
        )
        if exclude_stages:
            stmt = stmt.where(ApplicationEntity.stage.notin_(exclude_stages))
        stmt = stmt.order_by(ApplicationEntity.application_id)
        result = await session.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def list_by_job_and_stage(
        self,
        session: AsyncSession,
        job_id: int,
        stage: ApplicationStage,
        limit: int,
        offset: int,
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """One page of a single stage's latest-per-user applications,
        newest-entry first. The stage filter is applied to the LATEST row
        (outer query), so a user who re-applied does not surface an old
        rejected attempt here.
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        result = await session.execute(
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage == stage,
                ApplicationEntity.application_id.in_(latest_ids),
            )
            .order_by(
                ApplicationEntity.stage_entered_at.desc(),
                ApplicationEntity.application_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [tuple(row) for row in result.all()]

    async def count_latest_by_job_and_stage(
        self, session: AsyncSession, job_id: int, stage: ApplicationStage
    ) -> int:
        """Count latest-per-user applications for a job in one stage. Uses the
        SAME outer stage filter as list_by_job_and_stage so total == items.

        NOTE: deliberately named apart from the pre-existing
        count_by_job_and_stage (audit page; GROUP BY stage, no latest-per-user).
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        result = await session.execute(
            select(func.count())
            .select_from(ApplicationEntity)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage == stage,
                ApplicationEntity.application_id.in_(latest_ids),
            )
        )
        return int(result.scalar_one())
```

- [ ] **Step 4: Run to verify they pass**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/repository_test:application_repository_test --test_env=DATABASE_URL --test_output=errors`
Expected: PASS (all new tests + existing ones still green).

- [ ] **Step 5: Commit**

```bash
git add backend/repository/application_repository.py \
        tests/backend_test/repository_test/application_repository_test.py
git commit -m "[PUR-505] Add terminal-lane page and count repository queries

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Service — restructure get_board + add get_board_stage_page

**Files:**
- Modify: `backend/recruiting/board_service.py` (`get_board` ~`:266`; add `get_board_stage_page`)
- Modify: `backend/dto/board_dto.py` (add response DTOs — see Task 5 Interfaces; define here if Task 4 runs first)
- Test: `tests/backend_test/recruiting_test/board_service_test.py`

**Interfaces:**
- Consumes: `list_by_job(exclude_stages=)`, `list_by_job_and_stage`, `count_latest_by_job_and_stage` (Task 3).
- Produces:
  - `get_board(...) -> dict` shaped `{"stages": {stage_value: {"items": [BoardCardDto], "total": int, "has_more": bool}}}`
  - `get_board_stage_page(session, current_user, job_id, stage: ApplicationStage, limit: int, offset: int) -> dict` shaped `{"items": [BoardCardDto], "total": int, "has_more": bool}`
- `TERMINAL_PAGE_SIZE = 20` module constant in `board_service.py`.

- [ ] **Step 1: Write failing service tests**

In `tests/backend_test/recruiting_test/board_service_test.py` (follow existing fixture style):

```python
async def test_get_board_wraps_stages_and_pages_terminal(self):
    # Seed active + 25 rejected (distinct users). Expect:
    board = await service.get_board(session, owner, job_id)
    self.assertEqual(board["stages"]["recruiter_screening"]["has_more"], False)
    rej = board["stages"]["rejected"]
    self.assertEqual(len(rej["items"]), 20)     # first page N
    self.assertEqual(rej["total"], 25)
    self.assertTrue(rej["has_more"])
    # active stage: total == item count, never truncated
    self.assertEqual(board["stages"]["recruiter_screening"]["total"],
                     len(board["stages"]["recruiter_screening"]["items"]))

async def test_get_board_stage_page_second_page(self):
    page = await service.get_board_stage_page(session, owner, job_id,
                                              ApplicationStage.REJECTED, limit=20, offset=20)
    self.assertEqual(len(page["items"]), 5)
    self.assertEqual(page["total"], 25)
    self.assertFalse(page["has_more"])

async def test_get_board_stage_page_requires_owner(self):
    with self.assertRaises(ValueError):
        await service.get_board_stage_page(session, non_owner, job_id,
                                           ApplicationStage.REJECTED, limit=20, offset=0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_service_test --test_env=DATABASE_URL --test_output=errors`
Expected: FAIL — `get_board` returns the old flat dict; `get_board_stage_page` missing.

- [ ] **Step 3: Add the constant, a card-building helper, and rewrite get_board**

At module top of `board_service.py` (near `INTERVIEW_STAGES`):
```python
TERMINAL_PAGE_SIZE = 20
TERMINAL_STAGES = (ApplicationStage.REJECTED, ApplicationStage.HIRED)
```

Extract the existing per-row card construction (the assignments/reviewer/contact-email resolution + `to_board_card_dto` loop, currently `:296-350`) into a helper so both entry points reuse it. Move that exact logic here, returning a flat `list[BoardCardDto]` (do NOT bucket by stage — the caller decides):
```python
    async def _cards_for_rows(self, session, job, rows):
        """Build BoardCardDto list for (application, user) rows, resolving
        reviewer names + contact emails in batch (same logic get_board used)."""
        default_by_stage: dict[ApplicationStage, int] = {}
        for entry in (job.pipeline_config or {}).get("stages") or []:
            if not isinstance(entry, dict):
                continue
            default_id = entry.get("defaultAssigneeId")
            if default_id is None:
                continue
            try:
                stage = ApplicationStage(entry.get("stage"))
            except ValueError:
                continue
            default_by_stage[stage] = default_id

        application_ids = [application.application_id for application, _ in rows]
        assignments = await self.application_assignment_repository.list_by_application_ids(
            session, application_ids
        )
        assignment_by_key: dict[tuple[int, ApplicationStage, int], int] = {
            (a.application_id, a.stage, a.round): a.assignee_id for a in assignments
        }
        name_ids = {a.assignee_id for a in assignments} | set(default_by_stage.values())
        reviewers = await self.users_repository.get_all_by_ids(session, list(name_ids))
        names_by_id = {
            u.user_id: f"{u.first_name} {u.last_name}".strip() for u in reviewers
        }
        contact_by_user_id = await self.user_emails_repository.get_contact_emails_by_user_ids(
            session, [user.user_id for _, user in rows]
        )

        cards = []
        for application, user in rows:
            reviewer_name = None
            if application.stage in INTERVIEW_STAGES:
                assignee_id = assignment_by_key.get(
                    (application.application_id, application.stage, application.current_round)
                )
                if assignee_id is None and application.current_round == 1:
                    assignee_id = default_by_stage.get(application.stage)
                if assignee_id is not None:
                    reviewer_name = names_by_id.get(assignee_id)
            cards.append(
                self.recruiting_mapper.to_board_card_dto(
                    application,
                    user,
                    reviewer_name=reviewer_name,
                    applicant_email=contact_by_user_id.get(user.user_id, ""),
                )
            )
        return cards
```

Rewrite `get_board` to load active stages full + terminal stages first page:
```python
    async def get_board(self, session, current_user, job_id) -> dict:
        job = await self._require_owner(session, current_user, job_id, allow_read_all=True)

        active_rows = await self.application_repository.list_by_job(
            session, job_id, exclude_stages=set(TERMINAL_STAGES)
        )
        stages: dict[str, dict] = {}
        for card in await self._cards_for_rows(session, job, active_rows):
            bucket = stages.setdefault(
                card.stage.value, {"items": [], "total": 0, "has_more": False}
            )
            bucket["items"].append(card)
        for bucket in stages.values():
            bucket["total"] = len(bucket["items"])

        for stage in TERMINAL_STAGES:
            total = await self.application_repository.count_latest_by_job_and_stage(
                session, job_id, stage
            )
            rows = await self.application_repository.list_by_job_and_stage(
                session, job_id, stage, limit=TERMINAL_PAGE_SIZE, offset=0
            )
            items = await self._cards_for_rows(session, job, rows)
            if items or total:
                stages[stage.value] = {
                    "items": items,
                    "total": total,
                    "has_more": total > len(items),
                }
        return {"stages": stages}
```

Add `get_board_stage_page`:
```python
    async def get_board_stage_page(
        self, session, current_user, job_id, stage: ApplicationStage,
        limit: int, offset: int,
    ) -> dict:
        job = await self._require_owner(session, current_user, job_id, allow_read_all=True)
        total = await self.application_repository.count_latest_by_job_and_stage(
            session, job_id, stage
        )
        rows = await self.application_repository.list_by_job_and_stage(
            session, job_id, stage, limit=limit, offset=offset
        )
        items = await self._cards_for_rows(session, job, rows)
        return {"items": items, "total": total, "has_more": offset + len(items) < total}
```

- [ ] **Step 4: Run to verify they pass**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_service_test --test_env=DATABASE_URL --test_output=errors`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/recruiting/board_service.py tests/backend_test/recruiting_test/board_service_test.py
git commit -m "[PUR-505] Paginate terminal lanes in board service

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Endpoint constant + controller route + validation

**Files:**
- Modify: `backend/common/api_endpoints.py` (~`:102`)
- Modify: `backend/recruiting/board_controller.py`
- Test: `tests/backend_test/recruiting_test/board_controller_test.py`

**Interfaces:**
- Consumes: `BoardService.get_board_stage_page` (Task 4).
- Produces: `GET /recruiting/jobs/{job_id}/board/applications?stage=&limit=&offset=` → `api_response(data={"items", "total", "has_more"})`.

- [ ] **Step 1: Add the endpoint constant**

In `backend/common/api_endpoints.py`, after `RECRUITING_JOB_BOARD_ENDPOINT` (`:102`):
```python
RECRUITING_JOB_BOARD_STAGE_ENDPOINT = "/recruiting/jobs/{job_id}/board/applications"
```
Add it to that module's import in `board_controller.py`.

- [ ] **Step 2: Write the failing controller tests**

In `tests/backend_test/recruiting_test/board_controller_test.py` (follow existing route-test style; the service is mocked):
```python
async def test_board_stage_page_returns_service_payload(self):
    self.board_service.get_board_stage_page.return_value = {
        "items": [], "total": 25, "has_more": True}
    resp = await self.controller.get_board_stage_page(user, job_id=1,
                                                       stage="rejected", limit=20, offset=0)
    self.assertEqual(resp.data["total"], 25)

async def test_board_stage_page_rejects_bad_stage(self):
    with self.assertRaises(Exception):  # 400 / ValueError depending on layer
        await self.controller.get_board_stage_page(user, job_id=1,
                                                    stage="not_a_stage", limit=20, offset=0)

async def test_board_stage_page_clamps_limit(self):
    await self.controller.get_board_stage_page(user, job_id=1, stage="rejected",
                                               limit=9999, offset=0)
    called_limit = self.board_service.get_board_stage_page.call_args.kwargs.get("limit") \
        or self.board_service.get_board_stage_page.call_args.args[-2]
    self.assertLessEqual(called_limit, 100)
```

- [ ] **Step 3: Run to verify they fail**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_controller_test --test_env=DATABASE_URL --test_output=errors`
Expected: FAIL — handler/route missing.

- [ ] **Step 4: Register the route and implement the handler**

In `board_controller.py` `__init__`, after the `RECRUITING_JOB_BOARD_ENDPOINT` route:
```python
        self.router.add_api_route(
            RECRUITING_JOB_BOARD_STAGE_ENDPOINT,
            endpoint=authenticate()(self.get_board_stage_page),
            methods=["GET"],
            response_model=None,
        )
```
Add the handler (validates + clamps, converts `stage` to the enum → 400 on bad value):
```python
    async def get_board_stage_page(
        self, current_user: UserContextDto, job_id: int,
        stage: str, limit: int = 20, offset: int = 0,
    ):
        """One page of a terminal lane's applications (offset/limit)."""
        try:
            stage_enum = ApplicationStage(stage)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid stage.")
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be >= 0.")
        limit = max(1, min(limit, 100))
        async with self.database.session() as session:
            result = await self.board_service.get_board_stage_page(
                session, current_user, job_id, stage_enum, limit, offset
            )
        return api_response(message="Board page fetched.", data=result)
```
Ensure `ApplicationStage` and `HTTPException` are imported in `board_controller.py` (add if missing: `from fastapi import HTTPException`, `from backend.common.recruiting_enums import ApplicationStage`).

- [ ] **Step 5: Run to verify they pass**

Run: `DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_controller_test --test_env=DATABASE_URL --test_output=errors`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/common/api_endpoints.py backend/recruiting/board_controller.py \
        tests/backend_test/recruiting_test/board_controller_test.py
git commit -m "[PUR-505] Add board terminal-lane page endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Frontend — adapt to wrapped shape + "Load more" + dedupe

**Files:**
- Modify: `frontend/src/constants/ApiEndpoints.js` (~`:64`)
- Modify: `frontend/src/api/recruitingApi.js` (~`:107`)
- Modify: `frontend/src/pages/Recruiting/board/BoardPage.jsx`
- Test: `frontend/.../BoardPage.test.jsx` (create) — runs under `//tests/frontend_test:frontend_unit_tests`

**Interfaces:**
- Consumes: board response `{ stages: { [stage]: { items, total, has_more } } }`; page endpoint `{ items, total, has_more }`.
- Produces: terminal lanes render first page + count + a "Load more" button that appends deduped pages.

- [ ] **Step 1: Add the endpoint + api function**

`frontend/src/constants/ApiEndpoints.js` after `RECRUITING_JOB_BOARD` (`:64`):
```js
  RECRUITING_JOB_BOARD_STAGE: (jobId) => `/recruiting/jobs/${jobId}/board/applications`,
```
`frontend/src/api/recruitingApi.js` after `getJobBoard` (`:108`):
```js
/**
 * Fetch one page of a terminal lane's applications (offset/limit).
 */
export const getJobBoardStagePage = (jobId, { stage, limit = 20, offset = 0 }) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_BOARD_STAGE(jobId), {
    params: { stage, limit, offset },
  });
```

- [ ] **Step 2: Write the failing BoardPage test**

Create a BoardPage test using `createMemoryRouter` (NOT `vi.mock("react-router-dom")`; add `hasPointerCapture`/`scrollIntoView` no-ops if any Radix component renders — see repo test conventions). Mock the api module:
```jsx
// getJobBoard resolves { data: { stages: { rejected: { items: [20 cards], total: 25, has_more: true } } } }
// getJobBoardStagePage resolves { data: { items: [5 cards], total: 25, has_more: false } }
it("shows Load more on a terminal lane and appends deduped cards", async () => {
  // render BoardPage with a selected job whose pipeline has a rejected lane
  expect(await screen.findByText("Load more")).toBeInTheDocument();
  await userEvent.click(screen.getByText("Load more"));
  // 25 unique cards rendered, no duplicates, button gone (has_more false)
  expect(screen.queryByText("Load more")).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `bazel test //tests/frontend_test:frontend_unit_tests --test_output=errors`
Expected: FAIL — no "Load more"; `loadBoard` reads the old flat shape.

- [ ] **Step 4: Adapt loadBoard + add Load-more state/handler + render**

In `BoardPage.jsx`:
- Import: `import { listBoardJobs, getJobBoard, getJobBoardStagePage } from "@/api/recruitingApi";`
- `loadBoard` (`:62-72`) store the wrapped shape as-is: `setBoard(data?.stages ?? {})`.
- Where cards are read (`:188`) change `board[lane.stage] ?? []` to `board[lane.stage]?.items ?? []`; use `board[lane.stage]?.total ?? cards.length` for the count badge (`:214` `{cards.length}` → the lane's total); read `board[lane.stage]?.has_more`.
- Add a handler that appends a page, deduping by `card.id`:
```jsx
  const loadMore = useCallback(async (stage) => {
    const lane = board[stage];
    const { data } = await getJobBoardStagePage(selectedJobId, {
      stage, limit: 20, offset: lane.items.length,
    });
    setBoard((prev) => {
      const seen = new Set(prev[stage].items.map((c) => c.id));
      const merged = [...prev[stage].items,
                      ...data.items.filter((c) => !seen.has(c.id))];
      return { ...prev, [stage]: { ...prev[stage], items: merged, has_more: data.has_more } };
    });
  }, [board, selectedJobId]);
```
- After the cards `.map(...)` inside a terminal lane, render the button (Tailwind utilities, English copy):
```jsx
  {isTerminal && board[lane.stage]?.has_more && (
    <button
      type="button"
      onClick={() => loadMore(lane.stage)}
      className="mt-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
    >
      Load more
    </button>
  )}
```
- Failed load handling: wrap `loadMore`'s body in try/catch → `toast.error(e.message)` and leave `items` unchanged (matches `loadBoard`'s toast pattern).

- [ ] **Step 5: Run to verify it passes**

Run: `bazel test //tests/frontend_test:frontend_unit_tests --test_output=errors`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/constants/ApiEndpoints.js frontend/src/api/recruitingApi.js \
        frontend/src/pages/Recruiting/board/BoardPage.jsx \
        frontend/src/pages/Recruiting/board/*.test.jsx
git commit -m "[PUR-505] Render terminal-lane Load more on the board

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Final lint + full test sweep

**Files:** none (verification only).

- [ ] **Step 1: Lint everything once**

Run: `bash lint.sh --fix all_files`
Review the diff — `lint.sh --fix` can silently reformat unrelated files; `git add -p` only the intended changes if so.

- [ ] **Step 2: Full backend + frontend test sweep**

Run:
```bash
DATABASE_URL=$DATABASE_URL bazel test //tests/backend_test/recruiting_test:board_service_test \
  //tests/backend_test/recruiting_test:board_controller_test \
  //tests/backend_test/repository_test:application_repository_test \
  //tests/backend_test/repository_test:stage_entered_at_migration_test \
  --test_env=DATABASE_URL --test_output=errors
bazel test //tests/frontend_test:frontend_unit_tests --test_output=errors
```
Expected: all PASS.

- [ ] **Step 3: Commit any lint fixups**

```bash
git add -u
git commit -m "[PUR-505] Lint board pagination changes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Stop here — do NOT push. Report status to Yuji for review.

---

## Notes for the implementer

- **Migration ordering vs. test DB:** Task 3+ DB tests need the Task 2 migration applied to the test DB (Task 2 Step 5). If a later task's DB test fails with "column stage_entered_at does not exist", the migration wasn't applied to the DB your `DATABASE_URL` points at.
- **Latest-per-user is load-bearing:** the `stage` filter must stay in the OUTER query (on the latest row), never inside the `max(application_id) GROUP BY user_id` subquery — otherwise a re-applied user's old rejected row leaks into the rejected lane. (Spec §4.1, I2.)
- **Do not touch** the existing `count_by_job_and_stage` (audit page). The new count method is `count_latest_by_job_and_stage`.
- **Paging drift is expected and handled** by the frontend `card.id` dedupe (spec §7); do not attempt a keyset cursor — it's out of scope.
- **Performance:** the terminal page/count queries still re-run the latest-per-user subquery over all of a job's rows per request; if a perf test is added later, validate the plan with `EXPLAIN` and consider a `(job_id, user_id, application_id)` index (spec §3).
