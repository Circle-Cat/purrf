import unittest
from types import SimpleNamespace

from backend.communication.email_replies import reply_contact, reply_subject


def _in(sender, kind="human"):
    return SimpleNamespace(
        direction="inbound",
        inbound_kind=kind,
        from_address=sender,
        failed_recipients=None,
        to_addresses=None,
    )


def _out(to):
    return SimpleNamespace(
        direction="outbound",
        inbound_kind=None,
        from_address="us@circlecat.org",
        failed_recipients=None,
        to_addresses=to,
    )


class ReplySubjectTest(unittest.TestCase):
    def test_prefixes_re_once(self):
        self.assertEqual(reply_subject("Hello"), "Re: Hello")
        self.assertEqual(reply_subject("  RE: Hello "), "RE: Hello")
        self.assertEqual(reply_subject(None), "Re:")


class ReplyContactTest(unittest.TestCase):
    def test_the_newest_human_sender_wins(self):
        ordered = [
            _in("Ann <Ann@X.com>"),
            _out("ann@x.com"),
            _in("Bo <bo@y.com>"),
            _in("robot@z.com", kind="auto_reply"),
        ]

        self.assertEqual(reply_contact(ordered), "bo@y.com")

    def test_without_human_mail_our_first_recipient(self):
        self.assertEqual(reply_contact([_out("Pat <Pat@Ext.com>, x@y.com")]), "pat@ext.com")

    def test_nobody(self):
        self.assertIsNone(reply_contact([]))
        self.assertIsNone(reply_contact([_in("mailer@x.com", kind="bounce")]))


if __name__ == "__main__":
    unittest.main()
