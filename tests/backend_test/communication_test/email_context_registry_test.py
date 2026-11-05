import unittest

from backend.communication.email_context_registry import EmailContextRegistry


class TestEmailContextRegistry(unittest.TestCase):
    def test_get_returns_the_registered_handler(self):
        registry, handler = EmailContextRegistry(), object()
        registry.register("application", handler)
        self.assertIs(registry.get("application"), handler)

    def test_handlers_lists_every_registered_handler(self):
        registry, first, second = EmailContextRegistry(), object(), object()
        registry.register("application", first)
        registry.register("activity", second)
        self.assertEqual(registry.handlers(), [first, second])

    def test_unregistered_context_is_none(self):
        self.assertIsNone(EmailContextRegistry().get("activity"))

    def test_registering_twice_is_refused(self):
        registry = EmailContextRegistry()
        registry.register("application", object())
        with self.assertRaises(ValueError):
            registry.register("application", object())


if __name__ == "__main__":
    unittest.main()
