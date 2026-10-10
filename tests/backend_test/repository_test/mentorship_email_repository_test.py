import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult as R,
    MentorshipEmailSendStatus as S,
)
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.mentorship_email_send_entity import MentorshipEmailSendEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.mentorship_email_repository import MentorshipEmailRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class MentorshipEmailRepositoryTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipEmailRepository()
        self.round = MentorshipRoundEntity(
            name="Fall 2026",
            onboarding_deadline_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        )
        self.admin = UsersEntity(
            first_name="Ad",
            last_name="Min",
            timezone="UTC",
            timezone_updated_at=NOW,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=NOW,
        )
        self.u1 = UsersEntity(
            first_name="Ann",
            last_name="One",
            timezone="UTC",
            timezone_updated_at=NOW,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=NOW,
        )
        self.u2 = UsersEntity(
            first_name="Bob",
            last_name="Two",
            timezone="UTC",
            timezone_updated_at=NOW,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=NOW,
        )
        await self.insert_entities([self.round, self.admin, self.u1, self.u2])

    async def _send(self, recipients=None, stage="match_result"):
        return await self.repo.create_send(
            self.session,
            round_id=self.round.round_id,
            stage=stage,
            kit_draft_id=11,
            kit_draft_subject="Welcome to the round",
            created_by=self.admin.user_id,
            sender_address="notification-test@circlecat.org",
            kit_tag_name="purrf · Fall 2026 · Match result · 10-08",
            kit_tag_id=7,
            kit_broadcast_id=9,
            recipients=recipients
            if recipients is not None
            else [(self.u1.user_id, "ann@x.org"), (self.u2.user_id, None)],
        )

    async def test_create_send_marks_missing_email_failed(self):
        send = await self._send()
        rows = {
            r.user_id: r
            for r in await self.repo.list_recipients(self.session, send.send_id)
        }
        self.assertEqual(send.status, S.DRAFT)
        self.assertEqual(rows[self.u1.user_id].result, R.PENDING)
        self.assertEqual(rows[self.u2.user_id].result, R.IMPORT_FAILED)
        self.assertEqual(rows[self.u2.user_id].failure_reason, "no_email")
        pending = await self.repo.list_pending_recipients(self.session, send.send_id)
        self.assertEqual([r.user_id for r in pending], [self.u1.user_id])

    async def test_claim_for_prepare_is_exclusive_until_lease_expires(self):
        send = await self._send()
        send.status = S.PREPARING
        await self.session.flush()
        lease = timedelta(minutes=10)
        self.assertTrue(
            await self.repo.claim_for_prepare(
                self.session, send.send_id, now=NOW, lease=lease
            )
        )
        self.assertFalse(
            await self.repo.claim_for_prepare(
                self.session, send.send_id, now=NOW + timedelta(minutes=5), lease=lease
            )
        )
        self.assertTrue(
            await self.repo.claim_for_prepare(
                self.session, send.send_id, now=NOW + timedelta(minutes=11), lease=lease
            )
        )

    async def test_claim_refuses_when_not_preparing(self):
        send = await self._send()
        send.status = S.DRAFT
        await self.session.flush()
        self.assertFalse(
            await self.repo.claim_for_prepare(
                self.session, send.send_id, now=NOW, lease=timedelta(minutes=10)
            )
        )

    async def test_count_by_result(self):
        send = await self._send()
        counts = await self.repo.count_by_result(self.session, send.send_id)
        self.assertEqual(counts[R.PENDING], 1)
        self.assertEqual(counts[R.IMPORT_FAILED], 1)

    async def test_recent_recipients_only_counts_live_sends_and_handed_rows(self):
        old = await self._send(
            recipients=[(self.u1.user_id, "ann@x.org"), (self.u2.user_id, "bob@x.org")]
        )
        old.status = S.SENT
        rows = await self.repo.list_recipients(self.session, old.send_id)
        rows[0].result = R.HANDED_TO_KIT
        rows[1].result = R.UNSUBSCRIBED
        cancelled = await self._send(recipients=[(self.u2.user_id, "bob@x.org")])
        cancelled.status = S.CANCELLED
        (await self.repo.list_recipients(self.session, cancelled.send_id))[
            0
        ].result = R.HANDED_TO_KIT
        current = await self._send(recipients=[(self.u1.user_id, "ann@x.org")])
        await self.session.flush()
        got = await self.repo.recent_recipient_user_ids(
            self.session,
            round_id=self.round.round_id,
            stage="match_result",
            since=NOW - timedelta(days=30),
            exclude_send_id=current.send_id,
        )
        self.assertEqual(got, {rows[0].user_id})

    async def test_pending_greeting_name_falls_back_to_first_name(self):
        self.u1.preferred_name = "  "
        send = await self._send()
        got = await self.repo.list_pending_recipients_with_greeting_name(
            self.session, send.send_id
        )
        self.assertEqual(
            [(r.user_id, name) for r, name in got], [(self.u1.user_id, "Ann")]
        )

    async def test_pending_greeting_name_prefers_preferred_name(self):
        self.u1.preferred_name = "Annie"
        send = await self._send()
        got = await self.repo.list_pending_recipients_with_greeting_name(
            self.session, send.send_id
        )
        self.assertEqual(
            [(r.user_id, name) for r, name in got], [(self.u1.user_id, "Annie")]
        )

    async def test_unreached_with_users_skips_handed_and_pending_rows(self):
        send = await self._send(
            recipients=[
                (self.admin.user_id, "ad@x.org"),
                (self.u1.user_id, "ann@x.org"),
                (self.u2.user_id, None),
            ]
        )
        rows = await self.repo.list_recipients(self.session, send.send_id)
        rows[1].result = R.BOUNCED
        await self.session.flush()
        got = await self.repo.list_unreached_recipients_with_users(
            self.session, send.send_id
        )
        self.assertEqual(
            [(r.result, u.first_name) for r, u in got],
            [(R.BOUNCED, "Ann"), (R.IMPORT_FAILED, "Bob")],
        )

    async def test_get_send_rereads_a_row_changed_behind_the_session(self):
        send = await self._send()
        await self.session.flush()
        loaded = await self.repo.get_send(self.session, send.send_id)
        await self.session.execute(
            update(MentorshipEmailSendEntity)
            .where(MentorshipEmailSendEntity.send_id == send.send_id)
            .values(status=S.CANCELLED)
            .execution_options(synchronize_session=False)
        )
        again = await self.repo.get_send(self.session, send.send_id)
        self.assertIs(again, loaded)
        self.assertEqual(again.status, S.CANCELLED)

    async def test_kit_ids_beyond_int32_round_trip(self):
        send = await self.repo.create_send(
            self.session,
            round_id=self.round.round_id,
            stage="match_result",
            kit_draft_id=7000000003,
            kit_draft_subject="Welcome to the round",
            created_by=self.admin.user_id,
            sender_address="notification-test@circlecat.org",
            kit_tag_name="purrf · Fall 2026 · Match result · 10-08",
            kit_tag_id=5000000001,
            kit_broadcast_id=6000000002,
            recipients=[(self.u1.user_id, "ann@x.org")],
        )
        (await self.repo.list_recipients(self.session, send.send_id))[
            0
        ].kit_subscriber_id = 4330815278
        await self.session.flush()
        send_id = send.send_id
        self.session.expire_all()
        again = await self.repo.get_send(self.session, send_id)
        rows = await self.repo.list_recipients(self.session, send_id)
        self.assertEqual(again.kit_draft_id, 7000000003)
        self.assertEqual(again.kit_tag_id, 5000000001)
        self.assertEqual(again.kit_broadcast_id, 6000000002)
        self.assertEqual(rows[0].kit_subscriber_id, 4330815278)

    async def _handed(self, send, results):
        for row in await self.repo.list_recipients(self.session, send.send_id):
            row.result = results[row.user_id]

    async def test_sent_stages_count_only_sent_sends_and_handed_rows(self):
        both = [(self.u1.user_id, "ann@x.org"), (self.u2.user_id, "bob@x.org")]
        sent = await self._send(recipients=both, stage="admission")
        sent.status = S.SENT
        await self._handed(
            sent, {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.BOUNCED}
        )
        again = await self._send(recipients=both, stage="admission")
        again.status = S.SENT
        await self._handed(
            again, {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.UNSUBSCRIBED}
        )
        match = await self._send(recipients=both, stage="match_result")
        match.status = S.SENT
        await self._handed(
            match, {self.u1.user_id: R.IMPORT_FAILED, self.u2.user_id: R.HANDED_TO_KIT}
        )
        scheduled = await self._send(recipients=both, stage="rejected")
        scheduled.status = S.SCHEDULED
        await self._handed(
            scheduled,
            {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.HANDED_TO_KIT},
        )
        other_round = MentorshipRoundEntity(
            name="Spring 2027",
            onboarding_deadline_at=datetime(2027, 3, 15, tzinfo=timezone.utc),
        )
        await self.insert_entities([other_round])
        elsewhere = await self.repo.create_send(
            self.session,
            round_id=other_round.round_id,
            stage="midterm_reminder",
            kit_draft_id=12,
            kit_draft_subject="Sign up",
            created_by=self.admin.user_id,
            sender_address="notification-test@circlecat.org",
            kit_tag_name="purrf · Spring 2027 · Mid-term reminder · 03-01",
            kit_tag_id=8,
            kit_broadcast_id=10,
            recipients=[(self.u2.user_id, "bob@x.org")],
        )
        elsewhere.status = S.SENT
        await self._handed(elsewhere, {self.u2.user_id: R.HANDED_TO_KIT})
        await self.session.flush()
        got = await self.repo.list_sent_stages(self.session, self.round.round_id)
        self.assertEqual(
            got,
            [(self.u1.user_id, "admission"), (self.u2.user_id, "match_result")],
        )

    async def test_scheduled_stages_keep_confirmed_unsent_sends_and_reachable_rows(
        self,
    ):
        both = [(self.u1.user_id, "ann@x.org"), (self.u2.user_id, "bob@x.org")]
        later = NOW + timedelta(days=2)
        sooner = NOW + timedelta(hours=3)
        scheduled = await self._send(recipients=both, stage="midterm_reminder")
        scheduled.status = S.SCHEDULED
        scheduled.send_at = later
        await self._handed(
            scheduled,
            {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.UNSUBSCRIBED},
        )
        preparing = await self._send(stage="match_result")
        preparing.status = S.PREPARING
        preparing.send_at = sooner
        handed_while_importing = await self._send(
            recipients=[(self.u2.user_id, "bob@x.org")], stage="final_followup"
        )
        handed_while_importing.status = S.PREPARING
        handed_while_importing.send_at = NOW + timedelta(days=5)
        await self._handed(handed_while_importing, {self.u2.user_id: R.HANDED_TO_KIT})
        for status in (S.SENT, S.FAILED, S.ABORTED, S.CANCELLED):
            gone = await self._send(recipients=both, stage="feedback_invite")
            gone.status = status
            gone.send_at = NOW + timedelta(days=1)
        await self._send(recipients=both, stage="admission")
        await self.session.flush()
        got = await self.repo.list_scheduled_stages(self.session, self.round.round_id)
        self.assertEqual(
            got,
            [
                (self.u1.user_id, "match_result", sooner),
                (self.u1.user_id, "midterm_reminder", later),
                (self.u2.user_id, "final_followup", NOW + timedelta(days=5)),
            ],
        )

    async def test_scheduled_stages_stay_in_their_round(self):
        other_round = MentorshipRoundEntity(
            name="Spring 2027",
            onboarding_deadline_at=datetime(2027, 3, 15, tzinfo=timezone.utc),
        )
        await self.insert_entities([other_round])
        elsewhere = await self.repo.create_send(
            self.session,
            round_id=other_round.round_id,
            stage="midterm_reminder",
            kit_draft_id=12,
            kit_draft_subject="Sign up",
            created_by=self.admin.user_id,
            sender_address="notification-test@circlecat.org",
            kit_tag_name="purrf · Spring 2027 · Mid-term reminder · 03-01",
            kit_tag_id=8,
            kit_broadcast_id=10,
            recipients=[(self.u2.user_id, "bob@x.org")],
        )
        elsewhere.status = S.SCHEDULED
        elsewhere.send_at = NOW + timedelta(days=1)
        await self.session.flush()
        self.assertEqual(
            await self.repo.list_scheduled_stages(self.session, self.round.round_id),
            [],
        )

    async def test_list_sends_filters_by_round_and_status(self):
        draft = await self._send()
        scheduled = await self._send()
        scheduled.status = S.SCHEDULED
        preparing = await self._send()
        preparing.status = S.PREPARING
        await self.session.flush()
        got = await self.repo.list_sends(
            self.session, self.round.round_id, [S.SCHEDULED, S.PREPARING]
        )
        self.assertEqual(
            sorted(s.send_id for s in got),
            sorted([scheduled.send_id, preparing.send_id]),
        )
        self.assertNotIn(draft.send_id, [s.send_id for s in got])


if __name__ == "__main__":
    unittest.main()
