import json
import unittest
from pathlib import Path

# Importing the app factory imports every module that registers a recipient
# resolver, which is the set the bell can receive.
import backend.utils.fast_app_factory  # noqa: F401
from backend.notification_management import recipient_registry
from backend.recruiting import notification_links

_LISTED = Path("tests/shared/bell_event_types.json")


class TestBellEventTypes(unittest.TestCase):
    def test_the_shared_list_names_every_event_the_bell_can_receive(self):
        """The bell's own test runs every listed type through its wording, so
        an event fanned out to the bell but missing from the list could reach
        users as a line nobody wrote. A listed type with no resolver is a
        stale entry."""
        listed = set(json.loads(_LISTED.read_text(encoding="utf-8")))
        registered = set(recipient_registry._RESOLVERS)

        self.assertEqual(
            sorted(registered - listed), [], "registered but not in the list"
        )
        self.assertEqual(
            sorted(listed - registered), [], "in the list but not registered"
        )

    def test_every_listed_event_has_a_link_decision(self):
        """Each type the bell can receive either has a rule for where its
        reader acts on it or is deliberately linkless. A new type with
        neither has had nobody decide where it leads."""
        listed = set(json.loads(_LISTED.read_text(encoding="utf-8")))
        linked = set(notification_links.LINKED)
        linkless = set(notification_links.LINKLESS)

        self.assertEqual(sorted(linked & linkless), [], "both linked and linkless")
        self.assertEqual(
            sorted(listed - linked - linkless), [], "listed but no link decision"
        )
        self.assertEqual(
            sorted((linked | linkless) - listed),
            [],
            "a link decision for no listed type",
        )


if __name__ == "__main__":
    unittest.main()
