"""Marks end to end against a real database.

Mentor Mia has two pairs this round, one already ended. Uma registered and
has no pair. Every id is distinct: raiser, reviewer, Mia, her two mentees,
Uma and someone else's pair. Notes written in one transaction share its
start time, so wherever order matters the test sets created_at itself, an
hour or more apart."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantNoteTag,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.exempt_matching_handler import (
    ExemptMatchingHandler,
    exemption_target,
)
from backend.mentorship.mark_participant_handler import (
    MarkNoShowHandler,
    MarkRedFlagHandler,
)
from backend.mentorship.matching_eligibility import HistoryFinding, IneligibleReason
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
from backend.repository.approval_request_repository import ApprovalRequestRepository
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


def _pair(round_id, mentor, mentee, status=PairStatus.ACTIVE):
    return MentorshipPairsEntity(
        round_id=round_id,
        mentor_id=mentor.user_id,
        mentee_id=mentee.user_id,
        completed_count=0,
        status=status,
        mentor_action_status=MentorActionStatus.CONFIRMED,
        mentee_action_status=MenteeActionStatus.CONFIRMED,
        recommendation_reason="",
    )


def _registration(user, round_, role, status, cap=1):
    return MentorshipRoundParticipantsEntity(
        user_id=user.user_id,
        round_id=round_.round_id,
        participant_role=role,
        approval_status=status,
        max_partners=cap,
    )


class MarkParticipantFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.now = now
        self.raiser = _user("Ada")
        self.reviewer = _user("Rae", super_admin=True)
        self.mentor = _user("Mia")
        self.mentee_a = _user("Ann")
        self.mentee_e = _user("Eve")
        self.uma = _user("Uma")
        self.other_mentor = _user("Oto")
        self.other_mentee = _user("Dee")
        self.stranger = _user("Sol")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.mentor,
            self.mentee_a,
            self.mentee_e,
            self.uma,
            self.other_mentor,
            self.other_mentee,
            self.stranger,
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
        self.uma_reg = _registration(
            self.uma, self.round, ParticipantRole.MENTEE, ApprovalStatus.SIGNED_UP
        )
        await self.insert_entities([
            self.mentor_reg,
            _registration(
                self.mentee_a,
                self.round,
                ParticipantRole.MENTEE,
                ApprovalStatus.MATCHED,
            ),
            self.uma_reg,
            TrainingEntity(
                user_id=self.uma.user_id,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
                deadline=now,
            ),
        ])
        self.active_pair = _pair(self.round.round_id, self.mentor, self.mentee_a)
        self.ended_pair = _pair(
            self.round.round_id, self.mentor, self.mentee_e, PairStatus.INACTIVE
        )
        self.other_pair = _pair(
            self.round.round_id, self.other_mentor, self.other_mentee
        )
        await self.insert_entities([self.active_pair, self.ended_pair, self.other_pair])
        # Plain ints: rows expire when a test rolls back.
        self.round_id = self.round.round_id
        self.reviewer_id = self.reviewer.user_id

        logger = MagicMock()
        self.notes = MentorshipParticipantNoteRepository()
        rounds = MentorshipRoundRepository()
        users = UsersRepository()
        participants = MentorshipRoundParticipantsRepository()
        pairs = MentorshipPairsRepository()
        self.eligibility = MatchingEligibilityService(
            participants_repository=participants,
            pairs_repository=pairs,
            rounds_repository=rounds,
            training_repository=TrainingRepository(),
            note_repository=self.notes,
            logger=logger,
        )
        marks = dict(
            participants_repository=participants,
            pairs_repository=pairs,
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
            handlers=[
                MarkNoShowHandler(**marks),
                MarkRedFlagHandler(**marks),
                ExemptMatchingHandler(
                    matching_eligibility_service=self.eligibility,
                    rounds_repository=rounds,
                    note_repository=self.notes,
                    users_repository=users,
                    logger=logger,
                    participants_repository=participants,
                ),
            ],
        )

    async def _raise(self, action, person, pair_id=None):
        payload = {"round_id": self.round_id, "user_id": person.user_id}
        if pair_id is not None:
            payload["pair_id"] = pair_id
        row = await self.service.raise_request(
            self.session,
            action=action,
            raised_by=self.raiser.user_id,
            target_id=exemption_target(self.round_id, person.user_id),
            payload=payload,
            reason="Missed every call",
            reviewer_id=self.reviewer_id,
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

    async def _notes_on(self, person):
        return await self.notes.list_for_user_round(
            self.session, person.user_id, self.round_id
        )

    async def test_a_no_show_about_an_ended_pair_writes_one_note_only(self):
        ended_pair_id = self.ended_pair.pair_id
        closed = await self._approve(
            await self._raise("mark_no_show", self.mentor, ended_pair_id)
        )

        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        (note,) = await self._notes_on(self.mentor)
        self.assertIs(note.tag, ParticipantNoteTag.NO_SHOW)
        self.assertEqual(note.pair_id, ended_pair_id)
        self.assertEqual(note.author_user_id, self.reviewer_id)
        self.assertIn("Missed every call", note.body)
        await self.session.refresh(self.mentor_reg)
        await self.session.refresh(self.active_pair)
        self.assertIs(self.mentor_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertIs(self.active_pair.status, PairStatus.ACTIVE)

    async def test_a_no_show_about_someone_else_s_pair_is_refused(self):
        with self.assertRaises(ConflictError):
            await self._raise("mark_no_show", self.mentor, self.other_pair.pair_id)

    async def test_a_no_show_on_someone_never_paired_is_refused(self):
        with self.assertRaises(ConflictError):
            await self._raise("mark_no_show", self.uma, self.active_pair.pair_id)

    async def test_a_red_flag_on_someone_not_registered_is_refused(self):
        with self.assertRaises(ConflictError):
            await self._raise("mark_red_flag", self.stranger)

    async def test_a_red_flag_may_go_on_someone_who_has_left(self):
        self.uma_reg.approval_status = ApprovalStatus.WITHDRAWN
        await self.session.flush()

        await self._approve(await self._raise("mark_red_flag", self.uma))

        (note,) = await self._notes_on(self.uma)
        self.assertIs(note.tag, ParticipantNoteTag.RED_FLAG)
        self.assertIsNone(note.pair_id)

    async def test_both_marks_may_wait_together_but_not_two_of_one_kind(self):
        await self._raise("mark_no_show", self.mentor, self.active_pair.pair_id)
        await self._raise("mark_red_flag", self.mentor)

        with self.assertRaises(ConflictError):
            await self._raise("mark_no_show", self.mentor, self.ended_pair.pair_id)

    async def test_a_pair_no_longer_hers_at_approval_refuses_it(self):
        request_id = await self._raise(
            "mark_no_show", self.mentor, self.active_pair.pair_id
        )
        self.active_pair.mentor_id = self.other_mentor.user_id
        await self.session.flush()

        with self.assertRaises(ConflictError) as caught:
            await self._approve(request_id)
        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)

    async def test_a_red_flag_after_an_exemption_needs_a_second_one(self):
        # Exempted earlier this round, two hours ago.
        await self.insert_entities([
            MentorshipParticipantNoteEntity(
                user_id=self.uma.user_id,
                round_id=self.round_id,
                author_user_id=self.reviewer_id,
                body="Exempted",
                tag=ParticipantNoteTag.MATCHING_EXEMPTION,
                created_at=self.now - timedelta(hours=2),
            )
        ])
        uma_id = self.uma.user_id
        self.assertIn(
            uma_id, await self.eligibility.eligible_user_ids(self.session, self.round_id)
        )

        await self._approve(await self._raise("mark_red_flag", self.uma))
        # Flagged an hour after that exemption.
        flag = next(
            n
            for n in await self._notes_on(self.uma)
            if n.tag == ParticipantNoteTag.RED_FLAG
        )
        flag.created_at = self.now - timedelta(hours=1)
        await self.session.flush()

        self.assertEqual(
            await self.eligibility.needs_exemption(self.session, self.round_id),
            {uma_id: [HistoryFinding(IneligibleReason.RED_FLAG, self.round_id)]},
        )

        # A second exemption in the same round may be asked for, and clears it.
        await self._approve(await self._raise("exempt_matching", self.uma))
        self.assertIn(
            uma_id, await self.eligibility.eligible_user_ids(self.session, self.round_id)
        )


if __name__ == "__main__":
    unittest.main()
