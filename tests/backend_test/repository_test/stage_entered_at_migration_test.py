import unittest
from datetime import datetime, timezone

from sqlalchemy import select, text

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


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


class StageEnteredAtMigrationTest(BaseRepositoryTestLib):
    """Verifies the 82498a573699 migration: column + server_default + index.

    The feature is not launched, so this migration deliberately does NOT
    backfill historical rows — every existing row simply gets the
    migration-time `now()` via `server_default`. There is nothing to assert
    about historical accuracy; these tests only confirm the column and index
    are materialized as designed.
    """

    async def test_insert_without_stage_entered_at_gets_server_default(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        actor = _make_user("actor@b.com")
        await self.insert_entities([job, actor])

        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=actor.user_id,
            stage=ApplicationStage.REJECTED,
            created_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        # Deliberately do not set stage_entered_at — the column's
        # server_default (now()) must populate it.
        await self.insert_entities([app])

        result = await self.session.execute(
            select(ApplicationEntity.stage_entered_at).where(
                ApplicationEntity.application_id == app.application_id
            )
        )
        self.assertIsNotNone(result.scalar_one())

    async def test_index_exists(self):
        result = await self.session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'ix_application_job_stage_entered'"
            )
        )
        self.assertIsNotNone(result.scalar_one_or_none())


if __name__ == "__main__":
    unittest.main()
