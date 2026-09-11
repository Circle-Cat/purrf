import unittest
from datetime import datetime, timedelta, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
    NotificationStatus,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
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
                notification recipient. The event every notification here
                points at is created alongside them as ``self.event``.
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
        self.event = EventEntity(
            subject_type="application",
            subject_id=app.application_id,
            actor_id=recipient.user_id,
            event_type="recruiting.mentioned",
            details={},
        )
        await self.insert_entities([self.event])
        return app, recipient

    async def test_create_and_list_by_user(self):
        _app, recipient = await self._seed()
        repo = NotificationRepository()

        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
            ),
        )
        result = await repo.list_by_user(self.session, recipient.user_id)

        self.assertIsNotNone(created.notification_id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].notification_id, created.notification_id)

    async def test_list_by_user_orders_newest_first(self):
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        first = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
            ),
        )
        second = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
            ),
        )

        result = await repo.list_by_user(self.session, recipient.user_id)

        self.assertEqual(
            [n.notification_id for n in result],
            [second.notification_id, first.notification_id],
        )

    async def test_count_by_user_only_counts_that_user(self):
        _app, recipient = await self._seed()
        other = _make_user()
        await self.insert_entities([other])
        repo = NotificationRepository()
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
            ),
        )
        await repo.create(
            self.session,
            NotificationEntity(
                user_id=other.user_id,
                event_id=self.event.event_id,
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
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
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
        _app, recipient = await self._seed()
        other = _make_user()
        await self.insert_entities([other])
        repo = NotificationRepository()
        created = await repo.create(
            self.session,
            NotificationEntity(
                user_id=recipient.user_id,
                event_id=self.event.event_id,
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
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        rows = [
            await repo.create(
                self.session,
                NotificationEntity(
                    user_id=recipient.user_id,
                    event_id=self.event.event_id,
                ),
            )
            for _ in range(2)
        ]

        await repo.dismiss_all_by_user(self.session, recipient.user_id)

        self.assertEqual(await repo.count_by_user(self.session, recipient.user_id), 0)
        for row in rows:
            await self.session.refresh(row)
            self.assertIsNotNone(row.dismissed_at)

    async def _notification(
        self, recipient, *, status=None, claimed_at=None, created_at=None
    ):
        """One notification for ``recipient``, PENDING and created now unless overridden.

        Written field by field rather than through ``create`` because the
        delivery columns are the subject here, and ``create`` cannot set them.
        """
        kwargs = {"user_id": recipient.user_id, "event_id": self.event.event_id}
        if status is not None:
            kwargs["status"] = status
        if claimed_at is not None:
            kwargs["claimed_at"] = claimed_at
        if created_at is not None:
            kwargs["created_at"] = created_at
        row = NotificationEntity(**kwargs)
        await self.insert_entities([row])
        return row

    async def test_get_by_id_returns_the_row(self):
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        created = await self._notification(recipient)

        found = await repo.get_by_id(self.session, created.notification_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.notification_id, created.notification_id)

    async def test_get_by_id_returns_none_for_an_id_that_is_not_there(self):
        await self._seed()
        repo = NotificationRepository()

        self.assertIsNone(await repo.get_by_id(self.session, 999_999))

    async def test_claim_for_sending_takes_a_pending_row(self):
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        row = await self._notification(recipient)
        now = datetime.now(timezone.utc)

        claimed = await repo.claim_for_sending(
            self.session,
            row.notification_id,
            now=now,
            stale_before=now - timedelta(minutes=10),
        )

        self.assertTrue(claimed)
        await self.session.refresh(row)
        self.assertEqual(row.status, NotificationStatus.SENDING)
        self.assertEqual(row.claimed_at, now)

    async def test_claim_for_sending_refuses_a_claim_somebody_still_holds(self):
        """A second sender must not take a row whose claim has not aged out."""
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        held_since = now - timedelta(minutes=1)
        row = await self._notification(
            recipient, status=NotificationStatus.SENDING, claimed_at=held_since
        )

        claimed = await repo.claim_for_sending(
            self.session,
            row.notification_id,
            now=now,
            stale_before=now - timedelta(minutes=10),
        )

        self.assertFalse(claimed)
        await self.session.refresh(row)
        self.assertEqual(row.claimed_at, held_since)

    async def test_claim_for_sending_retakes_a_claim_older_than_the_cutoff(self):
        """A sender that died mid-send would otherwise strand the row forever."""
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        row = await self._notification(
            recipient,
            status=NotificationStatus.SENDING,
            claimed_at=now - timedelta(hours=1),
        )

        claimed = await repo.claim_for_sending(
            self.session,
            row.notification_id,
            now=now,
            stale_before=now - timedelta(minutes=10),
        )

        self.assertTrue(claimed)
        await self.session.refresh(row)
        self.assertEqual(row.claimed_at, now)

    async def test_claim_for_sending_refuses_a_row_that_is_already_settled(self):
        """SENT is terminal; a redelivered message must not send a second copy."""
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        row = await self._notification(recipient, status=NotificationStatus.SENT)

        claimed = await repo.claim_for_sending(
            self.session,
            row.notification_id,
            now=now,
            stale_before=now - timedelta(minutes=10),
        )

        self.assertFalse(claimed)
        await self.session.refresh(row)
        self.assertEqual(row.status, NotificationStatus.SENT)

    async def test_set_status_writes_the_status_and_drops_the_claim(self):
        """Releasing a row back to PENDING has to clear the claim with it.

        A PENDING row still carrying a claimed_at would look to the sweep
        like a live claim and never be retried.
        """
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        row = await self._notification(
            recipient,
            status=NotificationStatus.SENDING,
            claimed_at=datetime.now(timezone.utc),
        )

        await repo.set_status(
            self.session, row.notification_id, NotificationStatus.SENT
        )

        await self.session.refresh(row)
        self.assertEqual(row.status, NotificationStatus.SENT)
        self.assertIsNone(row.claimed_at)

    async def test_list_pending_ids_created_before_returns_oldest_first(self):
        """The oldest straggler has waited longest, so it is republished first."""
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        newer = await self._notification(recipient, created_at=now - timedelta(hours=1))
        older = await self._notification(recipient, created_at=now - timedelta(hours=2))

        ids = await repo.list_pending_ids_created_before(
            self.session, cutoff=now - timedelta(minutes=10), limit=20
        )

        mine = [i for i in ids if i in {newer.notification_id, older.notification_id}]
        self.assertEqual(mine, [older.notification_id, newer.notification_id])

    async def test_list_pending_ids_created_before_skips_rows_that_are_not_pending(
        self,
    ):
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        sending = await self._notification(
            recipient,
            status=NotificationStatus.SENDING,
            created_at=now - timedelta(hours=1),
        )
        sent = await self._notification(
            recipient,
            status=NotificationStatus.SENT,
            created_at=now - timedelta(hours=1),
        )

        ids = await repo.list_pending_ids_created_before(
            self.session, cutoff=now - timedelta(minutes=10), limit=20
        )

        self.assertNotIn(sending.notification_id, ids)
        self.assertNotIn(sent.notification_id, ids)

    async def test_list_pending_ids_created_before_skips_rows_newer_than_the_cutoff(
        self,
    ):
        """A row published seconds ago is still in flight, not a straggler."""
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        fresh = await self._notification(recipient, created_at=now)

        ids = await repo.list_pending_ids_created_before(
            self.session, cutoff=now - timedelta(minutes=10), limit=20
        )

        self.assertNotIn(fresh.notification_id, ids)

    async def test_list_pending_ids_created_before_respects_the_limit(self):
        _app, recipient = await self._seed()
        repo = NotificationRepository()
        now = datetime.now(timezone.utc)
        for hours in (1, 2, 3):
            await self._notification(recipient, created_at=now - timedelta(hours=hours))

        ids = await repo.list_pending_ids_created_before(
            self.session, cutoff=now - timedelta(minutes=10), limit=1
        )

        self.assertEqual(len(ids), 1)


if __name__ == "__main__":
    unittest.main()
