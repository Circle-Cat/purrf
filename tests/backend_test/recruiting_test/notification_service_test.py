import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, create_autospec

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.event_entity import EventEntity
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

    def _notification(self, event=None, **overrides):
        """A notification row plus the event it points at.

        The event is what the service reads to say what happened, so it is
        stubbed onto the session here rather than left to a bare mock.
        """
        entity = NotificationEntity(
            user_id=overrides.get("user_id", 2),
            event_id=overrides.get("event_id", 5),
            created_at=overrides.get("created_at", datetime.now(timezone.utc)),
        )
        entity.notification_id = overrides.get("notification_id", 1)
        self._stub_event(
            event
            if event is not None
            else self._event(event_type="recruiting.reassigned")
        )
        return entity

    def _event(self, **overrides):
        defaults = dict(
            subject_type="application",
            subject_id=10,
            actor_id=9,
            event_type="recruiting.reassigned",
            details={},
        )
        defaults.update(overrides)
        event = EventEntity(**defaults)
        event.event_id = overrides.get("event_id", 5)
        return event

    def _stub_event(self, event):
        self.session.get = AsyncMock(return_value=event)

    async def test_list_for_user_resolves_application_scoped_display_fields(self):
        row = self._notification()
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
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

    async def test_list_for_user_resolves_job_scoped_display_fields(self):
        row = self._notification(
            event=self._event(
                subject_type="job",
                subject_id=1,
                event_type="recruiting.review_opened",
            )
        )
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=0)
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
        self.assertEqual(item.event_type, "recruiting.review_opened")
        self.assertEqual(item.job_title, "Design Review")
        self.assertEqual(item.applicant_name, "")
        self.app_repo.get_by_id.assert_not_awaited()

    async def test_dismiss_returns_updated_pending_count(self):
        self.notification_repo.dismiss_by_id = AsyncMock(return_value=True)
        self.notification_repo.count_by_user = AsyncMock(return_value=3)

        result = await self.service.dismiss(self.session, user_id=2, notification_id=1)

        self.notification_repo.dismiss_by_id.assert_awaited_once_with(
            self.session, 1, 2
        )
        self.assertEqual(result.unread_count, 3)

    async def test_dismiss_all_commits_and_returns_zero(self):
        self.notification_repo.dismiss_all_by_user = AsyncMock()
        self.notification_repo.count_by_user = AsyncMock(return_value=0)

        result = await self.service.dismiss_all(self.session, user_id=2)

        self.notification_repo.dismiss_all_by_user.assert_awaited_once_with(
            self.session, 2
        )
        self.assertEqual(result.unread_count, 0)

    async def test_list_for_user_carries_job_kind_for_application_scoped_rows(self):
        row = self._notification()
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Mentorship", status=JobStatus.PUBLISHED
        )
        job.job_id = 3
        application = ApplicationEntity(
            job_id=3, user_id=4, stage=ApplicationStage.TECH
        )
        application.application_id = 10
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=UsersEntity(first_name="Ada", last_name="Lovelace")
        )

        result = await self.service.list_for_user(self.session, 2)

        self.assertEqual(result.notifications[0].job_kind, JobKind.ACTIVITY)

    async def test_list_for_user_leaves_job_kind_none_when_the_job_is_missing(self):
        row = self._notification(application_id=None, job_id=7)
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=None)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=None)

        result = await self.service.list_for_user(self.session, 2)

        self.assertIsNone(result.notifications[0].job_kind)

    async def test_resolve_returns_the_dto_and_the_application_stage(self):
        row = self._notification()
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Mentorship", status=JobStatus.PUBLISHED
        )
        job.job_id = 3
        application = ApplicationEntity(
            job_id=3, user_id=4, stage=ApplicationStage.TECH
        )
        application.application_id = 10
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=UsersEntity(first_name="Ada", last_name="Lovelace")
        )

        dto, stage = await self.service.resolve(self.session, row)

        self.assertEqual(dto.job_title, "Mentorship")
        self.assertEqual(stage, ApplicationStage.TECH)
