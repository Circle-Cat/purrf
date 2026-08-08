import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.notification_management import recipient_registry


class RecipientRegistryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = dict(recipient_registry._RESOLVERS)
        recipient_registry._RESOLVERS.clear()

    def tearDown(self):
        recipient_registry._RESOLVERS.clear()
        recipient_registry._RESOLVERS.update(self._saved)

    async def test_registered_resolver_is_called_with_the_event(self):
        event = SimpleNamespace()

        @recipient_registry.register_recipients("demo.thing_happened")
        async def resolver(session, incoming):
            self.assertIs(incoming, event)
            return [7, 9]

        recipients = await recipient_registry.resolve_recipients(
            AsyncMock(), _event("demo.thing_happened", event)
        )
        self.assertEqual(recipients, {7, 9})

    async def test_unregistered_event_type_yields_no_recipients(self):
        """An event nobody needs to know about still writes an event row."""
        recipients = await recipient_registry.resolve_recipients(
            AsyncMock(), _event("recruiting.job_created")
        )
        self.assertEqual(recipients, set())

    async def test_duplicate_recipients_collapse(self):
        @recipient_registry.register_recipients("demo.dup")
        async def resolver(session, event):
            return [7, 7, 9]

        recipients = await recipient_registry.resolve_recipients(
            AsyncMock(), _event("demo.dup")
        )
        self.assertEqual(recipients, {7, 9})

    def test_registering_the_same_event_type_twice_is_an_error(self):
        @recipient_registry.register_recipients("demo.once")
        async def first(session, event):
            return []

        with self.assertRaises(ValueError):

            @recipient_registry.register_recipients("demo.once")
            async def second(session, event):
                return []


def _event(event_type, identity=None):
    class _Stub:
        pass

    stub = identity if identity is not None else _Stub()
    stub.event_type = event_type
    return stub


if __name__ == "__main__":
    unittest.main()
