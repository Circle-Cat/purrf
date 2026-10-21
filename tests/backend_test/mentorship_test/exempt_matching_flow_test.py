"""A matching exemption end to end against a real database: someone short of
meetings last round needs one, it is raised and approved, and the
eligibility check then lets them in."""

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
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
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
from backend.mentorship.exempt_matching_handler import (
    ExemptMatchingHandler,
    exemption_target,
)
from backend.mentorship.matching_eligibility import IneligibleReason
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
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


class ExemptMatchingFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.raiser = _user("Ada")
        self.reviewer = _user("Rae", super_admin=True)
        self.mentee = _user("Ann")
        self.old_mentor = _user("Mia")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.mentee,
            self.old_mentor,
        ])
        self.last_round = MentorshipRoundEntity(
            name="Fall 2025",
            required_meetings=5,
            promotion_start_at=now - timedelta(days=300),
            onboarding_deadline_at=now - timedelta(days=260),
            meetings_completion_deadline_at=now - timedelta(days=120),
            feedback_deadline_at=now - timedelta(days=100),
        )
        self.round = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=5,
            promotion_start_at=now - timedelta(days=10),
            onboarding_deadline_at=now + timedelta(days=20),
            meetings_completion_deadline_at=now + timedelta(days=80),
            feedback_deadline_at=now + timedelta(days=100),
        )
        await self.insert_entities([self.last_round, self.round])
        # Last round her pair ran to the end with no meetings held.
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.mentee.user_id,
                round_id=self.last_round.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipPairsEntity(
                round_id=self.last_round.round_id,
                mentor_id=self.old_mentor.user_id,
                mentee_id=self.mentee.user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
            ),
            # This round she is registered and has done the course.
            MentorshipRoundParticipantsEntity(
                user_id=self.mentee.user_id,
                round_id=self.round.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
            TrainingEntity(
                user_id=self.mentee.user_id,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
                deadline=now,
            ),
        ])

        logger = MagicMock()
        notes = MentorshipParticipantNoteRepository()
        self.eligibility = MatchingEligibilityService(
            participants_repository=MentorshipRoundParticipantsRepository(),
            pairs_repository=MentorshipPairsRepository(),
            rounds_repository=MentorshipRoundRepository(),
            training_repository=TrainingRepository(),
            note_repository=notes,
            logger=logger,
        )
        handler = ExemptMatchingHandler(
            matching_eligibility_service=self.eligibility,
            rounds_repository=MentorshipRoundRepository(),
            note_repository=notes,
            users_repository=UsersRepository(),
            logger=logger,
            participants_repository=MentorshipRoundParticipantsRepository(),
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
            action="exempt_matching",
            raised_by=self.raiser.user_id,
            target_id=exemption_target(self.round.round_id, self.mentee.user_id),
            payload={"round_id": self.round.round_id, "user_id": self.mentee.user_id},
            reason="Her mentor stopped replying in week two",
            reviewer_id=self.reviewer.user_id,
        )

    async def test_an_approved_exemption_lets_her_into_matching(self):
        needing = await self.eligibility.needs_exemption(
            self.session, self.round.round_id
        )
        self.assertEqual(
            [f.reason for f in needing[self.mentee.user_id]],
            [IneligibleReason.MEETINGS_SHORT],
        )
        self.assertEqual(
            needing[self.mentee.user_id][0].round_id, self.last_round.round_id
        )

        request = await self._raise()
        closed = await self.service.decide(
            self.session,
            request_id=request.request_id,
            actor_id=self.reviewer.user_id,
            approve=True,
            comment=None,
        )

        self.assertIs(closed.status, ApprovalRequestStatus.APPROVED)
        self.assertIn(
            self.mentee.user_id,
            await self.eligibility.eligible_user_ids(self.session, self.round.round_id),
        )
        self.assertEqual(
            await self.eligibility.needs_exemption(self.session, self.round.round_id),
            {},
        )

    async def test_once_exempted_another_request_is_refused(self):
        request = await self._raise()
        await self.service.decide(
            self.session,
            request_id=request.request_id,
            actor_id=self.reviewer.user_id,
            approve=True,
            comment=None,
        )

        with self.assertRaises(ConflictError):
            await self._raise()

    async def test_a_rejected_exemption_leaves_her_out(self):
        request = await self._raise()
        await self.service.decide(
            self.session,
            request_id=request.request_id,
            actor_id=self.reviewer.user_id,
            approve=False,
            comment="Two rounds short in a row",
        )

        self.assertNotIn(
            self.mentee.user_id,
            await self.eligibility.eligible_user_ids(self.session, self.round.round_id),
        )

    async def test_an_exemption_for_someone_withdrawn_since_is_refused(self):
        request = await self._raise()
        request_id = request.request_id
        registration = (
            await MentorshipRoundParticipantsRepository().get_by_user_id_and_round_id(
                self.session, self.mentee.user_id, self.round.round_id
            )
        )
        registration.approval_status = ApprovalStatus.WITHDRAWN
        await self.session.flush()

        with self.assertRaises(ConflictError) as caught:
            await self.service.decide(
                self.session,
                request_id=request_id,
                actor_id=self.reviewer.user_id,
                approve=True,
                comment=None,
            )

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertIn("has left this round", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
