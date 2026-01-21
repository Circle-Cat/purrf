import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock

from backend.mentorship.participation_service import ParticipationService
from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RoundPreferencesDto
from backend.common.mentorship_enums import ParticipantRole
from backend.common.user_role import UserRole
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity


class TestParticipationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_all_by_ids = AsyncMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_all_partner_ids = AsyncMock()
        self.mock_pairs_repo.get_partner_ids_by_user_and_round = AsyncMock()

        self.mock_round_participants_repo = MagicMock()
        self.mock_round_participants_repo.get_recent_participant_by_user_id = (
            AsyncMock()
        )
        self.mock_round_participants_repo.get_by_user_id_and_round_id = AsyncMock()

        self.mock_session = AsyncMock()
        self.mock_mapper = MagicMock()
        self.logger = MagicMock()

        self.mock_identity_service = MagicMock()
        self.mock_identity_service.get_user = AsyncMock()

        self.participation_service = ParticipationService(
            logger=self.logger,
            users_repository=self.mock_users_repo,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_round_participants_repo=self.mock_round_participants_repo,
            mentorship_mapper=self.mock_mapper,
            user_identity_service=self.mock_identity_service,
        )

        self.mock_users_entities = [
            MagicMock(spec=UsersEntity, user_id=456),
            MagicMock(spec=UsersEntity, user_id=789),
        ]
        self.mock_specific_users_entity = [MagicMock(spec=UsersEntity, user_id=456)]

        self.mock_all_round_partner_ids = [456, 789]
        self.mock_specific_round_partner_ids = [456]

        self.mock_partner_dtos = [
            MagicMock(spec=PartnerDto, id=456),
            MagicMock(spec=PartnerDto, id=789),
        ]
        self.mock_specific_partner_dto = [MagicMock(spec=PartnerDto, id=456)]

        self.user_context = MagicMock(spec=UserContextDto, sub=str(uuid.uuid4()))

        self.mock_current_user = MagicMock(
            spec=UsersEntity, user_id=123, subject_identifier=self.user_context.sub
        )

    async def test_get_partners_for_user_full(self):
        """Test retrieve and map partners for a user with user context and round id."""
        mock_round_id = 1

        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )

        self.mock_pairs_repo.get_partner_ids_by_user_and_round.return_value = (
            self.mock_specific_round_partner_ids
        )
        self.mock_users_repo.get_all_by_ids.return_value = (
            self.mock_specific_users_entity
        )
        self.mock_mapper.map_to_partner_dto.return_value = (
            self.mock_specific_partner_dto
        )

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result, self.mock_specific_partner_dto)
        self.mock_pairs_repo.get_partner_ids_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.mock_current_user.user_id,
            round_id=mock_round_id,
        )

        self.mock_pairs_repo.get_all_partner_ids.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()
        self.mock_users_repo.get_all_by_ids.assert_awaited_once_with(
            session=self.mock_session, user_ids=self.mock_specific_round_partner_ids
        )

    async def test_get_partners_for_user_without_round_id(self):
        """Test retrieve and map partners for a user without round id."""
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )

        self.mock_pairs_repo.get_all_partner_ids.return_value = (
            self.mock_all_round_partner_ids
        )

        self.mock_users_repo.get_all_by_ids.return_value = self.mock_users_entities
        self.mock_mapper.map_to_partner_dto.return_value = self.mock_partner_dtos

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.assertEqual(result, self.mock_partner_dtos)

        self.mock_pairs_repo.get_all_partner_ids.assert_awaited_once_with(
            session=self.mock_session, user_id=self.mock_current_user.user_id
        )
        self.mock_pairs_repo.get_partner_ids_by_user_and_round.assert_not_awaited()

        self.mock_users_repo.get_all_by_ids.assert_awaited_once_with(
            session=self.mock_session, user_ids=self.mock_all_round_partner_ids
        )

        self.mock_session.commit.assert_not_awaited()

    async def test_get_partners_for_user_no_partners_found(self):
        """Test returns empty list when user exists but has no partners."""
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )
        self.mock_pairs_repo.get_all_partner_ids.return_value = []

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.assertEqual(result, [])
        self.mock_session.commit.assert_not_awaited()
        self.mock_users_repo.get_all_by_ids.assert_not_awaited()

    async def test_get_partners_for_user_commit_transaction_when_indicated(self):
        """Test when user identity service indicates a commit is needed (should_commit is True)."""
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            True,
        )

        self.mock_pairs_repo.get_all_partner_ids.return_value = []

        await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.mock_session.commit.assert_awaited_once()
        self.mock_pairs_repo.get_all_partner_ids.assert_awaited_once_with(
            session=self.mock_session, user_id=self.mock_current_user.user_id
        )

    async def test_resolve_role_from_most_recent_participation(self):
        """Uses the role from the most recent participant when the user has prior participation."""
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )

        mock_recent = MagicMock(
            spec=MentorshipRoundParticipantsEntity,
            participant_role=ParticipantRole.MENTOR,
        )
        self.mock_round_participants_repo.get_recent_participant_by_user_id.return_value = mock_recent

        role = await self.participation_service.resolve_participant_role_with_fallback(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
        )

        self.assertEqual(role, ParticipantRole.MENTOR)
        self.mock_round_participants_repo.get_recent_participant_by_user_id.assert_awaited_once_with(
            session=self.mock_session, user_id=self.mock_current_user.user_id
        )

    async def test_infers_mentor_role_from_user_permissions(self):
        """Uses mentor role if user has no participation history and has mentor permission."""
        self.mock_round_participants_repo.get_recent_participant_by_user_id.return_value = None
        self.user_context.has_role.side_effect = (
            lambda role: role == UserRole.CONTACT_GOOGLE_CHAT
        )

        role = await self.participation_service.resolve_participant_role_with_fallback(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
        )

        self.assertEqual(role, ParticipantRole.MENTOR)

    async def test_infers_mentee_role_from_user_permissions(self):
        """Uses mentee role if user has neither participation history nor mentor permission."""
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )
        self.mock_round_participants_repo.get_recent_participant_by_user_id.return_value = None
        self.user_context.has_role.side_effect = (
            lambda role: role == UserRole.MENTORSHIP
        )

        role = await self.participation_service.resolve_participant_role_with_fallback(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
        )

        self.assertEqual(role, ParticipantRole.MENTEE)

    async def test_get_user_round_preferences_found_current(self):
        """Returns preferences from the current round if record exists."""
        mock_round_id = 1
        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        expected_dto = RoundPreferencesDto(
            participant_role=ParticipantRole.MENTOR,
            expected_partner_ids=[456],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="I want to share my project management skills",
        )

        self.mock_mapper.map_to_round_preference_dto.return_value = expected_dto

        result = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
            round_id=mock_round_id,
        )

        self.assertEqual(result, expected_dto)
        self.assertEqual(result.participant_role, ParticipantRole.MENTOR)

        self.mock_round_participants_repo.get_by_user_id_and_round_id.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.mock_current_user.user_id,
            round_id=mock_round_id,
        )
        self.mock_mapper.map_to_round_preference_dto.assert_called_once_with(
            participants_entity=mock_participant
        )

    async def test_get_user_round_preferences_fallback_to_recent(self):
        """Falls back to most recent round if current round record is missing."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )
        mock_recent = MagicMock(spec=MentorshipRoundParticipantsEntity)
        self.mock_round_participants_repo.get_recent_participant_by_user_id.return_value = mock_recent

        historical_dto = RoundPreferencesDto(
            participant_role=ParticipantRole.MENTEE,
            expected_partner_ids=[],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="Historical Goal",
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = historical_dto

        result = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
            round_id=mock_round_id,
        )

        self.assertEqual(result, historical_dto)
        self.mock_round_participants_repo.get_by_user_id_and_round_id.assert_awaited_once()
        self.mock_round_participants_repo.get_recent_participant_by_user_id.assert_awaited_once()
        self.mock_mapper.map_to_round_preference_dto.assert_called_once_with(
            participants_entity=mock_recent
        )

    async def test_get_user_round_preferences_for_new_user(self):
        """Returns default round preferences for a new user."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )
        self.mock_round_participants_repo.get_recent_participant_by_user_id.return_value = None

        self.user_context.has_role.return_value = False

        result = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_context=self.user_context,
            user_id=self.mock_current_user.user_id,
            round_id=mock_round_id,
        )

        self.assertIsInstance(result, RoundPreferencesDto)
        self.assertEqual(result.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(result.expected_partner_ids, [])
        self.assertEqual(result.goal, "")
        self.assertEqual(result.max_partners, 1)


if __name__ == "__main__":
    unittest.main()
