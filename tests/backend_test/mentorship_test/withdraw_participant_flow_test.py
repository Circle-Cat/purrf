"""A withdrawal end to end against a real database.

Mentor Mia has two mentees this round; she is withdrawn. Her pairs end, the
meetings of those pairs that have not started are cancelled, her mentees stay
matched, and next round she -- and only she -- is flagged for quitting after
being matched. The fixture keeps every id distinct: raiser, reviewer, the
mentor, each mentee, an unrelated pair and its meetings."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    MeetingSource,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantNoteTag,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.exempt_matching_handler import exemption_target
from backend.mentorship.matching_eligibility import IneligibleReason
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
from backend.mentorship.meeting_service import MeetingService
from backend.mentorship.withdraw_participant_handler import WithdrawParticipantHandler
from backend.repository.approval_request_repository import ApprovalRequestRepository
from backend.repository.mentorship_meeting_repository import (
    MentorshipMeetingRepository,
)
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.repository.mentorship_participant_note_repository import (
    MentorshipParticipantNoteRepository,
)
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.training_repository import TrainingRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _user(first, *, super_admin=False):
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_super_admin=super_admin,
        updated_timestamp=datetime.now(timezone.utc),
    )


def _pair(round_id, mentor, mentee):
    return MentorshipPairsEntity(
        round_id=round_id,
        mentor_id=mentor.user_id,
        mentee_id=mentee.user_id,
        completed_count=0,
        status=PairStatus.ACTIVE,
        mentor_action_status=MentorActionStatus.CONFIRMED,
        mentee_action_status=MenteeActionStatus.CONFIRMED,
        recommendation_reason="",
    )


def _google(meeting_id, pair, start):
    return MentorshipMeetingEntity(
        meeting_id=meeting_id,
        pair_id=pair.pair_id,
        source=MeetingSource.GOOGLE,
        start_datetime=start,
        end_datetime=start + timedelta(hours=1),
        is_completed=False,
    )


def _registration(user, round_, role, status, cap=1):
    return MentorshipRoundParticipantsEntity(
        user_id=user.user_id,
        round_id=round_.round_id,
        participant_role=role,
        approval_status=status,
        max_partners=cap,
    )


class WithdrawParticipantFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.now = now
        self.raiser = _user("Ada")
        self.reviewer = _user("Rae", super_admin=True)
        self.mentor = _user("Mia")
        self.mentee_a = _user("Ann")
        self.mentee_b = _user("Bo")
        self.early = _user("Cy")
        self.other_mentor = _user("Oto")
        self.other_mentee = _user("Dee")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.mentor,
            self.mentee_a,
            self.mentee_b,
            self.early,
            self.other_mentor,
            self.other_mentee,
        ])
        self.round = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=4,
            promotion_start_at=now - timedelta(days=10),
            onboarding_deadline_at=now + timedelta(days=10),
            meetings_completion_deadline_at=now + timedelta(days=80),
            feedback_deadline_at=now + timedelta(days=100),
        )
        await self.insert_entities([self.round])
        self.mentor_reg = _registration(
            self.mentor, self.round, ParticipantRole.MENTOR, ApprovalStatus.MATCHED, 2
        )
        self.a_reg = _registration(
            self.mentee_a, self.round, ParticipantRole.MENTEE, ApprovalStatus.MATCHED
        )
        self.b_reg = _registration(
            self.mentee_b, self.round, ParticipantRole.MENTEE, ApprovalStatus.MATCHED
        )
        self.early_reg = _registration(
            self.early, self.round, ParticipantRole.MENTEE, ApprovalStatus.SIGNED_UP
        )
        # Left the old way: rejected with the pair still active, never
        # backfilled. Must not read as quitting after a match.
        self.old_reg = _registration(
            self.other_mentee, self.round, ParticipantRole.MENTEE, ApprovalStatus.REJECTED
        )
        await self.insert_entities([
            self.mentor_reg,
            self.a_reg,
            self.b_reg,
            self.early_reg,
            self.old_reg,
        ])
        self.pair_a = _pair(self.round.round_id, self.mentor, self.mentee_a)
        self.pair_b = _pair(self.round.round_id, self.mentor, self.mentee_b)
        self.other_pair = _pair(self.round.round_id, self.other_mentor, self.other_mentee)
        await self.insert_entities([self.pair_a, self.pair_b, self.other_pair])
        # Plain ints: the rows expire when a test rolls back.
        self.reviewer_id = self.reviewer.user_id
        self.pair_ids = [
            self.pair_a.pair_id,
            self.pair_b.pair_id,
            self.other_pair.pair_id,
        ]
        await self.insert_entities([
            _google("g-a-up", self.pair_a, now + timedelta(days=2)),
            _google("g-a-past", self.pair_a, now - timedelta(days=2)),
            _google("g-b-up", self.pair_b, now + timedelta(days=5)),
            _google("g-other-up", self.other_pair, now + timedelta(days=3)),
        ])

        logger = MagicMock()
        self.calendar = MagicMock()
        self.calendar.cancel = AsyncMock(
            side_effect=lambda ids, calendar_id: (list(ids), [])
        )
        self.notes = MentorshipParticipantNoteRepository()
        self.meetings = MentorshipMeetingRepository()
        rounds = MentorshipRoundRepository()
        users = UsersRepository()
        participants = MentorshipRoundParticipantsRepository()
        pairs = MentorshipPairsRepository()
        handler = WithdrawParticipantHandler(
            participants_repository=participants,
            pairs_repository=pairs,
            meeting_service=MeetingService(
                logger=logger,
                mentorship_pairs_repository=pairs,
                mentorship_mapper=MagicMock(),
                users_repository=users,
                meeting_scheduling_service=self.calendar,
                mentorship_calendar_id="cal-test",
                mentorship_meeting_repository=self.meetings,
                mentorship_round_repository=rounds,
            ),
            rounds_repository=rounds,
            note_repository=self.notes,
            users_repository=users,
            logger=logger,
        )
        self.service = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=UserPermissionsRepository(),
            users_repository=users,
            logger=logger,
            handlers=[handler],
        )
        self.eligibility = MatchingEligibilityService(
            participants_repository=participants,
            pairs_repository=pairs,
            rounds_repository=rounds,
            training_repository=TrainingRepository(),
            note_repository=self.notes,
            logger=logger,
        )

    async def _raise(self, person):
        row = await self.service.raise_request(
            self.session,
            action="withdraw_participant",
            raised_by=self.raiser.user_id,
            target_id=exemption_target(self.round.round_id, person.user_id),
            payload={"round_id": self.round.round_id, "user_id": person.user_id},
            reason="Stopped replying",
            reviewer_id=self.reviewer.user_id,
        )
        return row.request_id

    async def _approve(self, request_id):
        return await self.service.decide(
            self.session,
            request_id=request_id,
            actor_id=self.reviewer_id,
            approve=True,
            comment=None,
        )

    async def _meeting_ids(self, *more_pair_ids):
        rows = await self.session.execute(
            select(MentorshipMeetingEntity.meeting_id).where(
                MentorshipMeetingEntity.pair_id.in_([*self.pair_ids, *more_pair_ids])
            )
        )
        return sorted(rows.scalars().all())

    async def _refresh(self, *rows):
        for row in rows:
            await self.session.refresh(row)

    async def test_approving_withdraws_her_and_ends_only_her_pairs(self):
        closed = await self._approve(await self._raise(self.mentor))

        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        await self._refresh(
            self.mentor_reg, self.a_reg, self.b_reg, self.pair_a, self.pair_b, self.other_pair
        )
        self.assertIs(self.mentor_reg.approval_status, ApprovalStatus.WITHDRAWN)
        self.assertIs(self.a_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertIs(self.b_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertIs(self.pair_a.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_b.status, PairStatus.INACTIVE)
        self.assertIs(self.other_pair.status, PairStatus.ACTIVE)
        self.assertEqual(await self._meeting_ids(), ["g-a-past", "g-other-up"])
        cancelled_ids = self.calendar.cancel.await_args.args[0]
        self.assertEqual(sorted(cancelled_ids), ["g-a-up", "g-b-up"])

        notes = await self.notes.list_for_user_round(
            self.session, self.mentor.user_id, self.round.round_id
        )
        self.assertEqual([n.tag for n in notes], [ParticipantNoteTag.STATUS_CHANGE])
        body = notes[0].body
        self.assertEqual(notes[0].author_user_id, self.reviewer.user_id)
        self.assertIn("matched -> withdrawn", body)
        self.assertIn(f"pair {self.pair_a.pair_id}", body)
        self.assertIn(f"pair {self.pair_b.pair_id}", body)
        self.assertNotIn(f"pair {self.other_pair.pair_id}", body)
        self.assertIn("Upcoming meetings cancelled: 2.", body)

    async def test_a_calendar_refusal_changes_nothing_and_a_retry_succeeds(self):
        request_id = await self._raise(self.mentor)
        self.calendar.cancel.side_effect = [
            (["g-a-up"], ["g-b-up"]),
            # Google now answers 404 for g-a-up, which counts as deleted.
            (["g-a-up", "g-b-up"], []),
        ]

        with self.assertRaises(ConflictError) as caught:
            await self._approve(request_id)
        self.assertEqual(caught.exception.code, "calendar_cancel_failed")
        # What the controller's session context does on an exception.
        await self.session.rollback()

        request = await ApprovalRequestRepository().get(self.session, request_id)
        self.assertIs(request.status, ApprovalRequestStatus.PENDING)
        await self._refresh(self.mentor_reg, self.pair_a, self.pair_b)
        self.assertIs(self.mentor_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertIs(self.pair_a.status, PairStatus.ACTIVE)
        self.assertIs(self.pair_b.status, PairStatus.ACTIVE)
        self.assertEqual(
            await self._meeting_ids(), ["g-a-past", "g-a-up", "g-b-up", "g-other-up"]
        )

        closed = await self._approve(request_id)
        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        self.assertEqual(await self._meeting_ids(), ["g-a-past", "g-other-up"])

    async def test_a_status_changed_since_refuses_the_approval(self):
        request_id = await self._raise(self.mentor)
        self.mentor_reg.approval_status = ApprovalStatus.REJECTED
        await self.session.flush()

        with self.assertRaises(ConflictError) as caught:
            await self._approve(request_id)

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)
        self.calendar.cancel.assert_not_awaited()

    async def test_a_second_withdrawal_of_the_same_person_is_refused(self):
        await self._raise(self.mentor)

        with self.assertRaises(ConflictError):
            await self._raise(self.mentor)

    async def test_next_round_flags_only_who_left_after_being_matched(self):
        await self._approve(await self._raise(self.mentor))
        await self._approve(await self._raise(self.early))

        later = MentorshipRoundEntity(
            name="Fall 2026",
            required_meetings=4,
            promotion_start_at=self.now + timedelta(days=120),
            onboarding_deadline_at=self.now + timedelta(days=140),
            meetings_completion_deadline_at=self.now + timedelta(days=220),
            feedback_deadline_at=self.now + timedelta(days=240),
        )
        await self.insert_entities([later])
        people = [
            (self.mentor, ParticipantRole.MENTOR, TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING),
            (self.mentee_a, ParticipantRole.MENTEE, TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING),
            (self.early, ParticipantRole.MENTEE, TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING),
            (self.other_mentee, ParticipantRole.MENTEE, TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING),
        ]
        await self.insert_entities(
            [
                _registration(user, later, role, ApprovalStatus.SIGNED_UP)
                for user, role, _ in people
            ]
            + [
                TrainingEntity(
                    user_id=user.user_id,
                    category=category,
                    status=TrainingStatus.DONE,
                    deadline=self.now,
                )
                for user, _, category in people
            ]
        )

        reasons = await self.eligibility.ineligible_by_user(
            self.session, later.round_id
        )

        quit_ = IneligibleReason.QUIT_AFTER_MATCH
        self.assertIn(quit_, reasons[self.mentor.user_id])
        self.assertNotIn(quit_, reasons[self.mentee_a.user_id])
        self.assertNotIn(quit_, reasons[self.early.user_id])
        self.assertNotIn(quit_, reasons[self.other_mentee.user_id])

    async def test_only_active_pairs_end_when_the_mentor_has_an_ended_one(self):
        ended_mentee = _user("Eve")
        await self.insert_entities([ended_mentee])
        ended_pair = _pair(self.round.round_id, self.mentor, ended_mentee)
        ended_pair.status = PairStatus.INACTIVE
        await self.insert_entities([ended_pair])
        await self.insert_entities([
            _google("g-ended-up", ended_pair, self.now + timedelta(days=4))
        ])

        await self._approve(await self._raise(self.mentor))

        await self._refresh(self.pair_a, self.pair_b, ended_pair)
        self.assertIs(self.pair_a.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_b.status, PairStatus.INACTIVE)
        self.assertIs(ended_pair.status, PairStatus.INACTIVE)
        self.assertEqual(
            sorted(self.calendar.cancel.await_args.args[0]), ["g-a-up", "g-b-up"]
        )
        self.assertIn(
            "g-ended-up", await self._meeting_ids(ended_pair.pair_id)
        )
        notes = await self.notes.list_for_user_round(
            self.session, self.mentor.user_id, self.round.round_id
        )
        self.assertNotIn(f"pair {ended_pair.pair_id}", notes[0].body)
        self.assertIn("Upcoming meetings cancelled: 2.", notes[0].body)

    async def test_withdrawn_before_ever_paired_touches_no_calendar(self):
        await self._approve(await self._raise(self.early))

        await self._refresh(self.early_reg)
        self.assertIs(self.early_reg.approval_status, ApprovalStatus.WITHDRAWN)
        self.calendar.cancel.assert_not_awaited()
        self.assertEqual(
            await self._meeting_ids(),
            ["g-a-past", "g-a-up", "g-b-up", "g-other-up"],
        )
        notes = await self.notes.list_for_user_round(
            self.session, self.early.user_id, self.round.round_id
        )
        self.assertIn(
            "Pairs ended: none. Upcoming meetings cancelled: 0.", notes[0].body
        )


if __name__ == "__main__":
    unittest.main()