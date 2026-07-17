import unittest
from datetime import datetime, timezone

from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.job_entity import JobEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.training_entity import TrainingEntity
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
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
from backend.common.recruiting_enums import ApplicationStage, JobKind
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestMentorshipRoundParticipantsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundParticipantsRepository()

        self.user = UsersEntity(
            first_name="Alice",
            last_name="Admin",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

        await self.insert_entities([self.user])
        await self._hire_for_activity(self.user)

        self.rounds = [
            MentorshipRoundEntity(
                name="2025-spring",
                mentee_average_score=4.3,
                mentor_average_score=4.5,
                expectations="improving mentee's ability",
                description={
                    "goal": "basic skills",
                    "meetings_completion_deadline_at": "2025-06-30T00:00:00+00:00",
                },
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                mentee_average_score=4.8,
                mentor_average_score=4.6,
                expectations="guiding career development paths",
                description={
                    "goal": "career planning",
                    "meetings_completion_deadline_at": "2025-12-31T00:00:00+00:00",
                },
                required_meetings=5,
            ),
        ]

        await self.insert_entities(self.rounds)

    def _make_user(
        self, *, first_name="Test", last_name="User", email, preferred_name=None
    ):
        return UsersEntity(
            first_name=first_name,
            last_name=last_name,
            preferred_name=preferred_name,
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email=email,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def _hire_for_activity(self, user, role=ParticipantRole.MENTEE):
        """Insert a hired application to an activity posting for the given user."""
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=role,
            title=f"{role.value} activity",
        )
        await self.insert_entities([job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            )
        ])

    async def _add_training(
        self,
        user,
        category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        status=TrainingStatus.DONE,
    ):
        """Insert a training record for the given user, category, and status."""
        await self.insert_entities([
            TrainingEntity(
                user_id=user.user_id,
                category=category,
                status=status,
                deadline=datetime.now(timezone.utc),
            )
        ])

    async def test_get_by_user_id_and_round_id(self):
        """Test retrieve a mentorship round participants entity."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.user.user_id)
        self.assertEqual(result.round_id, self.rounds[0].round_id)

    async def test_get_by_user_id_and_round_id_empty(self):
        """Test retrieve none when the participants table is empty."""
        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNone(result)

    async def test_get_by_user_id_and_round_id_not_found(self):
        """Test retrieve none when participants exist but none match the given IDs."""
        participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
        )
        await self.insert_entities([participant])

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[1].round_id
        )

        self.assertIsNone(result)

    async def test_get_recent_participant_by_user_id(self):
        """Ensure the participant in the round with the latest meetings_completion_deadline_at is returned."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.round_id, self.rounds[1].round_id)

    async def test_get_recent_participant_by_user_id_empty(self):
        """Should return None if the user has no participant records."""
        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNone(result)

    async def test_upsert_participant_insert(self):
        """Test insert a new participant entity correctly."""
        participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[1].round_id,
        )

        result = await self.repo.upsert_participant(self.session, participant)

        self.assertIsNotNone(result.participant_id)
        self.assertEqual(result.user_id, self.user.user_id)
        self.assertEqual(result.round_id, self.rounds[1].round_id)

    async def test_get_average_program_rating_by_round_and_role(self):
        """Returns the average program_rating across all matching participants."""
        user2 = self._make_user(
            first_name="Bob", last_name="Builder", email="bob@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 4},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 2},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 3.0)

    async def test_get_average_program_rating_excludes_other_role(self):
        """Does not include participants with a different role in the average."""
        user2 = self._make_user(
            first_name="Carol", last_name="Coach", email="carol@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 5},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                program_feedback={"program_rating": 1},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 5.0)

    async def test_get_average_program_rating_excludes_null_ratings(self):
        """Skips participants whose program_feedback has no program_rating key."""
        user2 = self._make_user(
            first_name="Dave", last_name="Doe", email="dave@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 4},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"most_valuable_aspects": "networking"},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 4.0)

    async def test_get_average_program_rating_returns_none_when_no_ratings(self):
        """Returns None when no participants in the round/role have submitted a rating."""
        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertIsNone(result)

    async def test_upsert_participant_update(self):
        """Test update an existing participant entity correctly."""
        old_participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
            match_email_sent=False,
            expected_partner_user_id=[],
            goal="",
        )
        await self.insert_entities([old_participant])

        participant = MentorshipRoundParticipantsEntity(
            participant_id=old_participant.participant_id,
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
            match_email_sent=True,
            expected_partner_user_id=[456],
            goal="New goal",
        )

        result = await self.repo.upsert_participant(self.session, participant)

        self.assertEqual(result.participant_id, old_participant.participant_id)
        self.assertTrue(result.match_email_sent)
        self.assertEqual(
            result.expected_partner_user_id, participant.expected_partner_user_id
        )
        self.assertEqual(result.goal, participant.goal)

    async def test_search_no_filters_returns_all_mentorship_users(self):
        """Verify all users meeting the base mentorship gate are returned
        when no filters are applied."""
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self._hire_for_activity(user2)

        rows, total = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=50, offset=0
        )

        self.assertEqual(total, 2)
        user_ids = {r.user_id for r in rows}
        self.assertIn(self.user.user_id, user_ids)
        self.assertIn(user2.user_id, user_ids)

    async def test_search_includes_onboarding_training_only_users(self):
        """Ensure users with mentorship onboarding training are included,
        while unrelated categories are excluded."""
        trained_user = self._make_user(
            first_name="Tina", last_name="Trained", email="tina@example.com"
        )
        unrelated_trained_user = self._make_user(
            first_name="Rey", last_name="Resident", email="rey@example.com"
        )
        await self.insert_entities([trained_user, unrelated_trained_user])
        await self._add_training(trained_user)
        await self._add_training(
            unrelated_trained_user,
            category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
        )

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=20, offset=0
        )

        user_ids = {r.user_id for r in rows}
        self.assertIn(trained_user.user_id, user_ids)
        self.assertNotIn(unrelated_trained_user.user_id, user_ids)

    async def test_search_onboarding_status_completed_by_role(self):
        """MENTOR only checks mentor training; MENTEE only checks mentee
        training; no role (non-participant) counts either category."""
        mentor_user = self._make_user(
            first_name="Mel", last_name="Mentor", email="mel@example.com"
        )
        mentee_user = self._make_user(
            first_name="Nia", last_name="Mentee", email="nia@example.com"
        )
        non_participant_user = self._make_user(
            first_name="Norah", last_name="NonParticipant", email="norah@example.com"
        )
        await self.insert_entities([mentor_user, mentee_user, non_participant_user])
        await self._hire_for_activity(mentor_user, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(mentee_user, role=ParticipantRole.MENTEE)
        await self._hire_for_activity(non_participant_user)
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=mentor_user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=mentee_user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
        ])
        await self._add_training(
            mentor_user, category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING
        )
        await self._add_training(
            mentee_user, category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING
        )
        await self._add_training(
            non_participant_user, category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING
        )

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(onboarding_status="completed"),
            limit=20,
            offset=0,
        )

        user_ids = {r.user_id for r in rows}
        self.assertIn(mentor_user.user_id, user_ids)
        self.assertIn(mentee_user.user_id, user_ids)
        self.assertIn(non_participant_user.user_id, user_ids)

    async def test_search_onboarding_status_excludes_wrong_role_or_missing_training(self):
        """A mentor with only mentee training, or a mentor with no training
        at all, does not count as completed; both correctly show up under
        incomplete instead."""
        mentor_wrong_training_user = self._make_user(
            first_name="Wren", last_name="WrongTraining", email="wren@example.com"
        )
        no_training_user = self._make_user(
            first_name="Nora", last_name="NoTraining", email="nora@example.com"
        )
        await self.insert_entities([mentor_wrong_training_user, no_training_user])
        await self._hire_for_activity(mentor_wrong_training_user, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(no_training_user, role=ParticipantRole.MENTOR)
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=mentor_wrong_training_user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=no_training_user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
        ])
        await self._add_training(
            mentor_wrong_training_user, category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING
        )

        completed_rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(onboarding_status="completed"),
            limit=20,
            offset=0,
        )
        incomplete_rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(onboarding_status="incomplete"),
            limit=20,
            offset=0,
        )

        completed_ids = {r.user_id for r in completed_rows}
        incomplete_ids = {r.user_id for r in incomplete_rows}
        self.assertNotIn(mentor_wrong_training_user.user_id, completed_ids)
        self.assertNotIn(no_training_user.user_id, completed_ids)
        self.assertIn(mentor_wrong_training_user.user_id, incomplete_ids)
        self.assertIn(no_training_user.user_id, incomplete_ids)

    async def test_search_excludes_unqualified_users(self):
        """Verify the mentorship gate excludes users with non-hired applications,
        non-activity jobs, or no application at all."""
        hired_user = self._make_user(
            first_name="Hana", last_name="Hired", email="hana@example.com"
        )
        applied_user = self._make_user(
            first_name="Amy", last_name="Applied", email="amy@example.com"
        )
        employment_hired_user = self._make_user(
            first_name="Eve", last_name="Employed", email="eve@example.com"
        )
        no_application_user = self._make_user(
            first_name="Xin", last_name="External", email="xin@example.com"
        )
        await self.insert_entities([
            hired_user,
            applied_user,
            employment_hired_user,
            no_application_user,
        ])
        await self._hire_for_activity(hired_user)

        activity_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            title="mentee activity",
        )
        await self.insert_entities([activity_job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=activity_job.job_id,
                user_id=applied_user.user_id,
                stage=ApplicationStage.APPLIED,
            )
        ])

        employment_job = JobEntity(kind=JobKind.EMPLOYMENT, title="SWE Intern")
        await self.insert_entities([employment_job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=employment_job.job_id,
                user_id=employment_hired_user.user_id,
                stage=ApplicationStage.HIRED,
            )
        ])
        # no_application_user has no application at all (recruiting first-login only).

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=20, offset=0
        )

        user_ids = {r.user_id for r in rows}
        self.assertIn(hired_user.user_id, user_ids)
        self.assertNotIn(applied_user.user_id, user_ids)
        self.assertNotIn(employment_hired_user.user_id, user_ids)
        self.assertNotIn(no_application_user.user_id, user_ids)

    async def test_search_filter_by_user_id(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_name(self):
        """Verify name filtering matches first, last, and preferred names using
        case-insensitive partial matching."""
        alice = self.user
        bob_jones = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        rosalie_wu = self._make_user(
            first_name="Tina",
            last_name="Wu",
            email="tina@example.com",
            preferred_name="Rosalie Wu",
        )
        await self.insert_entities([bob_jones, rosalie_wu])
        await self._hire_for_activity(bob_jones)
        await self._hire_for_activity(rosalie_wu)

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(name="ali"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 2)
        user_ids = {r.user_id for r in rows}
        self.assertIn(alice.user_id, user_ids)
        self.assertIn(rosalie_wu.user_id, user_ids)
        self.assertNotIn(bob_jones.user_id, user_ids)

    async def test_search_filter_by_email(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="alice@work.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(email="alice@work"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_round_id(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(round_id=self.rounds[0].round_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participant_role(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participant_role=ParticipantRole.MENTOR),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_approval_status(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(approval_status=ApprovalStatus.MATCHED),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participation_status_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participation_status="participant"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participation_status_non_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self._hire_for_activity(user2)
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participation_status="non_participant"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, user2.user_id)

    async def test_search_filter_by_matched_user(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
        ])
        await self.insert_entities([
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.user.user_id,
                mentee_id=user2.user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="test",
            )
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(matched_user="jones"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_pagination(self):
        extra_users = [
            self._make_user(
                first_name=f"User{i}", last_name="Test", email=f"user{i}@example.com"
            )
            for i in range(3)
        ]
        await self.insert_entities(extra_users)
        for extra_user in extra_users:
            await self._hire_for_activity(extra_user)

        rows_p1, total = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=2, offset=0
        )
        rows_p2, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=2, offset=2
        )

        self.assertEqual(total, 4)
        self.assertEqual(len(rows_p1), 2)
        self.assertEqual(len(rows_p2), 2)
        self.assertEqual(
            len({r.user_id for r in rows_p1} & {r.user_id for r in rows_p2}), 0
        )

    async def test_search_sort_by_user_id_desc(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self._hire_for_activity(user2)

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(),
            limit=50,
            offset=0,
            sort_by="user_id",
            order="desc",
        )

        user_ids = [r.user_id for r in rows]
        self.assertEqual(user_ids, sorted(user_ids, reverse=True))

    async def test_search_row_fields_for_paired_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
        ])
        pair = MentorshipPairsEntity(
            round_id=self.rounds[0].round_id,
            mentor_id=self.user.user_id,
            mentee_id=user2.user_id,
            completed_count=2,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="test",
        )
        await self.insert_entities([pair])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        row = rows[0]
        self.assertEqual(row.round_id, self.rounds[0].round_id)
        self.assertEqual(row.pair_id, pair.pair_id)
        self.assertEqual(row.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(row.approval_status, ApprovalStatus.MATCHED)
        self.assertEqual(row.completed_count, 2)
        self.assertEqual(row.mentor_id, self.user.user_id)
        self.assertEqual(row.mentee_id, user2.user_id)

    async def test_list_distinct_user_roles_dedupes_across_rounds(self):
        round_a = MentorshipRoundEntity(name="Round A")
        round_b = MentorshipRoundEntity(name="Round B")
        mentee_user = UsersEntity(
            first_name="Bob",
            last_name="Mentee",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="bob@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([round_a, round_b, mentee_user])
        await self.session.flush()

        # Same user, same role, two different rounds - must dedupe to one row.
        await self.repo.upsert_participant(
            self.session,
            MentorshipRoundParticipantsEntity(
                user_id=mentee_user.user_id,
                round_id=round_a.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
        )
        await self.repo.upsert_participant(
            self.session,
            MentorshipRoundParticipantsEntity(
                user_id=mentee_user.user_id,
                round_id=round_b.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
        )
        # A second, distinct participant already inserted in asyncSetUp
        # (self.user, no participant row) is not a participant - must not
        # appear.

        rows = await self.repo.list_distinct_user_roles(self.session)

        self.assertEqual(rows, [(mentee_user.user_id, ParticipantRole.MENTEE)])


if __name__ == "__main__":
    unittest.main()
