import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock

from backend.mentorship.participation_service import ParticipationService
from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.users_entity import UsersEntity


class TestParticipationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_all_by_ids = AsyncMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_all_partner_ids = AsyncMock()
        self.mock_pairs_repo.get_partner_ids_by_user_and_round = AsyncMock()

        self.mock_session = AsyncMock()
        self.mock_mapper = MagicMock()
        self.logger = MagicMock()

        self.mock_identity_service = MagicMock()
        self.mock_identity_service.get_user = AsyncMock()

        self.participation_service = ParticipationService(
            logger=self.logger,
            users_repository=self.mock_users_repo,
            mentorship_pairs_repository=self.mock_pairs_repo,
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

        self.mock_current_user = MagicMock(
            spec=UsersEntity, user_id=123, subject_identifier=str(uuid.uuid4())
        )
        self.user_context = MagicMock(spec=UserContextDto, sub="user_sub")

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

    async def test_get_partners_for_user_not_found(self):
        """Test returns empty list when current user is not found."""
        self.mock_identity_service.get_user.return_value = None
        self.user_context.sub = "non-existent-sub"

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.assertEqual(result, [])
        self.mock_identity_service.get_user.assert_awaited_once_with(
            session=self.mock_session, user_info=self.user_context
        )
        self.mock_pairs_repo.get_all_partner_ids.assert_not_awaited()
        self.mock_pairs_repo.get_partner_ids_by_user_and_round.assert_not_awaited()
        self.mock_users_repo.get_all_by_ids.assert_not_awaited()

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
