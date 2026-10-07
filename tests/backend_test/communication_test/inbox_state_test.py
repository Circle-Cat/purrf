import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.communication.inbox_state import is_archived, needs_reply


def _m(direction, minute, kind="human", internal=True):
    at = datetime(2026, 10, 1, 9, minute, tzinfo=timezone.utc)
    return SimpleNamespace(
        direction=direction,
        inbound_kind=kind if direction == "inbound" else None,
        gmail_internal_date=at if internal else None,
        created_at=at,
    )


class InboxStateTest(unittest.TestCase):
    def test_inbound_after_our_reply_needs_reply(self):
        self.assertTrue(
            needs_reply([_m("outbound", 1, internal=False), _m("inbound", 2)], None)
        )

    def test_our_reply_clears_it(self):
        self.assertFalse(
            needs_reply([_m("inbound", 1), _m("outbound", 2, internal=False)], None)
        )

    def test_auto_reply_and_bounce_never_count(self):
        self.assertFalse(
            needs_reply(
                [
                    _m("outbound", 1),
                    _m("inbound", 2, kind="auto_reply"),
                    _m("inbound", 3, kind="bounce"),
                ],
                None,
            )
        )

    def test_archive_hides_until_a_newer_human_message(self):
        archived = datetime(2026, 10, 1, 9, 5, tzinfo=timezone.utc)
        msgs = [_m("inbound", 1)]
        self.assertTrue(is_archived(msgs, archived))
        self.assertFalse(needs_reply(msgs, archived))
        msgs.append(_m("inbound", 9))
        self.assertFalse(is_archived(msgs, archived))
        self.assertTrue(needs_reply(msgs, archived))

    def test_legacy_inbound_without_kind_counts_as_human(self):
        self.assertTrue(needs_reply([_m("inbound", 1, kind=None)], None))
