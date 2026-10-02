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
from backend.repository.event_repository import EventRepository
from backend.repository.job_repository import JobRepository
from backend.repository.notification_repository import NotificationRepository
from backend.repository.users_repository import UsersRepository


class TestRecruitingNotificationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.notification_repo = create_autospec(NotificationRepository, instance=True)
        self.app_repo = create_autospec(ApplicationRepository, instance=True)
        self.job_repo = create_autospec(JobRepository, instance=True)
        self.users_repo = create_autospec(UsersRepository, instance=True)
        self.event_repo = create_autospec(EventRepository, instance=True)
        self.session = AsyncMock()
        self.service = RecruitingNotificationService(
            self.notification_repo,
            self.app_repo,
            self.job_repo,
            self.users_repo,
            self.event_repo,
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
        self.event_repo.get_by_ids = AsyncMock(return_value=[event])

    def _stub_users(self, *users):
        self.users_repo.get_all_by_ids = AsyncMock(return_value=list(users))

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
        self.app_repo.get_by_ids = AsyncMock(return_value=[application])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        applicant = UsersEntity(first_name="Ada", last_name="Lovelace")
        applicant.user_id = 3
        actor = UsersEntity(first_name="Grace", last_name="Hopper")
        actor.user_id = 9

        self._stub_users(applicant, actor)

        result = await self.service.list_for_user(self.session, user_id=2)

        self.assertEqual(result.unread_count, 1)
        self.assertEqual(len(result.notifications), 1)
        item = result.notifications[0]
        self.assertEqual(item.job_title, "Backend Engineer")
        self.assertEqual(item.applicant_name, "Ada Lovelace")
        self.assertEqual(item.actor_name, "Grace Hopper")

    async def test_list_for_user_names_the_person_a_user_scoped_event_is_about(self):
        """A block-request event is about a person, not an application, so the
        bell has to resolve its subject or the line has nobody in it.

        Named the way the email about the same event names them -- preferred
        first -- so the two channels never disagree about who this is.
        """
        row = self._notification(
            event=self._event(
                subject_type="user",
                subject_id=3,
                actor_id=9,
                event_type="user.block_request_decided",
                details={"requestId": 12, "approved": False},
            )
        )
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
        target = UsersEntity(
            first_name="Ada", last_name="Lovelace", preferred_name="Addy"
        )
        target.user_id = 3
        actor = UsersEntity(
            first_name="Grace", last_name="Hopper", preferred_name="Amazing Grace"
        )
        actor.user_id = 9

        self._stub_users(target, actor)

        result = await self.service.list_for_user(self.session, user_id=2)

        item = result.notifications[0]
        self.assertEqual(item.subject_name, "Addy")
        self.assertEqual(item.actor_name, "Amazing Grace")
        # The application fields stay empty: there is no application here, and
        # filling them from the subject would name the same person twice under
        # two different rules.
        self.assertEqual(item.applicant_name, "")
        self.assertEqual(item.job_title, "")

    async def test_subject_name_is_blank_for_an_application_scoped_event(self):
        """The field answers "who is this event about" only where the subject
        is a person. An application-scoped row leaves it empty rather than
        resolving the applicant a second time under the colleague rule."""
        row = self._notification()
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
        self.app_repo.get_by_ids = AsyncMock(return_value=[])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[])
        actor = UsersEntity(first_name="Grace", last_name="Hopper")
        actor.user_id = 9
        self._stub_users(actor)

        result = await self.service.list_for_user(self.session, user_id=2)

        self.assertEqual(result.notifications[0].subject_name, "")

    async def test_list_for_user_names_the_actor_by_preferred_and_applicant_legally(
        self,
    ):
        """The bell names a colleague by preference, the candidate legally."""
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
        self.app_repo.get_by_ids = AsyncMock(return_value=[application])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        applicant = UsersEntity(
            first_name="Ada", last_name="Lovelace", preferred_name="Addy"
        )
        applicant.user_id = 3
        actor = UsersEntity(
            first_name="Grace", last_name="Hopper", preferred_name="Amazing Grace"
        )
        actor.user_id = 9

        self._stub_users(applicant, actor)

        item = (
            await self.service.list_for_user(self.session, user_id=2)
        ).notifications[0]

        self.assertEqual(item.applicant_name, "Ada Lovelace")
        self.assertEqual(item.actor_name, "Amazing Grace")

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
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        actor = UsersEntity(first_name="Grace", last_name="Hopper")
        actor.user_id = 9
        self._stub_users(actor)

        result = await self.service.list_for_user(self.session, user_id=2)

        item = result.notifications[0]
        self.assertEqual(item.event_type, "recruiting.review_opened")
        self.assertEqual(item.job_title, "Design Review")
        self.assertEqual(item.applicant_name, "")
        self.app_repo.get_by_ids.assert_not_awaited()

    def _row(self, notification_id, event_id):
        row = NotificationEntity(
            user_id=2, event_id=event_id, created_at=datetime.now(timezone.utc)
        )
        row.notification_id = notification_id
        return row

    def _per_row_getters(self):
        return [
            self.event_repo.get_by_id,
            self.app_repo.get_by_id,
            self.job_repo.get_by_job_id,
            self.users_repo.get_user_by_user_id,
        ]

    async def test_list_for_user_loads_each_kind_once_for_mixed_rows(self):
        """Three rows of three subject types, two actors: one load per kind."""
        events = [
            self._event(
                event_id=1, subject_type="application", subject_id=10, actor_id=8
            ),
            self._event(event_id=2, subject_type="job", subject_id=1, actor_id=9),
            self._event(
                event_id=3,
                subject_type="user",
                subject_id=3,
                actor_id=9,
                event_type="user.block_request_decided",
            ),
        ]
        rows = [self._row(n, n) for n in (1, 2, 3)]
        self.notification_repo.list_by_user = AsyncMock(return_value=rows)
        self.notification_repo.count_by_user = AsyncMock(return_value=3)
        self.event_repo.get_by_ids = AsyncMock(return_value=events)
        application = ApplicationEntity(
            job_id=1, user_id=4, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.application_id = 10
        self.app_repo.get_by_ids = AsyncMock(return_value=[application])
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Mentorship", status=JobStatus.PUBLISHED
        )
        job.job_id = 1
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        users = []
        for user_id, first in ((3, "Tara"), (4, "Ada"), (8, "Bea"), (9, "Cy")):
            user = UsersEntity(first_name=first, last_name="X")
            user.user_id = user_id
            users.append(user)
        self._stub_users(*users)

        result = await self.service.list_for_user(self.session, user_id=2)

        for loader in (
            self.event_repo.get_by_ids,
            self.app_repo.get_by_ids,
            self.job_repo.get_by_job_ids,
            self.users_repo.get_all_by_ids,
        ):
            loader.assert_awaited_once()
        for getter in self._per_row_getters():
            getter.assert_not_awaited()
        app_item, job_item, user_item = result.notifications
        self.assertEqual(
            (app_item.applicant_name, app_item.job_title, app_item.actor_name),
            ("Ada X", "Mentorship", "Bea X"),
        )
        self.assertEqual(
            (job_item.job_title, job_item.actor_name), ("Mentorship", "Cy X")
        )
        self.assertEqual(
            (user_item.subject_name, user_item.actor_name), ("Tara X", "Cy X")
        )

    async def test_list_for_user_asks_for_a_shared_application_once(self):
        """Twenty rows about one application ask for that one id, once."""
        rows = [self._row(n, n) for n in range(1, 21)]
        self.notification_repo.list_by_user = AsyncMock(return_value=rows)
        self.notification_repo.count_by_user = AsyncMock(return_value=20)
        self.event_repo.get_by_ids = AsyncMock(
            return_value=[self._event(event_id=n, subject_id=10) for n in range(1, 21)]
        )
        self.app_repo.get_by_ids = AsyncMock(return_value=[])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[])
        self._stub_users()

        result = await self.service.list_for_user(self.session, user_id=2)

        self.assertEqual(len(result.notifications), 20)
        self.app_repo.get_by_ids.assert_awaited_once()
        self.assertEqual(list(self.app_repo.get_by_ids.await_args.args[1]), [10])

    async def test_list_for_user_renders_a_row_whose_event_is_gone_as_blank(self):
        rows = [self._row(1, 1), self._row(2, 2)]
        self.notification_repo.list_by_user = AsyncMock(return_value=rows)
        self.notification_repo.count_by_user = AsyncMock(return_value=2)
        self.event_repo.get_by_ids = AsyncMock(
            return_value=[
                self._event(
                    event_id=2,
                    subject_type="job",
                    subject_id=1,
                    event_type="recruiting.review_opened",
                )
            ]
        )
        self.app_repo.get_by_ids = AsyncMock(return_value=[])
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Design Review", status=JobStatus.DRAFT
        )
        job.job_id = 1
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        self._stub_users()

        gone, kept = (
            await self.service.list_for_user(self.session, user_id=2)
        ).notifications

        self.assertEqual((gone.event_type, gone.job_title, gone.details), ("", "", {}))
        self.assertIsNone(gone.actor_name)
        self.assertEqual(
            (kept.event_type, kept.job_title),
            ("recruiting.review_opened", "Design Review"),
        )

    async def test_list_for_user_with_no_rows_loads_nothing(self):
        self.notification_repo.list_by_user = AsyncMock(return_value=[])
        self.notification_repo.count_by_user = AsyncMock(return_value=0)

        result = await self.service.list_for_user(self.session, user_id=2)

        self.assertEqual(result.notifications, [])
        for loader in (
            self.event_repo.get_by_ids,
            self.app_repo.get_by_ids,
            self.job_repo.get_by_job_ids,
            self.users_repo.get_all_by_ids,
        ):
            loader.assert_not_awaited()

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
        self.app_repo.get_by_ids = AsyncMock(return_value=[application])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[job])
        applicant = UsersEntity(first_name="Ada", last_name="Lovelace")
        applicant.user_id = 4
        self._stub_users(applicant)

        result = await self.service.list_for_user(self.session, 2)

        self.assertEqual(result.notifications[0].job_kind, JobKind.ACTIVITY)

    async def test_list_for_user_leaves_job_kind_none_when_the_job_is_missing(self):
        row = self._notification()
        self.notification_repo.list_by_user = AsyncMock(return_value=[row])
        self.notification_repo.count_by_user = AsyncMock(return_value=1)
        application = ApplicationEntity(
            job_id=7, user_id=4, stage=ApplicationStage.TECH
        )
        application.application_id = 10
        self.app_repo.get_by_ids = AsyncMock(return_value=[application])
        self.job_repo.get_by_job_ids = AsyncMock(return_value=[])
        self._stub_users()

        result = await self.service.list_for_user(self.session, 2)

        self.assertIsNone(result.notifications[0].job_kind)


if __name__ == "__main__":
    unittest.main()
