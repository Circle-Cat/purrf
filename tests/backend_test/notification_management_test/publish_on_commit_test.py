import concurrent.futures
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.application_comment_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    ApplicationCommentEntity,
)
from backend.entity.application_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    ApplicationEntity,
)
from backend.entity.job_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    JobEntity,
)
from backend.entity.job_review_entity import (  # noqa: F401 (registers table for NotificationEntity's FK)
    JobReviewEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.notification_management import recipient_registry
from backend.notification_management.event_recorder import record_event
from backend.notification_management.publish_on_commit import (
    install_publish_listener,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a minimal, unsaved user row for use as an actor or recipient.

    Copied from event_recorder_test.py's helper of the same name:
    EventEntity.actor_id and NotificationEntity.user_id are real Postgres
    foreign keys to users.user_id, so a real row is needed rather than a
    hardcoded literal id.
    """
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class PublishOnCommitTest(BaseRepositoryTestLib):
    """Covers install_publish_listener() against a real async Session.

    Uses BaseRepositoryTestLib (per-test connection + outer transaction in
    ``join_transaction_mode="create_savepoint"`` mode, rolled back in
    asyncTearDown) rather than the brief's literal
    ``tests.backend_test.helpers.db.async_session_for_tests`` -- that helper
    does not exist anywhere in this repo (same gap Tasks 2 and 3 hit and
    solved the same way).

    The tests below call ``self.session.commit()`` / ``self.session.rollback()``
    directly, which no earlier test in this repo has done: every prior
    BaseRepositoryTestLib-based test only ever calls ``insert_entities()``
    (a flush) and relies on asyncTearDown's outer rollback for cleanup. That
    matters here because after_commit/after_rollback are SQLAlchemy Session
    events, not Core/DBAPI events -- they fire once per Session.commit() /
    Session.rollback() call regardless of whether the underlying connection
    is doing a real COMMIT or, as here, releasing/rolling back to a
    SAVEPOINT nested inside the test's outer transaction. That is exactly
    what was verified empirically before trusting these tests: see
    task-4-report.md for the confirmation that after_commit fires on
    self.session.commit() and after_rollback (not after_commit) fires on
    self.session.rollback(), even though neither ever reaches a real COMMIT
    at the Postgres level.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._saved = dict(recipient_registry._RESOLVERS)
        recipient_registry._RESOLVERS.clear()
        self.publisher = MagicMock()
        install_publish_listener(self.publisher, "projects/p/topics/t")

    async def asyncTearDown(self):
        recipient_registry._RESOLVERS.clear()
        recipient_registry._RESOLVERS.update(self._saved)
        await super().asyncTearDown()

    async def test_one_message_per_notification_after_commit(self):
        actor = _make_user()
        recipients = [_make_user(), _make_user()]
        await self.insert_entities([actor, *recipients])
        recipient_ids = [user.user_id for user in recipients]

        @recipient_registry.register_recipients("demo.two", subject_type="application")
        async def resolver(session, event):
            return recipient_ids

        _, notifications = await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.two",
        )
        self.publisher.publish.assert_not_called()
        await self.session.commit()

        published = [
            json.loads(call.args[1]) for call in self.publisher.publish.call_args_list
        ]
        self.assertCountEqual(
            published,
            [{"notification_id": n.notification_id} for n in notifications],
        )

    async def test_rollback_publishes_nothing(self):
        """Rollback must fire after_rollback, not after_commit.

        This is the test that would pass vacuously if the listener never
        fired at all, so it is written to fail loudly if that happens:
        without record_event actually writing a notification row first,
        "the publisher was never called" would be true for the wrong
        reason. Here a real notification is created and flushed, then the
        transaction is genuinely rolled back -- the discard listener must
        pop the pending id off session.info so it can never leak into a
        later commit of this same session.
        """
        actor = _make_user()
        recipient = _make_user()
        await self.insert_entities([actor, recipient])

        @recipient_registry.register_recipients(
            "demo.rollback", subject_type="application"
        )
        async def resolver(session, event):
            return [recipient.user_id]

        await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.rollback",
        )
        self.assertIn("pending_notification_ids", self.session.info)
        await self.session.rollback()

        # The rollback listener must have discarded the id: nothing left to
        # leak into a later commit of this same session.
        self.assertNotIn("pending_notification_ids", self.session.info)
        self.publisher.publish.assert_not_called()

    async def test_a_publish_failure_does_not_break_the_request(self):
        """The row stays pending and the ride-along sweep picks it up later."""
        self.publisher.publish.side_effect = RuntimeError("pubsub down")
        actor = _make_user()
        recipient = _make_user()
        await self.insert_entities([actor, recipient])

        @recipient_registry.register_recipients("demo.boom", subject_type="application")
        async def resolver(session, event):
            return [recipient.user_id]

        await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.boom",
        )
        await self.session.commit()  # must not raise
        self.publisher.publish.assert_called_once()

    async def test_a_future_failure_is_logged_with_the_notification_id(self):
        """The dominant real Pub/Sub failures land on the Future, not the call.

        publish() returning without raising is not proof of delivery -- it
        only means the message was queued for batching.
        PublisherClient.publish() surfaces missing-topic, IAM-denied, and
        network errors on the returned Future well after the call returns,
        so a mock that merely fails synchronously (as
        test_a_publish_failure_does_not_break_the_request does) never
        exercises this path at all. This test returns an already-failed
        Future instead -- add_done_callback() on an already-done Future
        runs the callback immediately, so the failure must show up in the
        logs by the time commit() returns.

        A test that only checked add_done_callback() was *called* would
        pass even if the callback silently discarded the error; asserting
        on assertLogs' captured output is what proves a trace is actually
        left behind.
        """
        actor = _make_user()
        recipient = _make_user()
        await self.insert_entities([actor, recipient])

        failed_future = concurrent.futures.Future()
        failed_future.set_exception(RuntimeError("NOT_FOUND: Topic not found"))
        self.publisher.publish.return_value = failed_future

        @recipient_registry.register_recipients(
            "demo.future_boom", subject_type="application"
        )
        async def resolver(session, event):
            return [recipient.user_id]

        _, notifications = await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.future_boom",
        )
        notification_id = notifications[0].notification_id

        with self.assertLogs(level="ERROR") as logs:
            await self.session.commit()  # must not raise

        self.assertTrue(
            any(str(notification_id) in message for message in logs.output),
            f"expected notification id {notification_id} in logged output: "
            f"{logs.output}",
        )

    async def test_repeated_install_replaces_rather_than_stacks(self):
        """A second install_publish_listener() call must not double-publish.

        asyncSetUp already installed a listener bound to self.publisher.
        Installing two more here, each with a fresh mock, must leave exactly
        one listener active -- the last one installed -- rather than three
        listeners all firing on the same commit. If install_publish_listener
        stacked instead of replacing, the *first* mock (self.publisher, since
        it was registered earliest) would win every time, and second_publisher
        below would never see a call.
        """
        first_publisher = MagicMock()
        second_publisher = MagicMock()
        install_publish_listener(first_publisher, "projects/p/topics/first")
        install_publish_listener(second_publisher, "projects/p/topics/second")

        actor = _make_user()
        recipient = _make_user()
        await self.insert_entities([actor, recipient])

        @recipient_registry.register_recipients(
            "demo.dedup", subject_type="application"
        )
        async def resolver(session, event):
            return [recipient.user_id]

        await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.dedup",
        )
        await self.session.commit()

        self.publisher.publish.assert_not_called()
        first_publisher.publish.assert_not_called()
        second_publisher.publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
