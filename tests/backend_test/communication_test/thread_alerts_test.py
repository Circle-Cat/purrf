import unittest
from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

from backend.common.communication_enums import EmailDirection, InboundKind
from backend.communication.thread_alerts import BounceAlert, alerts_after_sync

_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
_ids = count(1)
_THREAD = SimpleNamespace(thread_id=70, subject="Hi", archived_at=None)


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


def _in(minutes, kind=InboundKind.HUMAN, sender="ann@x.com", failed=None):
    return SimpleNamespace(
        message_id=next(_ids),
        direction=EmailDirection.INBOUND,
        inbound_kind=kind,
        from_address=sender,
        to_addresses=None,
        subject="Re: Hi",
        gmail_internal_date=_at(minutes),
        created_at=_at(minutes + 1),
        failed_recipients=failed,
        sent_by_user_id=None,
    )


def _out(minutes, sent_by=None, subject="Hi"):
    return SimpleNamespace(
        message_id=next(_ids),
        direction=EmailDirection.OUTBOUND,
        inbound_kind=None,
        from_address="us@circlecat.org",
        to_addresses="ann@x.com",
        subject=subject,
        gmail_internal_date=None,
        created_at=_at(minutes),
        failed_recipients=None,
        sent_by_user_id=sent_by,
    )


class AlertsAfterSyncTest(unittest.TestCase):
    def _alerts(self, existing, new):
        return alerts_after_sync(_THREAD, existing + new, new)

    def test_the_first_unanswered_human_mail_tips_the_thread(self):
        alerts = self._alerts(
            [_out(0, sent_by=9)],
            [_in(5, sender="first@x.com"), _in(6, sender="last@x.com")],
        )

        self.assertEqual(alerts.needs_reply_from, "last@x.com")
        self.assertEqual(alerts.bounces, [])

    def test_a_thread_already_waiting_does_not_tip_again(self):
        self.assertIsNone(self._alerts([_in(0)], [_in(5)]).needs_reply_from)

    def test_a_bounce_names_the_newest_earlier_send_and_its_sender(self):
        alerts = self._alerts(
            [_out(0, sent_by=8, subject="Old"), _out(10, sent_by=None, subject="New")],
            [
                _in(
                    20,
                    kind=InboundKind.BOUNCE,
                    sender="mailer@x.com",
                    failed="Ann <ann@x.com>",
                )
            ],
        )

        self.assertEqual(
            alerts.bounces,
            [BounceAlert(bounced_to="ann@x.com", subject="New", sender_user_id=None)],
        )
        self.assertIsNone(alerts.needs_reply_from)

    def test_a_bounce_before_any_send_is_not_an_alert(self):
        alerts = self._alerts(
            [], [_in(5, kind=InboundKind.BOUNCE, failed="a@x.com")]
        )

        self.assertEqual(alerts.bounces, [])


if __name__ == "__main__":
    unittest.main()
