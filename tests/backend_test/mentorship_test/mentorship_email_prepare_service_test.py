import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.exceptions import RateLimitedError
from backend.common.kit_client import KitApiError, TagResult
from backend.common.mentorship_email_enums import (
    MentorshipEmailFailure as F,
    MentorshipEmailRecipientResult as R,
    MentorshipEmailSendStatus as S,
)
from backend.common.kit_html_checks import fingerprint_of
from backend.mentorship import mentorship_email_prepare_service as mod
from backend.mentorship.mentorship_email_prepare_service import (
    MentorshipEmailPrepareService,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
SENDER = "notification-test@circlecat.org"
FILTER = [{"all": [{"type": "tag", "ids": [77]}]}]


def _broadcast(**kw):
    b = {
        "id": 900,
        "content": "<p>Oct 20</p>",
        "subject": "Your match",
        "email_address": SENDER,
        "subscriber_filter": FILTER,
        "description": "Purrf · tag",
        "preview_text": None,
        "send_at": None,
        "email_template": {"id": 11, "name": "Classic"},
    }
    b.update(kw)
    return b


def _recipient(rid, email):
    r = MagicMock()
    r.recipient_id, r.email, r.result, r.failure_reason, r.kit_subscriber_id = (
        rid,
        email,
        R.PENDING,
        None,
        None,
    )
    return r


class PrepareServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.session.begin_nested = MagicMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.send = MagicMock(
            send_id=5,
            round_id=3,
            stage="match_result",
            kit_draft_subject="Your match",
            created_by=42,
            status=S.PREPARING,
            kit_tag_id=77,
            kit_broadcast_id=900,
            sender_address=SENDER,
            error_message=None,
            failure_code=None,
            send_at=NOW + timedelta(hours=1),
            preview_fingerprint=fingerprint_of(_broadcast()),
        )
        self.repo = MagicMock()
        self.repo.claim_for_prepare = AsyncMock(return_value=True)
        self.repo.get_send = AsyncMock(return_value=self.send)
        self.a, self.b = _recipient(1, "a@x.org"), _recipient(2, "b@x.org")
        self.repo.list_pending_recipients_with_greeting_name = AsyncMock(
            return_value=[(self.a, "Ann"), (self.b, "Bob")]
        )
        self.repo.count_by_result = AsyncMock(return_value={R.HANDED_TO_KIT: 2})
        self.repo.list_unreached_recipients_with_users = AsyncMock(return_value=[])
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(
            return_value=SimpleNamespace(round_id=3, name="Fall 2026")
        )
        self.commits_at_record = []
        self.record_event = AsyncMock(
            side_effect=lambda *_a, **_kw: self.commits_at_record.append(
                self.session.commit.await_count
            )
        )
        patcher = patch.object(mod, "record_event", self.record_event)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.kit = MagicMock()
        self.kit.tag_subscriber_by_email.return_value = TagResult(True, 1, "active")
        self.kit.get_broadcast.return_value = _broadcast()
        self.kit.get_broadcast_stats.return_value = {"recipients": 2}
        self.kit.update_broadcast.side_effect = lambda _id, body: _broadcast(
            send_at=body["send_at"]
        )
        self.pause = AsyncMock()
        self.service = MentorshipEmailPrepareService(
            database=self.database,
            mentorship_email_repository=self.repo,
            mentorship_round_repository=self.rounds,
            kit_client=self.kit,
            logger=MagicMock(),
            clock=lambda: NOW,
            pause=self.pause,
        )

    async def test_happy_path_imports_then_schedules_the_confirmed_draft(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            TagResult(True, 10, "active"),
            TagResult(False, None, None),
            TagResult(True, 11, "active"),
        ]
        self.kit.create_subscriber.return_value = TagResult(True, 11, "active")
        await self.service.run(5)
        self.kit.create_subscriber.assert_called_once_with("b@x.org", "Bob")
        self.assertEqual(
            (self.a.result, self.b.result), (R.HANDED_TO_KIT, R.HANDED_TO_KIT)
        )
        body = self.kit.update_broadcast.call_args.args[1]
        self.assertEqual(body["send_at"], "2026-10-08T13:00:00Z")
        self.assertEqual(body["email_address"], SENDER)
        self.assertIs(body["allow_starting_point"], True)
        self.assertEqual(body["email_template_id"], 11)
        self.assertEqual(self.send.status, S.SCHEDULED)
        self.kit.create_tag.assert_not_called()
        self.kit.create_broadcast.assert_not_called()

    async def test_states_map_to_results(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            TagResult(True, 1, "cancelled"),
            TagResult(True, 2, "bounced"),
        ]
        self.repo.count_by_result = AsyncMock(return_value={R.HANDED_TO_KIT: 0})
        await self.service.run(5)
        self.assertEqual((self.a.result, self.b.result), (R.UNSUBSCRIBED, R.BOUNCED))
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.NO_RECIPIENTS)
        )

    async def test_one_kit_error_fails_only_that_person(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            KitApiError(422, "bad email"),
            TagResult(True, 2, "active"),
        ]
        self.repo.count_by_result = AsyncMock(return_value={R.HANDED_TO_KIT: 1})
        self.kit.get_broadcast_stats.return_value = {"recipients": 1}
        await self.service.run(5)
        self.assertEqual(
            (self.a.result, self.a.failure_reason), (R.IMPORT_FAILED, "kit_422")
        )
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_rate_limit_waits_and_retries_same_person(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            RateLimitedError(),
            TagResult(True, 1, "active"),
            TagResult(True, 2, "active"),
        ]
        await self.service.run(5)
        self.pause.assert_any_await(60)
        self.assertEqual(self.a.result, R.HANDED_TO_KIT)

    async def test_resume_only_processes_pending(self):
        self.repo.list_pending_recipients_with_greeting_name = AsyncMock(
            return_value=[(self.b, "Bob")]
        )
        await self.service.run(5)
        self.assertEqual(self.kit.tag_subscriber_by_email.call_count, 1)
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_cancel_during_import_stops(self):
        calls = []

        async def get_send(_session, _id, **_kw):
            calls.append(1)
            if len(calls) == 2:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        with patch.object(mod, "BATCH_SIZE", 1):
            await self.service.run(5)
        self.assertEqual(self.kit.tag_subscriber_by_email.call_count, 1)
        self.kit.update_broadcast.assert_not_called()
        self.assertEqual(self.send.status, S.CANCELLED)

    async def test_cancel_during_finalize_is_not_overwritten(self):
        async def get_send(_session, _id, *, for_update=False):
            if for_update:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        await self.service.run(5)
        self.kit.update_broadcast.assert_not_called()
        self.assertEqual(self.send.status, S.CANCELLED)

    async def test_rerun_after_kit_already_scheduled_records_scheduled(self):
        self.kit.get_broadcast.return_value = _broadcast(send_at="2026-10-08T13:00:00Z")
        self.send.send_at = NOW + timedelta(hours=1)
        await self.service.run(5)
        self.kit.update_broadcast.assert_not_called()
        self.assertEqual(
            (self.send.status, self.send.kit_recipient_count), (S.SCHEDULED, 2)
        )

    async def test_rerun_already_scheduled_skips_time_check(self):
        self.send.send_at = NOW + timedelta(minutes=1)
        self.kit.get_broadcast.return_value = _broadcast(send_at="2026-10-08T12:01:00Z")
        await self.service.run(5)
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_missing_send_at_fails_clearly(self):
        self.send.send_at = None
        await self.service.run(5)
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.KIT_ERROR)
        )
        self.assertIn("send time", self.send.error_message)

    async def test_draft_changed_after_confirm_is_not_scheduled(self):
        self.kit.get_broadcast.return_value = _broadcast(content="<p>edited later</p>")
        await self.service.run(5)
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.DRAFT_CHANGED)
        )
        self.kit.update_broadcast.assert_not_called()

    async def test_tampered_filter_is_not_scheduled(self):
        self.kit.get_broadcast.return_value = _broadcast(
            subscriber_filter=[{"all": [{"type": "tag", "ids": [1]}]}]
        )
        self.send.preview_fingerprint = fingerprint_of(
            self.kit.get_broadcast.return_value
        )
        await self.service.run(5)
        self.assertEqual(self.send.failure_code, F.DRAFT_TAMPERED)

    async def test_deleted_draft(self):
        self.kit.get_broadcast.side_effect = KitApiError(404, "Not Found")

        async def get_send(_session, _id, *, for_update=False):
            if for_update:
                self.send.kit_broadcast_id = (
                    900  # a real re-read overwrites unflushed edits
                )
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        await self.service.run(5)
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.DRAFT_GONE)
        )
        self.assertIsNone(self.send.kit_broadcast_id)

    async def test_count_catches_up_after_a_wait(self):
        self.kit.get_broadcast_stats.side_effect = [
            {"recipients": 1},
            {"recipients": 2},
        ]
        await self.service.run(5)
        self.pause.assert_any_await(30)
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_count_mismatch_after_all_checks(self):
        self.kit.get_broadcast_stats.return_value = {"recipients": 1}
        await self.service.run(5)
        self.assertEqual(self.kit.get_broadcast_stats.call_count, 6)
        self.assertEqual(self.send.failure_code, F.COUNT_MISMATCH)
        self.kit.update_broadcast.assert_not_called()

    async def test_send_time_passed_while_preparing(self):
        self.send.send_at = NOW + timedelta(minutes=1)
        await self.service.run(5)
        self.assertEqual(self.send.failure_code, F.TIME_PASSED)
        self.kit.update_broadcast.assert_not_called()

    async def test_readback_mismatch_is_a_kit_error(self):
        self.kit.update_broadcast.side_effect = lambda _id, body: _broadcast(
            send_at=body["send_at"], email_address="outreach@circlecat.org\t"
        )
        await self.service.run(5)
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.KIT_ERROR)
        )

    async def test_readback_mismatch_unschedules_the_draft(self):
        self.kit.update_broadcast.side_effect = [
            _broadcast(send_at="2026-10-08T13:00:00Z", email_address="x@y.org"),
            _broadcast(),
        ]
        await self.service.run(5)
        self.assertEqual(self.kit.update_broadcast.call_count, 2)
        self.assertIsNone(self.kit.update_broadcast.call_args.args[1]["send_at"])
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.KIT_ERROR)
        )
        self.assertIn("undone", self.send.error_message)

    async def test_readback_mismatch_with_failed_unschedule_warns(self):
        self.kit.update_broadcast.side_effect = [
            _broadcast(send_at="bad"),
            KitApiError(500, "boom"),
        ]
        await self.service.run(5)
        self.assertEqual(self.send.failure_code, F.KIT_ERROR)
        self.assertIn("may still be scheduled", self.send.error_message)

    async def test_no_lease_does_nothing(self):
        self.repo.claim_for_prepare = AsyncMock(return_value=False)
        await self.service.run(5)
        self.kit.tag_subscriber_by_email.assert_not_called()

    async def test_kit_calls_do_not_pause_without_a_rate_limit(self):
        await self.service.run(5)
        self.pause.assert_not_awaited()

    async def test_complained_and_inactive_are_listed_and_not_counted(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            TagResult(True, 1, "complained"),
            TagResult(True, 2, "inactive"),
        ]
        self.repo.count_by_result = AsyncMock(return_value={R.UNSUBSCRIBED: 2})
        await self.service.run(5)
        self.assertEqual(
            (self.a.result, self.a.failure_reason), (R.UNSUBSCRIBED, "complained")
        )
        self.assertEqual(
            (self.b.result, self.b.failure_reason), (R.UNSUBSCRIBED, "inactive")
        )
        self.assertEqual(self.send.failure_code, F.NO_RECIPIENTS)

    async def test_second_tag_miss_after_create_is_import_failed(self):
        self.kit.tag_subscriber_by_email.side_effect = [
            TagResult(False, None, None),
            TagResult(False, None, None),
            TagResult(True, 2, "active"),
        ]
        self.kit.create_subscriber.return_value = TagResult(True, 11, "active")
        self.repo.count_by_result = AsyncMock(return_value={R.HANDED_TO_KIT: 1})
        self.kit.get_broadcast_stats.return_value = {"recipients": 1}
        await self.service.run(5)
        self.assertEqual(
            (self.a.result, self.a.failure_reason), (R.IMPORT_FAILED, "kit_not_found")
        )
        self.assertEqual(self.b.result, R.HANDED_TO_KIT)
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_cancel_before_create_stops_without_creating(self):
        self.kit.tag_subscriber_by_email.return_value = TagResult(False, None, None)
        calls = []

        async def get_send(_session, _id, **_kw):
            calls.append(1)
            if len(calls) == 2:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        await self.service.run(5)
        self.kit.create_subscriber.assert_not_called()
        self.kit.update_broadcast.assert_not_called()
        self.assertEqual(self.send.status, S.CANCELLED)
        self.assertEqual(self.a.result, R.PENDING)

    async def test_readback_with_offset_and_milliseconds_is_accepted(self):
        self.kit.update_broadcast.side_effect = lambda _id, body: _broadcast(
            send_at="2026-10-08T13:00:00.000+00:00"
        )
        await self.service.run(5)
        self.assertEqual(self.kit.update_broadcast.call_count, 1)
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_rerun_with_offset_format_counts_as_already_scheduled(self):
        self.kit.get_broadcast.return_value = _broadcast(
            send_at="2026-10-08T13:00:00+00:00"
        )
        await self.service.run(5)
        self.kit.update_broadcast.assert_not_called()
        self.assertEqual(self.send.status, S.SCHEDULED)

    async def test_unexpected_failure_message_says_the_draft_may_be_scheduled(self):
        self.kit.get_broadcast.side_effect = KitApiError(500, "boom")
        await self.service.run(5)
        self.assertEqual(
            (self.send.status, self.send.failure_code), (S.FAILED, F.KIT_ERROR)
        )
        self.assertTrue(
            self.send.error_message.startswith(
                "Something went wrong talking to Kit; check the draft in Kit"
            )
        )
        self.assertIn("may already be scheduled. Details: ", self.send.error_message)
        self.assertIn("boom", self.send.error_message)

    def _recorded(self):
        self.record_event.assert_awaited_once()
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(
            (
                kwargs["subject_type"],
                kwargs["subject_id"],
                kwargs["actor_id"],
                kwargs["event_type"],
            ),
            ("mentorship_email_send", 5, None, "mentorship.email_send_prepared"),
        )
        return kwargs["details"]

    async def test_scheduled_send_notifies_in_the_scheduling_transaction(self):
        unreached = MagicMock(
            email="cy@x.org", result=R.IMPORT_FAILED, failure_reason="kit_422"
        )
        user = MagicMock(first_name="Cy", last_name="Three", preferred_name="Cee")
        self.repo.list_unreached_recipients_with_users = AsyncMock(
            return_value=[(unreached, user)]
        )
        await self.service.run(5)
        self.assertEqual(self.send.status, S.SCHEDULED)
        self.assertEqual(
            self._recorded(),
            {
                "status": "scheduled",
                "roundName": "Fall 2026",
                "stage": "match_result",
                "subject": "Your match",
                "sendAt": "2026-10-08T13:00:00+00:00",
                "handedCount": 2,
                "notHanded": [
                    {
                        "name": "Cee",
                        "result": "import_failed",
                        "failureReason": "kit_422",
                    }
                ],
            },
        )
        # Recorded after the claim commit and before the scheduling commit.
        self.assertEqual(self.commits_at_record, [self.session.commit.await_count - 1])

    async def test_failed_send_notifies_with_the_failure(self):
        self.kit.get_broadcast.return_value = _broadcast(content="<p>edited later</p>")
        await self.service.run(5)
        self.assertEqual(
            self._recorded(),
            {
                "status": "failed",
                "roundName": "Fall 2026",
                "stage": "match_result",
                "subject": "Your match",
                "failureCode": "draft_changed",
                "errorMessage": self.send.error_message,
                "mayStillBeScheduled": False,
            },
        )
        self.assertEqual(self.commits_at_record, [self.session.commit.await_count - 1])

    async def test_failed_unschedule_notifies_that_kit_may_still_send(self):
        self.kit.update_broadcast.side_effect = [
            _broadcast(send_at="bad"),
            KitApiError(500, "boom"),
        ]
        await self.service.run(5)
        self.assertTrue(self._recorded()["mayStillBeScheduled"])

    async def test_unexpected_failure_notifies_too(self):
        self.kit.get_broadcast.side_effect = KitApiError(500, "boom")
        await self.service.run(5)
        self.assertEqual(self._recorded()["failureCode"], "kit_error")

    async def test_cancel_during_import_does_not_notify(self):
        calls = []

        async def get_send(_session, _id, **_kw):
            calls.append(1)
            if len(calls) == 2:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        with patch.object(mod, "BATCH_SIZE", 1):
            await self.service.run(5)
        self.record_event.assert_not_awaited()

    async def test_cancel_during_finalize_does_not_notify(self):
        async def get_send(_session, _id, *, for_update=False):
            if for_update:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        await self.service.run(5)
        self.record_event.assert_not_awaited()

    async def test_failure_after_cancel_does_not_notify(self):
        self.kit.get_broadcast.return_value = _broadcast(content="<p>edited later</p>")

        async def get_send(_session, _id, *, for_update=False):
            if for_update:
                self.send.status = S.CANCELLED
            return self.send

        self.repo.get_send = AsyncMock(side_effect=get_send)
        await self.service.run(5)
        self.assertEqual(self.send.status, S.CANCELLED)
        self.record_event.assert_not_awaited()

    async def test_a_notification_error_does_not_undo_the_schedule(self):
        self.record_event.side_effect = RuntimeError("bell down")
        await self.service.run(5)
        self.assertEqual(self.send.status, S.SCHEDULED)
        self.assertIsNone(self.send.failure_code)


if __name__ == "__main__":
    unittest.main()
