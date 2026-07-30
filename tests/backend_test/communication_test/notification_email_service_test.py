import unittest
from unittest.mock import MagicMock

from backend.communication.notification_email_service import (
    NotificationEmailService,
)


class TestNotificationEmailService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = MagicMock()
        self.gmail.send_message = MagicMock(
            return_value={
                "gmail_message_id": "m1",
                "gmail_thread_id": "t1",
                "rfc822_message_id": "<r1>",
            }
        )
        self.logger = MagicMock()
        self.service = NotificationEmailService(
            gmail_client=self.gmail,
            logger=self.logger,
            sender_address="notifications-test@circlecat.org",
        )

    async def test_send_uses_the_notification_sender_and_no_cc(self):
        sent = await self.service.send("a@b.com", "Subject", "<p>Body</p>")

        self.assertTrue(sent)
        _, kwargs = self.gmail.send_message.call_args
        self.assertEqual(kwargs["sender"], "notifications-test@circlecat.org")
        self.assertEqual(kwargs["to"], ["a@b.com"])
        self.assertEqual(kwargs["cc"], [])
        self.assertEqual(kwargs["subject"], "Subject")
        self.assertEqual(kwargs["body"], "<p>Body</p>")

    async def test_send_swallows_a_gmail_failure_and_logs_it(self):
        self.gmail.send_message = MagicMock(side_effect=RuntimeError("boom"))

        sent = await self.service.send("a@b.com", "Subject", "<p>Body</p>")

        self.assertFalse(sent)
        self.logger.error.assert_called_once()
        # The recipient must be in the log line -- a silent drop with no way
        # to tell who missed their notification is not debuggable.
        self.assertIn("a@b.com", str(self.logger.error.call_args))

    async def test_send_does_not_start_a_thread_or_reply(self):
        await self.service.send("a@b.com", "Subject", "<p>Body</p>")

        _, kwargs = self.gmail.send_message.call_args
        self.assertIsNone(kwargs.get("thread_id"))
        self.assertIsNone(kwargs.get("in_reply_to"))


if __name__ == "__main__":
    unittest.main()
