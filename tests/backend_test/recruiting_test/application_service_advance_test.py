import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole, ApprovalStatus
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.recruiting.application_service import ApplicationService


class TestAdvance(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app_repo = MagicMock()
        self.job_repo = MagicMock()
        self.round_repo = MagicMock()
        self.participants_repo = MagicMock()
        self.session = AsyncMock()
        self.now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.svc = ApplicationService(
            self.app_repo,
            self.job_repo,
            self.round_repo,
            MagicMock(),
            RecruitingMapper(),
            MagicMock(),
            self.participants_repo,
        )
        self.app = ApplicationEntity(
            application_id=10,
            user_id=5,
            job_id=3,
            round_id=9,
            stage=ApplicationStage.RECRUITER_SCREENING,
            is_viewed=False,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=self.app)
        self.app_repo.update_application = AsyncMock(side_effect=lambda s, e: e)
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=JobEntity(
                job_id=3,
                kind=JobKind.ACTIVITY,
                mentorship_role=ParticipantRole.MENTOR,
                status=JobStatus.PUBLISHED,
                title="m",
            )
        )

    async def test_hired_enrolls_participant_when_absent(self):
        """HIRED stage idempotently creates a participant entry when none exists."""
        self.participants_repo.get_by_user_id_and_round_id = AsyncMock(return_value=None)
        self.participants_repo.upsert_participant = AsyncMock(side_effect=lambda s, e: e)
        result = await self.svc.advance(self.session, 10, ApplicationStage.HIRED, self.now)
        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.participants_repo.upsert_participant.assert_awaited_once()
        created = self.participants_repo.upsert_participant.call_args.args[1]
        self.assertEqual(created.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(created.approval_status, ApprovalStatus.SIGNED_UP)

    async def test_hired_idempotent_when_already_enrolled(self):
        """HIRED stage skips upsert when the participant already exists."""
        self.participants_repo.get_by_user_id_and_round_id = AsyncMock(
            return_value=MagicMock()
        )
        self.participants_repo.upsert_participant = AsyncMock()
        result = await self.svc.advance(self.session, 10, ApplicationStage.HIRED, self.now)
        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.participants_repo.upsert_participant.assert_not_awaited()

    async def test_rejected_records_round_and_time(self):
        """REJECTED stage stamps rejected_round_id and rejected_at on the entity."""
        result = await self.svc.advance(self.session, 10, ApplicationStage.REJECTED, self.now)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(self.app.rejected_round_id, 9)
        self.assertEqual(self.app.rejected_at, self.now)

    async def test_list_board_computes_freeze_until(self):
        """list_board computes freeze_until from the prior rejected application's round."""
        active = ApplicationEntity(
            application_id=20,
            user_id=5,
            job_id=3,
            round_id=9,
            stage=ApplicationStage.RECRUITER_SCREENING,
            is_viewed=False,
        )
        prior_reject = ApplicationEntity(
            application_id=11,
            user_id=5,
            job_id=3,
            round_id=8,
            stage=ApplicationStage.REJECTED,
            rejected_round_id=8,
            rejected_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            is_viewed=False,
        )
        self.app_repo.list_active_by_job = AsyncMock(return_value=[active])
        self.app_repo.get_latest_rejected = AsyncMock(return_value=prior_reject)
        self.round_repo.get_by_round_id = AsyncMock(
            return_value=MentorshipRoundEntity(
                round_id=8, name="r8", required_meetings=5, reapply_freeze_days=90
            )
        )
        cards = await self.svc.list_board(self.session, 3, self.now)
        self.assertEqual(len(cards), 1)
        self.assertEqual(
            cards[0].freeze_until,
            datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(days=90),
        )


if __name__ == "__main__":
    unittest.main()
