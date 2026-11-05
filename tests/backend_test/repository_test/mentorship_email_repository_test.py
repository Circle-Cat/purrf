import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult as R,
    MentorshipEmailSendStatus as S,
)
from backend.common.mentorship_enums import CommunicationMethod, ParticipantNoteTag
from backend.entity.approval_request_entity import ApprovalRequestEntity  # noqa: F401
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity  # noqa: F401
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)
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

    async def test_person_sends_pair_each_send_with_that_persons_row(self):
        both = [(self.u1.user_id, "ann@x.org"), (self.u2.user_id, "bob@x.org")]
        sent = await self._send(recipients=both, stage="admission")
        sent.status = S.SENT
        await self._handed(
            sent, {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.BOUNCED}
        )
        failed = await self._send(
            recipients=[(self.u2.user_id, "bob@x.org")], stage="final_followup"
        )
        failed.status = S.FAILED
        cancelled = await self._send(recipients=both, stage="midterm_reminder")
        cancelled.status = S.CANCELLED
        only_u1 = await self._send(
            recipients=[(self.u1.user_id, "ann@x.org")], stage="feedback_invite"
        )
        only_u1.status = S.SENT
        await self.session.flush()

        got = await self.repo.list_person_sends(
            self.session, self.round.round_id, self.u2.user_id, [S.SENT, S.FAILED]
        )

        self.assertEqual(
            [(send.send_id, row.user_id, row.result) for send, row in got],
            [
                (sent.send_id, self.u2.user_id, R.BOUNCED),
                (failed.send_id, self.u2.user_id, R.PENDING),
            ],
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

    async def _ids(self, stage, **flags):
        query = self.repo.notified_user_ids(self.round.round_id, stage, **flags)
        rows = await self.session.execute(
            select(UsersEntity.user_id)
            .where(UsersEntity.user_id.in_(query))
            .order_by(UsersEntity.user_id)
        )
        return list(rows.scalars())

    async def test_notified_user_ids_by_state(self):
        u3 = UsersEntity(
            first_name="Cy",
            last_name="Three",
            timezone="UTC",
            timezone_updated_at=NOW,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=NOW,
        )
        await self.insert_entities([u3])
        both = [(self.u1.user_id, "ann@x.org"), (self.u2.user_id, "bob@x.org")]
        sent = await self._send(recipients=both, stage="midterm_reminder")
        sent.status = S.SENT
        await self._handed(
            sent, {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.UNSUBSCRIBED}
        )
        again = await self._send(
            recipients=[(self.u1.user_id, "ann@x.org")], stage="midterm_reminder"
        )
        again.status = S.SCHEDULED
        again.send_at = NOW + timedelta(days=1)
        preparing = await self._send(
            recipients=[(u3.user_id, "cy@x.org")], stage="midterm_reminder"
        )
        preparing.status = S.PREPARING
        preparing.send_at = NOW + timedelta(hours=2)
        for status in (S.FAILED, S.ABORTED, S.CANCELLED):
            gone = await self._send(recipients=both, stage="midterm_reminder")
            gone.status = status
            gone.send_at = NOW
            await self._handed(
                gone,
                {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.HANDED_TO_KIT},
            )
        other_stage = await self._send(recipients=both, stage="final_followup")
        other_stage.status = S.SENT
        await self._handed(
            other_stage,
            {self.u1.user_id: R.HANDED_TO_KIT, self.u2.user_id: R.HANDED_TO_KIT},
        )
        await self.session.flush()

        self.assertEqual(
            await self._ids("midterm_reminder", sent=True, scheduled=False),
            [self.u1.user_id],
        )
        self.assertEqual(
            await self._ids("midterm_reminder", sent=False, scheduled=True),
            [self.u1.user_id, u3.user_id],
        )
        self.assertEqual(
            await self._ids("midterm_reminder", sent=True, scheduled=True),
            [self.u1.user_id, u3.user_id],
        )
        self.assertEqual(
            await self._ids("final_followup", sent=True, scheduled=False),
            [self.u1.user_id, self.u2.user_id],
        )

    async def test_notified_user_ids_stay_in_their_round(self):
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
        self.assertEqual(
            await self._ids("midterm_reminder", sent=True, scheduled=True), []
        )

    def test_notified_user_ids_needs_a_state(self):
        with self.assertRaises(ValueError):
            self.repo.notified_user_ids(1, "admission", sent=False, scheduled=False)

    async def _note(self, user, stage, *, tag=ParticipantNoteTag.NOTIFIED, round_=None):
        await self.insert_entities([
            MentorshipParticipantNoteEntity(
                user_id=user.user_id,
                round_id=(round_ or self.round).round_id,
                author_user_id=self.admin.user_id,
                body="Sent on Teams.",
                tag=tag,
                notification_stage=stage,
            )
        ])

    async def _other_round(self):
        other = MentorshipRoundEntity(
            name="Spring 2027",
            onboarding_deadline_at=datetime(2027, 3, 15, tzinfo=timezone.utc),
        )
        await self.insert_entities([other])
        return other

    async def test_manual_stages_are_the_notified_notes_of_this_round(self):
        other = await self._other_round()
        await self._note(self.u2, "match_result")
        await self._note(self.u1, "admission")
        await self._note(self.u1, "match_result")
        await self._note(self.u1, "match_result")
        await self._note(self.u2, None, tag=ParticipantNoteTag.STATUS_CHANGE)
        await self._note(self.u2, "midterm_reminder", round_=other)

        self.assertEqual(
            await self.repo.list_manual_stages(self.session, self.round.round_id),
            [
                (self.u1.user_id, "admission"),
                (self.u1.user_id, "match_result"),
                (self.u2.user_id, "match_result"),
            ],
        )

    async def test_notified_user_ids_count_people_marked_by_hand(self):
        other = await self._other_round()
        sent = await self._send(
            recipients=[(self.u1.user_id, "ann@x.org")], stage="midterm_reminder"
        )
        sent.status = S.SENT
        await self._handed(sent, {self.u1.user_id: R.HANDED_TO_KIT})
        await self.session.flush()
        await self._note(self.u2, "midterm_reminder")
        await self._note(self.admin, "final_followup")
        await self._note(self.admin, "midterm_reminder", round_=other)

        self.assertEqual(
            await self._ids("midterm_reminder", sent=True, scheduled=False),
            [self.u1.user_id, self.u2.user_id],
        )
        self.assertEqual(
            await self._ids("midterm_reminder", sent=True, scheduled=True),
            [self.u1.user_id, self.u2.user_id],
        )
        self.assertEqual(
            await self._ids("midterm_reminder", sent=False, scheduled=True), []
        )
        self.assertEqual(
            await self._ids("final_followup", sent=True, scheduled=False),
            [self.admin.user_id],
        )

    async def test_list_sends_can_keep_one_stage(self):
        mid = await self._send(stage="midterm_reminder")
        mid.status = S.SCHEDULED
        other = await self._send(stage="admission")
        other.status = S.SCHEDULED
        await self.session.flush()
        got = await self.repo.list_sends(
            self.session, self.round.round_id, [S.SCHEDULED], stage="midterm_reminder"
        )
        self.assertEqual([s.send_id for s in got], [mid.send_id])


if __name__ == "__main__":
    unittest.main()
