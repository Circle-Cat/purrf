import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from http import HTTPStatus
from backend.dto.rounds_dto import RoundsDto
from backend.mentorship.mentorship_controller import MentorshipController


class TestMentorshipController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_rounds_service = MagicMock()
        self.mock_rounds_service.get_all_rounds = AsyncMock()

        self.mock_database = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.controller = MentorshipController(
            mentorship_service=self.mock_rounds_service,
            database=self.mock_database,
        )

        self.patcher = patch("backend.mentorship.mentorship_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK: {
                "message": message,
                "data": data,
                "status_code": status_code,
            }
        )

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_get_all_rounds(self):
        """Test retrieve mentorship rounds with complete data."""
        mock_data = [MagicMock(spec=RoundsDto)]
        self.mock_rounds_service.get_all_rounds.return_value = mock_data

        response = await self.controller.get_all_rounds()

        self.mock_rounds_service.get_all_rounds.assert_awaited_once_with(
            self.mock_session
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched all mentorship rounds.", data=mock_data
        )

        self.assertEqual(response["data"], mock_data)

    async def test_get_all_rounds_empty(self):
        """Test return an empty list when no rounds exist."""
        self.mock_rounds_service.get_all_rounds.return_value = []

        response = await self.controller.get_all_rounds()

        self.mock_rounds_service.get_all_rounds.assert_awaited_once_with(
            self.mock_session
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched all mentorship rounds.", data=[]
        )

        self.assertEqual(response["data"], [])


if __name__ == "__main__":
    unittest.main()
