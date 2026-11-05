import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.notification_management import render_registry


class RenderRegistryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = dict(render_registry._RENDERERS)
        render_registry._RENDERERS.clear()

    def tearDown(self):
        render_registry._RENDERERS.clear()
        render_registry._RENDERERS.update(self._saved)

    async def test_registered_renderer_is_called_with_the_event(self):
        event = SimpleNamespace(event_type="demo.thing_happened")

        @render_registry.register_render("demo.thing_happened")
        async def renderer(session, incoming):
            self.assertIs(incoming, event)
            return ("subject", "body")

        subject, body = await render_registry.render(AsyncMock(), event)
        self.assertEqual((subject, body), ("subject", "body"))

    async def test_unregistered_event_type_raises_lookup_error(self):
        """A blank email is worse than a loud failure -- and KeyError is a
        LookupError, so DeliveryService treats it as permanent, not worth
        retrying."""
        event = SimpleNamespace(event_type="recruiting.job_created")

        with self.assertRaises(LookupError):
            await render_registry.render(AsyncMock(), event)

    def test_registering_the_same_event_type_twice_is_an_error(self):
        @render_registry.register_render("demo.once")
        async def first(session, event):
            return ("s", "b")

        with self.assertRaises(ValueError):

            @render_registry.register_render("demo.once")
            async def second(session, event):
                return ("s", "b")


if __name__ == "__main__":
    unittest.main()
