import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from backend.mentorship.registration_service import RegistrationService
from backend.dto.registration_create_dto import (
    RegistrationCreateDto,
    GlobalPreferencesDto,
    RoundPreferencesDto,
    ProfileSurveyCreateDto,
)
from backend.dto.registration_dto import (
    RegistrationDto,
    GlobalPreferencesDto as GlobalPreferencesResponseDto,
    RoundPreferencesDto as RoundPreferencesResponseDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.dto.preference_dto import (
    SpecificIndustryDto,
    SkillsetsDto,
)
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingStatus,
    TrainingCategory,
)
from backend.entity.training_entity import TrainingEntity
from backend.common.exceptions import ConflictError


class TestRegistrationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_preference_repo = MagicMock()
        self.mock_preference_repo.get_preferences_by_user_id = AsyncMock()
        self.mock_preference_repo.upsert_preference = AsyncMock()

        self.mock_round_repo = MagicMock()
        self.mock_round_repo.get_by_round_id = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.get_by_user_id_and_round_id = AsyncMock(
            return_value=None
        )
        self.mock_participants_repo.upsert_participant = AsyncMock()

        self.mock_logger = MagicMock()
        self.mock_session = AsyncMock()

        self.mock_participation_service = MagicMock()
        self.mock_participation_service.get_user_round_preferences = AsyncMock()

        self.mock_mapper = MagicMock()

        self.mock_onboarding_training_service = MagicMock()
        self.mock_onboarding_training_service.ensure_onboarding_training = AsyncMock()

        self.mock_application_repo = MagicMock()
        self.mock_application_repo.get_hired_activity_application = AsyncMock(
            return_value=MagicMock()
        )

        self.service = RegistrationService(
            logger=self.mock_logger,
            preferences_repository=self.mock_preference_repo,
            mentorship_round_repository=self.mock_round_repo,
            mentorship_round_participants_repository=self.mock_participants_repo,
            participation_service=self.mock_participation_service,
            mentorship_mapper=self.mock_mapper,
            onboarding_training_service=self.mock_onboarding_training_service,
            application_repository=self.mock_application_repo,
        )

        self.sample_dto = RegistrationCreateDto(
            global_preferences=GlobalPreferencesDto(
                specific_industry=SpecificIndustryDto(swe=True, uiux=False),
                skillsets=SkillsetsDto(project_management=True, networking=False),
            ),
            round_preferences=RoundPreferencesDto(
                participant_role="mentee", max_partners=1
            ),
        )
        self.sample_registration_dto = RegistrationDto(
            is_registered=True,
            round_name="test round",
            global_preferences=GlobalPreferencesResponseDto(
                specific_industry=SpecificIndustryDto(swe=True, uiux=False),
                skillsets=SkillsetsDto(project_management=True, networking=False),
            ),
            round_preferences=RoundPreferencesResponseDto(
                participant_role="mentor",
                expected_partner_ids=[123],
                unexpected_partner_ids=[],
                max_partners=1,
                goal="I want to share project management skills",
            ),
        )

        self.user_id = 123
        self.user_context = UserContextDto(
            sub="auth0|123",
            primary_email="user@example.com",
            identity_type="external",
            user_id=self.user_id,
        )
        self.mock_round_id = 1

        self.fixed_now = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)
        self.datetime_patcher = patch(
            "backend.mentorship.registration_service.datetime"
        )
        self.mock_dt = self.datetime_patcher.start()
        self.mock_dt.now.return_value = self.fixed_now
        self.mock_dt.fromisoformat.side_effect = datetime.fromisoformat

    async def asyncTearDown(self):
        self.datetime_patcher.stop()

    async def test_update_preferences_new_user(self):
        """Test: When the user does not have existing preferences, create a new entity."""

        self.mock_preference_repo.get_preferences_by_user_id.return_value = None
        self.mock_preference_repo.upsert_preference.return_value = {"status": "success"}

        await self.service._update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.mock_preference_repo.get_preferences_by_user_id.assert_called_once_with(
            session=self.mock_session, user_id=self.user_id
        )
        _, kwargs = self.mock_preference_repo.upsert_preference.call_args
        upserted_entity = kwargs["entity"]

        self.assertIsInstance(upserted_entity, PreferenceEntity)
        self.assertEqual(upserted_entity.user_id, self.user_id)
        self.assertTrue(upserted_entity.project_management)
        self.assertEqual(
            upserted_entity.specific_industry,
            {"swe": True, "uiux": False, "ds": False, "pm": False},
        )

    async def test_update_preferences_existing_user(self):
        """Test: When the user already has preferences, update the existing entity."""
        existing_entity = PreferenceEntity(
            user_id=self.user_id, project_management=False
        )
        self.mock_preference_repo.get_preferences_by_user_id.return_value = (
            existing_entity
        )

        await self.service._update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertTrue(existing_entity.project_management)
        self.mock_preference_repo.upsert_preference.assert_called_once_with(
            session=self.mock_session, entity=existing_entity
        )

    async def test_update_preferences_clears_industry_if_none(self):
        """Test: When specific industry is None, the database field should be cleared."""
        self.sample_dto.global_preferences.specific_industry = None

        existing_entity = PreferenceEntity(
            user_id=self.user_id, specific_industry={"old": "data"}
        )
        self.mock_preference_repo.get_preferences_by_user_id.return_value = (
            existing_entity
        )

        await self.service._update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertIsNone(existing_entity.specific_industry)

    async def test_get_registration_info(self):
        """Test: Get registration info, containing global and round preferences,
        for a caller who names a role they were admitted into."""
        mock_entity = MagicMock(spec=PreferenceEntity)
        self.mock_preference_repo.get_preferences_by_user_id.return_value = mock_entity
        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_participation_service.get_user_round_preferences.return_value = (
            self.sample_registration_dto.round_preferences,
            True,
        )
        mock_round = MagicMock()
        mock_round.name = "test_round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        await self.service.get_registration_info(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=self.mock_round_id,
            role=ParticipantRole.MENTOR,
        )

        # The named role is checked against the HIRED activity application
        # and, once cleared, passed straight through — never inferred.
        self.mock_application_repo.get_hired_activity_application.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            mentorship_role=ParticipantRole.MENTOR,
        )
        self.mock_participation_service.get_user_round_preferences.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=ParticipantRole.MENTOR,
        )
        self.mock_preference_repo.get_preferences_by_user_id.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_id
        )
        self.mock_mapper.map_to_global_preferences_dto.assert_called_once_with(
            preference_entity=mock_entity
        )

    async def test_get_registration_info_rejects_a_role_the_user_lacks(self):
        """A role named by the caller is checked, not trusted: no HIRED
        activity application in that role is a 403, mapped from
        PermissionError by the global handler."""
        mock_round = MagicMock()
        mock_round.name = "test_round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_application_repo.get_hired_activity_application.return_value = None

        with self.assertRaises(PermissionError):
            await self.service.get_registration_info(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=self.mock_round_id,
                role=ParticipantRole.MENTOR,
            )

        self.mock_participation_service.get_user_round_preferences.assert_not_awaited()

    async def test_get_registration_info_without_a_role_skips_the_eligibility_check(
        self,
    ):
        """Omitting the role asks only "am I registered, and as what" — no
        eligibility check runs, and there may be nothing to prefill."""
        mock_round = MagicMock()
        mock_round.name = "test_round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_application_repo.get_hired_activity_application.return_value = None
        self.mock_preference_repo.get_preferences_by_user_id.return_value = None
        self.mock_participation_service.get_user_round_preferences.return_value = (
            None,
            False,
        )

        result = await self.service.get_registration_info(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=self.mock_round_id,
        )

        self.assertIsNone(result.round_preferences)
        self.assertFalse(result.is_registered)
        self.mock_application_repo.get_hired_activity_application.assert_not_awaited()
        self.mock_participation_service.get_user_round_preferences.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=None,
        )

    async def test_update_user_round_preferences_existing(self):
        """Test: When the user already has participant record, update the existing entity"""
        existing_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=ParticipantRole.MENTOR,
            goal="Old goal",
        )
        self.mock_participants_repo.get_by_user_id_and_round_id.return_value = (
            existing_entity
        )

        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        self.sample_dto.round_preferences.goal = "New goal"

        await self.service._update_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.mock_round_id,
            data=self.sample_dto,
        )

        self.assertEqual(existing_entity.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(existing_entity.goal, "New goal")

        self.mock_participants_repo.upsert_participant.assert_called_once_with(
            session=self.mock_session, entity=existing_entity
        )

    async def test_update_registration_info_success(self):
        """Test: Post registration info, containing updated global and round preferences."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )

        global_entity = PreferenceEntity(user_id=self.user_id)
        participant_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id, round_id=self.mock_round_id
        )
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=datetime(2026, 4, 29, 23, 59, 59, tzinfo=timezone.utc),
            link="https://mentor",
        )

        with patch.object(
            self.service,
            "_update_skill_and_industry_preferences",
            new_callable=AsyncMock,
        ) as mock_global_update:
            with patch.object(
                self.service, "_update_user_round_preferences", new_callable=AsyncMock
            ) as mock_round_update:
                mock_global_update.return_value = global_entity
                mock_round_update.return_value = participant_entity

                result = await self.service.update_registration_info(
                    session=self.mock_session,
                    user_context=self.user_context,
                    round_id=self.mock_round_id,
                    preferences_data=self.sample_dto,
                )

                self.assertEqual(
                    self.sample_dto.round_preferences.participant_role,
                    ParticipantRole.MENTOR,
                )

                self.mock_session.commit.assert_awaited_once()

                self.mock_mapper.map_to_global_preferences_dto.assert_called_once_with(
                    global_entity
                )
                self.mock_mapper.map_to_round_preference_dto.assert_called_once_with(
                    participant_entity
                )

                self.assertIsInstance(result, RegistrationDto)
                self.mock_onboarding_training_service.ensure_onboarding_training.assert_awaited_once()
                self.assertFalse(result.is_onboarding_training_completed)

    async def test_update_registration_info_training_already_completed(self):
        """Test: When the user already has a completed training, do not create a new one."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )

        completed_training = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            status=TrainingStatus.DONE,
        )
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = completed_training

        global_entity = PreferenceEntity(user_id=self.user_id)
        participant_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id, round_id=self.mock_round_id
        )

        with patch.object(
            self.service,
            "_update_skill_and_industry_preferences",
            new_callable=AsyncMock,
        ) as mock_global_update:
            with patch.object(
                self.service, "_update_user_round_preferences", new_callable=AsyncMock
            ) as mock_round_update:
                mock_global_update.return_value = global_entity
                mock_round_update.return_value = participant_entity

                result = await self.service.update_registration_info(
                    session=self.mock_session,
                    user_context=self.user_context,
                    round_id=self.mock_round_id,
                    preferences_data=self.sample_dto,
                )

                self.assertTrue(result.is_onboarding_training_completed)

    async def test_update_registration_info_missing_deadline(self):
        """Test: When the restration round missing deadline, stop registration."""
        mock_round = MagicMock()
        mock_round.description = {}
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        with self.assertRaisesRegex(ValueError, "missing application deadline"):
            await self.service.update_registration_info(
                self.mock_session,
                self.user_context,
                self.mock_round_id,
                self.sample_dto,
            )

    async def test_update_registration_info_round_not_found(self):
        """Test: When the registration round non-existent, stop registration."""
        self.mock_round_repo.get_by_round_id.return_value = None

        with self.assertRaisesRegex(ValueError, "not found"):
            await self.service.update_registration_info(
                self.mock_session, self.user_context, 999, self.sample_dto
            )

    async def test_mentor_expired_blocks_registration(self):
        """Test: Blocks mentor when mentor deadline has passed even if mentee deadline has not."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        self.mock_dt.now.return_value = datetime(
            2026, 4, 28, 0, 0, 0, tzinfo=timezone.utc
        )
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z",
            "mentee_application_deadline_at": "2026-05-01T23:59:59Z",
        }
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        with self.assertRaisesRegex(ValueError, "has ended at 2026-04-27"):
            await self.service.update_registration_info(
                self.mock_session,
                self.user_context,
                self.mock_round_id,
                self.sample_dto,
            )

    async def test_mentee_expired_blocks_registration(self):
        """Test: Blocks mentee when mentee deadline has passed even if mentor deadline has not."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTEE
        self.mock_dt.now.return_value = datetime(
            2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc
        )
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-05-01T23:59:59Z",
            "mentee_application_deadline_at": "2026-04-25T23:59:59Z",
        }
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        with self.assertRaisesRegex(ValueError, "has ended at 2026-04-25"):
            await self.service.update_registration_info(
                self.mock_session,
                self.user_context,
                self.mock_round_id,
                self.sample_dto,
            )

    async def test_update_registration_info_never_overwrites_the_submitted_role(self):
        """Test: The role persisted is the one submitted, not any role
        inferred server-side, as long as the user is admitted into it."""
        mock_round = MagicMock()
        mock_round.description = {
            "mentee_application_deadline_at": "2026-04-25T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )

        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTEE

        global_entity = PreferenceEntity(user_id=self.user_id)
        participant_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id, round_id=self.mock_round_id
        )

        with patch.object(
            self.service,
            "_update_skill_and_industry_preferences",
            new_callable=AsyncMock,
        ) as mock_global_update:
            with patch.object(
                self.service, "_update_user_round_preferences", new_callable=AsyncMock
            ) as mock_round_update:
                mock_global_update.return_value = global_entity
                mock_round_update.return_value = participant_entity

                await self.service.update_registration_info(
                    session=self.mock_session,
                    user_context=self.user_context,
                    round_id=self.mock_round_id,
                    preferences_data=self.sample_dto,
                )

                self.assertEqual(
                    self.sample_dto.round_preferences.participant_role,
                    ParticipantRole.MENTEE,
                )

                called_data = mock_round_update.call_args[1]["data"]
                self.assertEqual(
                    called_data.round_preferences.participant_role,
                    ParticipantRole.MENTEE,
                )

                # The eligibility check has to be asked about the role that
                # was submitted. A hardcoded role here would let a
                # mentee-only user register as a mentor.
                self.mock_application_repo.get_hired_activity_application.assert_awaited_once_with(
                    session=self.mock_session,
                    user_id=self.user_id,
                    mentorship_role=ParticipantRole.MENTEE,
                )

                self.mock_session.commit.assert_awaited_once()

    async def test_update_rejects_a_role_the_user_was_not_admitted_into(self):
        """Test: A role the user holds no HIRED activity application for is
        rejected with PermissionError, and nothing is written."""
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_application_repo.get_hired_activity_application.return_value = None
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR

        with self.assertRaises(PermissionError):
            await self.service.update_registration_info(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=self.mock_round_id,
                preferences_data=self.sample_dto,
            )

        self.mock_session.commit.assert_not_awaited()

    async def test_update_rejects_a_role_that_disagrees_with_the_existing_row(self):
        """Test: A submitted role that disagrees with an existing registration
        row for this round is rejected with ConflictError, and the row is
        not overwritten."""
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        existing_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=ParticipantRole.MENTEE,
        )
        self.mock_participants_repo.get_by_user_id_and_round_id.return_value = (
            existing_entity
        )
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR

        with self.assertRaises(ConflictError) as ctx:
            await self.service.update_registration_info(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=self.mock_round_id,
                preferences_data=self.sample_dto,
            )

        self.assertIn("mentee", str(ctx.exception))
        self.mock_session.commit.assert_not_awaited()

    async def test_update_enforces_the_deadline_of_the_submitted_role(self):
        """Test: The deadline enforced is the one for the role actually
        submitted, not any fixed role: mentor open, mentee closed."""
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2099-01-01T00:00:00+00:00",
            "mentee_application_deadline_at": "2000-01-01T00:00:00+00:00",
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )

        global_entity = PreferenceEntity(user_id=self.user_id)
        participant_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id, round_id=self.mock_round_id
        )

        with patch.object(
            self.service,
            "_update_skill_and_industry_preferences",
            new_callable=AsyncMock,
        ) as mock_global_update:
            with patch.object(
                self.service, "_update_user_round_preferences", new_callable=AsyncMock
            ) as mock_round_update:
                mock_global_update.return_value = global_entity
                mock_round_update.return_value = participant_entity

                self.sample_dto.round_preferences.participant_role = (
                    ParticipantRole.MENTOR
                )
                await self.service.update_registration_info(
                    session=self.mock_session,
                    user_context=self.user_context,
                    round_id=self.mock_round_id,
                    preferences_data=self.sample_dto,
                )  # does not raise

                self.sample_dto.round_preferences.participant_role = (
                    ParticipantRole.MENTEE
                )
                with self.assertRaises(ValueError):
                    await self.service.update_registration_info(
                        session=self.mock_session,
                        user_context=self.user_context,
                        round_id=self.mock_round_id,
                        preferences_data=self.sample_dto,
                    )

    async def test_update_preferences_saves_profile_survey(self):
        """When profile_survey is provided, it should be serialized with exclude_none and saved."""
        self.sample_dto.global_preferences.profile_survey = ProfileSurveyCreateDto(
            career_transition="tech",
            region="us_west",
        )
        existing_entity = PreferenceEntity(user_id=self.user_id)
        self.mock_preference_repo.get_preferences_by_user_id.return_value = (
            existing_entity
        )

        await self.service._update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertEqual(
            existing_entity.profile_survey,
            {"career_transition": "tech", "region": "us_west"},
        )

    async def test_update_preferences_clears_profile_survey_if_none(self):
        """When profile_survey is None, the entity field should be set to None."""
        self.sample_dto.global_preferences.profile_survey = None
        existing_entity = PreferenceEntity(
            user_id=self.user_id,
            profile_survey={"career_transition": "old_value"},
        )
        self.mock_preference_repo.get_preferences_by_user_id.return_value = (
            existing_entity
        )

        await self.service._update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertIsNone(existing_entity.profile_survey)

    async def test_update_user_round_preferences_saves_current_stage_and_time_urgency(
        self,
    ):
        """current_stage and time_urgency from round preferences should be saved to entity."""
        existing_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=ParticipantRole.MENTOR,
        )
        self.mock_participants_repo.get_by_user_id_and_round_id.return_value = (
            existing_entity
        )

        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        self.sample_dto.round_preferences.current_stage = "exploring"
        self.sample_dto.round_preferences.time_urgency = "high"

        await self.service._update_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.mock_round_id,
            data=self.sample_dto,
        )

        self.assertEqual(existing_entity.current_stage, "exploring")
        self.assertEqual(existing_entity.time_urgency, "high")

    async def test_update_user_round_preferences_none_current_stage_and_time_urgency(
        self,
    ):
        """When current_stage and time_urgency are None, entity fields should be None."""
        existing_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id,
            round_id=self.mock_round_id,
            participant_role=ParticipantRole.MENTOR,
            current_stage="old_stage",
            time_urgency="old_urgency",
        )
        self.mock_participants_repo.get_by_user_id_and_round_id.return_value = (
            existing_entity
        )

        self.sample_dto.round_preferences.current_stage = None
        self.sample_dto.round_preferences.time_urgency = None

        await self.service._update_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.mock_round_id,
            data=self.sample_dto,
        )

        self.assertIsNone(existing_entity.current_stage)
        self.assertIsNone(existing_entity.time_urgency)

    async def _register(self):
        """Invoke update_registration_info with the round/preferences mapper
        plumbing stubbed out, returning its RegistrationDto result."""
        global_entity = PreferenceEntity(user_id=self.user_id)
        participant_entity = MentorshipRoundParticipantsEntity(
            user_id=self.user_id, round_id=self.mock_round_id
        )
        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )
        with patch.object(
            self.service,
            "_update_skill_and_industry_preferences",
            new_callable=AsyncMock,
        ) as mock_global_update:
            with patch.object(
                self.service, "_update_user_round_preferences", new_callable=AsyncMock
            ) as mock_round_update:
                mock_global_update.return_value = global_entity
                mock_round_update.return_value = participant_entity

                return await self.service.update_registration_info(
                    session=self.mock_session,
                    user_context=self.user_context,
                    round_id=self.mock_round_id,
                    preferences_data=self.sample_dto,
                )

    async def test_registration_delegates_with_the_computed_deadline(self):
        """Test: The deadline passed to ensure_onboarding_training is the
        round's application deadline for the submitted role, plus two days."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=datetime(2026, 4, 29, 23, 59, 59, tzinfo=timezone.utc),
            link="https://mentor",
        )

        await self._register()

        self.mock_onboarding_training_service.ensure_onboarding_training.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            deadline=datetime(
                2026, 4, 29, 23, 59, 59, tzinfo=timezone.utc
            ),  # app deadline + 2 days
        )

    async def test_registration_uses_the_mentee_category_for_a_mentee(self):
        """Test: A mentee's registration passes the mentee onboarding category,
        not the mentor one used elsewhere in this fixture's default role."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTEE
        mock_round = MagicMock()
        mock_round.description = {
            "mentee_application_deadline_at": "2026-04-25T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=None,
            link="https://mentee",
        )

        await self._register()

        kwargs = self.mock_onboarding_training_service.ensure_onboarding_training.await_args.kwargs
        self.assertEqual(
            kwargs["category"], TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING
        )

    async def test_registration_reports_completed_training(self):
        """Test: is_onboarding_training_completed reflects a DONE row returned
        by ensure_onboarding_training."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            status=TrainingStatus.DONE,
            completed_timestamp=datetime(2026, 4, 20, tzinfo=timezone.utc),
            deadline=datetime(2026, 4, 29, 23, 59, 59, tzinfo=timezone.utc),
            link="https://mentor",
        )

        result = await self._register()

        self.assertTrue(result.is_onboarding_training_completed)

    async def test_registration_reports_incomplete_training(self):
        """Test: is_onboarding_training_completed reflects a non-DONE row
        returned by ensure_onboarding_training."""
        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR
        mock_round = MagicMock()
        mock_round.description = {
            "mentor_application_deadline_at": "2026-04-27T23:59:59Z"
        }
        mock_round.name = "test round"
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_onboarding_training_service.ensure_onboarding_training.return_value = TrainingEntity(
            user_id=self.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            status=TrainingStatus.TO_DO,
            completed_timestamp=None,
            deadline=datetime(2026, 4, 29, 23, 59, 59, tzinfo=timezone.utc),
            link="https://mentor",
        )

        result = await self._register()

        self.assertFalse(result.is_onboarding_training_completed)


if __name__ == "__main__":
    unittest.main()
