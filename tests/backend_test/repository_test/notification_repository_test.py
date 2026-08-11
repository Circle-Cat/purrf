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
from backend.entity.event_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    EventEntity,
)
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

    async def test_event_shaped_rows_are_returned_by_the_read_paths(self):
        """An event-shaped row has type NULL, and the reader resolves the event.

        The read paths scope on dismissed_at alone: what a notification is
        about is read from the event it points at, so a NULL type is the
        normal shape now rather than a row the bell cannot render. The badge
        counts exactly what the list hands over.

        Email is not checked here: those rows are the only ones the delivery
        pipeline sends, and it claims them itself.
        """
        app, recipient = await self._seed()
        repo = NotificationRepository()
        event = EventEntity(
            subject_type="application",
            subject_id=app.application_id,
            actor_id=recipient.user_id,
            event_type="recruiting.stage_changed",
        )
        await self.insert_entities([event])
        created = await repo.create(
            self.session,
            NotificationEntity(user_id=recipient.user_id, event_id=event.event_id),
        )

        result = await repo.list_by_user(self.session, recipient.user_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].notification_id, created.notification_id)
        self.assertIsNone(result[0].type)
        self.assertEqual(result[0].event_id, event.event_id)
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 1)

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

    async def test_dismiss_by_id_marks_the_row_and_keeps_it(self):
        """Dismissing hides a notification; it must not destroy it.

        The row carries the email state machine, so deleting it on dismiss
        would drop an email that had not gone out yet -- and would erase the
        record of one that had.
        """
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

        dismissed = await repo.dismiss_by_id(
            self.session, created.notification_id, recipient.user_id
        )

        self.assertTrue(dismissed)
        await self.session.refresh(created)
        self.assertIsNotNone(created.dismissed_at)
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)
        self.assertEqual(await repo.list_by_user(self.session, recipient.user_id), [])

    async def test_dismiss_by_id_wrong_user_is_a_no_op(self):
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

        result = await repo.dismiss_by_id(
            self.session, created.notification_id, other.user_id
        )

        self.assertFalse(result)
        await self.session.refresh(created)
        self.assertIsNone(created.dismissed_at)
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 1)

    async def test_dismiss_all_by_user_marks_every_row_and_keeps_them(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        rows = [
            await repo.create(
                self.session,
                NotificationEntity(
                    user_id=recipient.user_id,
                    type=NotificationType.MENTIONED,
                    application_id=app.application_id,
                ),
            )
            for _ in range(2)
        ]

        await repo.dismiss_all_by_user(self.session, recipient.user_id)

        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)
        for row in rows:
            await self.session.refresh(row)
            self.assertIsNotNone(row.dismissed_at)


if __name__ == "__main__":
    unittest.main()
