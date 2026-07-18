import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
    NotificationType,
)
from backend.entity.application_comment_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    ApplicationCommentEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    JobReviewEntity,
)
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.notification_repository import NotificationRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestNotificationRepository(BaseRepositoryTestLib):
    async def _seed(self):
        """Create a job, an application, and one recipient user.

        Returns:
            tuple[ApplicationEntity, UsersEntity]: The application and the
                notification recipient.
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        recipient = _make_user()
        await self.insert_entities([job, recipient])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=recipient.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app, recipient

    async def test_create_and_list_by_user(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()

        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.ASSIGNED_TO_EVALUATE,
                application_id=app.application_id,
                round=1,
            ),
        )
        result = await repo.list_by_user(self.session, recipient.user_id)

        self.assertIsNotNone(created.notification_id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].notification_id, created.notification_id)

    async def test_list_by_user_orders_newest_first(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        first = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        second = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )

        result = await repo.list_by_user(self.session, recipient.user_id)

        self.assertEqual(
            [n.notification_id for n in result],
            [second.notification_id, first.notification_id],
        )

    async def test_count_by_user_only_counts_that_user(self):
        app, recipient = await self._seed()
        other = _make_user()
        await self.insert_entities([other])
        repo = NotificationRepository()
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=other.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )

        count = await repo.count_by_user(self.session, recipient.user_id)

        self.assertEqual(count, 1)

    async def test_delete_by_id_removes_the_row_and_returns_true(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )

        deleted = await repo.delete_by_id(
            self.session, created.notification_id, recipient.user_id
        )

        self.assertTrue(deleted)
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)

    async def test_delete_by_id_wrong_user_is_a_no_op(self):
        app, recipient = await self._seed()
        other = _make_user()
        await self.insert_entities([other])
        repo = NotificationRepository()
        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )

        result = await repo.delete_by_id(
            self.session, created.notification_id, other.user_id
        )

        self.assertFalse(result)
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 1)

    async def test_delete_all_by_user_removes_every_row_for_that_user(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.ASSIGNED_TO_EVALUATE,
                application_id=app.application_id,
            ),
        )

        await repo.delete_all_by_user(self.session, recipient.user_id)

        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)


if __name__ == "__main__":
    unittest.main()
