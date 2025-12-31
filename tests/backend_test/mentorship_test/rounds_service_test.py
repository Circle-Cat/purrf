import unittest
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.rounds_service import RoundsService
from backend.dto.rounds_dto import RoundsDto
from backend.entity.mentorship_round_entity import MentorshipRoundEntity


class TestRoundsService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_all_rounds = AsyncMock()

        self.mock_session = AsyncMock()

        self.mock_mapper = MagicMock()

        self.service = RoundsService(
            mentorship_round_repository=self.mock_repo,
            mentorship_mapper=self.mock_mapper,
        )

    async def test_get_all_rounds(self):
        """Test retrieving and mapping of all mentorship rounds."""
        mock_mentorship_round_entities = [MagicMock(spec=MentorshipRoundEntity)]
        mock_rounds_dtos = [MagicMock(spec=RoundsDto)]

        self.mock_repo.get_all_rounds.return_value = mock_mentorship_round_entities
        self.mock_mapper.map_to_rounds_dto.return_value = mock_rounds_dtos

        result = await self.service.get_all_rounds(self.mock_session)

        self.mock_repo.get_all_rounds.assert_awaited_once_with(self.mock_session)
        self.mock_mapper.map_to_rounds_dto.assert_called_once_with(
            mock_mentorship_round_entities
        )

        self.assertEqual(result, mock_rounds_dtos)

    async def test_get_all_rounds_empty(self):
        """Test return an empty list when no rounds exist."""
        self.mock_repo.get_all_rounds.return_value = []
        self.mock_mapper.map_to_rounds_dto.return_value = []

        result = await self.service.get_all_rounds(self.mock_session)

        self.assertEqual(result, [])
        self.mock_repo.get_all_rounds.assert_awaited_once_with(self.mock_session)
        self.mock_mapper.map_to_rounds_dto.assert_called_once_with([])
