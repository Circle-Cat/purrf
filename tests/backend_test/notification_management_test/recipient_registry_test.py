import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.notification_management import recipient_registry


def _event(event_type, subject_type="demo", subject_id=1):
    """Build a stand-in carrying only the columns resolve_recipients reads.

    Args:
        event_type (str): Domain-prefixed type to resolve.
        subject_type (str): What the subject id points at.
        subject_id (int): Primary key of that subject.

    Returns:
        SimpleNamespace: The stand-in event.
    """
    return SimpleNamespace(
        event_type=event_type, subject_type=subject_type, subject_id=subject_id
    )


class RecipientRegistryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = dict(recipient_registry._RESOLVERS)
        recipient_registry._RESOLVERS.clear()

    def tearDown(self):
        recipient_registry._RESOLVERS.clear()
        recipient_registry._RESOLVERS.update(self._saved)

    async def test_registered_resolver_is_called_with_the_event(self):
        event = _event("demo.thing_happened")

        @recipient_registry.register_recipients(
            "demo.thing_happened", subject_type="demo"
        )
        async def resolver(session, incoming):
            self.assertIs(incoming, event)
            return [7, 9]

        recipients = await recipient_registry.resolve_recipients(AsyncMock(), event)
        self.assertEqual(recipients, {7, 9})

    async def test_unregistered_event_type_yields_no_recipients(self):
        """An event nobody needs to know about still writes an event row."""
        recipients = await recipient_registry.resolve_recipients(
            AsyncMock(), _event("recruiting.job_created")
        )
        self.assertEqual(recipients, set())

    async def test_duplicate_recipients_collapse(self):
        @recipient_registry.register_recipients("demo.dup", subject_type="demo")
        async def resolver(session, event):
            return [7, 7, 9]

        recipients = await recipient_registry.resolve_recipients(
            AsyncMock(), _event("demo.dup")
        )
        self.assertEqual(recipients, {7, 9})

    async def test_subject_type_the_resolver_does_not_expect_is_an_error(self):
        """Reading subject_id as an id of the wrong table resolves the wrong people."""
        resolver = AsyncMock(return_value=[7])
        recipient_registry.register_recipients("demo.scoped", subject_type="job")(
            resolver
        )

        with self.assertRaises(ValueError):
            await recipient_registry.resolve_recipients(
                AsyncMock(), _event("demo.scoped", subject_type="application")
            )
        resolver.assert_not_awaited()

    def test_registering_the_same_event_type_twice_is_an_error(self):
        @recipient_registry.register_recipients("demo.once", subject_type="demo")
        async def first(session, event):
            return []

        with self.assertRaises(ValueError):

            @recipient_registry.register_recipients("demo.once", subject_type="demo")
            async def second(session, event):
                return []


if __name__ == "__main__":
    unittest.main()
