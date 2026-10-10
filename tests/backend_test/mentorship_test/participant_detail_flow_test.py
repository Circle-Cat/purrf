"""The page for one person in one round, read against a real database.

The fixture keeps every value it could confuse distinct: two partners with
different names, two note authors, three rounds whose deadlines sort
differently from their ids."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from backend.admin.block_service import BLOCK_TARGET, BLOCK_USER
from backend.admin.block_user_handler import BlockUserHandler
from backend.approval.approval_service import ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError, NotFoundError
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
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
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
from backend.mentorship.end_pair_handler import EndPairHandler
from backend.mentorship.exempt_matching_handler import (
    ExemptMatchingHandler,
    exemption_target,
)
from backend.mentorship.mark_participant_handler import (
    MarkNoShowHandler,
    MarkRedFlagHandler,
)
from backend.mentorship.withdraw_participant_handler import WithdrawParticipantHandler
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.mentorship.mentorship_approval_service import MentorshipApprovalService
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.repository.application_repository import ApplicationRepository
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


def _user(first):
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


def _pair(round_id, mentor_id, mentee_id, status=PairStatus.ACTIVE):
    return MentorshipPairsEntity(
        round_id=round_id,
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        completed_count=0,
        status=status,
        mentor_action_status=MentorActionStatus.CONFIRMED,
        mentee_action_status=MenteeActionStatus.CONFIRMED,
        recommendation_reason="",
    )


def _meeting(pair_id, start):
    return MentorshipMeetingEntity(
        meeting_id=uuid.uuid4().hex,
        pair_id=pair_id,
        source=MeetingSource.MANUAL,
        start_datetime=start,
        end_datetime=start + timedelta(hours=1),
        created_datetime=start,
        is_completed=False,
    )


class ParticipantDetailFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.now = now
        self.mentee = _user("Ann")
        self.mentor = _user("Mia")
        self.old_mentor = _user("Oto")
        self.writer = _user("Wes")
        self.approver = _user("Ari")
        self.stranger = _user("Sol")
        await self.insert_entities([
            self.mentee,
            self.mentor,
            self.old_mentor,
            self.writer,
            self.approver,
            self.stranger,
        ])

        # Inserted newest first, so ids run opposite to deadlines.
        self.round = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=4,
            promotion_start_at=now - timedelta(days=10),
            onboarding_deadline_at=now + timedelta(days=10),
            meetings_completion_deadline_at=now + timedelta(days=80),
            feedback_deadline_at=now + timedelta(days=100),
        )
        self.fall = MentorshipRoundEntity(
            name="Fall 2025",
            required_meetings=5,
            promotion_start_at=now - timedelta(days=300),
            onboarding_deadline_at=now - timedelta(days=260),
            meetings_completion_deadline_at=now - timedelta(days=120),
            feedback_deadline_at=now - timedelta(days=100),
        )
        self.spring = MentorshipRoundEntity(
            name="Spring 2025",
            required_meetings=6,
            promotion_start_at=now - timedelta(days=500),
            onboarding_deadline_at=now - timedelta(days=460),
            meetings_completion_deadline_at=now - timedelta(days=320),
            feedback_deadline_at=now - timedelta(days=300),
        )
        await self.insert_entities([self.round, self.fall, self.spring])

        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.mentee.user_id,
                round_id=self.round.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
                program_feedback={
                    "most_valuable_aspects": "Mock interviews",
                    "challenges": "Time zones",
                    "program_rating": 4,
                },
                pair_feedback=[
                    {"partner_id": self.mentor.user_id, "rating": 5, "feedback": "Kind"}
                ],
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.mentee.user_id,
                round_id=self.fall.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.mentee.user_id,
                round_id=self.spring.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.UN_MATCHED,
            ),
        ])
        # The participant search only lists people with a mentorship
        # onboarding record.
        await self.insert_entities([
            TrainingEntity(
                user_id=self.mentee.user_id,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
                deadline=now,
            )
        ])
        self.current_pair = _pair(
            self.round.round_id, self.mentor.user_id, self.mentee.user_id
        )
        self.fall_pair = _pair(
            self.fall.round_id,
            self.old_mentor.user_id,
            self.mentee.user_id,
            status=PairStatus.INACTIVE,
        )
        await self.insert_entities([self.current_pair, self.fall_pair])
        self.first_meeting = now - timedelta(days=3)
        await self.insert_entities([
            _meeting(self.current_pair.pair_id, now + timedelta(days=4)),
            _meeting(self.current_pair.pair_id, self.first_meeting),
        ])

        self.notes = MentorshipParticipantNoteRepository()
        logger = MagicMock()
        rounds = MentorshipRoundRepository()
        users = UsersRepository()
        participants = MentorshipRoundParticipantsRepository()
        self.approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=UserPermissionsRepository(),
            users_repository=users,
            logger=logger,
            handlers=[],
        )
        self.approvals.register(
            BlockUserHandler(
                users,
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
            )
        )
        self.approvals.register(
            WithdrawParticipantHandler(
                participants_repository=participants,
                pairs_repository=MentorshipPairsRepository(),
                meeting_service=MagicMock(),
                rounds_repository=rounds,
                note_repository=self.notes,
                users_repository=users,
                logger=logger,
            )
        )
        self.approvals.register(
            EndPairHandler(
                participants_repository=participants,
                pairs_repository=MentorshipPairsRepository(),
                meeting_service=MagicMock(),
                rounds_repository=rounds,
                note_repository=self.notes,
                users_repository=users,
                logger=logger,
            )
        )
        eligibility = MatchingEligibilityService(
            participants_repository=participants,
            pairs_repository=MentorshipPairsRepository(),
            rounds_repository=rounds,
            training_repository=TrainingRepository(),
            note_repository=self.notes,
            logger=logger,
        )
        self.approvals.register(
            ExemptMatchingHandler(
                matching_eligibility_service=eligibility,
                rounds_repository=rounds,
                note_repository=self.notes,
                users_repository=users,
                logger=logger,
                participants_repository=participants,
            )
        )
        for handler in (MarkNoShowHandler, MarkRedFlagHandler):
            self.approvals.register(
                handler(
                    participants_repository=participants,
                    pairs_repository=MentorshipPairsRepository(),
                    rounds_repository=rounds,
                    note_repository=self.notes,
                    users_repository=users,
                    logger=logger,
                )
            )
        self.service = MentorshipAdminService(
            users_repository=users,
            participants_repository=participants,
            rounds_repository=rounds,
            training_repository=TrainingRepository(),
            pairs_repository=MentorshipPairsRepository(),
            mentorship_mapper=MentorshipMapper(),
            logger=logger,
            mentorship_meeting_repository=MentorshipMeetingRepository(),
            application_repository=ApplicationRepository(),
            matching_eligibility_service=eligibility,
            mentorship_approval_service=MentorshipApprovalService(
                approval_service=self.approvals,
                matching_storage=MagicMock(),
                users_repository=users,
                rounds_repository=rounds,
                pairs_repository=MentorshipPairsRepository(),
                logger=logger,
            ),
            note_repository=self.notes,
            approval_service=self.approvals,
            mentorship_email_service=MagicMock(),
        )

    async def _detail(self, round_=None, user=None):
        return await self.service.get_participant_detail(
            self.session,
            (round_ or self.round).round_id,
            (user or self.mentee).user_id,
        )

    async def _note(self, user, round_, tag, hours_ago, pair_id=None):
        await self.insert_entities([
            MentorshipParticipantNoteEntity(
                user_id=user.user_id,
                round_id=round_.round_id,
                author_user_id=self.approver.user_id,
                body=tag.value,
                tag=tag,
                pair_id=pair_id,
                created_at=self.now - timedelta(hours=hours_ago),
            )
        ])

    async def test_rows_count_marks_in_their_own_round(self):
        await self._note(
            self.mentee,
            self.fall,
            ParticipantNoteTag.NO_SHOW,
            5,
            pair_id=self.fall_pair.pair_id,
        )
        await self._note(self.mentee, self.round, ParticipantNoteTag.RED_FLAG, 4)

        detail = await self._detail()

        self.assertEqual(
            (detail.registration.marks.no_show, detail.registration.marks.red_flag),
            (0, 1),
        )
        self.assertEqual(
            [(h.round_name, h.marks.no_show, h.marks.red_flag) for h in detail.history],
            [("Fall 2025", 1, 0), ("Spring 2025", 0, 0)],
        )

    async def test_a_mark_after_this_round_s_exemption_shows_again(self):
        uma = _user("Uma")
        await self.insert_entities([uma])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=uma.user_id,
                round_id=self.round.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
            TrainingEntity(
                user_id=uma.user_id,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
                deadline=self.now,
            ),
        ])
        await self._note(uma, self.round, ParticipantNoteTag.MATCHING_EXEMPTION, 2)
        await self._note(uma, self.round, ParticipantNoteTag.RED_FLAG, 1)

        detail = await self._detail(user=uma)

        self.assertTrue(detail.exempted)
        self.assertEqual(
            [
                (f.reason, f.round_id, f.round_name)
                for f in detail.registration.exemption_findings
            ],
            [("red_flag", self.round.round_id, "Spring 2026")],
        )
        self.assertEqual(detail.registration.marks.red_flag, 1)

    async def test_the_round_registration_and_pair(self):
        detail = await self._detail()

        self.assertEqual(detail.person.user_id, self.mentee.user_id)
        self.assertEqual(detail.round.name, "Spring 2026")
        self.assertEqual(detail.round.required_meetings, 4)
        self.assertTrue(detail.round.in_progress)
        self.assertEqual(detail.registration.round_id, self.round.round_id)
        (pair,) = detail.registration.pairs
        self.assertEqual(pair.partner.id, self.mentor.user_id)
        self.assertEqual(pair.first_meeting_at, self.first_meeting)

    async def test_history_lists_only_earlier_rounds_newest_first(self):
        await self.notes.create(
            self.session,
            user_id=self.mentee.user_id,
            round_id=self.fall.round_id,
            author_user_id=self.approver.user_id,
            body="Exempted",
            tag=ParticipantNoteTag.MATCHING_EXEMPTION,
        )

        detail = await self._detail()

        self.assertEqual(
            [(h.round_name, h.exempted) for h in detail.history],
            [("Fall 2025", True), ("Spring 2025", False)],
        )
        self.assertEqual(detail.history[0].pairs[0].partner.id, self.old_mentor.user_id)
        self.assertFalse(detail.exempted)

    async def test_an_earlier_round_has_no_later_round_in_its_history(self):
        detail = await self._detail(round_=self.fall)

        self.assertEqual([h.round_name for h in detail.history], ["Spring 2025"])
        self.assertFalse(detail.round.in_progress)

    async def test_feedback_is_this_rounds_and_names_the_partner(self):
        detail = await self._detail()

        self.assertTrue(detail.feedback.has_submitted)
        self.assertEqual(detail.feedback.program_rating, 4)
        (about,) = detail.feedback.partner_feedback
        self.assertEqual(about.partner_id, self.mentor.user_id)
        self.assertTrue(about.partner_name.startswith("Mia"))

    async def test_no_pair_means_no_feedback(self):
        detail = await self._detail(round_=self.spring)

        self.assertIsNone(detail.feedback)

    async def test_notes_newest_first_with_their_authors(self):
        older = await self.notes.create(
            self.session,
            user_id=self.mentee.user_id,
            round_id=self.round.round_id,
            author_user_id=self.writer.user_id,
            body="Called her",
        )
        older.created_at = self.now - timedelta(days=2)
        newer = await self.notes.create(
            self.session,
            user_id=self.mentee.user_id,
            round_id=self.round.round_id,
            author_user_id=self.approver.user_id,
            body="Status changed",
            tag=ParticipantNoteTag.STATUS_CHANGE,
        )
        newer.created_at = self.now - timedelta(days=1)
        await self.notes.create(
            self.session,
            user_id=self.mentee.user_id,
            round_id=self.fall.round_id,
            author_user_id=self.writer.user_id,
            body="Another round",
        )
        await self.session.flush()

        detail = await self._detail()

        self.assertEqual(
            [(n.body, n.tag, n.author.user_id) for n in detail.notes],
            [
                (
                    "Status changed",
                    ParticipantNoteTag.STATUS_CHANGE,
                    self.approver.user_id,
                ),
                ("Called her", None, self.writer.user_id),
            ],
        )
        self.assertTrue(detail.notes[1].author.name.startswith("Wes"))

    async def test_someone_not_registered_still_has_a_page(self):
        await self.notes.create(
            self.session,
            user_id=self.stranger.user_id,
            round_id=self.round.round_id,
            author_user_id=self.writer.user_id,
            body="Asked about next round",
        )

        detail = await self._detail(user=self.stranger)

        self.assertIsNone(detail.registration)
        self.assertIsNone(detail.feedback)
        self.assertEqual(detail.history, [])
        self.assertEqual([n.body for n in detail.notes], ["Asked about next round"])

    async def test_a_pending_block_request_names_only_its_reviewer(self):
        row = ApprovalRequestEntity(
            action=BLOCK_USER,
            target_type=BLOCK_TARGET,
            target_id=str(self.mentee.user_id),
            payload={"raised_from": "mentorship_participant"},
            reason="Harassment",
            raised_by=self.writer.user_id,
            reviewer_id=self.approver.user_id,
            status=ApprovalRequestStatus.PENDING,
        )
        await self.insert_entities([row])

        detail = await self._detail()

        self.assertEqual(detail.pending_block_request.request_id, row.request_id)
        self.assertEqual(
            detail.pending_block_request.reviewer.user_id, self.approver.user_id
        )
        self.assertIsNone((await self._detail(user=self.mentor)).pending_block_request)

    async def test_pending_requests_name_who_raised_them_and_who_decides(self):
        target = exemption_target(self.round.round_id, self.mentee.user_id)
        pending = ApprovalRequestEntity(
            action="withdraw_participant",
            target_type="round_participant",
            target_id=target,
            payload={"round_id": self.round.round_id, "user_id": self.mentee.user_id},
            reason="Stopped replying",
            raised_by=self.writer.user_id,
            reviewer_id=self.approver.user_id,
            status=ApprovalRequestStatus.PENDING,
        )
        closed = ApprovalRequestEntity(
            action="withdraw_participant",
            target_type="round_participant",
            target_id=target,
            payload={"round_id": self.round.round_id, "user_id": self.mentee.user_id},
            reason=None,
            raised_by=self.approver.user_id,
            reviewer_id=self.writer.user_id,
            status=ApprovalRequestStatus.WITHDRAWN,
        )
        await self.insert_entities([pending, closed])

        detail = await self._detail()

        self.assertEqual(
            [r.request_id for r in detail.pending_requests], [pending.request_id]
        )
        only = detail.pending_requests[0]
        self.assertEqual(only.action, "withdraw_participant")
        self.assertEqual(only.raised_by.user_id, self.writer.user_id)
        self.assertEqual(only.raised_by.name.split()[0], "Wes")
        self.assertEqual(only.reviewer.user_id, self.approver.user_id)
        self.assertEqual(only.reason, "Stopped replying")
        self.assertIsNotNone(only.created_at)
        self.assertEqual((await self._detail(user=self.mentor)).pending_requests, [])

    async def test_a_pending_mark_names_the_pair_it_is_about(self):
        pending = ApprovalRequestEntity(
            action="mark_no_show",
            target_type="round_participant",
            target_id=exemption_target(self.round.round_id, self.mentee.user_id),
            payload={
                "round_id": self.round.round_id,
                "user_id": self.mentee.user_id,
                "pair_id": self.current_pair.pair_id,
            },
            reason=None,
            raised_by=self.writer.user_id,
            reviewer_id=self.approver.user_id,
            status=ApprovalRequestStatus.PENDING,
        )
        await self.insert_entities([pending])

        detail = await self._detail()

        (only,) = detail.pending_requests
        self.assertEqual(only.action, "mark_no_show")
        self.assertEqual(only.pair_id, self.current_pair.pair_id)

    async def test_a_pending_end_pair_shows_on_both_pages(self):
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.mentor.user_id,
                round_id=self.round.round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            TrainingEntity(
                user_id=self.mentor.user_id,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.DONE,
                deadline=self.now,
            ),
        ])
        pending = ApprovalRequestEntity(
            action="end_pair",
            target_type="mentorship_pair",
            target_id=str(self.current_pair.pair_id),
            payload={
                "round_id": self.round.round_id,
                "pair_id": self.current_pair.pair_id,
                "mentor_id": self.mentor.user_id,
                "mentee_id": self.mentee.user_id,
            },
            reason=None,
            raised_by=self.writer.user_id,
            reviewer_id=self.approver.user_id,
            status=ApprovalRequestStatus.PENDING,
        )
        await self.insert_entities([pending])

        for user in (self.mentee, self.mentor):
            with self.subTest(user=user.first_name):
                (only,) = (await self._detail(user=user)).pending_requests
                self.assertEqual(only.action, "end_pair")
                self.assertEqual(only.pair_id, self.current_pair.pair_id)
                self.assertEqual(only.pair.mentor.user_id, self.mentor.user_id)
                self.assertEqual(only.pair.mentee.user_id, self.mentee.user_id)

    async def test_unknown_round_or_user_is_not_found(self):
        with self.assertRaises(NotFoundError):
            await self.service.get_participant_detail(
                self.session, 999999, self.mentee.user_id
            )
        with self.assertRaises(NotFoundError):
            await self.service.get_participant_detail(
                self.session, self.round.round_id, 999999
            )

    async def test_a_note_written_is_committed_and_read_back(self):
        note = await self.service.add_participant_note(
            self.session,
            round_id=self.round.round_id,
            user_id=self.stranger.user_id,
            author_id=self.writer.user_id,
            body="Not registered yet; emailed her",
        )

        self.assertIsNone(note.tag)
        self.assertIsNone(note.pair_id)
        self.assertEqual(note.author.user_id, self.writer.user_id)
        self.assertIsNotNone(note.created_at)
        round_id, user_id = self.round.round_id, self.stranger.user_id
        # The session runs inside a savepoint: a rollback here throws away
        # anything only flushed, and keeps what the service committed.
        await self.session.rollback()
        detail = await self.service.get_participant_detail(
            self.session, round_id, user_id
        )
        self.assertEqual([n.note_id for n in detail.notes], [note.note_id])

    async def test_a_round_not_in_progress_takes_no_notes(self):
        with self.assertRaises(ConflictError) as caught:
            await self.service.add_participant_note(
                self.session,
                round_id=self.fall.round_id,
                user_id=self.mentee.user_id,
                author_id=self.writer.user_id,
                body="Too late",
            )

        self.assertEqual(caught.exception.code, "round_not_in_progress")
        self.assertEqual((await self._detail(round_=self.fall)).notes, [])

    async def test_a_note_on_nobody_is_not_found(self):
        with self.assertRaises(NotFoundError):
            await self.service.add_participant_note(
                self.session,
                round_id=self.round.round_id,
                user_id=999999,
                author_id=self.writer.user_id,
                body="Who?",
            )


if __name__ == "__main__":
    unittest.main()
