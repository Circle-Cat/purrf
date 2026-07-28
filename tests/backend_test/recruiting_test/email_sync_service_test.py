import logging
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
            application_repository=AsyncMock(),
            logger=Mock(),
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


class TestSyncDueApplications(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conversation_service = AsyncMock()
        self.conversation_service.sync_context = AsyncMock(return_value=[])
        self.activity_repo = AsyncMock()
        self.application_repo = AsyncMock()
        self.logger = Mock()
        self.session = AsyncMock()
        self.service = EmailSyncService(
            email_conversation_service=self.conversation_service,
            application_activity_repository=self.activity_repo,
            application_repository=self.application_repo,
            logger=self.logger,
        )

    def _due(self, *application_ids):
        applications = [
            SimpleNamespace(application_id=i, user_id=100 + i) for i in application_ids
        ]
        self.application_repo.list_due_email_sync_applications = AsyncMock(
            return_value=applications
        )
        return applications

    async def test_no_due_applications_is_a_clean_no_op(self):
        self._due()
        summary = await self.service.sync_due_applications(self.session)
        self.assertEqual(
            summary,
            {"scanned": 0, "synced": 0, "failed": 0, "newMessages": 0},
        )
        self.session.commit.assert_not_awaited()
        # The summary must be logged even on an empty sweep — it is the only
        # signal the job ran at all, since the endpoint always returns 200.
        self.logger.log.assert_called_once()

    async def test_syncs_every_due_application_and_commits_each(self):
        self._due(1, 2, 3)
        summary = await self.service.sync_due_applications(self.session)
        self.assertEqual(self.conversation_service.sync_context.await_count, 3)
        # Each due application, not the same one three times.
        self.assertEqual(
            [
                call.args[2]
                for call in self.conversation_service.sync_context.await_args_list
            ],
            [1, 2, 3],
        )
        # One commit per application, not one for the whole sweep.
        self.assertEqual(self.session.commit.await_count, 3)
        self.assertEqual(summary["scanned"], 3)
        self.assertEqual(summary["synced"], 3)
        self.assertEqual(summary["failed"], 0)

    async def test_sweeps_terminal_applications_for_seven_days(self):
        # Nothing else pins the cutoff: with `now + window` instead of
        # `now - window`, every terminal application becomes permanently
        # ineligible and late replies stop being captured, silently.
        self._due()
        before = datetime.now(timezone.utc)

        await self.service.sync_due_applications(self.session)

        call = self.application_repo.list_due_email_sync_applications.await_args
        session_arg, cutoff = call.args
        self.assertIs(session_arg, self.session)
        self.assertAlmostEqual((before - cutoff).total_seconds(), 7 * 86400, delta=5)

    async def test_counts_new_messages_across_applications(self):
        self._due(1, 2)
        self.conversation_service.sync_context.side_effect = [
            [_message(EmailDirection.INBOUND), _message(EmailDirection.INBOUND)],
            [_message(EmailDirection.INBOUND)],
        ]
        summary = await self.service.sync_due_applications(self.session)
        self.assertEqual(summary["newMessages"], 3)

    async def test_one_failure_does_not_stop_the_others(self):
        # The whole point of the sweep's error handling: a single bad thread
        # must not silently cost every later application its nightly sync.
        self._due(1, 2, 3)
        self.conversation_service.sync_context.side_effect = [
            [],
            RuntimeError("Gmail API error"),
            [],
        ]

        summary = await self.service.sync_due_applications(self.session)

        self.assertEqual(self.conversation_service.sync_context.await_count, 3)
        self.assertEqual(
            summary,
            {
                "scanned": 3,
                "synced": 2,
                "failed": 1,
                "newMessages": 0,
            },
        )
        # The successful ones are still committed; the failed one is rolled back.
        self.assertEqual(self.session.commit.await_count, 2)
        self.session.rollback.assert_awaited_once()

    async def test_failure_is_logged_with_the_application_id(self):
        self._due(1)
        self.conversation_service.sync_context.side_effect = RuntimeError("boom")
        await self.service.sync_due_applications(self.session)
        self.logger.exception.assert_called_once()
        self.assertIn(1, self.logger.exception.call_args.args)

    async def test_summary_logged_at_info_when_all_succeed(self):
        self._due(1)
        await self.service.sync_due_applications(self.session)
        self.logger.log.assert_called_once()
        self.assertEqual(self.logger.log.call_args.args[0], logging.INFO)

    async def test_summary_logged_at_warning_when_any_failed(self):
        # The endpoint always returns 200 and the k8s job is always green, so a
        # grep-able WARNING is the only signal that something went wrong.
        self._due(1)
        self.conversation_service.sync_context.side_effect = RuntimeError("boom")
        await self.service.sync_due_applications(self.session)
        self.logger.log.assert_called_once()
        self.assertEqual(self.logger.log.call_args.args[0], logging.WARNING)


if __name__ == "__main__":
    unittest.main()
