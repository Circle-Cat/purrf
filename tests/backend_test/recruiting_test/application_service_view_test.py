import unittest
from unittest.mock import AsyncMock, MagicMock
from backend.entity.application_entity import ApplicationEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, UserType
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.recruiting.application_service import ApplicationService


def _service():
    """Build an ApplicationService with all repos mocked."""
    app_repo = MagicMock()
    users_repo = MagicMock()
    exp_repo = MagicMock()
    svc = ApplicationService(
        app_repo, MagicMock(), MagicMock(), users_repo, RecruitingMapper(), exp_repo, MagicMock()
    )
    return svc, app_repo, users_repo, exp_repo


class TestApplicationServiceView(unittest.IsolatedAsyncioTestCase):
    """Tests for ApplicationService.mark_viewed."""

    async def test_first_view_locks_and_snapshots(self):
        """First call sets is_viewed=True and writes a snapshot dict."""
        svc, app_repo, users_repo, exp_repo = _service()
        session = AsyncMock()
        app = ApplicationEntity(
            application_id=10,
            user_id=5,
            job_id=3,
            round_id=9,
            stage=ApplicationStage.RECRUITER_SCREENING,
            is_viewed=False,
            form_answers={"q": "v"},
        )
        app_repo.get_by_id = AsyncMock(return_value=app)
        app_repo.update_application = AsyncMock(side_effect=lambda s, e: e)
        users_repo.get_user_by_user_id = AsyncMock(
            return_value=UsersEntity(
                user_id=5,
                user_type=UserType.EXTERNAL,
                first_name="a",
                last_name="b",
                primary_email="a@b.c",
                timezone="America/Los_Angeles",
            )
        )
        exp_repo.get_experience_by_user_id = AsyncMock(
            return_value=MagicMock(
                education=[{"school": "X"}], work_history=[{"title": "Y"}]
            )
        )

        result = await svc.mark_viewed(session, 10)
        self.assertTrue(result.is_viewed)
        self.assertIsNotNone(app.snapshot)
        self.assertIn("form_answers", app.snapshot)

    async def test_second_view_is_idempotent(self):
        """Second call returns the DTO unchanged without overwriting the snapshot."""
        svc, app_repo, users_repo, exp_repo = _service()
        session = AsyncMock()
        app = ApplicationEntity(
            application_id=10,
            user_id=5,
            job_id=3,
            round_id=9,
            stage=ApplicationStage.RECRUITER_SCREENING,
            is_viewed=True,
            snapshot={"frozen": True},
        )
        app_repo.get_by_id = AsyncMock(return_value=app)
        app_repo.update_application = AsyncMock(side_effect=lambda s, e: e)

        result = await svc.mark_viewed(session, 10)
        self.assertEqual(app.snapshot, {"frozen": True})
        self.assertTrue(result.is_viewed)

    async def test_missing_application_raises(self):
        """ValueError is raised when the application does not exist."""
        svc, app_repo, users_repo, exp_repo = _service()
        session = AsyncMock()
        app_repo.get_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await svc.mark_viewed(session, 999)


if __name__ == "__main__":
    unittest.main()
