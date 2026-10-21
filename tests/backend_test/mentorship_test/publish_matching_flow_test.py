"""Publishing a matching result end to end against a real database: raise,
approve, and read back what landed. The unit tests check each step with mocks;
this one checks the steps commit and the rows are really there."""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import select

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    PairStatus,
    ParticipantNoteTag,
    ParticipantRole,
)
from backend.entity.event_entity import EventEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.mentorship.matching_contract import (
    SKILL_KEYS,
    Candidate,
    MenteeResult,
    PersonRecord,
)
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
from backend.mentorship.publish_matching_handler import PublishMatchingHandler
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
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

RUN = "r-flow"


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


class PublishMatchingFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.raiser = _user("Ada")
        # A super admin holds every permission, so may be named as reviewer.
        self.reviewer = _user("Rae", super_admin=True)
        self.mentor = _user("Mia")
        self.spare_mentor = _user("Owen")
        self.mentee = _user("Ann")
        self.unplaced = _user("Cy")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.mentor,
            self.spare_mentor,
            self.mentee,
            self.unplaced,
        ])
        self.round = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        await self.insert_entities([self.round])
        roles = {
            self.mentor: ParticipantRole.MENTOR,
            self.spare_mentor: ParticipantRole.MENTOR,
            self.mentee: ParticipantRole.MENTEE,
            self.unplaced: ParticipantRole.MENTEE,
        }
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=user.user_id,
                round_id=self.round.round_id,
                participant_role=role,
                approval_status=ApprovalStatus.SIGNED_UP,
                max_partners=1,
            )
            for user, role in roles.items()
        ])

        no_skills = {key: False for key in SKILL_KEYS}
        mentor_id, spare_id = str(self.mentor.user_id), str(self.spare_mentor.user_id)
        results = {
            str(self.mentee.user_id): MenteeResult(
                mentor_id=mentor_id,
                match_type="hungarian",
                score=80,
                recommendation_reason="Both work in data",
                candidates=[Candidate(mentor_id=spare_id, score=40)],
            ),
            str(self.unplaced.user_id): MenteeResult(
                candidates=[Candidate(mentor_id=spare_id, score=20)]
            ),
        }
        mentors = {
            mentor_id: PersonRecord(
                role="mentor",
                user_id=mentor_id,
                display_name="Mia",
                skills=no_skills,
                max_partners=1,
            ),
            spare_id: PersonRecord(
                role="mentor",
                user_id=spare_id,
                display_name="Owen",
                skills=no_skills,
                max_partners=1,
            ),
        }
        self.storage = MagicMock()
        self.storage.current_run_id.return_value = RUN
        self.storage.read_run_result.return_value = SimpleNamespace(status="succeeded")
        self.storage.edit_lock.return_value = None
        self.storage.read_all_results.return_value = results
        self.storage.read_draft.return_value = {}
        self.storage.read_all_people.side_effect = lambda run_id, role: (
            mentors if role == "mentor" else {}
        )

        logger = MagicMock()
        self.notes = MentorshipParticipantNoteRepository()
        handler = PublishMatchingHandler(
            matching_storage=self.storage,
            pairs_repository=MentorshipPairsRepository(),
            participants_repository=MentorshipRoundParticipantsRepository(),
            note_repository=self.notes,
            users_repository=UsersRepository(),
            rounds_repository=MentorshipRoundRepository(),
            logger=logger,
            matching_eligibility_service=MatchingEligibilityService(
                participants_repository=MentorshipRoundParticipantsRepository(),
                pairs_repository=MentorshipPairsRepository(),
                rounds_repository=MentorshipRoundRepository(),
                training_repository=TrainingRepository(),
                note_repository=self.notes,
                logger=logger,
            ),
        )
        self.service = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=UserPermissionsRepository(),
            users_repository=UsersRepository(),
            logger=logger,
            handlers=[handler],
        )

    async def _raise(self):
        return await self.service.raise_request(
            self.session,
            action="publish_matching",
            raised_by=self.raiser.user_id,
            target_id=RUN,
            payload={"round_id": self.round.round_id},
            reason="Reviewed every pair",
            reviewer_id=self.reviewer.user_id,
        )

    async def test_approving_writes_the_pairs_statuses_notes_and_events(self):
        request = await self._raise()

        closed = await self.service.decide(
            self.session,
            request_id=request.request_id,
            actor_id=self.reviewer.user_id,
            approve=True,
            comment=None,
        )

        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        self.assertEqual(closed.decided_by, self.reviewer.user_id)

        pairs = (
            (
                await self.session.execute(
                    select(MentorshipPairsEntity).where(
                        MentorshipPairsEntity.round_id == self.round.round_id
                    )
                )
            )
            .scalars()
            .all()
        )
        self.assertEqual(
            [
                (p.mentor_id, p.mentee_id, p.status, p.recommendation_reason)
                for p in pairs
            ],
            [
                (
                    self.mentor.user_id,
                    self.mentee.user_id,
                    PairStatus.ACTIVE,
                    "Both work in data",
                )
            ],
        )

        statuses = dict(
            (
                await self.session.execute(
                    select(
                        MentorshipRoundParticipantsEntity.user_id,
                        MentorshipRoundParticipantsEntity.approval_status,
                    ).where(
                        MentorshipRoundParticipantsEntity.round_id
                        == self.round.round_id
                    )
                )
            ).all()
        )
        self.assertEqual(
            statuses,
            {
                self.mentor.user_id: ApprovalStatus.MATCHED,
                self.mentee.user_id: ApprovalStatus.MATCHED,
                self.spare_mentor.user_id: ApprovalStatus.UN_MATCHED,
                self.unplaced.user_id: ApprovalStatus.UN_MATCHED,
            },
        )

        notes = (
            (
                await self.session.execute(
                    select(MentorshipParticipantNoteEntity).where(
                        MentorshipParticipantNoteEntity.request_id == request.request_id
                    )
                )
            )
            .scalars()
            .all()
        )
        self.assertEqual(len(notes), 4)
        self.assertEqual({n.tag for n in notes}, {ParticipantNoteTag.STATUS_CHANGE})
        self.assertEqual({n.author_user_id for n in notes}, {self.reviewer.user_id})

        events = (
            await self.session.execute(
                select(EventEntity.event_type, EventEntity.details)
                .where(
                    EventEntity.subject_type == "mentorship_round",
                    EventEntity.subject_id == self.round.round_id,
                )
                .order_by(EventEntity.event_id)
            )
        ).all()
        self.assertEqual(
            [(t, d["decision"] if "decision" in d else None) for t, d in events],
            [
                ("mentorship.approval_requested", None),
                ("mentorship.approval_decided", "approved"),
            ],
        )
        self.assertEqual(events[0][1]["roundName"], "Spring 2026")
        self.storage.clear_round_pointer.assert_called_once_with(
            self.round.round_id, RUN
        )

    async def test_a_raised_request_reads_back_whole(self):
        # created_at is the database's default; reading it on the returned row
        # must not need another round trip, which an async session refuses.
        request = await self._raise()

        self.assertIs(request.status, ApprovalRequestStatus.PENDING)
        self.assertIsNotNone(request.created_at)
        self.assertEqual(request.payload, {"round_id": self.round.round_id})

    async def test_a_second_request_on_the_same_run_is_refused(self):
        await self._raise()

        with self.assertRaises(ConflictError):
            await self._raise()

    async def test_a_red_flag_raised_after_the_run_refuses_the_publish(self):
        request = await self._raise()
        await self.notes.create(
            self.session,
            user_id=self.mentee.user_id,
            round_id=self.round.round_id,
            author_user_id=self.reviewer.user_id,
            body="Red flag raised.",
            tag=ParticipantNoteTag.RED_FLAG,
        )

        with self.assertRaises(ConflictError) as caught:
            await self.service.decide(
                self.session,
                request_id=request.request_id,
                actor_id=self.reviewer.user_id,
                approve=True,
                comment=None,
            )

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertIn("has a red flag in this round.", str(caught.exception))
        self.assertIn("Ann", str(caught.exception))

    async def test_rejecting_writes_nothing_but_the_decision(self):
        request = await self._raise()

        closed = await self.service.decide(
            self.session,
            request_id=request.request_id,
            actor_id=self.reviewer.user_id,
            approve=False,
            comment="Mia is away until May",
        )

        self.assertIs(closed.status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(closed.decision_comment, "Mia is away until May")
        pairs = (
            (
                await self.session.execute(
                    select(MentorshipPairsEntity).where(
                        MentorshipPairsEntity.round_id == self.round.round_id
                    )
                )
            )
            .scalars()
            .all()
        )
        self.assertEqual(pairs, [])
        self.storage.clear_round_pointer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
