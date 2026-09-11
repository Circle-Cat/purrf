import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.event_entity import EventEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.event_repository import EventRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a minimal, unsaved user row to act as an event's actor."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestEventRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = EventRepository()

    async def _event(self) -> EventEntity:
        """One event with a real actor, since actor_id is an FK on users."""
        actor = _make_user()
        await self.insert_entities([actor])
        event = EventEntity(
            subject_type="application",
            subject_id=7,
            actor_id=actor.user_id,
            event_type="demo.thing",
            details={},
        )
        await self.insert_entities([event])
        return event

    async def test_get_by_id_returns_the_event(self):
        event = await self._event()

        found = await self.repo.get_by_id(self.session, event.event_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.event_id, event.event_id)
        self.assertEqual(found.event_type, "demo.thing")
        self.assertEqual(found.subject_id, 7)

    async def test_get_by_id_returns_none_for_an_id_that_is_not_there(self):
        """The email side leans on the FK for this never happening.

        The bell side does not -- it renders empty display fields instead --
        so the method has to answer rather than raise.
        """
        self.assertIsNone(await self.repo.get_by_id(self.session, 999_999))


if __name__ == "__main__":
    unittest.main()
