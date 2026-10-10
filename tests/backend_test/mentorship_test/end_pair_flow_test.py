"""Ending a pair end to end against a real database.

Mentor Mia has two mentees this round, Ann and Bo. Ending Mia and Ann's pair
ends only that pair, cancels only its meetings that have not started, moves
Ann -- left with no pair -- to un_matched, keeps Mia matched for Bo, and notes
it on both. The fixture keeps every id distinct."""

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
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.end_pair_handler import EndPairHandler
from backend.mentorship.meeting_service import MeetingService
from backend.mentorship.mentorship_approval_service import MentorshipApprovalService
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


class EndPairFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.now = now
        self.raiser = _user("Ada")
        self.reviewer = _user("Rae", super_admin=True)
        self.mentor = _user("Mia")
        self.mentee_a = _user("Ann")
        self.mentee_b = _user("Bo")
        await self.insert_entities([
            self.raiser, self.reviewer, self.mentor, self.mentee_a, self.mentee_b
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
        await self.insert_entities([self.mentor_reg, self.a_reg, self.b_reg])
        self.pair_a = _pair(self.round.round_id, self.mentor, self.mentee_a)
        self.pair_b = _pair(self.round.round_id, self.mentor, self.mentee_b)
        await self.insert_entities([self.pair_a, self.pair_b])
        # Plain ints: the rows expire when a test rolls back.
        self.round_id = self.round.round_id
        self.reviewer_id = self.reviewer.user_id
        self.pair_a_id, self.pair_b_id = self.pair_a.pair_id, self.pair_b.pair_id
        await self.insert_entities([
            _google("g-a-up", self.pair_a, now + timedelta(days=2)),
            _google("g-a-past", self.pair_a, now - timedelta(days=2)),
            _google("g-b-up", self.pair_b, now + timedelta(days=5)),
        ])

        logger = MagicMock()
        self.calendar = MagicMock()
        self.calendar.cancel = AsyncMock(
            side_effect=lambda ids, calendar_id: (list(ids), [])
        )
        self.notes = MentorshipParticipantNoteRepository()
        rounds = MentorshipRoundRepository()
        users = UsersRepository()
        participants = MentorshipRoundParticipantsRepository()
        pairs = MentorshipPairsRepository()
        handler = EndPairHandler(
            participants_repository=participants,
            pairs_repository=pairs,
            meeting_service=MeetingService(
                logger=logger,
                mentorship_pairs_repository=pairs,
                mentorship_mapper=MagicMock(),
                users_repository=users,
                meeting_scheduling_service=self.calendar,
                mentorship_calendar_id="cal-test",
                mentorship_meeting_repository=MentorshipMeetingRepository(),
                mentorship_round_repository=rounds,
            ),
            rounds_repository=rounds,
            note_repository=self.notes,
            users_repository=users,
            logger=logger,
        )
        self.approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=UserPermissionsRepository(),
            users_repository=users,
            logger=logger,
            handlers=[handler],
        )
        self.service = MentorshipApprovalService(
            approval_service=self.approvals,
            matching_storage=MagicMock(),
            users_repository=users,
            rounds_repository=rounds,
            pairs_repository=pairs,
            logger=logger,
        )

    async def _raise(self, pair_id, from_user_id, reviewer_id=None):
        described = await self.service.request_end_pair(
            self.session,
            round_id=self.round_id,
            user_id=from_user_id,
            pair_id=pair_id,
            actor_id=self.raiser.user_id,
            reviewer_id=reviewer_id or self.reviewer_id,
            reason="They never met",
        )
        return described["request_id"]

    async def _approve(self, request_id):
        return await self.approvals.decide(
            self.session,
            request_id=request_id,
            actor_id=self.reviewer_id,
            approve=True,
            comment=None,
        )

    async def _meeting_ids(self):
        rows = await self.session.execute(
            select(MentorshipMeetingEntity.meeting_id).where(
                MentorshipMeetingEntity.pair_id.in_([self.pair_a_id, self.pair_b_id])
            )
        )
        return sorted(rows.scalars().all())

    async def _refresh(self, *rows):
        for row in rows:
            await self.session.refresh(row)

    async def test_ending_one_of_two_pairs_keeps_the_mentor_matched(self):
        closed = await self._approve(
            await self._raise(self.pair_a_id, self.mentor.user_id)
        )

        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        await self._refresh(
            self.pair_a, self.pair_b, self.mentor_reg, self.a_reg, self.b_reg
        )
        self.assertIs(self.pair_a.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_b.status, PairStatus.ACTIVE)
        self.assertIs(self.a_reg.approval_status, ApprovalStatus.UN_MATCHED)
        self.assertIs(self.mentor_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertIs(self.b_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertEqual(await self._meeting_ids(), ["g-a-past", "g-b-up"])

        mia = await self.notes.list_for_user_round(
            self.session, self.mentor.user_id, self.round_id
        )
        ann = await self.notes.list_for_user_round(
            self.session, self.mentee_a.user_id, self.round_id
        )
        for notes in (mia, ann):
            self.assertEqual(len(notes), 1)
            self.assertIs(notes[0].tag, ParticipantNoteTag.STATUS_CHANGE)
            self.assertEqual(notes[0].pair_id, self.pair_a_id)
            self.assertEqual(notes[0].request_id, closed.request_id)
            self.assertEqual(notes[0].author_user_id, self.reviewer_id)
            self.assertIn("1 upcoming meetings cancelled.", notes[0].body)
        self.assertTrue(mia[0].body.startswith("Pair ended. Raised by"))
        self.assertTrue(
            ann[0].body.startswith("Pair ended; matched -> un_matched. Raised by")
        )

    async def test_ending_her_last_pair_unmatches_the_mentor(self):
        await self._approve(await self._raise(self.pair_a_id, self.mentor.user_id))
        await self._approve(await self._raise(self.pair_b_id, self.mentee_b.user_id))

        await self._refresh(self.mentor_reg, self.b_reg)
        self.assertIs(self.mentor_reg.approval_status, ApprovalStatus.UN_MATCHED)
        self.assertIs(self.b_reg.approval_status, ApprovalStatus.UN_MATCHED)

    async def test_the_other_side_cannot_raise_a_second_request(self):
        await self._raise(self.pair_a_id, self.mentor.user_id)

        with self.assertRaises(ConflictError):
            await self._raise(self.pair_a_id, self.mentee_a.user_id)
        # The other pair is a different target.
        await self._raise(self.pair_b_id, self.mentor.user_id)

    async def test_a_pair_ended_since_refuses_the_approval(self):
        request_id = await self._raise(self.pair_a_id, self.mentor.user_id)
        self.pair_a.status = PairStatus.INACTIVE
        await self.session.flush()

        with self.assertRaises(ConflictError) as caught:
            await self._approve(request_id)

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertEqual(str(caught.exception), "This pair has already ended.")
        await self._refresh(self.a_reg)
        self.assertIs(self.a_reg.approval_status, ApprovalStatus.MATCHED)
        self.calendar.cancel.assert_not_awaited()

    async def test_a_calendar_refusal_changes_nothing_and_a_retry_succeeds(self):
        request_id = await self._raise(self.pair_a_id, self.mentor.user_id)
        self.calendar.cancel.side_effect = [([], ["g-a-up"]), (["g-a-up"], [])]

        with self.assertRaises(ConflictError) as caught:
            await self._approve(request_id)
        self.assertEqual(caught.exception.code, "calendar_cancel_failed")
        await self.session.rollback()

        request = await ApprovalRequestRepository().get(self.session, request_id)
        self.assertIs(request.status, ApprovalRequestStatus.PENDING)
        await self._refresh(self.pair_a, self.a_reg)
        self.assertIs(self.pair_a.status, PairStatus.ACTIVE)
        self.assertIs(self.a_reg.approval_status, ApprovalStatus.MATCHED)

        closed = await self._approve(request_id)
        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)

    async def test_either_person_in_the_pair_is_refused_as_reviewer(self):
        for reviewer in (self.mentor.user_id, self.mentee_a.user_id):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(ValueError):
                    await self._raise(
                        self.pair_a_id, self.mentor.user_id, reviewer_id=reviewer
                    )


if __name__ == "__main__":
    unittest.main()
