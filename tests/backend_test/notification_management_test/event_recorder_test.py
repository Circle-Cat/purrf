from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import NotificationStatus
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
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a minimal, unsaved user row for use as an actor or recipient."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class EventRecorderTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._saved = dict(recipient_registry._RESOLVERS)
        recipient_registry._RESOLVERS.clear()

    async def asyncTearDown(self):
        recipient_registry._RESOLVERS.clear()
        recipient_registry._RESOLVERS.update(self._saved)
        await super().asyncTearDown()

    async def test_writes_one_event_and_one_notification_per_recipient(self):
        actor = _make_user()
        recipients = [_make_user(), _make_user(), _make_user()]
        await self.insert_entities([actor, *recipients])
        recipient_ids = [user.user_id for user in recipients]

        @recipient_registry.register_recipients("demo.three")
        async def resolver(session, event):
            return recipient_ids

        event, notifications = await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.three",
            details={"to": recipient_ids[0]},
        )

        self.assertIsNotNone(event.event_id)
        self.assertEqual(len(notifications), 3)
        self.assertEqual({n.user_id for n in notifications}, set(recipient_ids))
        self.assertTrue(
            all(n.status == NotificationStatus.PENDING for n in notifications)
        )
        self.assertTrue(all(n.event_id == event.event_id for n in notifications))

    async def test_actor_never_notifies_themselves(self):
        actor = _make_user()
        other = _make_user()
        await self.insert_entities([actor, other])

        @recipient_registry.register_recipients("demo.includes_actor")
        async def resolver(session, event):
            return [other.user_id, actor.user_id]

        _, notifications = await record_event(
            self.session,
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.includes_actor",
        )
        self.assertEqual({n.user_id for n in notifications}, {other.user_id})

    async def test_event_row_is_written_when_no_resolver_is_registered(self):
        """An unregistered type still lands on the timeline, notifying nobody.

        Which production types are deliberately silent is asserted against the
        real registry in ``recipient_resolvers_test``; this covers only what
        ``record_event`` does when nothing resolves.
        """
        actor = _make_user()
        await self.insert_entities([actor])
        self.assertNotIn("demo.unregistered", recipient_registry._RESOLVERS)

        event, notifications = await record_event(
            self.session,
            subject_type="job",
            subject_id=3,
            actor_id=actor.user_id,
            event_type="demo.unregistered",
        )
        self.assertIsNotNone(event.event_id)
        self.assertEqual(notifications, [])

    async def test_details_defaults_to_an_empty_dict_not_none(self):
        actor = _make_user()
        await self.insert_entities([actor])

        event, _ = await record_event(
            self.session,
            subject_type="job",
            subject_id=3,
            actor_id=actor.user_id,
            event_type="demo.unregistered",
        )
        self.assertEqual(event.details, {})


if __name__ == "__main__":
    import unittest

    unittest.main()
