import unittest
from datetime import datetime, timedelta, timezone

from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.job_entity import JobEntity

# Registers the table training.course_id points at.
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.application_entity import ApplicationEntity
from backend.entity.training_entity import TrainingEntity
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.common.mentorship_enums import (
    MeetingSource,
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
                onboarding_deadline_at=datetime(2025, 2, 15, tzinfo=timezone.utc),
                meetings_completion_deadline_at=datetime(
                    2025, 6, 30, tzinfo=timezone.utc
                ),
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                mentee_average_score=4.8,
                mentor_average_score=4.6,
                expectations="guiding career development paths",
                onboarding_deadline_at=datetime(2025, 8, 15, tzinfo=timezone.utc),
                meetings_completion_deadline_at=datetime(
                    2025, 12, 31, tzinfo=timezone.utc
                ),
                required_meetings=5,
            ),
        ]

        await self.insert_entities(self.rounds)

    def _make_user(
        self,
        *,
        first_name="Test",
        last_name="User",
        email,
        preferred_name=None,
        is_active=True,
        is_blocked=False,
        is_internal=False,
    ):
        return UsersEntity(
            first_name=first_name,
            last_name=last_name,
            preferred_name=preferred_name,
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=is_active,
            is_blocked=is_blocked,
            is_internal=is_internal,
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

    async def _register(self, *users, round_index=0):
        """Give each user a participant row in one of the setUp rounds."""
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=user.user_id,
                round_id=self.rounds[round_index].round_id,
            )
            for user in users
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

    async def test_get_recent_participant_by_user_id_and_role_filters_by_role(self):
        """Returns the most recent round matching the requested role, even
        when a more recent round exists in the OTHER role."""
        # rounds[0] (2025-06-30) as MENTOR; rounds[1] (2025-12-31, newer) as MENTEE.
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
        ]
        await self.insert_entities(participants)

        mentor_result = await self.repo.get_recent_participant_by_user_id_and_role(
            self.session,
            user_id=self.user.user_id,
            participant_role=ParticipantRole.MENTOR,
        )
        self.assertIsNotNone(mentor_result)
        # The newer round is a MENTEE round, so the role filter must skip it.
        self.assertEqual(mentor_result.round_id, self.rounds[0].round_id)

        mentee_result = await self.repo.get_recent_participant_by_user_id_and_role(
            self.session,
            user_id=self.user.user_id,
            participant_role=ParticipantRole.MENTEE,
        )
        self.assertIsNotNone(mentee_result)
        self.assertEqual(mentee_result.round_id, self.rounds[1].round_id)

    async def test_get_recent_participant_by_user_id_and_role_returns_most_recent(self):
        """Among multiple rounds in the SAME role, returns the one with the
        latest meetings_completion_deadline_at."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_recent_participant_by_user_id_and_role(
            self.session,
            user_id=self.user.user_id,
            participant_role=ParticipantRole.MENTEE,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.round_id, self.rounds[1].round_id)

    async def test_get_recent_participant_orders_by_the_meetings_deadline(self):
        """Recency is the meetings completion deadline alone: a round created
        later, or with a later onboarding deadline, does not win on that, and
        a round with no meetings deadline is never picked."""
        earlier_meetings = MentorshipRoundEntity(
            name="2025-winter",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2025, 3, 31, tzinfo=timezone.utc),
        )
        no_meetings_deadline = MentorshipRoundEntity(
            name="2026-draft",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        await self.insert_entities([earlier_meetings, no_meetings_deadline])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=round_.round_id,
                participant_role=ParticipantRole.MENTEE,
            )
            for round_ in (self.rounds[0], earlier_meetings, no_meetings_deadline)
        ])

        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )
        by_role = await self.repo.get_recent_participant_by_user_id_and_role(
            self.session,
            user_id=self.user.user_id,
            participant_role=ParticipantRole.MENTEE,
        )

        self.assertEqual(result.round_id, self.rounds[0].round_id)
        self.assertEqual(by_role.round_id, self.rounds[0].round_id)

    async def test_get_recent_participant_by_user_id_and_role_none_when_no_match(self):
        """Returns None when the user has participation but not in the role."""
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
            )
        ])

        result = await self.repo.get_recent_participant_by_user_id_and_role(
            self.session,
            user_id=self.user.user_id,
            participant_role=ParticipantRole.MENTOR,
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

    async def test_search_no_filters_returns_registered_mentorship_users_only(self):
        """With no filters every registered user meeting the base mentorship
        gate is returned, and an admitted user with no registration is not."""
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        unregistered = self._make_user(
            first_name="Una", last_name="Unregistered", email="una@example.com"
        )
        await self.insert_entities([user2, unregistered])
        await self._hire_for_activity(user2)
        await self._hire_for_activity(unregistered)
        await self._register(self.user)
        await self._register(user2, round_index=1)

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
        await self._register(trained_user, unrelated_trained_user)

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=20, offset=0
        )

        user_ids = {r.user_id for r in rows}
        self.assertIn(trained_user.user_id, user_ids)
        self.assertNotIn(unrelated_trained_user.user_id, user_ids)

    async def test_search_onboarding_status_completed_by_role(self):
        """MENTOR only checks mentor training; MENTEE only checks mentee
        training; someone with no registration is not listed at all."""
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
        self.assertNotIn(non_participant_user.user_id, user_ids)

    async def test_search_onboarding_status_excludes_wrong_role_or_missing_training(
        self,
    ):
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
        await self._hire_for_activity(
            mentor_wrong_training_user, role=ParticipantRole.MENTOR
        )
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
            mentor_wrong_training_user,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
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
        await self._register(
            hired_user, applied_user, employment_hired_user, no_application_user
        )

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=20, offset=0
        )

        user_ids = {r.user_id for r in rows}
        self.assertIn(hired_user.user_id, user_ids)
        self.assertNotIn(applied_user.user_id, user_ids)
        self.assertNotIn(employment_hired_user.user_id, user_ids)
        self.assertNotIn(no_application_user.user_id, user_ids)

    async def test_search_includes_deactivated_users(self):
        """Deactivated users who meet the mentorship gate are listed, flagged."""
        inactive_user = self._make_user(
            first_name="Ina",
            last_name="Inactive",
            email="ina@example.com",
            is_active=False,
        )
        await self.insert_entities([inactive_user])
        await self._hire_for_activity(inactive_user)
        await self._register(self.user, inactive_user)

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=20, offset=0
        )

        by_id = {r.user_id: r for r in rows}
        self.assertIn(inactive_user.user_id, by_id)
        self.assertTrue(by_id[inactive_user.user_id].is_deactivated)
        self.assertFalse(by_id[self.user.user_id].is_deactivated)

    async def test_search_filter_by_user_id(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self._hire_for_activity(user2)
        await self._register(self.user, user2)

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_user_id_outside_int32_matches_nothing(self):
        for user_id in (2**31, 0, -1):
            with self.subTest(user_id=user_id):
                rows, total = await self.repo.search_participants_for_admin(
                    self.session,
                    ParticipantSearchFilterDto(user_id=user_id),
                    limit=50,
                    offset=0,
                )

                self.assertEqual(total, 0)
                self.assertEqual(rows, [])

    async def test_search_q_matches_first_last_and_preferred_name(self):
        """q is a case-insensitive contains on each name part."""
        first = self._make_user(
            first_name="Quinlan", last_name="Adams", email="q1@example.com"
        )
        last = self._make_user(
            first_name="Bea", last_name="McQuinn", email="q2@example.com"
        )
        preferred = self._make_user(
            first_name="Tina",
            last_name="Wu",
            email="q3@example.com",
            preferred_name="Quincy",
        )
        unrelated = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([first, last, preferred, unrelated])
        for user in (first, last, preferred, unrelated):
            await self._hire_for_activity(user)
        await self._register(first, last, preferred, unrelated)

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(q="QUIN"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 3)
        self.assertEqual(
            {r.user_id for r in rows},
            {first.user_id, last.user_id, preferred.user_id},
        )

    async def test_search_q_matches_a_secondary_email_once(self):
        """A non-primary address matches, case-insensitively, and a user with
        several matching addresses still yields one row."""
        bob = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([bob])
        await self._hire_for_activity(bob)
        await self._register(self.user, bob)
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="alice@home.org",
                otp_confirmed=True,
                is_primary=True,
            ),
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="Alice.Backup@Work.com",
                otp_confirmed=True,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="alice.old@work.com",
                otp_confirmed=True,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=bob.user_id,
                email="bob@home.org",
                otp_confirmed=True,
                is_primary=True,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(q="@WORK.com"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual([r.user_id for r in rows], [self.user.user_id])

    async def test_search_filter_by_account_status(self):
        """Each account status selects only its own user; blocked and
        deactivated are read from different columns."""
        blocked = self._make_user(
            first_name="Bella",
            last_name="Blocked",
            email="b@example.com",
            is_blocked=True,
        )
        deactivated = self._make_user(
            first_name="Dora",
            last_name="Deactivated",
            email="d@example.com",
            is_active=False,
        )
        await self.insert_entities([blocked, deactivated])
        await self._hire_for_activity(blocked)
        await self._hire_for_activity(deactivated)
        await self._register(self.user, blocked, deactivated)

        expected = {
            "active": {self.user.user_id},
            "blocked": {blocked.user_id},
            "deactivated": {deactivated.user_id},
            None: {self.user.user_id, blocked.user_id, deactivated.user_id},
        }
        for status, user_ids in expected.items():
            with self.subTest(account_status=status):
                rows, total = await self.repo.search_participants_for_admin(
                    self.session,
                    ParticipantSearchFilterDto(account_status=status),
                    limit=50,
                    offset=0,
                )

                self.assertEqual({r.user_id for r in rows}, user_ids)
                self.assertEqual(total, len(user_ids))

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=50, offset=0
        )
        flags = {r.user_id: (r.is_blocked, r.is_deactivated) for r in rows}
        self.assertEqual(
            flags,
            {
                self.user.user_id: (False, False),
                blocked.user_id: (True, False),
                deactivated.user_id: (False, True),
            },
        )

    async def test_search_blocked_and_deactivated_user_is_in_both_not_active(self):
        both = self._make_user(
            first_name="Bo",
            last_name="Both",
            email="both@example.com",
            is_active=False,
            is_blocked=True,
        )
        await self.insert_entities([both])
        await self._hire_for_activity(both)
        await self._register(both)

        found = {}
        for status in ("active", "blocked", "deactivated"):
            rows, _ = await self.repo.search_participants_for_admin(
                self.session,
                ParticipantSearchFilterDto(account_status=status),
                limit=50,
                offset=0,
            )
            found[status] = both.user_id in {r.user_id for r in rows}

        self.assertEqual(found, {"active": False, "blocked": True, "deactivated": True})

    async def test_search_filter_by_internal(self):
        staff = self._make_user(
            first_name="Ivy",
            last_name="Internal",
            email="ivy@example.com",
            is_internal=True,
        )
        await self.insert_entities([staff])
        await self._hire_for_activity(staff)
        await self._register(self.user, staff)

        expected = {
            "internal": {staff.user_id},
            "external": {self.user.user_id},
            None: {staff.user_id, self.user.user_id},
        }
        for internal, user_ids in expected.items():
            with self.subTest(internal=internal):
                rows, total = await self.repo.search_participants_for_admin(
                    self.session,
                    ParticipantSearchFilterDto(internal=internal),
                    limit=50,
                    offset=0,
                )

                self.assertEqual({r.user_id for r in rows}, user_ids)
                self.assertEqual(total, len(user_ids))

        rows, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=50, offset=0
        )
        self.assertEqual(
            {r.user_id: r.is_internal for r in rows},
            {staff.user_id: True, self.user.user_id: False},
        )

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
        await self._register(self.user, *extra_users)

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
        # completed_count is read from the meeting rows, so the two completed
        # ones below are what the assertion further down is about; the column
        # stays at 2 only so this fixture keeps saying the same thing.
        meeting_start = datetime.now(timezone.utc)
        await self.insert_entities([
            MentorshipMeetingEntity(
                meeting_id=f"row-fields-{index}",
                pair_id=pair.pair_id,
                source=MeetingSource.MANUAL,
                start_datetime=meeting_start,
                end_datetime=meeting_start + timedelta(minutes=30),
                is_completed=True,
                created_datetime=meeting_start,
            )
            for index in range(2)
        ])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        row = rows[0]
        self.assertEqual(row.round_id, self.rounds[0].round_id)
        self.assertEqual(row.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(row.approval_status, ApprovalStatus.MATCHED)
        (row_pair,) = row.pairs
        self.assertEqual(row_pair.pair_id, pair.pair_id)
        self.assertEqual(row_pair.completed_count, 2)
        self.assertEqual(row_pair.mentor_id, self.user.user_id)
        self.assertEqual(row_pair.mentee_id, user2.user_id)
        self.assertEqual(row_pair.pair_status, PairStatus.ACTIVE)

    async def test_search_participant_without_a_pair_has_no_pairs(self):
        """Someone who was never paired still gets a row, with no pairs."""
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.REJECTED,
            )
        ])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pairs, [])

    async def _seed_mentor_with_two_mentees(self):
        """
        Round 0: self.user (Alice Admin) mentors Bea (active pair 901, two
        completed meetings and one pending) and Cid (pair 902, ended, no
        meetings). Pair ids are set far from the user ids so a pair id read
        as a user id, or the reverse, cannot pass.
        """
        bea = self._make_user(first_name="Bea", last_name="Marlow", email="b@x.io")
        cid = self._make_user(first_name="Cid", last_name="Nash", email="c@x.io")
        await self.insert_entities([bea, cid])
        for mentee in (bea, cid):
            await self._hire_for_activity(mentee)
        round_id = self.rounds[0].round_id
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            *[
                MentorshipRoundParticipantsEntity(
                    user_id=mentee.user_id,
                    round_id=round_id,
                    participant_role=ParticipantRole.MENTEE,
                    approval_status=ApprovalStatus.MATCHED,
                )
                for mentee in (bea, cid)
            ],
        ])
        await self.insert_entities([
            MentorshipPairsEntity(
                pair_id=pair_id,
                round_id=round_id,
                mentor_id=self.user.user_id,
                mentee_id=mentee.user_id,
                completed_count=0,
                status=status,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="test",
            )
            for pair_id, mentee, status in (
                (901, bea, PairStatus.ACTIVE),
                (902, cid, PairStatus.INACTIVE),
            )
        ])
        now = datetime.now(timezone.utc)
        await self.insert_entities([
            MentorshipMeetingEntity(
                meeting_id=f"two-mentees-{index}",
                pair_id=901,
                source=MeetingSource.MANUAL,
                start_datetime=now,
                end_datetime=now + timedelta(minutes=30),
                is_completed=index < 2,
                created_datetime=now,
            )
            for index in range(3)
        ])
        return bea, cid

    async def test_search_mentor_with_two_mentees_is_one_row(self):
        bea, cid = await self._seed_mentor_with_two_mentees()

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(round_id=self.rounds[0].round_id),
            limit=50,
            offset=0,
        )

        # Three people, two pairs: the count is of people.
        self.assertEqual(total, 3)
        self.assertEqual(
            [r.user_id for r in rows],
            [self.user.user_id, bea.user_id, cid.user_id],
        )
        mentor_row = rows[0]
        self.assertEqual(
            [
                (p.pair_id, p.mentor_id, p.mentee_id, p.pair_status, p.completed_count)
                for p in mentor_row.pairs
            ],
            [
                (901, self.user.user_id, bea.user_id, PairStatus.ACTIVE, 2),
                (902, self.user.user_id, cid.user_id, PairStatus.INACTIVE, 0),
            ],
        )
        self.assertEqual([p.pair_id for p in rows[1].pairs], [901])
        self.assertEqual([p.pair_id for p in rows[2].pairs], [902])

    async def test_search_pages_by_participant_not_by_pair(self):
        """A limit of 1 would have cut the mentor's rows in half when rows
        were one per pair; now it is the mentor, with both pairs."""
        bea, cid = await self._seed_mentor_with_two_mentees()
        filters = ParticipantSearchFilterDto(round_id=self.rounds[0].round_id)

        page_1, total = await self.repo.search_participants_for_admin(
            self.session, filters, limit=1, offset=0
        )
        page_2, _ = await self.repo.search_participants_for_admin(
            self.session, filters, limit=2, offset=1
        )

        self.assertEqual(total, 3)
        self.assertEqual([r.user_id for r in page_1], [self.user.user_id])
        self.assertEqual([p.pair_id for p in page_1[0].pairs], [901, 902])
        self.assertEqual([r.user_id for r in page_2], [bea.user_id, cid.user_id])

    async def test_search_sorted_by_user_id_is_still_one_row_per_participant(self):
        await self._seed_mentor_with_two_mentees()

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(round_id=self.rounds[0].round_id),
            limit=50,
            offset=0,
            sort_by="user_id",
            order="desc",
        )

        self.assertEqual(total, 3)
        user_ids = [r.user_id for r in rows]
        self.assertEqual(user_ids, sorted(set(user_ids), reverse=True))

    async def test_search_person_in_two_rounds_gets_a_row_per_round(self):
        """Without a round filter a person has one row per round, each
        holding only that round's pairs."""
        bea = self._make_user(first_name="Bea", last_name="Marlow", email="b@x.io")
        dev = self._make_user(first_name="Dev", last_name="Okafor", email="d@x.io")
        await self.insert_entities([bea, dev])
        spring, fall = (r.round_id for r in self.rounds)
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            )
            for round_id in (spring, fall)
        ])
        await self.insert_entities([
            MentorshipPairsEntity(
                pair_id=pair_id,
                round_id=round_id,
                mentor_id=self.user.user_id,
                mentee_id=mentee.user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="test",
            )
            for pair_id, round_id, mentee in (
                (911, spring, bea),
                (912, fall, dev),
            )
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 2)
        self.assertEqual(
            [(r.round_id, [p.pair_id for p in r.pairs]) for r in rows],
            [(spring, [911]), (fall, [912])],
        )

    async def test_list_distinct_user_roles_dedupes_across_rounds(self):
        round_a = MentorshipRoundEntity(
            name="Round A",
            onboarding_deadline_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        round_b = MentorshipRoundEntity(
            name="Round B",
            onboarding_deadline_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        mentee_user = UsersEntity(
            first_name="Bob",
            last_name="Mentee",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
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

    async def test_search_completed_count_comes_from_meeting_rows(self):
        """The search reports the number of completed meeting rows, not the
        denormalised mentorship_pairs.completed_count. Seeded here so the two
        disagree: a stale column would return 9, the meeting rows say 2 (one
        MANUAL, one LEGACY -- historical rounds only have LEGACY rows, so
        skipping them would report 0 for every pre-Purrf pairing)."""
        user2 = self._make_user(
            first_name="Pat", last_name="Meeting", email="pat.meeting@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
        ])
        pair = MentorshipPairsEntity(
            round_id=self.rounds[0].round_id,
            mentor_id=self.user.user_id,
            mentee_id=user2.user_id,
            completed_count=9,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="test",
        )
        await self.insert_entities([pair])
        now = datetime.now(timezone.utc)
        later = now + timedelta(minutes=30)
        await self.insert_entities([
            MentorshipMeetingEntity(
                meeting_id="m-done",
                pair_id=pair.pair_id,
                source=MeetingSource.MANUAL,
                start_datetime=now,
                end_datetime=later,
                is_completed=True,
                created_datetime=now,
            ),
            MentorshipMeetingEntity(
                meeting_id="m-legacy",
                pair_id=pair.pair_id,
                source=MeetingSource.LEGACY,
                is_completed=True,
                created_datetime=now,
            ),
            MentorshipMeetingEntity(
                meeting_id="m-pending",
                pair_id=pair.pair_id,
                source=MeetingSource.MANUAL,
                start_datetime=now,
                end_datetime=later,
                is_completed=False,
                created_datetime=now,
            ),
        ])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(round_id=self.rounds[0].round_id),
            limit=50,
            offset=0,
        )

        row = next(r for r in rows if r.user_id == self.user.user_id)
        self.assertEqual([p.completed_count for p in row.pairs], [2])

    async def test_search_never_paired_has_no_pair_entry_at_all(self):
        """A registered participant who was never paired has no pair entry,
        so no meeting count either -- not a pair with 0, which would turn
        "never paired" into "paired, met nobody" in the admin table."""
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.UN_MATCHED,
            ),
        ])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(rows[0].pairs, [])

    async def _seed_feedback_round(self):
        """
        Round 0: the mentor (self.user) and Ann paired and going, Ben paired
        and ended; Cid registered but never paired; Dee paired then left
        (rejected); Eve paired but blocked. Mentor and Ann sent feedback.
        Round 1: Gus paired, not sent. Only Cid owes nothing: owed is 5/1
        and sent 2/0 by round.
        """
        names = ["Ann", "Ben", "Cid", "Dee", "Eve", "Gus"]
        users = {
            n: self._make_user(first_name=n, email=f"{n.lower()}@example.com")
            for n in names
        }
        users["Eve"].is_blocked = True
        await self.insert_entities(list(users.values()))

        r0, r1 = self.rounds[0].round_id, self.rounds[1].round_id
        sent = {"program_rating": 4, "most_valuable_aspects": "x"}

        def participant(user, round_id, role, status, feedback=None):
            return MentorshipRoundParticipantsEntity(
                user_id=user.user_id,
                round_id=round_id,
                participant_role=role,
                approval_status=status,
                program_feedback=feedback,
            )

        await self.insert_entities([
            participant(
                self.user, r0, ParticipantRole.MENTOR, ApprovalStatus.MATCHED, sent
            ),
            participant(
                users["Ann"], r0, ParticipantRole.MENTEE, ApprovalStatus.MATCHED, sent
            ),
            participant(
                users["Ben"], r0, ParticipantRole.MENTEE, ApprovalStatus.MATCHED
            ),
            participant(
                users["Cid"], r0, ParticipantRole.MENTEE, ApprovalStatus.SIGNED_UP
            ),
            participant(
                users["Dee"], r0, ParticipantRole.MENTEE, ApprovalStatus.REJECTED
            ),
            participant(
                users["Eve"], r0, ParticipantRole.MENTEE, ApprovalStatus.MATCHED
            ),
            participant(
                users["Gus"], r1, ParticipantRole.MENTEE, ApprovalStatus.MATCHED
            ),
        ])

        def pair(round_id, mentee, status=PairStatus.ACTIVE):
            return MentorshipPairsEntity(
                round_id=round_id,
                mentor_id=self.user.user_id,
                mentee_id=mentee.user_id,
                completed_count=0,
                status=status,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="test",
            )

        await self.insert_entities([
            pair(r0, users["Ann"]),
            pair(r0, users["Ben"], PairStatus.INACTIVE),
            pair(r0, users["Dee"], PairStatus.INACTIVE),
            pair(r0, users["Eve"]),
            pair(r1, users["Gus"]),
        ])
        return users

    async def test_get_feedback_counts_by_round(self):
        """Counts everyone paired in the round, left or blocked included."""
        await self._seed_feedback_round()

        result = await self.repo.get_feedback_counts_by_round(self.session)

        self.assertEqual(
            result,
            {
                self.rounds[0].round_id: {"owed": 5, "sent": 2},
                self.rounds[1].round_id: {"owed": 1, "sent": 0},
            },
        )

    async def test_get_feedback_owed_in_round(self):
        """Returns the owed participants of that round only, with their users."""
        users = await self._seed_feedback_round()

        rows = await self.repo.get_feedback_owed_in_round(
            self.session, self.rounds[0].round_id
        )

        self.assertEqual(
            [user.user_id for _, user in rows],
            sorted(
                [self.user.user_id]
                + [users[n].user_id for n in ("Ann", "Ben", "Dee", "Eve")]
            ),
        )
        for participant, user in rows:
            self.assertEqual(participant.user_id, user.user_id)
            self.assertEqual(participant.round_id, self.rounds[0].round_id)

    # --- search_unregistered_for_admin ---

    async def _unregistered_ids(self, filters=None, **kwargs):
        rows, total = await self.repo.search_unregistered_for_admin(
            self.session,
            self.rounds[1].round_id,
            filters or UnregisteredFilterDto(),
            limit=kwargs.pop("limit", 50),
            offset=kwargs.pop("offset", 0),
            **kwargs,
        )
        return [r.user_id for r in rows], total

    async def test_unregistered_is_admitted_with_no_row_in_the_round(self):
        """Admitted and not registered for this round is listed even when
        registered for another; registered for this one, admitted only to a
        non-activity posting, merely applied, or only trained is not."""
        other_round = self._make_user(first_name="Oli", email="o@example.com")
        this_round = self._make_user(first_name="Tia", email="t@example.com")
        employment = self._make_user(first_name="Emp", email="e@example.com")
        applied = self._make_user(first_name="App", email="a@example.com")
        trained = self._make_user(first_name="Tra", email="tr@example.com")
        await self.insert_entities([
            other_round,
            this_round,
            employment,
            applied,
            trained,
        ])
        await self._hire_for_activity(other_round, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(this_round)
        await self._register(other_round, round_index=0)
        await self._register(this_round, round_index=1)

        employment_job = JobEntity(kind=JobKind.EMPLOYMENT, title="SWE Intern")
        activity_job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTEE,
            title="mentee activity",
        )
        await self.insert_entities([employment_job, activity_job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=employment_job.job_id,
                user_id=employment.user_id,
                stage=ApplicationStage.HIRED,
            ),
            ApplicationEntity(
                job_id=activity_job.job_id,
                user_id=applied.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        ])
        await self._add_training(trained)

        ids, total = await self._unregistered_ids()

        self.assertEqual(ids, sorted([self.user.user_id, other_round.user_id]))
        self.assertEqual(total, 2)

    async def test_unregistered_admitted_as_both_roles_is_one_row(self):
        both = self._make_user(first_name="Bo", email="bo@example.com")
        await self.insert_entities([both])
        await self._hire_for_activity(both, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(both, role=ParticipantRole.MENTEE)
        await self._register(self.user, round_index=1)

        ids, total = await self._unregistered_ids()

        self.assertEqual((ids, total), ([both.user_id], 1))

    async def test_unregistered_admitted_role_filter(self):
        """setUp's user is a mentee; one mentor and one person admitted as
        both, so a filter reading the wrong role cannot pass."""
        mentor = self._make_user(first_name="Mo", email="mo@example.com")
        both = self._make_user(first_name="Bo", email="bo@example.com")
        await self.insert_entities([mentor, both])
        await self._hire_for_activity(mentor, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(both, role=ParticipantRole.MENTOR)
        await self._hire_for_activity(both, role=ParticipantRole.MENTEE)

        expected = {
            ParticipantRole.MENTOR: sorted([mentor.user_id, both.user_id]),
            ParticipantRole.MENTEE: sorted([self.user.user_id, both.user_id]),
        }
        for role, user_ids in expected.items():
            with self.subTest(role=role):
                ids, _ = await self._unregistered_ids(
                    UnregisteredFilterDto(admitted_role=role)
                )
                self.assertEqual(ids, user_ids)

    async def test_unregistered_lists_blocked_and_deactivated_and_filters_them(self):
        blocked = self._make_user(
            first_name="Bella", email="b@example.com", is_blocked=True
        )
        deactivated = self._make_user(
            first_name="Dora", email="d@example.com", is_active=False
        )
        staff = self._make_user(
            first_name="Ivy", email="i@example.com", is_internal=True
        )
        await self.insert_entities([blocked, deactivated, staff])
        for user in (blocked, deactivated, staff):
            await self._hire_for_activity(user)

        rows, _ = await self.repo.search_unregistered_for_admin(
            self.session, self.rounds[1].round_id, UnregisteredFilterDto(), 50, 0
        )
        self.assertEqual(
            {r.user_id: (r.is_blocked, r.is_deactivated, r.is_internal) for r in rows},
            {
                self.user.user_id: (False, False, False),
                blocked.user_id: (True, False, False),
                deactivated.user_id: (False, True, False),
                staff.user_id: (False, False, True),
            },
        )

        expected = [
            (
                UnregisteredFilterDto(account_status="active"),
                sorted([self.user.user_id, staff.user_id]),
            ),
            (UnregisteredFilterDto(account_status="blocked"), [blocked.user_id]),
            (
                UnregisteredFilterDto(account_status="deactivated"),
                [deactivated.user_id],
            ),
            (UnregisteredFilterDto(internal="internal"), [staff.user_id]),
            (UnregisteredFilterDto(user_id=blocked.user_id), [blocked.user_id]),
            (UnregisteredFilterDto(q="DORA"), [deactivated.user_id]),
        ]
        for filters, user_ids in expected:
            with self.subTest(filters=filters):
                ids, total = await self._unregistered_ids(filters)
                self.assertEqual((ids, total), (user_ids, len(user_ids)))

    async def test_unregistered_pages_by_user_id_in_either_direction(self):
        extra = [
            self._make_user(first_name=f"U{i}", email=f"u{i}@example.com")
            for i in range(3)
        ]
        await self.insert_entities(extra)
        for user in extra:
            await self._hire_for_activity(user)
        everyone = sorted([self.user.user_id] + [u.user_id for u in extra])

        asc_p1, total = await self._unregistered_ids(limit=2, offset=0)
        asc_p2, _ = await self._unregistered_ids(limit=2, offset=2)
        desc, _ = await self._unregistered_ids(order="desc")

        self.assertEqual(total, 4)
        self.assertEqual(asc_p1 + asc_p2, everyone)
        self.assertEqual(desc, everyone[::-1])

    # --- list_registered_rounds_by_user_ids ---

    async def test_registered_rounds_latest_first_by_meetings_deadline(self):
        """Every status counts; latest is by meetings deadline, not id, and a
        round with no deadline comes last."""
        # Created after the setUp rounds, so it has the highest id, but ends
        # between them; a second has no deadline at all.
        middle = MentorshipRoundEntity(
            name="2025-summer",
            onboarding_deadline_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2025, 9, 30, tzinfo=timezone.utc),
        )
        undated = MentorshipRoundEntity(
            name="undated",
            onboarding_deadline_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        await self.insert_entities([middle, undated])
        other = self._make_user(first_name="Oz", email="oz@example.com")
        loner = self._make_user(first_name="Lo", email="lo@example.com")
        await self.insert_entities([other, loner])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=round_id,
                approval_status=status,
            )
            for round_id, status in (
                (undated.round_id, ApprovalStatus.MATCHED),
                (self.rounds[0].round_id, ApprovalStatus.REJECTED),
                (middle.round_id, ApprovalStatus.SIGNED_UP),
                (self.rounds[1].round_id, ApprovalStatus.UN_MATCHED),
            )
        ])
        await self._register(other, round_index=0)

        result = await self.repo.list_registered_rounds_by_user_ids(
            self.session, [self.user.user_id, other.user_id, loner.user_id]
        )

        self.assertEqual(
            {uid: [r.name for r in rounds] for uid, rounds in result.items()},
            {
                self.user.user_id: [
                    "2025-fall",
                    "2025-summer",
                    "2025-spring",
                    "undated",
                ],
                other.user_id: ["2025-spring"],
            },
        )

    async def test_registered_rounds_empty_input_skips_the_query(self):
        self.assertEqual(
            await self.repo.list_registered_rounds_by_user_ids(self.session, []), {}
        )


if __name__ == "__main__":
    unittest.main()
