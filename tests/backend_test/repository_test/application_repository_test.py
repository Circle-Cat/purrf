import unittest
import uuid
from datetime import datetime, timezone
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.repository.application_repository import ApplicationRepository
from backend.common.recruiting_enums import (
    JobKind,
    JobStatus,
    ApplicationStage,
    UserType,
)
from backend.common.mentorship_enums import ParticipantRole
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestApplicationRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = ApplicationRepository()
        self.user = UsersEntity(
            first_name="C",
            last_name="D",
            timezone="America/Los_Angeles",
            timezone_updated_at=datetime.now(timezone.utc),
            primary_email="c@example.com",
            subject_identifier=str(uuid.uuid4()),
            is_active=False,
            updated_timestamp=datetime.now(timezone.utc),
            user_type=UserType.EXTERNAL,
        )
        self.round = MentorshipRoundEntity(name="r1", required_meetings=5)
        self.job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            status=JobStatus.PUBLISHED,
            title="Mentee",
        )
        await self.insert_entities([self.user, self.round, self.job])

    async def test_create_and_get(self):
        app = ApplicationEntity(
            user_id=self.user.user_id,
            job_id=self.job.job_id,
            round_id=self.round.round_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
            form_answers={"q1": "a1"},
        )
        created = await self.repo.create_application(self.session, app)
        self.assertIsNotNone(created.application_id)
        fetched = await self.repo.get_by_id(self.session, created.application_id)
        self.assertEqual(fetched.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertFalse(fetched.is_viewed)

    async def test_latest_rejected_lookup(self):
        rejected = ApplicationEntity(
            user_id=self.user.user_id,
            job_id=self.job.job_id,
            round_id=self.round.round_id,
            stage=ApplicationStage.REJECTED,
            rejected_round_id=self.round.round_id,
            rejected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        await self.insert_entities([rejected])
        found = await self.repo.get_latest_rejected(
            self.session, self.user.user_id, self.job.job_id
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.rejected_round_id, self.round.round_id)

    async def test_partial_unique_blocks_second_active(self):
        from sqlalchemy.exc import IntegrityError

        a1 = ApplicationEntity(
            user_id=self.user.user_id,
            job_id=self.job.job_id,
            round_id=self.round.round_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([a1])
        a2 = ApplicationEntity(
            user_id=self.user.user_id,
            job_id=self.job.job_id,
            round_id=self.round.round_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        with self.assertRaises(IntegrityError):
            await self.insert_entities([a2])


if __name__ == "__main__":
    unittest.main()
