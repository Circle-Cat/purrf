import logging
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy.exc import MissingGreenlet

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


class _ExpiringApplication:
    """Reproduces what a real ``ApplicationEntity`` does after
    ``session.rollback()``: SQLAlchemy expires every object in the identity
    map, so the next attribute access performs an implicit refresh SELECT.
    Inside an async coroutine that SELECT runs outside ``greenlet_spawn`` and
    raises ``sqlalchemy.exc.MissingGreenlet``.

    ``application_id``/``user_id`` are properties that raise exactly that
    once ``expired["value"]`` flips to True (which this test's fake
    ``rollback()`` does). A ``SimpleNamespace``/``AsyncMock`` double cannot
    reproduce this: plain attribute access on them is never IO, which is
    exactly why the 13 pre-existing tests never saw this defect.
    """

    def __init__(self, application_id, user_id, expired):
        self._application_id = application_id
        self._user_id = user_id
        self._expired = expired

    @property
    def application_id(self):
        if self._expired["value"]:
            raise MissingGreenlet(
                "greenlet_spawn has not been called; can't call await_only() here"
            )
        return self._application_id

    @property
    def user_id(self):
        if self._expired["value"]:
            raise MissingGreenlet(
                "greenlet_spawn has not been called; can't call await_only() here"
            )
        return self._user_id


class TestSyncApplication(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conversation_service = AsyncMock()
        self.conversation_service.sync_context = AsyncMock(return_value=[])
        self.activity_repo = AsyncMock()
        self.session = Mock()
        self.gmail = Mock()
        self.gmail.list_recent_message_thread_ids = Mock(return_value=set())
        self.service = EmailSyncService(
            gmail_client=self.gmail,
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
        self.gmail = Mock()
        self.gmail.list_recent_message_thread_ids = Mock(return_value=set())
        self.service = EmailSyncService(
            gmail_client=self.gmail,
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

    async def test_rollback_expiring_the_application_does_not_crash_the_sweep(self):
        # Regression test for a Critical review defect: session.rollback()
        # expires *every* ORM object in the session's identity map, including
        # every application in `due` and the one currently being handled. The
        # very next statement in the except block,
        # logger.exception(..., application.application_id), then performs an
        # implicit refresh SELECT on that expired instance - IO outside
        # greenlet_spawn, which raises sqlalchemy.exc.MissingGreenlet from
        # *inside* the except block, where nothing catches it. That escapes
        # sync_due_applications entirely: the first bad application (a Gmail
        # rate limit, a message deleted between listing and fetch, an expired
        # refresh token) would kill the whole nightly sweep - exactly the
        # outcome per-application isolation exists to prevent.
        #
        # The 13 pre-existing tests use AsyncMock()/SimpleNamespace doubles:
        # rollback() has no side effect on them and attribute access is never
        # IO, so none of them can observe this. _ExpiringApplication models
        # the real mechanism instead: rollback() flips a shared "expired"
        # flag, and application_id/user_id are properties that raise
        # MissingGreenlet once that flag is set - reproducing an expired
        # instance without a real database.
        expired = {"value": False}
        applications = [_ExpiringApplication(i, 100 + i, expired) for i in (1, 2, 3)]
        self.application_repo.list_due_email_sync_applications = AsyncMock(
            return_value=applications
        )
        self.session.rollback = AsyncMock(
            side_effect=lambda: expired.__setitem__("value", True)
        )
        self.conversation_service.sync_context.side_effect = [
            RuntimeError("Gmail API error"),
            [],
            [],
        ]

        summary = await self.service.sync_due_applications(self.session)

        # One failure must not end the run: the sweep still returns, still
        # attempts every due application, and reports the failure as a count
        # rather than letting it escape as an unhandled exception.
        self.assertEqual(
            summary,
            {"scanned": 3, "synced": 2, "failed": 1, "newMessages": 0},
        )
        self.assertEqual(self.conversation_service.sync_context.await_count, 3)

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

    async def test_reconcile_passes_no_thread_filter_and_is_labelled(self):
        self._due(1)
        await self.service.sync_due_applications(self.session)
        call = self.application_repo.list_due_email_sync_applications.await_args
        self.assertIsNone(call.kwargs.get("gmail_thread_ids"))
        # Render the message rather than reading the raw template: the
        # requirement is about the line that gets emitted, so the test should
        # be agnostic to whether the label is interpolated eagerly or lazily.
        call = self.logger.log.call_args
        message = call.args[1] % call.args[2:]
        self.assertIn("reconcile", message)
        self.assertIn("sweep finished", message)


class TestSyncRecentApplications(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conversation_service = AsyncMock()
        self.conversation_service.sync_context = AsyncMock(return_value=[])
        self.activity_repo = AsyncMock()
        self.application_repo = AsyncMock()
        self.application_repo.list_due_email_sync_applications = AsyncMock(
            return_value=[]
        )
        self.gmail = Mock()
        self.logger = Mock()
        self.session = AsyncMock()
        self.service = EmailSyncService(
            gmail_client=self.gmail,
            email_conversation_service=self.conversation_service,
            application_activity_repository=self.activity_repo,
            application_repository=self.application_repo,
            logger=self.logger,
        )

    def _flagged(self, *thread_ids):
        self.gmail.list_recent_message_thread_ids = Mock(return_value=set(thread_ids))

    def _due(self, *application_ids):
        applications = [
            SimpleNamespace(application_id=i, user_id=100 + i) for i in application_ids
        ]
        self.application_repo.list_due_email_sync_applications = AsyncMock(
            return_value=applications
        )
        return applications

    async def test_asks_gmail_for_a_two_day_window(self):
        # Day-granular operator, so the window carries a day of slack on
        # purpose — see the design note in GmailClient.
        self._flagged()
        await self.service.sync_recent_applications(self.session)
        self.gmail.list_recent_message_thread_ids.assert_called_once_with(2)

    async def test_passes_the_flagged_threads_to_the_eligibility_query(self):
        self._flagged("T1", "T2")
        self._due(1)

        await self.service.sync_recent_applications(self.session)

        call = self.application_repo.list_due_email_sync_applications.await_args
        self.assertIs(call.args[0], self.session)
        self.assertEqual(call.kwargs["gmail_thread_ids"], {"T1", "T2"})

    async def test_sweeps_the_terminal_window_like_the_reconcile_does(self):
        # Same seven-day cutoff as the weekly job: the delta narrows *which*
        # applications are looked at, never *whether* they are eligible.
        self._flagged("T1")
        self._due(1)
        before = datetime.now(timezone.utc)

        await self.service.sync_recent_applications(self.session)

        cutoff = self.application_repo.list_due_email_sync_applications.await_args.args[
            1
        ]
        self.assertAlmostEqual(
            (before - cutoff).total_seconds(), 7 * 86400, delta=5
        )

    async def test_nothing_flagged_skips_the_query_entirely(self):
        self._flagged()

        summary = await self.service.sync_recent_applications(self.session)

        self.application_repo.list_due_email_sync_applications.assert_not_awaited()
        self.conversation_service.sync_context.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.assertEqual(
            summary, {"scanned": 0, "synced": 0, "failed": 0, "newMessages": 0}
        )

    async def test_nothing_flagged_still_logs_a_summary(self):
        # The endpoint always returns 200 and the job is always green, so the
        # log is the only evidence the run happened at all.
        self._flagged()
        await self.service.sync_recent_applications(self.session)
        self.logger.log.assert_called_once()

    async def test_isolates_failures_like_the_reconcile_does(self):
        self._flagged("T1")
        self._due(1, 2, 3)
        self.conversation_service.sync_context.side_effect = [
            [],
            RuntimeError("Gmail API error"),
            [],
        ]

        summary = await self.service.sync_recent_applications(self.session)

        self.assertEqual(self.conversation_service.sync_context.await_count, 3)
        self.assertEqual(
            summary, {"scanned": 3, "synced": 2, "failed": 1, "newMessages": 0}
        )
        self.assertEqual(self.session.commit.await_count, 2)
        self.session.rollback.assert_awaited_once()

    async def test_summary_log_names_the_delta_job(self):
        # One log stream carries both jobs; they must be distinguishable.
        self._flagged("T1")
        self._due(1)
        await self.service.sync_recent_applications(self.session)
        call = self.logger.log.call_args
        message = call.args[1] % call.args[2:]
        self.assertIn("delta", message)
        self.assertIn("sweep finished", message)

    async def test_a_failed_gmail_lookup_is_not_isolated(self):
        # Per-application failures are caught and counted; this one is not.
        # Without the flagged set there is no sweep to run, so it propagates
        # and the endpoint 500s rather than reporting a misleading all-zero
        # summary.
        self.gmail.list_recent_message_thread_ids = Mock(
            side_effect=RuntimeError("Gmail API error")
        )

        with self.assertRaises(RuntimeError):
            await self.service.sync_recent_applications(self.session)

        self.application_repo.list_due_email_sync_applications.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.logger.log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
