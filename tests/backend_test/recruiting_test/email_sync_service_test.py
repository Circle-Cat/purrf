import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType, EmailDirection
from backend.recruiting.email_sync_service import EmailSyncService

RECEIVED_AT = datetime(2023, 5, 6, 7, 8, tzinfo=timezone.utc)


def _message(direction, subject="Re: Hello"):
    return SimpleNamespace(
        direction=direction,
        subject=subject,
        from_address="cand@x",
        to_addresses="recruiting@corp.com",
        cc_addresses="boss@x",
        thread_id=10,
        gmail_internal_date=RECEIVED_AT,
    )


class TestSyncApplication(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conversation_service = AsyncMock()
        self.conversation_service.sync_context = AsyncMock(return_value=[])
        self.activity_repo = AsyncMock()
        self.session = Mock()
        self.service = EmailSyncService(
            email_conversation_service=self.conversation_service,
            application_activity_repository=self.activity_repo,
        )
        self.application = SimpleNamespace(application_id=7, user_id=5)

    async def test_syncs_the_application_context(self):
        await self.service.sync_application(self.session, self.application)
        self.conversation_service.sync_context.assert_awaited_once_with(
            self.session, ContextType.APPLICATION, 7
        )

    async def test_writes_email_received_for_inbound_only(self):
        self.conversation_service.sync_context.return_value = [
            _message(EmailDirection.INBOUND),
            _message(EmailDirection.OUTBOUND, subject="Hello"),
        ]

        await self.service.sync_application(self.session, self.application)

        self.activity_repo.create.assert_awaited_once()
        args, kwargs = self.activity_repo.create.await_args
        self.assertEqual(args[1], 7)
        # Actor is the candidate (thread owner), not the recruiter.
        self.assertEqual(args[2], 5)
        self.assertEqual(args[3], "email_received")
        self.assertEqual(kwargs["details"]["subject"], "Re: Hello")
        self.assertEqual(kwargs["details"]["from"], "cand@x")
        self.assertEqual(kwargs["details"]["to"], "recruiting@corp.com")
        self.assertEqual(kwargs["details"]["cc"], "boss@x")
        self.assertEqual(kwargs["details"]["threadId"], 10)
        self.assertEqual(kwargs["details"]["direction"], "inbound")
        # Backdated to when the mail actually arrived, not to now.
        self.assertEqual(kwargs["created_at"], RECEIVED_AT)

    async def test_no_new_messages_writes_no_activity(self):
        await self.service.sync_application(self.session, self.application)
        self.activity_repo.create.assert_not_awaited()

    async def test_returns_the_new_messages(self):
        messages = [_message(EmailDirection.INBOUND)]
        self.conversation_service.sync_context.return_value = messages
        result = await self.service.sync_application(self.session, self.application)
        self.assertEqual(result, messages)

    async def test_does_not_commit(self):
        # The caller owns the transaction boundary: manual Refresh commits once,
        # the nightly sweep commits per application.
        self.conversation_service.sync_context.return_value = [
            _message(EmailDirection.INBOUND)
        ]
        await self.service.sync_application(self.session, self.application)
        self.session.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
