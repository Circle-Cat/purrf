import unittest
from datetime import datetime, timezone

from sqlalchemy import select, text

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_activity_entity import ApplicationActivityEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# Copied verbatim from the `upgrade()` step 2 backfill UPDATE in
# alembic_setup/versions/82498a573699_add_stage_entered_at_to_application.py.
# Kept in sync manually — the migration file is the source of truth.
BACKFILL_SQL = """
UPDATE application AS app
SET stage_entered_at = COALESCE(
    (SELECT max(act.created_at)
       FROM application_activity AS act
      WHERE act.application_id = app.application_id
        AND (act.event_type = 'blacklisted'
             OR (act.event_type = 'stage_changed'
                 AND act.details->>'toStage' = app.stage::text))),
    app.created_datetime
)
"""


def _make_user(email: str) -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column."""
    return UsersEntity(
        first_name="A",
        last_name="B",
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class StageEnteredAtBackfillTest(BaseRepositoryTestLib):
    async def _seed_job_and_actor(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        actor = _make_user("actor@b.com")
        await self.insert_entities([job, actor])
        return job, actor

    async def _run_backfill(self):
        await self.session.execute(text(BACKFILL_SQL))

    async def _stage_entered_at(self, application_id: int):
        result = await self.session.execute(
            select(ApplicationEntity.stage_entered_at).where(
                ApplicationEntity.application_id == application_id
            )
        )
        return result.scalar_one()

    async def test_manual_move_uses_last_stage_changed_to_current_stage(self):
        # App currently REJECTED, with stage_changed toStage=tech at T1, then
        # stage_changed toStage=rejected at T2 (T2 > T1). Backfill must pick
        # T2 (the change that actually landed the row in its current stage).
        job, actor = await self._seed_job_and_actor()
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 2, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 3, tzinfo=timezone.utc)
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.REJECTED,
            created_datetime=created,
        )
        await self.insert_entities([app])
        await self.insert_entities(
            [
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="stage_changed",
                    details={"toStage": "tech"},
                    created_at=t1,
                ),
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="stage_changed",
                    details={"toStage": "rejected"},
                    created_at=t2,
                ),
            ]
        )

        await self._run_backfill()

        self.assertEqual(await self._stage_entered_at(app.application_id), t2)

    async def test_blacklisted_row_uses_blacklisted_event_time(self):
        # App REJECTED via a 'blacklisted' activity at TB (no stage_changed
        # at all). Backfill must pick TB.
        job, actor = await self._seed_job_and_actor()
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        tb = datetime(2026, 1, 5, tzinfo=timezone.utc)
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.REJECTED,
            created_datetime=created,
        )
        await self.insert_entities([app])
        await self.insert_entities(
            [
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="blacklisted",
                    details={},
                    created_at=tb,
                )
            ]
        )

        await self._run_backfill()

        self.assertEqual(await self._stage_entered_at(app.application_id), tb)

    async def test_hired_then_swept_to_rejected_does_not_use_hire_time(self):
        # stage_changed toStage=hired at TH, then 'blacklisted' at TS
        # (TS > TH) sweeps the row to REJECTED. Backfill must pick TS, not
        # the earlier hire time.
        job, actor = await self._seed_job_and_actor()
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        th = datetime(2026, 1, 2, tzinfo=timezone.utc)
        ts = datetime(2026, 1, 10, tzinfo=timezone.utc)
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.REJECTED,
            created_datetime=created,
        )
        await self.insert_entities([app])
        await self.insert_entities(
            [
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="stage_changed",
                    details={"toStage": "hired"},
                    created_at=th,
                ),
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="blacklisted",
                    details={},
                    created_at=ts,
                ),
            ]
        )

        await self._run_backfill()

        self.assertEqual(await self._stage_entered_at(app.application_id), ts)

    async def test_auto_landed_row_falls_back_to_created_datetime(self):
        # App REJECTED with only an 'auto_rejected' activity (no
        # 'stage_changed' or 'blacklisted' event at all). Backfill must fall
        # back to created_datetime.
        job, actor = await self._seed_job_and_actor()
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.REJECTED,
            created_datetime=created,
        )
        await self.insert_entities([app])
        await self.insert_entities(
            [
                ApplicationActivityEntity(
                    application_id=app.application_id,
                    actor_id=actor.user_id,
                    event_type="auto_rejected",
                    details={},
                    created_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                )
            ]
        )

        await self._run_backfill()

        self.assertEqual(await self._stage_entered_at(app.application_id), created)


if __name__ == "__main__":
    unittest.main()
