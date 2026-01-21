import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.mentorship.registration_service import RegistrationService
from backend.dto.registration_create_dto import (
    RegistrationCreateDto,
    GlobalPreferencesDto,
    RoundPreferencesDto,
)
from backend.dto.registration_dto import (
    RegistrationDto,
    GlobalPreferencesDto as GlobalPreferencesResponseDto,
    RoundPreferencesDto as RoundPreferencesResponseDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.common.user_role import UserRole
from backend.common.mentorship_enums import ParticipantRole


class TestRegistrationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_preference_repo = MagicMock()
        self.mock_preference_repo.get_preferences_by_user_id = AsyncMock()
        self.mock_preference_repo.upsert_preference = AsyncMock()

        self.mock_round_repo = MagicMock()
        self.mock_round_repo.get_by_round_id = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.get_by_user_id_and_round_id = AsyncMock()
        self.mock_participants_repo.upsert_participant = AsyncMock()

        self.mock_logger = MagicMock()
        self.mock_session = AsyncMock()

        self.mock_participation_service = MagicMock()
        self.mock_participation_service.get_user_round_preferences = AsyncMock()
        self.mock_participation_service.resolve_participant_role_with_fallback = (
            AsyncMock()
        )

        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.get_user = AsyncMock()

        self.mock_mapper = MagicMock()

        self.service = RegistrationService(
            logger=self.mock_logger,
            preferences_repository=self.mock_preference_repo,
            mentorship_round_repository=self.mock_round_repo,
            mentorship_round_participants_repository=self.mock_participants_repo,
            participation_service=self.mock_participation_service,
            user_identity_service=self.mock_user_identity_service,
            mentorship_mapper=self.mock_mapper,
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
        self.mock_user = MagicMock()
        self.mock_user.user_id = self.user_id
        self.user_context = MagicMock(
            spec=UserContextDto, roles=[UserRole.CONTACT_GOOGLE_CHAT]
        )
        self.mock_round_id = 1

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
        """Test: Get registration info, containing global and round preferences."""
        mock_entity = MagicMock(spec=PreferenceEntity)
        self.mock_user_identity_service.get_user.return_value = (self.mock_user, False)
        self.mock_preference_repo.get_preferences_by_user_id.return_value = mock_entity
        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_participation_service.get_user_round_preferences.return_value = (
            self.sample_registration_dto.round_preferences
        )

        await self.service.get_registration_info(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=self.mock_round_id,
        )

        self.mock_user_identity_service.get_user.assert_awaited_once_with(
            session=self.mock_session, user_info=self.user_context
        )
        self.mock_participation_service.get_user_round_preferences.assert_awaited_once_with(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.user_id,
            round_id=self.mock_round_id,
        )
        self.mock_preference_repo.get_preferences_by_user_id.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_id
        )
        self.mock_mapper.map_to_global_preferences_dto.assert_called_once_with(
            preference_entity=mock_entity
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
        mock_round = MagicMock()
        mock_round.description = {"application_deadline_at": "2099-01-01"}
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        self.mock_user_identity_service.get_user.return_value = (self.mock_user, False)
        self.mock_participation_service.resolve_participant_role_with_fallback.return_value = ParticipantRole.MENTOR

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

    async def test_update_registration_info_expired(self):
        """Test: When the registration period has ended, stop registration."""
        mock_round = MagicMock()
        mock_round.description = {"application_deadline_at": "2024-01-01"}
        self.mock_round_repo.get_by_round_id.return_value = mock_round

        with self.assertRaisesRegex(ValueError, "has ended"):
            await self.service.update_registration_info(
                self.mock_session,
                self.user_context,
                self.mock_round_id,
                self.sample_dto,
            )

    async def test_update_registration_info_role_override(self):
        """Test: Overrides user-provided role with fallback logic regardless of frontend input."""
        mock_round = MagicMock()
        mock_round.description = {"application_deadline_at": "2099-01-01"}
        self.mock_round_repo.get_by_round_id.return_value = mock_round
        self.mock_user_identity_service.get_user.return_value = (self.mock_user, False)

        self.mock_participation_service.resolve_participant_role_with_fallback.return_value = ParticipantRole.MENTEE

        self.mock_mapper.map_to_global_preferences_dto.return_value = (
            self.sample_registration_dto.global_preferences
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = (
            self.sample_registration_dto.round_preferences
        )

        self.sample_dto.round_preferences.participant_role = ParticipantRole.MENTOR

        self.user_context.roles = [UserRole.MENTORSHIP]

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

                self.mock_session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
