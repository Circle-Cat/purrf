import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, create_autospec

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
    NotificationType,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.recruiting.notification_service import RecruitingNotificationService
from backend.repository.application_repository import ApplicationRepository
from backend.repository.job_repository import JobRepository
from backend.repository.notification_repository import NotificationRepository
from backend.repository.users_repository import UsersRepository


class TestRecruitingNotificationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.notification_repo = create_autospec(NotificationRepository, instance=True)
        self.app_repo = create_autospec(ApplicationRepository, instance=True)
        self.job_repo = create_autospec(JobRepository, instance=True)
        self.users_repo = create_autospec(UsersRepository, instance=True)
        self.session = AsyncMock()
        self.service = RecruitingNotificationService(
            self.notification_repo, self.app_repo, self.job_repo, self.users_repo
        )

    def _notification(self, **overrides):
        defaults = dict(
            user_id=2,
            type=NotificationType.ASSIGNED_TO_EVALUATE,
            application_id=10,
            round=1,
            comment_id=None,
            job_id=None,
            job_review_id=None,
            actor_user_id=9,
            read_at=None,
            created_at=datetime.now(timezone.utc),
        )
        defaults.update(overrides)
        entity = NotificationEntity(**defaults)
        entity.notification_id = overrides.get("notification_id", 1)
        return entity

    async def test_list_for_user_resolves_application_scoped_display_fields(self):
        row = self._notification()
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_unread = AsyncMock(return_value=1)
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Backend Engineer", status=JobStatus.PUBLISHED
        )
        job.job_id = 1
        application = ApplicationEntity(
            job_id=1, user_id=3, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.application_id = 10
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        applicant = UsersEntity(first_name="Ada", last_name="Lovelace")
        applicant.user_id = 3
        actor = UsersEntity(first_name="Grace", last_name="Hopper")
        actor.user_id = 9

        async def get_user(session, user_id):
            return {3: applicant, 9: actor}[user_id]

        self.users_repo.get_user_by_user_id = AsyncMock(side_effect=get_user)

        result = await self.service.list_for_user(self.session, user_id=2)

        self.assertEqual(result.unread_count, 1)
        self.assertEqual(len(result.notifications), 1)
        item = result.notifications[0]
        self.assertEqual(item.job_title, "Backend Engineer")
        self.assertEqual(item.applicant_name, "Ada Lovelace")
        self.assertEqual(item.actor_name, "Grace Hopper")
        self.assertFalse(item.read)

    async def test_list_for_user_resolves_job_scoped_display_fields(self):
        row = self._notification(
            type=NotificationType.JOB_REVIEW_REQUESTED,
            application_id=None,
            round=None,
            job_id=1,
            job_review_id=100,
            read_at=datetime.now(timezone.utc),
        )
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_unread = AsyncMock(return_value=0)
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Design Review", status=JobStatus.DRAFT
        )
        job.job_id = 1
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        actor = UsersEntity(first_name="Grace", last_name="Hopper")
        actor.user_id = 9
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=actor)

        result = await self.service.list_for_user(self.session, user_id=2)

        item = result.notifications[0]
        self.assertEqual(item.job_id, 1)
        self.assertEqual(item.job_title, "Design Review")
        self.assertEqual(item.applicant_name, "")
        self.assertTrue(item.read)
        self.app_repo.get_by_id.assert_not_awaited()

    async def test_mark_read_returns_updated_unread_count(self):
        self.notification_repo.mark_read = AsyncMock(return_value=self._notification())
        self.notification_repo.count_unread = AsyncMock(return_value=3)

        result = await self.service.mark_read(
            self.session, user_id=2, notification_id=1
        )

        self.notification_repo.mark_read.assert_awaited_once_with(self.session, 1, 2)
        self.assertEqual(result.unread_count, 3)

    async def test_mark_all_read_commits_and_returns_zero(self):
        self.notification_repo.mark_all_read = AsyncMock()
        self.notification_repo.count_unread = AsyncMock(return_value=0)

        result = await self.service.mark_all_read(self.session, user_id=2)

        self.notification_repo.mark_all_read.assert_awaited_once_with(self.session, 2)
        self.assertEqual(result.unread_count, 0)


if __name__ == "__main__":
    unittest.main()
