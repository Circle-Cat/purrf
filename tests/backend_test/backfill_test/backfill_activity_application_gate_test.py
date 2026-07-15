import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.backfill.backfill_activity_application_gate import (
    ActivityApplicationGateBackfillService,
)
from backend.common.mentorship_enums import ParticipantRole
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity


class TestActivityApplicationGateBackfillService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_application_repo = MagicMock()
        self.mock_application_repo.get_hired_activity_application = AsyncMock()
        self.mock_application_repo.get_latest_by_job_and_user = AsyncMock()
        self.mock_application_repo.create = AsyncMock()
        self.mock_application_repo.update = AsyncMock()

        self.mock_job_repo = MagicMock()
        self.mock_job_repo.list_published = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.list_distinct_user_roles = AsyncMock()

        self.mock_session = AsyncMock()

        self.service = ActivityApplicationGateBackfillService(
            application_repo=self.mock_application_repo,
            job_repo=self.mock_job_repo,
            participants_repo=self.mock_participants_repo,
        )

        self.mentee_job = JobEntity(
            job_id=1, kind=JobKind.ACTIVITY, mentorship_role=ParticipantRole.MENTEE
        )
        self.mentor_job = JobEntity(
            job_id=2, kind=JobKind.ACTIVITY, mentorship_role=ParticipantRole.MENTOR
        )
        self.mock_job_repo.list_published.return_value = [
            self.mentee_job,
            self.mentor_job,
        ]

    async def test_skips_user_who_already_has_hired_application(self):
        self.mock_participants_repo.list_distinct_user_roles.return_value = [
            (101, ParticipantRole.MENTEE)
        ]
        self.mock_application_repo.get_hired_activity_application.return_value = (
            MagicMock()
        )

        await self.service.backfill(self.mock_session)

        self.mock_application_repo.create.assert_not_awaited()
        self.mock_application_repo.update.assert_not_awaited()

    async def test_creates_hired_application_when_none_exists(self):
        self.mock_participants_repo.list_distinct_user_roles.return_value = [
            (101, ParticipantRole.MENTEE)
        ]
        self.mock_application_repo.get_hired_activity_application.return_value = None
        self.mock_application_repo.get_latest_by_job_and_user.return_value = None

        await self.service.backfill(self.mock_session)

        self.mock_application_repo.create.assert_awaited_once()
        created_entity = self.mock_application_repo.create.call_args.kwargs["entity"]
        self.assertIsInstance(created_entity, ApplicationEntity)
        self.assertEqual(created_entity.job_id, self.mentee_job.job_id)
        self.assertEqual(created_entity.user_id, 101)
        self.assertEqual(created_entity.stage, ApplicationStage.HIRED)

    async def test_promotes_existing_non_hired_application(self):
        self.mock_participants_repo.list_distinct_user_roles.return_value = [
            (101, ParticipantRole.MENTOR)
        ]
        self.mock_application_repo.get_hired_activity_application.return_value = None
        existing = ApplicationEntity(
            job_id=self.mentor_job.job_id,
            user_id=101,
            stage=ApplicationStage.REJECTED,
        )
        self.mock_application_repo.get_latest_by_job_and_user.return_value = existing

        await self.service.backfill(self.mock_session)

        self.mock_application_repo.create.assert_not_awaited()
        self.mock_application_repo.update.assert_awaited_once()
        updated_entity = self.mock_application_repo.update.call_args.kwargs["entity"]
        self.assertIs(updated_entity, existing)
        self.assertEqual(updated_entity.stage, ApplicationStage.HIRED)

    async def test_skips_user_with_no_published_posting_for_role(self):
        self.mock_job_repo.list_published.return_value = [self.mentee_job]
        self.mock_participants_repo.list_distinct_user_roles.return_value = [
            (101, ParticipantRole.MENTOR)
        ]

        await self.service.backfill(self.mock_session)

        self.mock_application_repo.get_hired_activity_application.assert_not_awaited()
        self.mock_application_repo.create.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
