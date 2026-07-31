import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.mentorship.onboarding_training_service import OnboardingTrainingService
from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.common.recruiting_enums import JobKind
from backend.entity.training_entity import TrainingEntity


def _job(kind=JobKind.ACTIVITY, mentorship_role=ParticipantRole.MENTEE):
    job = MagicMock()
    job.kind = kind
    job.mentorship_role = mentorship_role
    return job


class TestOnboardingTrainingService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_id_and_category = AsyncMock(
            return_value=None
        )
        self.mock_training_repo.upsert_training = AsyncMock()
        self.service = OnboardingTrainingService(
            logger=self.mock_logger,
            training_repository=self.mock_training_repo,
        )

    async def test_creates_mentee_onboarding_with_no_deadline(self):
        with patch.dict(
            "os.environ", {"MENTORSHIP_MENTEE_ONBOARDING_LINK": "https://mentee"}
        ):
            await self.service.ensure_for_admitted(
                session=self.mock_session, user_id=7, job=_job()
            )

        self.mock_training_repo.upsert_training.assert_awaited_once()
        entity = self.mock_training_repo.upsert_training.await_args.kwargs["entity"]
        self.assertIsInstance(entity, TrainingEntity)
        self.assertEqual(entity.user_id, 7)
        self.assertEqual(entity.category, TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)
        self.assertEqual(entity.status, TrainingStatus.TO_DO)
        self.assertIsNone(entity.deadline)
        self.assertIsNone(entity.completed_timestamp)
        self.assertEqual(entity.link, "https://mentee")

    async def test_creates_mentor_onboarding_with_the_mentor_link(self):
        with patch.dict(
            "os.environ", {"MENTORSHIP_MENTOR_ONBOARDING_LINK": "https://mentor"}
        ):
            await self.service.ensure_for_admitted(
                session=self.mock_session,
                user_id=7,
                job=_job(mentorship_role=ParticipantRole.MENTOR),
            )

        entity = self.mock_training_repo.upsert_training.await_args.kwargs["entity"]
        self.assertEqual(entity.category, TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        self.assertEqual(entity.link, "https://mentor")

    async def test_skips_employment_jobs(self):
        await self.service.ensure_for_admitted(
            session=self.mock_session,
            user_id=7,
            job=_job(kind=JobKind.EMPLOYMENT, mentorship_role=None),
        )

        self.mock_training_repo.get_training_by_user_id_and_category.assert_not_awaited()
        self.mock_training_repo.upsert_training.assert_not_awaited()

    async def test_skips_activity_jobs_with_no_mentorship_role(self):
        await self.service.ensure_for_admitted(
            session=self.mock_session,
            user_id=7,
            job=_job(mentorship_role=None),
        )

        self.mock_training_repo.upsert_training.assert_not_awaited()

    async def test_is_idempotent_when_a_row_already_exists(self):
        self.mock_training_repo.get_training_by_user_id_and_category.return_value = (
            TrainingEntity(user_id=7)
        )

        await self.service.ensure_for_admitted(
            session=self.mock_session, user_id=7, job=_job()
        )

        self.mock_training_repo.upsert_training.assert_not_awaited()

    async def test_does_not_commit(self):
        # The caller owns the transaction: the admission decision and the
        # training row must land together or not at all.
        with patch.dict(
            "os.environ", {"MENTORSHIP_MENTEE_ONBOARDING_LINK": "https://mentee"}
        ):
            await self.service.ensure_for_admitted(
                session=self.mock_session, user_id=7, job=_job()
            )

        self.mock_session.commit.assert_not_awaited()

    async def test_creates_with_the_deadline_it_is_given(self):
        deadline = datetime(2026, 8, 3, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ", {"MENTORSHIP_MENTEE_ONBOARDING_LINK": "https://mentee"}
        ):
            await self.service.ensure_onboarding_training(
                session=self.mock_session,
                user_id=7,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                deadline=deadline,
            )

        entity = self.mock_training_repo.upsert_training.await_args.kwargs["entity"]
        self.assertEqual(entity.deadline, deadline)

    async def test_stamps_a_deadline_onto_an_existing_row_that_has_none(self):
        existing = TrainingEntity(
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=None,
            link="https://mentee",
        )
        self.mock_training_repo.get_training_by_user_id_and_category.return_value = (
            existing
        )
        deadline = datetime(2026, 8, 3, tzinfo=timezone.utc)

        await self.service.ensure_onboarding_training(
            session=self.mock_session,
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            deadline=deadline,
        )

        saved = self.mock_training_repo.upsert_training.await_args.kwargs["entity"]
        self.assertEqual(saved.deadline, deadline)

    async def test_never_overwrites_a_deadline_that_is_already_set(self):
        original = datetime(2026, 1, 1, tzinfo=timezone.utc)
        existing = TrainingEntity(
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=original,
            link="https://mentee",
        )
        self.mock_training_repo.get_training_by_user_id_and_category.return_value = (
            existing
        )

        result = await self.service.ensure_onboarding_training(
            session=self.mock_session,
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            deadline=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )

        self.mock_training_repo.upsert_training.assert_not_awaited()
        self.assertEqual(result.deadline, original)

    async def test_returns_the_existing_row_untouched_when_no_deadline_is_given(self):
        existing = TrainingEntity(
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            status=TrainingStatus.DONE,
            completed_timestamp=None,
            deadline=None,
            link="https://mentee",
        )
        self.mock_training_repo.get_training_by_user_id_and_category.return_value = (
            existing
        )

        result = await self.service.ensure_onboarding_training(
            session=self.mock_session,
            user_id=7,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        )

        self.mock_training_repo.upsert_training.assert_not_awaited()
        self.assertIs(result, existing)


if __name__ == "__main__":
    unittest.main()
