import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.dto.application_dto import ApplicationSubmitDto
from backend.common.recruiting_enums import (
    JobKind,
    JobStatus,
    ApplicationStage,
    UserType,
)
from backend.common.mentorship_enums import ApprovalStatus, ParticipantRole
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.recruiting.application_service import ApplicationService


class TestApplicationServiceSubmit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app_repo = MagicMock()
        self.job_repo = MagicMock()
        self.round_repo = MagicMock()
        self.users_repo = MagicMock()
        self.participants_repo = MagicMock()
        self.session = AsyncMock()
        self.now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.service = ApplicationService(
            self.app_repo,
            self.job_repo,
            self.round_repo,
            self.users_repo,
            RecruitingMapper(),
            MagicMock(),
            self.participants_repo,
        )
        self.job = JobEntity(
            job_id=3,
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            status=JobStatus.PUBLISHED,
            title="Mentee",
        )
        self.round = MentorshipRoundEntity(round_id=9, name="r", required_meetings=5)
        self.job_repo.get_by_job_id = AsyncMock(return_value=self.job)
        self.round_repo.get_open_application_round = AsyncMock(return_value=self.round)

        async def fake_create(session, entity):
            entity.application_id = 100
            return entity

        self.app_repo.create_application = AsyncMock(side_effect=fake_create)

    def _make_user(
        self, *, is_blocked: bool, primary_email: str = "a@b.c"
    ) -> UsersEntity:
        return UsersEntity(
            user_id=5,
            user_type=UserType.EXTERNAL,
            is_blocked=is_blocked,
            first_name="a",
            last_name="b",
            primary_email=primary_email,
            timezone="America/Los_Angeles",
            subject_identifier="auth0|test-subject-5",
            is_active=True,
        )

    def _make_mentor_job(self) -> JobEntity:
        return JobEntity(
            job_id=3,
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            status=JobStatus.PUBLISHED,
            title="Mentor",
        )

    async def test_normal_user_lands_in_screening(self):
        """A non-blocked user's application is created at RECRUITER_SCREENING with round stamped."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False)
        )
        dto = ApplicationSubmitDto(form_answers={"q": "v"})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.round_id, 9)
        self.session.commit.assert_awaited_once()

    async def test_blocked_user_auto_rejected(self):
        """A blocked user's application is auto-created at REJECTED stage."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=True)
        )
        dto = ApplicationSubmitDto(form_answers={"q": "v"})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)

    async def test_no_open_round_raises(self):
        """ValueError is raised when no open application round exists for the role."""
        self.round_repo.get_open_application_round = AsyncMock(return_value=None)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False)
        )
        with self.assertRaises(ValueError):
            await self.service.submit(
                self.session, 3, 5, ApplicationSubmitDto(form_answers={}), self.now
            )

    async def test_missing_job_raises(self):
        """ValueError is raised when the job does not exist."""
        self.job_repo.get_by_job_id = AsyncMock(return_value=None)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False)
        )
        with self.assertRaises(ValueError):
            await self.service.submit(
                self.session, 999, 5, ApplicationSubmitDto(form_answers={}), self.now
            )

    async def test_blocked_user_rejected_fields_stamped(self):
        """A blocked user's application has rejected_round_id and rejected_at populated."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=True)
        )
        dto = ApplicationSubmitDto(form_answers={})

        captured = {}

        async def capture_create(session, entity):
            captured["entity"] = entity
            entity.application_id = 101
            return entity

        self.app_repo.create_application = AsyncMock(side_effect=capture_create)
        await self.service.submit(self.session, 3, 5, dto, self.now)

        entity = captured["entity"]
        self.assertEqual(entity.rejected_round_id, 9)
        self.assertEqual(entity.rejected_at, self.now)

    async def test_commit_called_once_on_success(self):
        """Session is committed exactly once per submit call."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False)
        )
        await self.service.submit(
            self.session, 3, 5, ApplicationSubmitDto(form_answers={}), self.now
        )
        self.session.commit.assert_awaited_once()

    async def test_mentor_allowed_domain_auto_hired(self):
        """A MENTOR applicant with an allowed email domain is auto-approved to HIRED and enrolled."""
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._make_mentor_job())
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False, primary_email="a@google.com")
        )
        self.participants_repo.get_by_user_id_and_round_id = AsyncMock(
            return_value=None
        )
        self.participants_repo.upsert_participant = AsyncMock(
            side_effect=lambda s, e: e
        )
        dto = ApplicationSubmitDto(form_answers={})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.participants_repo.upsert_participant.assert_awaited_once()
        created = self.participants_repo.upsert_participant.call_args.args[1]
        self.assertEqual(created.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(created.approval_status, ApprovalStatus.SIGNED_UP)

    async def test_mentor_disallowed_domain_auto_rejected(self):
        """A MENTOR applicant with a disallowed email domain is auto-rejected."""
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._make_mentor_job())
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False, primary_email="a@gmail.com")
        )
        self.participants_repo.upsert_participant = AsyncMock()
        dto = ApplicationSubmitDto(form_answers={})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.participants_repo.upsert_participant.assert_not_awaited()

    async def test_mentor_allowed_idempotent_skip(self):
        """Auto-approve skips enrollment upsert when participant already exists."""
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._make_mentor_job())
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=False, primary_email="a@google.com")
        )
        self.participants_repo.get_by_user_id_and_round_id = AsyncMock(
            return_value=MagicMock()
        )
        self.participants_repo.upsert_participant = AsyncMock()
        dto = ApplicationSubmitDto(form_answers={})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.participants_repo.upsert_participant.assert_not_awaited()

    async def test_blocked_mentor_applicant_rejected_not_enrolled(self):
        """A blocked user on a MENTOR job is rejected; block takes precedence over domain check."""
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._make_mentor_job())
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._make_user(is_blocked=True, primary_email="a@google.com")
        )
        self.participants_repo.upsert_participant = AsyncMock()
        dto = ApplicationSubmitDto(form_answers={})
        result = await self.service.submit(self.session, 3, 5, dto, self.now)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.participants_repo.upsert_participant.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
