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

    async def test_event_shaped_rows_are_left_out_of_the_read_paths(self):
        """An event-shaped row has type NULL, and every renderer reads type.

        Returned rather than skipped, one such row fails the whole list -- the
        user's bell breaks instead of one entry going missing -- and the badge
        would promise a row the list cannot hand over. They become visible
        when a renderer that reads the event exists.
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
        await repo.create(
            self.session,
            NotificationEntity(user_id=recipient.user_id, event_id=event.event_id),
        )

        self.assertEqual(await repo.list_by_user(self.session, recipient.user_id), [])
        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)
        self.assertEqual(await repo.claim_unemailed(self.session, 10), [])

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

    async def test_claim_unemailed_returns_only_unstamped_rows(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        unsent = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        already_sent = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
                email_sent_at=datetime.now(timezone.utc),
            ),
        )

        claimed = await repo.claim_unemailed(self.session, 10)

        ids = [row.notification_id for row in claimed]
        self.assertIn(unsent.notification_id, ids)
        self.assertNotIn(already_sent.notification_id, ids)

    async def test_claim_unemailed_returns_oldest_first(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        first = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
        second = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
                created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
        )

        claimed = await repo.claim_unemailed(self.session, 10)

        self.assertEqual(
            [row.notification_id for row in claimed],
            [first.notification_id, second.notification_id],
        )

    async def test_claim_unemailed_honours_the_limit(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        for _ in range(3):
            await repo.create(
                self.session,
                NotificationEntity(
                    user_id=recipient.user_id,
                    type=NotificationType.MENTIONED,
                    application_id=app.application_id,
                ),
            )

        claimed = await repo.claim_unemailed(self.session, 2)

        self.assertEqual(len(claimed), 2)

    async def test_mark_emailed_stamps_the_named_rows_only(self):
        app, recipient = await self._seed()
        repo = NotificationRepository()
        stamped = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        untouched = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                type=NotificationType.MENTIONED,
                application_id=app.application_id,
            ),
        )
        sent_at = datetime.now(timezone.utc)

        await repo.mark_emailed(self.session, [stamped.notification_id], sent_at)

        remaining = [
            row.notification_id for row in await repo.claim_unemailed(self.session, 10)
        ]
        self.assertNotIn(stamped.notification_id, remaining)
        self.assertIn(untouched.notification_id, remaining)

    async def test_mark_emailed_is_a_no_op_for_an_empty_id_list(self):
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

        await repo.mark_emailed(self.session, [], datetime.now(timezone.utc))

        self.assertEqual(len(await repo.claim_unemailed(self.session, 10)), 1)


if __name__ == "__main__":
    unittest.main()
