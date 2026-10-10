"""Blocking a mentor end to end against a real database.

Zed mentors Ann and Bo in Spring 2026, which is under way, and has an old pair
with Old in Fall 2025, which is over. Blocking Zed ends the two Spring pairs,
cancels their upcoming meetings, withdraws Zed from Spring and moves Ann and Bo
to un_matched, while Fall and the bystanders Mo and Cy are left alone. Every id
and name in the fixture is distinct."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from backend.admin.block_service import BlockService
from backend.admin.block_user_handler import BlockUserHandler
from backend.approval.approval_service import ApprovalService
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    MeetingSource,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantRole,
)
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_interview_entity import ApplicationInterviewEntity
from backend.entity.job_entity import JobEntity
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity
from backend.mentorship.meeting_service import MeetingService
from backend.mentorship.mentorship_block_service import MentorshipBlockService
from backend.repository.application_interview_repository import (
    ApplicationInterviewRepository,
)
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
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
from backend.user_identity import notification_renderers  # noqa: F401 (registers)
from backend.user_identity import user_recipient_resolvers  # noqa: F401 (registers)
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


class BlockEndsMentorshipFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.raiser = _user("Ada")
        self.reviewer = _user("Rae", super_admin=True)
        self.operator = _user("Opa", super_admin=True)
        self.zed = _user("Zed")
        self.ann = _user("Ann")
        self.bo = _user("Bo")
        self.mo = _user("Mo")
        self.cy = _user("Cy")
        self.old = _user("Old")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.operator,
            self.zed,
            self.ann,
            self.bo,
            self.mo,
            self.cy,
            self.old,
        ])
        spring = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=4,
            promotion_start_at=now - timedelta(days=10),
            onboarding_deadline_at=now + timedelta(days=10),
            meetings_completion_deadline_at=now + timedelta(days=80),
            feedback_deadline_at=now + timedelta(days=100),
        )
        fall = MentorshipRoundEntity(
            name="Fall 2025",
            required_meetings=4,
            promotion_start_at=now - timedelta(days=300),
            onboarding_deadline_at=now - timedelta(days=280),
            meetings_completion_deadline_at=now - timedelta(days=170),
            feedback_deadline_at=now - timedelta(days=150),
        )
        await self.insert_entities([spring, fall])
        mentor, mentee = ParticipantRole.MENTOR, ParticipantRole.MENTEE
        matched = ApprovalStatus.MATCHED
        self.zed_reg = _registration(self.zed, spring, mentor, matched, 2)
        self.ann_reg = _registration(self.ann, spring, mentee, matched)
        self.bo_reg = _registration(self.bo, spring, mentee, matched)
        self.mo_reg = _registration(self.mo, spring, mentor, matched, 2)
        self.cy_reg = _registration(self.cy, spring, mentee, matched)
        await self.insert_entities([
            self.zed_reg,
            self.ann_reg,
            self.bo_reg,
            self.mo_reg,
            self.cy_reg,
        ])
        self.pair_ann = _pair(spring.round_id, self.zed, self.ann)
        self.pair_bo = _pair(spring.round_id, self.zed, self.bo)
        self.pair_cy = _pair(spring.round_id, self.mo, self.cy)
        self.pair_old = _pair(fall.round_id, self.zed, self.old)
        await self.insert_entities([
            self.pair_ann,
            self.pair_bo,
            self.pair_cy,
            self.pair_old,
        ])
        # Plain ints: the rows expire when a test rolls back.
        self.spring_id = spring.round_id
        self.raiser_id = self.raiser.user_id
        self.reviewer_id = self.reviewer.user_id
        self.operator_id = self.operator.user_id
        self.zed_id = self.zed.user_id
        self.ann_id = self.ann.user_id
        self.bo_id = self.bo.user_id
        self.pair_ann_id = self.pair_ann.pair_id
        self.pair_bo_id = self.pair_bo.pair_id
        await self.insert_entities([
            _google("g-ann-up", self.pair_ann, now + timedelta(days=2)),
            _google("g-ann-past", self.pair_ann, now - timedelta(days=2)),
        ])
        job = JobEntity(kind=JobKind.ACTIVITY, title="Zed block flow job")
        await self.insert_entities([job])
        application = ApplicationEntity(
            job_id=job.job_id, user_id=self.zed_id, stage=ApplicationStage.TECH
        )
        await self.insert_entities([application])
        await self.insert_entities([
            ApplicationInterviewEntity(
                application_id=application.application_id,
                stage=ApplicationStage.TECH,
                round=1,
                google_event_id="zed-interview-event",
                start_at=now + timedelta(days=3),
                end_at=now + timedelta(days=3, hours=1),
                scheduled_by=self.operator_id,
            )
        ])
        # Release the setup savepoint so the rollback in the refusal test
        # discards only what the block did.
        await self.session.commit()

        logger = MagicMock()
        self.calendar = MagicMock()
        self.calendar.cancel = AsyncMock(
            side_effect=lambda ids, calendar_id: (list(ids), [])
        )
        self.notes = MentorshipParticipantNoteRepository()
        rounds = MentorshipRoundRepository()
        users = UsersRepository()
        pairs = MentorshipPairsRepository()
        mentorship = MentorshipBlockService(
            participants_repository=MentorshipRoundParticipantsRepository(),
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
            note_repository=self.notes,
            users_repository=users,
            logger=logger,
        )
        perms = UserPermissionsRepository()
        applications = ApplicationRepository()
        submissions = ApplicationSubmissionRepository()
        interviews = ApplicationInterviewRepository()
        self.interviews_svc = MagicMock()
        self.interviews_svc.cancel_for_round = AsyncMock()
        approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=perms,
            users_repository=users,
            logger=logger,
        )
        approvals.register(
            BlockUserHandler(
                users,
                applications,
                submissions,
                interviews,
                self.interviews_svc,
                mentorship,
            )
        )
        self.service = BlockService(
            users,
            applications,
            submissions,
            interviews,
            self.interviews_svc,
            approvals,
            perms,
            mentorship_block_service=mentorship,
            logger=logger,
        )

    async def _refresh_all(self):
        for row in (
            self.zed,
            self.pair_ann,
            self.pair_bo,
            self.pair_old,
            self.zed_reg,
            self.ann_reg,
            self.bo_reg,
            self.mo_reg,
            self.cy_reg,
        ):
            await self.session.refresh(row)

    async def _meeting_ids(self):
        rows = await self.session.execute(
            select(MentorshipMeetingEntity.meeting_id).where(
                MentorshipMeetingEntity.pair_id.in_(
                    [self.pair_ann_id, self.pair_bo_id]
                )
            )
        )
        return sorted(rows.scalars().all())

    async def test_approving_a_block_ends_the_pairs_and_keeps_the_reason_out_of_notes(self):
        raised = await self.service.raise_request(
            self.session,
            actor_id=self.raiser_id,
            user_id=self.zed_id,
            reason="Harassed a mentee in a session",
            reviewer_id=self.reviewer_id,
            raised_from="mentorship_participant",
        )
        await self.service.decide(
            self.session,
            actor_id=self.reviewer_id,
            request_id=raised.id,
            approved=True,
            note=None,
        )

        await self._refresh_all()
        self.assertTrue(self.zed.is_blocked)
        self.assertIs(self.pair_ann.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_bo.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_old.status, PairStatus.ACTIVE)
        self.assertIs(self.zed_reg.approval_status, ApprovalStatus.WITHDRAWN)
        self.assertIs(self.ann_reg.approval_status, ApprovalStatus.UN_MATCHED)
        self.assertIs(self.bo_reg.approval_status, ApprovalStatus.UN_MATCHED)
        self.assertIs(self.cy_reg.approval_status, ApprovalStatus.MATCHED)
        self.assertEqual(await self._meeting_ids(), ["g-ann-past"])
        notes = [
            *await self.notes.list_for_user_round(self.session, self.zed_id, self.spring_id),
            *await self.notes.list_for_user_round(self.session, self.ann_id, self.spring_id),
            *await self.notes.list_for_user_round(self.session, self.bo_id, self.spring_id),
        ]
        self.assertEqual(len(notes), 3)
        for note in notes:
            self.assertEqual(note.request_id, raised.id)
            self.assertEqual(note.author_user_id, self.reviewer_id)
            self.assertNotIn("Harassed", note.body)
        self.calendar.cancel.assert_awaited_once_with(["g-ann-up"], calendar_id="cal-test")

    async def test_an_operator_block_ends_the_pairs_with_no_request(self):
        await self.service.block_directly(
            self.session,
            actor_id=self.operator_id,
            user_id=self.zed_id,
            reason="Fabricated credentials",
        )

        await self._refresh_all()
        self.assertIs(self.pair_ann.status, PairStatus.INACTIVE)
        notes = await self.notes.list_for_user_round(
            self.session, self.ann_id, self.spring_id
        )
        self.assertEqual(len(notes), 1)
        self.assertIsNone(notes[0].request_id)
        self.assertEqual(notes[0].author_user_id, self.operator_id)

    async def test_a_calendar_refusal_blocks_nobody_and_a_retry_succeeds(self):
        self.calendar.cancel = AsyncMock(return_value=([], ["g-ann-up"]))

        with self.assertRaises(ConflictError) as caught:
            await self.service.block_directly(
                self.session,
                actor_id=self.operator_id,
                user_id=self.zed_id,
                reason="Fabricated credentials",
            )
        await self.session.rollback()

        self.assertEqual(caught.exception.code, "calendar_cancel_failed")
        self.assertIn("nobody was blocked", str(caught.exception))
        await self._refresh_all()
        self.assertFalse(self.zed.is_blocked)
        self.assertIs(self.pair_ann.status, PairStatus.ACTIVE)
        self.assertIs(self.zed_reg.approval_status, ApprovalStatus.MATCHED)
        self.interviews_svc.cancel_for_round.assert_not_awaited()
        self.assertEqual(await self._meeting_ids(), ["g-ann-past", "g-ann-up"])
        for user_id in (self.zed_id, self.ann_id, self.bo_id):
            self.assertEqual(
                await self.notes.list_for_user_round(
                    self.session, user_id, self.spring_id
                ),
                [],
            )

        self.calendar.cancel = AsyncMock(side_effect=lambda ids, calendar_id: (list(ids), []))
        await self.service.block_directly(
            self.session,
            actor_id=self.operator_id,
            user_id=self.zed_id,
            reason="Fabricated credentials",
        )
        await self._refresh_all()
        self.assertTrue(self.zed.is_blocked)
        self.assertIs(self.pair_ann.status, PairStatus.INACTIVE)
        self.interviews_svc.cancel_for_round.assert_awaited_once()
        count = 0
        for user_id in (self.zed_id, self.ann_id, self.bo_id):
            count += len(
                await self.notes.list_for_user_round(
                    self.session, user_id, self.spring_id
                )
            )
        self.assertEqual(count, 3)

    async def test_the_preflight_counts_the_mentorship_it_ends(self):
        view = await self.service.preflight(self.session, self.zed_id)

        self.assertEqual(view.mentorship_pair_count, 2)
        self.assertEqual(view.mentorship_meeting_count, 1)


if __name__ == "__main__":
    unittest.main()
