import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.communication.inbox_state import (
    is_archived,
    is_bounce,
    is_human_inbound,
    needs_reply,
)


def _at(minute):
    return datetime(2026, 10, 1, 9, minute, tzinfo=timezone.utc)


def _m(direction, minute, kind="human", internal=True, stored=None, failed=None):
    at = _at(minute)
    return SimpleNamespace(
        direction=direction,
        inbound_kind=kind if direction == "inbound" else None,
        gmail_internal_date=at if internal else None,
        created_at=_at(stored) if stored is not None else at,
        failed_recipients=failed,
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

    def test_mail_dated_before_the_archive_but_stored_after_it_reopens_the_thread(
        self,
    ):
        late = [_m("inbound", 1, stored=9)]
        self.assertFalse(is_archived(late, _at(5)))
        self.assertTrue(needs_reply(late, _at(5)))

    def test_mail_dated_after_the_archive_but_stored_before_it_stays_archived(self):
        msgs = [_m("inbound", 9, stored=4)]
        self.assertTrue(is_archived(msgs, _at(5)))
        self.assertFalse(needs_reply(msgs, _at(5)))

    def test_mail_dated_before_our_reply_but_stored_after_it_needs_reply(self):
        msgs = [_m("outbound", 5, internal=False), _m("inbound", 1, stored=9)]
        self.assertTrue(needs_reply(msgs, None))

    def test_mail_stored_before_our_reply_is_answered_whatever_its_date(self):
        msgs = [_m("outbound", 5, internal=False), _m("inbound", 9, stored=4)]
        self.assertFalse(needs_reply(msgs, None))

    def test_legacy_inbound_with_failed_recipients_is_a_bounce(self):
        legacy = _m("inbound", 1, kind=None, failed="asker@ext.com")
        self.assertTrue(is_bounce(legacy))
        self.assertFalse(is_human_inbound(legacy))
        self.assertFalse(needs_reply([legacy], None))

    def test_legacy_bounce_naming_nobody_is_still_a_bounce(self):
        self.assertTrue(is_bounce(_m("inbound", 1, kind=None, failed="")))

    def test_classified_kind_wins_over_failed_recipients(self):
        self.assertTrue(is_bounce(_m("inbound", 1, kind="bounce")))
        self.assertFalse(is_bounce(_m("inbound", 1, kind="auto_reply", failed="x")))
        self.assertTrue(is_human_inbound(_m("inbound", 1, kind="human", failed="x")))
        self.assertFalse(is_bounce(_m("outbound", 1)))
        self.assertTrue(is_human_inbound(_m("inbound", 1, kind=None)))
