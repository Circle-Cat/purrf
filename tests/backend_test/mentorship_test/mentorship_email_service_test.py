import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import requests

from backend.common.exceptions import ConflictError, RateLimitedError
from backend.common.kit_client import KitApiError
from backend.common.kit_html_checks import fingerprint_of
from backend.common.mentorship_email_enums import MentorshipEmailRecipientResult as R
from backend.common.mentorship_email_enums import (
    MentorshipEmailSendStatus,
    MentorshipEmailStage,
)
from backend.dto.mentorship_email_dto import (
    EmailConfirmDto,
    EmailSendCreateDto,
)
from backend.mentorship.mentorship_email_service import MentorshipEmailService

TAG = "purrf · Fall 2026 · Match result · 10-08"


def _send_row(**kw):
    row = MagicMock()
    defaults = dict(
        send_id=5,
        round_id=1,
        stage="match_result",
        kit_draft_id=4400,
        kit_draft_subject="Welcome to the round",
        kit_tag_name=TAG,
        kit_tag_id=77,
        status=MentorshipEmailSendStatus.DRAFT,
        failure_code=None,
        sender_address="notification-test@circlecat.org",
        kit_broadcast_id=900,
        error_message=None,
        send_at=None,
        created_at=None,
        prepare_claimed_at=None,
        tag_deleted=False,
        preview_fingerprint=None,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _draft(**kw):
    d = {
        "id": 4400,
        "status": "draft",
        "subject": "Welcome to the round",
        "preview_text": "See you soon",
        "content": '<a href="https://a.org">x</a>',
        "description": "Written by the program team",
        "email_address": "mentorship@circlecat.org",
        "email_template": {"id": 11, "name": "Classic"},
        "created_at": "2026-10-01T10:00:00Z",
        "subscriber_filter": [{"all": [{"type": "all_subscribers"}]}],
    }
    d.update(kw)
    return d


class MentorshipEmailServiceCreateTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.repo = MagicMock()
        self.repo.create_send = AsyncMock(return_value=_send_row())
        self.repo.count_by_result = AsyncMock(return_value={})
        self.emails = MagicMock()
        self.emails.get_contact_emails_by_user_ids = AsyncMock(
            return_value={1: "ann@x.org"}
        )
        self.rounds = MagicMock()
        round_row = MagicMock()
        round_row.name = "Fall 2026"
        self.rounds.get_by_round_id = AsyncMock(return_value=round_row)
        self.kit = MagicMock()
        self.kit.get_broadcast.return_value = _draft()
        self.kit.list_tag_names.return_value = set()
        self.kit.create_tag.return_value = 77
        self.kit.create_broadcast.return_value = {"id": 900}
        self.service = MentorshipEmailService(
            mentorship_email_repository=self.repo,
            user_emails_repository=self.emails,
            mentorship_round_repository=self.rounds,
            kit_client=self.kit,
            sender_address="notification-test@circlecat.org",
            logger=MagicMock(),
            clock=lambda: datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc),
        )
        self.body = EmailSendCreateDto(
            round_id=1,
            stage=MentorshipEmailStage.MATCH_RESULT,
            kit_draft_id=4400,
            user_ids=[1, 2, 2],
        )

    async def test_list_drafts_hides_purrf_copies_newest_first(self):
        self.kit.list_draft_broadcasts.return_value = [
            _draft(id=1, subject="Old", created_at="2026-09-01T10:00:00Z"),
            _draft(
                id=2,
                subject="Copy",
                description=f"Purrf · {TAG}",
                created_at="2026-10-07T10:00:00Z",
            ),
            _draft(id=3, subject=None, created_at="2026-10-05T10:00:00Z"),
            _draft(id=4, subject="New", created_at="2026-10-08T09:00:00Z"),
        ]
        got = await self.service.list_drafts()
        self.assertEqual(
            [(d.id, d.subject) for d in got], [(4, "New"), (3, ""), (1, "Old")]
        )
        self.assertEqual(
            got[0].created_at, datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc)
        )

    async def test_list_drafts_says_why_a_draft_cannot_be_sent(self):
        self.kit.list_draft_broadcasts.return_value = [
            _draft(id=1, created_at="2026-10-03T10:00:00Z"),
            _draft(
                id=2,
                content='<a href="circlecat.org">x</a>',
                created_at="2026-10-02T10:00:00Z",
            ),
            _draft(id=3, subject="  ", created_at="2026-10-01T10:00:00Z"),
        ]
        got = await self.service.list_drafts()
        self.assertEqual(
            [(d.id, d.problem) for d in got],
            [
                (1, None),
                (2, "links Kit cannot send: 'circlecat.org'"),
                (3, "it has no subject"),
            ],
        )

    async def test_create_copies_the_draft_and_leaves_the_original_alone(self):
        await self.service.create_send(self.session, self.body, created_by=99)
        # 12:00 UTC on 8 Oct is still 8 Oct in Pacific Time.
        self.kit.get_broadcast.assert_called_once_with(4400)
        self.kit.create_tag.assert_called_once_with(TAG)
        body = self.kit.create_broadcast.call_args.args[0]
        self.assertEqual(
            body["subscriber_filter"],
            [{"all": [{"type": "tag", "ids": [77]}], "any": None, "none": None}],
        )
        self.assertEqual(
            (body["subject"], body["preview_text"], body["content"]),
            ("Welcome to the round", "See you soon", '<a href="https://a.org">x</a>'),
        )
        self.assertEqual(body["email_template_id"], 11)
        self.assertEqual(body["description"], f"Purrf · {TAG}")
        self.assertEqual(body["email_address"], "notification-test@circlecat.org")
        self.assertIs(body["public"], False)
        self.assertIsNone(body["send_at"])
        self.kit.update_broadcast.assert_not_called()
        self.kit.delete_broadcast.assert_not_called()
        kwargs = self.repo.create_send.await_args.kwargs
        self.assertEqual(
            (kwargs["kit_tag_name"], kwargs["kit_tag_id"], kwargs["kit_broadcast_id"]),
            (TAG, 77, 900),
        )
        self.assertEqual(
            (kwargs["kit_draft_id"], kwargs["kit_draft_subject"]),
            (4400, "Welcome to the round"),
        )
        self.session.commit.assert_awaited_once()

    async def test_create_rejects_a_broadcast_that_is_not_a_draft(self):
        self.kit.get_broadcast.return_value = _draft(status="completed")
        with self.assertRaises(ValueError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.kit.create_tag.assert_not_called()
        self.kit.create_broadcast.assert_not_called()

    async def test_create_rejects_a_purrf_copy(self):
        self.kit.get_broadcast.return_value = _draft(description=f"Purrf · {TAG}")
        with self.assertRaises(ValueError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.kit.create_tag.assert_not_called()

    async def test_create_rejects_a_draft_without_subject(self):
        self.kit.get_broadcast.return_value = _draft(subject="  ")
        with self.assertRaises(ValueError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.kit.create_tag.assert_not_called()

    async def test_create_logs_orphaned_kit_objects_when_store_fails(self):
        self.repo.create_send = AsyncMock(side_effect=RuntimeError("db down"))
        with self.assertRaises(RuntimeError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.service.logger.error.assert_called_once()
        logged = " ".join(str(a) for a in self.service.logger.error.call_args.args)
        self.assertIn(TAG, logged)
        self.assertIn("900", logged)
        self.session.commit.assert_not_awaited()

    async def test_create_logs_orphaned_tag_when_draft_creation_fails(self):
        self.kit.create_broadcast.side_effect = KitApiError(500, "boom")
        with self.assertRaises(KitApiError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.service.logger.error.assert_called_once()
        logged = " ".join(str(a) for a in self.service.logger.error.call_args.args)
        self.assertIn(TAG, logged)
        self.assertIn("77", logged)
        self.repo.create_send.assert_not_awaited()

    async def test_create_marks_users_without_email(self):
        await self.service.create_send(self.session, self.body, created_by=99)
        self.assertEqual(
            self.repo.create_send.await_args.kwargs["recipients"],
            [(1, "ann@x.org"), (2, None)],
        )

    async def test_taken_tag_name_gets_a_suffix(self):
        self.kit.list_tag_names.return_value = {TAG, f"{TAG} #2"}
        await self.service.create_send(self.session, self.body, created_by=99)
        self.kit.create_tag.assert_called_once_with(f"{TAG} #3")

    async def test_create_rejects_invalid_links_before_any_kit_write(self):
        self.kit.get_broadcast.return_value = _draft(
            content='<a href="circlecat.org">x</a>'
        )
        with self.assertRaises(ValueError) as ctx:
            await self.service.create_send(self.session, self.body, created_by=99)
        self.assertIn("circlecat.org", str(ctx.exception))
        self.kit.create_tag.assert_not_called()
        self.kit.create_broadcast.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_create_reports_deleted_draft_as_bad_request(self):
        self.kit.get_broadcast.side_effect = KitApiError(404, "Not Found")
        with self.assertRaises(ValueError) as ctx:
            await self.service.create_send(self.session, self.body, created_by=99)
        self.assertEqual(
            str(ctx.exception), "This Kit draft no longer exists. Pick another one."
        )
        self.kit.create_tag.assert_not_called()

    async def test_create_rejects_unknown_round(self):
        self.rounds.get_by_round_id = AsyncMock(return_value=None)
        with self.assertRaises(ValueError):
            await self.service.create_send(self.session, self.body, created_by=99)
        self.kit.create_tag.assert_not_called()

    async def test_create_requires_sender_config(self):
        self.service.sender_address = None
        with self.assertRaises(ValueError):
            await self.service.create_send(self.session, self.body, created_by=99)

    def test_resume_needed_only_for_stale_preparing(self):
        now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        fresh = _send_row(
            status=MentorshipEmailSendStatus.PREPARING, prepare_claimed_at=now
        )
        stale = _send_row(
            status=MentorshipEmailSendStatus.PREPARING,
            prepare_claimed_at=datetime(2026, 10, 8, 11, 0, tzinfo=timezone.utc),
        )
        draft = _send_row(status=MentorshipEmailSendStatus.DRAFT)
        self.assertFalse(self.service.to_dto(fresh, {}).resume_needed)
        self.assertTrue(self.service.to_dto(stale, {}).resume_needed)
        self.assertFalse(self.service.to_dto(draft, {}).resume_needed)


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
FILTER = [{"all": [{"type": "tag", "ids": [77]}]}]


def _broadcast(**kw):
    b = {
        "id": 900,
        "content": "<p>Oct 20</p>",
        "subject": "Your match",
        "email_address": "notification-test@circlecat.org",
        "subscriber_filter": FILTER,
    }
    b.update(kw)
    return b


class MentorshipEmailServiceFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.send = _send_row(preview_fingerprint=None)
        self.no_email = MagicMock(
            user_id=3,
            email=None,
            result=R.IMPORT_FAILED,
            failure_reason="no_email",
        )
        self.repo = MagicMock()
        self.repo.get_send = AsyncMock(return_value=self.send)
        self.repo.count_by_result = AsyncMock(
            return_value={R.PENDING: 2, R.IMPORT_FAILED: 1}
        )
        self.repo.list_recipients = AsyncMock(return_value=[self.no_email])
        self.repo.recent_recipient_user_ids = AsyncMock(return_value=set())
        self.kit = MagicMock()
        self.kit.get_broadcast.return_value = _broadcast()
        self.service = MentorshipEmailService(
            mentorship_email_repository=self.repo,
            user_emails_repository=MagicMock(),
            mentorship_round_repository=MagicMock(),
            kit_client=self.kit,
            sender_address="notification-test@circlecat.org",
            logger=MagicMock(),
            clock=lambda: NOW,
        )

    async def _confirm(self, token=None, send_at=NOW + timedelta(hours=1)):
        self.send.preview_fingerprint = fingerprint_of(_broadcast())
        return await self.service.confirm(
            self.session,
            5,
            EmailConfirmDto(
                send_at=send_at, preview_token=token or fingerprint_of(_broadcast())
            ),
        )

    async def test_preview_stores_fingerprint_and_lists_people_without_email(self):
        got = await self.service.refresh_preview(self.session, 5)
        self.assertEqual(got.preview_token, fingerprint_of(_broadcast()))
        self.assertEqual(self.send.preview_html, "<p>Oct 20</p>")
        self.assertTrue(got.filter_ok)
        self.assertEqual(got.recipient_count, 2)
        self.assertEqual([r.user_id for r in got.no_email], [3])
        self.session.commit.assert_awaited_once()

    async def test_preview_flags_tampered_filter(self):
        self.kit.get_broadcast.return_value = _broadcast(
            subscriber_filter=[{"all": []}]
        )
        self.assertFalse(
            (await self.service.refresh_preview(self.session, 5)).filter_ok
        )

    async def test_preview_only_for_drafts(self):
        self.send.status = MentorshipEmailSendStatus.SCHEDULED
        with self.assertRaises(ConflictError):
            await self.service.refresh_preview(self.session, 5)

    async def test_confirm_moves_to_preparing_with_send_time(self):
        await self._confirm()
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.PREPARING)
        self.assertEqual(self.send.send_at, NOW + timedelta(hours=1))
        self.kit.update_broadcast.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_confirm_rejects_stale_token(self):
        with self.assertRaises(ConflictError) as ctx:
            await self._confirm(token="old")
        self.assertEqual(ctx.exception.code, "stale_preview")

    async def test_confirm_needs_thirty_minutes(self):
        with self.assertRaises(ValueError):
            await self._confirm(send_at=NOW + timedelta(minutes=20))
        self.session.commit.assert_not_awaited()

    async def test_confirm_rejects_changed_content(self):
        self.send.preview_fingerprint = fingerprint_of(_broadcast())
        self.kit.get_broadcast.return_value = _broadcast(content="<p>edited later</p>")
        with self.assertRaises(ConflictError) as ctx:
            await self.service.confirm(
                self.session,
                5,
                EmailConfirmDto(
                    send_at=NOW + timedelta(hours=1),
                    preview_token=fingerprint_of(_broadcast()),
                ),
            )
        self.assertEqual(ctx.exception.code, "content_changed")

    async def test_confirm_rejects_changed_filter(self):
        tampered = _broadcast(
            subscriber_filter=[{"all": [{"type": "tag", "ids": [1]}]}]
        )
        self.kit.get_broadcast.return_value = tampered
        self.send.preview_fingerprint = fingerprint_of(tampered)
        with self.assertRaises(ConflictError) as ctx:
            await self.service.confirm(
                self.session,
                5,
                EmailConfirmDto(
                    send_at=NOW + timedelta(hours=1),
                    preview_token=fingerprint_of(tampered),
                ),
            )
        self.assertEqual(ctx.exception.code, "draft_tampered")

    async def test_cancel_draft_deletes_broadcast_and_tag(self):
        await self.service.cancel(self.session, 5)
        self.kit.delete_broadcast.assert_called_once_with(900)
        self.kit.delete_tag.assert_called_once_with(77)
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.CANCELLED)

    async def test_cancel_refuses_after_send_time(self):
        self.send.status = MentorshipEmailSendStatus.SCHEDULED
        self.send.send_at = NOW - timedelta(minutes=1)
        with self.assertRaises(ConflictError) as ctx:
            await self.service.cancel(self.session, 5)
        self.assertEqual(ctx.exception.code, "already_sending")
        self.kit.delete_broadcast.assert_not_called()

    async def test_cancel_after_kit_started_sending_is_a_conflict(self):
        self.send.status = MentorshipEmailSendStatus.SCHEDULED
        self.send.send_at = NOW + timedelta(minutes=5)
        self.kit.delete_broadcast.side_effect = KitApiError(422, "already sending")
        with self.assertRaises(ConflictError) as ctx:
            await self.service.cancel(self.session, 5)
        self.assertEqual(ctx.exception.code, "already_sending")
        self.kit.delete_tag.assert_not_called()
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.SCHEDULED)
        self.session.commit.assert_not_awaited()


class MentorshipEmailServiceNotifiedTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.send = _send_row(
            status=MentorshipEmailSendStatus.SCHEDULED,
            kit_broadcast_id=900,
            send_at=NOW - timedelta(minutes=5),
        )
        self.repo = MagicMock()
        self.repo.list_sends = AsyncMock(return_value=[self.send])
        self.repo.list_sent_stages = AsyncMock(
            return_value=[(1, "admission"), (1, "match_result"), (2, "admission")]
        )
        self.repo.list_scheduled_stages = AsyncMock(return_value=[])
        self.kit = MagicMock()
        self.kit.get_broadcast_stats.return_value = {
            "status": "scheduled",
            "recipients": 2,
        }
        self.service = MentorshipEmailService(
            mentorship_email_repository=self.repo,
            user_emails_repository=MagicMock(),
            mentorship_round_repository=MagicMock(),
            kit_client=self.kit,
            sender_address="notification-test@circlecat.org",
            logger=MagicMock(),
            clock=lambda: NOW,
        )

    async def test_groups_sent_stages_by_person(self):
        notified, _ = await self.service.list_notified(self.session, 1)
        self.assertEqual(
            [(n.user_id, n.stages) for n in notified],
            [(1, ["admission", "match_result"]), (2, ["admission"])],
        )
        self.repo.list_sent_stages.assert_awaited_once_with(self.session, 1)

    async def test_scheduled_keeps_the_latest_send_of_each_stage(self):
        soon = NOW + timedelta(hours=2)
        later = NOW + timedelta(days=3)
        self.repo.list_scheduled_stages = AsyncMock(
            return_value=[
                (2, "match_result", later),
                (2, "match_result", soon),
                (2, "final_followup", soon),
                (3, "midterm_reminder", later),
            ]
        )
        notified, _ = await self.service.list_notified(self.session, 1)
        self.assertEqual(
            [
                (n.user_id, n.stages, [(s.stage, s.send_at) for s in n.scheduled])
                for n in notified
            ],
            [
                (1, ["admission", "match_result"], []),
                (
                    2,
                    ["admission"],
                    [("match_result", later), ("final_followup", soon)],
                ),
                (3, [], [("midterm_reminder", later)]),
            ],
        )
        self.repo.list_scheduled_stages.assert_awaited_once_with(self.session, 1)

    async def test_send_that_just_went_out_is_not_read_as_scheduled(self):
        self.kit.get_broadcast_stats.return_value = {
            "status": "completed",
            "recipients": 2,
        }
        seen = []
        self.repo.list_scheduled_stages = AsyncMock(
            side_effect=lambda *_: seen.append(self.send.status) or []
        )
        await self.service.list_notified(self.session, 1)
        self.assertEqual(seen, [MentorshipEmailSendStatus.SENT])

    async def test_completed_send_becomes_sent_before_reading_stages(self):
        self.kit.get_broadcast_stats.return_value = {
            "status": "completed",
            "recipients": 2,
        }
        seen = []
        self.repo.list_sent_stages = AsyncMock(
            side_effect=lambda *_: seen.append(self.send.status) or []
        )
        await self.service.list_notified(self.session, 1)
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.SENT)
        self.assertEqual(seen, [MentorshipEmailSendStatus.SENT])
        self.kit.delete_tag.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_aborted_is_recorded(self):
        self.kit.get_broadcast_stats.return_value = {
            "status": "aborted",
            "recipients": 2,
        }
        await self.service.list_notified(self.session, 1)
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.ABORTED)
        self.assertIn("Kit", self.send.error_message)

    async def test_still_sending_changes_nothing(self):
        await self.service.list_notified(self.session, 1)
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.SCHEDULED)
        self.session.commit.assert_not_awaited()

    async def test_send_time_not_reached_is_not_asked_of_kit(self):
        self.send.send_at = NOW + timedelta(hours=1)
        await self.service.list_notified(self.session, 1)
        self.kit.get_broadcast_stats.assert_not_called()

    async def test_only_scheduled_and_preparing_sends_are_loaded(self):
        await self.service.list_notified(self.session, 1)
        args = self.repo.list_sends.await_args.args
        self.assertEqual(args[1], 1)
        self.assertEqual(
            set(args[2]),
            {MentorshipEmailSendStatus.SCHEDULED, MentorshipEmailSendStatus.PREPARING},
        )

    async def test_returns_stale_preparing_sends_to_resume(self):
        stale = _send_row(
            send_id=6,
            status=MentorshipEmailSendStatus.PREPARING,
            prepare_claimed_at=NOW - timedelta(hours=1),
        )
        fresh = _send_row(
            send_id=7,
            status=MentorshipEmailSendStatus.PREPARING,
            prepare_claimed_at=NOW,
        )
        self.repo.list_sends = AsyncMock(return_value=[self.send, stale, fresh])
        _, resume = await self.service.list_notified(self.session, 1)
        self.assertEqual(resume, [6])

    async def test_kit_error_leaves_the_read_working(self):
        self.kit.get_broadcast_stats.side_effect = KitApiError(503, "down")
        notified, _ = await self.service.list_notified(self.session, 1)
        self.assertEqual(len(notified), 2)
        self.assertEqual(self.send.status, MentorshipEmailSendStatus.SCHEDULED)
        self.session.commit.assert_not_awaited()
        self.service.logger.warning.assert_called_once()

    async def test_rate_limit_leaves_the_read_working(self):
        self.kit.get_broadcast_stats.side_effect = RateLimitedError()
        notified, _ = await self.service.list_notified(self.session, 1)
        self.assertEqual(len(notified), 2)
        self.session.commit.assert_not_awaited()

    async def test_connection_error_leaves_the_read_working(self):
        self.kit.get_broadcast_stats.side_effect = requests.exceptions.ConnectionError(
            "reset"
        )
        notified, _ = await self.service.list_notified(self.session, 1)
        self.assertEqual(len(notified), 2)
        self.session.commit.assert_not_awaited()
        self.assertEqual(self.service.logger.warning.call_args.args[1], 5)


def _recipient(result, failure_reason=None):
    return MagicMock(result=result, failure_reason=failure_reason)


class MentorshipEmailServicePersonSendsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.repo = MagicMock()
        self.repo.list_person_sends = AsyncMock(return_value=[])
        self.kit = MagicMock()
        self.service = MentorshipEmailService(
            mentorship_email_repository=self.repo,
            user_emails_repository=MagicMock(),
            mentorship_round_repository=MagicMock(),
            kit_client=self.kit,
            sender_address="notification-test@circlecat.org",
            logger=MagicMock(),
            clock=lambda: NOW,
        )

    def _rows(self, *rows):
        self.repo.list_person_sends = AsyncMock(return_value=list(rows))

    async def test_reads_only_this_persons_settled_and_scheduled_sends(self):
        await self.service.list_person_sends(self.session, 1, 42)
        args = self.repo.list_person_sends.await_args.args
        self.assertEqual(args[1:3], (1, 42))
        self.assertEqual(
            set(args[3]),
            {
                MentorshipEmailSendStatus.SCHEDULED,
                MentorshipEmailSendStatus.SENT,
                MentorshipEmailSendStatus.ABORTED,
                MentorshipEmailSendStatus.FAILED,
            },
        )

    async def test_each_outcome_newest_first(self):
        sent = _send_row(
            send_id=11,
            stage="admission",
            kit_draft_subject="Welcome aboard",
            status=MentorshipEmailSendStatus.SENT,
            send_at=NOW - timedelta(days=9),
        )
        unsubscribed = _send_row(
            send_id=12,
            stage="match_result",
            kit_draft_subject="Your match",
            status=MentorshipEmailSendStatus.SENT,
            send_at=NOW - timedelta(days=6),
        )
        aborted = _send_row(
            send_id=13,
            stage="midterm_reminder",
            kit_draft_subject="Halfway there",
            status=MentorshipEmailSendStatus.ABORTED,
            send_at=NOW - timedelta(days=3),
        )
        failed = _send_row(
            send_id=14,
            stage="final_followup",
            kit_draft_subject="Wrapping up",
            status=MentorshipEmailSendStatus.FAILED,
            failure_code="draft_gone",
            send_at=NOW + timedelta(days=4),
            updated_at=NOW - timedelta(hours=2),
        )
        self._rows(
            (sent, _recipient(R.HANDED_TO_KIT)),
            (unsubscribed, _recipient(R.UNSUBSCRIBED)),
            (aborted, _recipient(R.HANDED_TO_KIT)),
            (failed, _recipient(R.PENDING)),
        )

        got = await self.service.list_person_sends(self.session, 1, 42)

        self.assertEqual(
            [(s.send_id, s.stage, s.subject, s.delivered, s.at) for s in got],
            [
                (14, "final_followup", "Wrapping up", False, NOW - timedelta(hours=2)),
                (
                    13,
                    "midterm_reminder",
                    "Halfway there",
                    False,
                    NOW - timedelta(days=3),
                ),
                (12, "match_result", "Your match", False, NOW - timedelta(days=6)),
                (11, "admission", "Welcome aboard", True, NOW - timedelta(days=9)),
            ],
        )
        reasons = {s.send_id: s.reason for s in got}
        self.assertIsNone(reasons[11])
        self.assertEqual(reasons[12], "Not handed to Kit: unsubscribed")
        self.assertIn("Kit refused", reasons[13])
        self.assertIn("deleted in Kit", reasons[14])
        self.kit.get_broadcast_stats.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_own_reason_wins_over_the_sends(self):
        aborted = _send_row(
            status=MentorshipEmailSendStatus.ABORTED, send_at=NOW - timedelta(days=1)
        )
        self._rows((aborted, _recipient(R.IMPORT_FAILED, "no_email")))
        (got,) = await self.service.list_person_sends(self.session, 1, 42)
        self.assertEqual(got.reason, "Not handed to Kit: no email address")
        self.assertFalse(got.delivered)

    async def test_scheduled_due_is_caught_up_with_kit_first(self):
        due = _send_row(
            send_id=21,
            status=MentorshipEmailSendStatus.SCHEDULED,
            kit_broadcast_id=901,
            send_at=NOW - timedelta(minutes=5),
        )
        later = _send_row(
            send_id=22,
            status=MentorshipEmailSendStatus.SCHEDULED,
            kit_broadcast_id=902,
            send_at=NOW + timedelta(hours=1),
        )
        self._rows(
            (due, _recipient(R.HANDED_TO_KIT)), (later, _recipient(R.HANDED_TO_KIT))
        )
        self.kit.get_broadcast_stats.return_value = {"status": "completed"}

        got = await self.service.list_person_sends(self.session, 1, 42)

        self.kit.get_broadcast_stats.assert_called_once_with(901)
        self.assertEqual([(s.send_id, s.delivered) for s in got], [(21, True)])
        self.session.commit.assert_awaited_once()

    async def test_kit_still_sending_or_down_leaves_it_out(self):
        due = _send_row(
            status=MentorshipEmailSendStatus.SCHEDULED,
            send_at=NOW - timedelta(minutes=5),
        )
        self._rows((due, _recipient(R.HANDED_TO_KIT)))
        for answer in ({"status": "scheduled"}, KitApiError(503, "down")):
            self.kit.get_broadcast_stats.side_effect = (
                answer if isinstance(answer, Exception) else None
            )
            self.kit.get_broadcast_stats.return_value = answer
            self.assertEqual(
                await self.service.list_person_sends(self.session, 1, 42), []
            )
        self.session.commit.assert_not_awaited()


class MentorshipEmailServiceNotifiedUserIdsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.due = _send_row(
            send_id=6,
            stage="midterm_reminder",
            status=MentorshipEmailSendStatus.SCHEDULED,
            kit_broadcast_id=901,
            send_at=NOW - timedelta(minutes=5),
        )
        self.query = object()
        self.repo = MagicMock()
        self.repo.list_sends = AsyncMock(return_value=[self.due])
        self.repo.notified_user_ids = MagicMock(return_value=self.query)
        self.kit = MagicMock()
        self.kit.get_broadcast_stats.return_value = {"status": "completed"}
        self.service = MentorshipEmailService(
            mentorship_email_repository=self.repo,
            user_emails_repository=MagicMock(),
            mentorship_round_repository=MagicMock(),
            kit_client=self.kit,
            sender_address="notification-test@circlecat.org",
            logger=MagicMock(),
            clock=lambda: NOW,
        )

    async def test_catches_up_only_this_stage_then_returns_the_query(self):
        got = await self.service.notified_user_ids(
            self.session, 1, "midterm_reminder", sent=True, scheduled=False
        )

        self.assertIs(got, self.query)
        self.repo.list_sends.assert_awaited_once_with(
            self.session,
            1,
            [MentorshipEmailSendStatus.SCHEDULED],
            stage="midterm_reminder",
        )
        self.assertEqual(self.due.status, MentorshipEmailSendStatus.SENT)
        self.session.commit.assert_awaited_once()
        self.repo.notified_user_ids.assert_called_once_with(
            1, "midterm_reminder", sent=True, scheduled=False
        )

    async def test_nothing_due_does_not_ask_kit(self):
        self.due.send_at = NOW + timedelta(minutes=30)
        await self.service.notified_user_ids(
            self.session, 1, "midterm_reminder", sent=True, scheduled=True
        )
        self.kit.get_broadcast_stats.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_kit_error_still_returns_the_query(self):
        self.kit.get_broadcast_stats.side_effect = requests.ConnectionError("down")
        got = await self.service.notified_user_ids(
            self.session, 1, "midterm_reminder", sent=False, scheduled=True
        )
        self.assertIs(got, self.query)
        self.assertEqual(self.due.status, MentorshipEmailSendStatus.SCHEDULED)
        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
