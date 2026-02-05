import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from http import HTTPStatus
from datetime import date
from backend.dto.rounds_dto import RoundsDto
from backend.dto.rounds_create_dto import TimelineCreateDto
from backend.dto.rounds_create_dto import RoundsCreateDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RegistrationDto
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.mentorship.mentorship_controller import MentorshipController


class TestMentorshipController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_rounds_service = MagicMock()
        self.mock_rounds_service.get_all_rounds = AsyncMock()
        self.mock_rounds_service.upsert_rounds = AsyncMock()

        self.mock_participation_service = MagicMock()
        self.mock_participation_service.get_partners_for_user = AsyncMock()

        self.mock_registration_service = MagicMock()
        self.mock_registration_service.get_registration_info = AsyncMock()
        self.mock_registration_service.update_registration_info = AsyncMock()

        self.mock_database = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.controller = MentorshipController(
            rounds_service=self.mock_rounds_service,
            participation_service=self.mock_participation_service,
            registration_service=self.mock_registration_service,
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

        self.timeline_data = TimelineCreateDto(
            promotion_start_at=date(2025, 12, 1),
            application_deadline_at=date(2026, 1, 15),
            review_start_at=date(2026, 1, 16),
            acceptance_notification_at=date(2026, 1, 25),
            matching_completed_at=date(2026, 1, 31),
            match_notification_at=date(2026, 2, 2),
            first_meeting_deadline_at=date(2026, 2, 25),
            meetings_completion_deadline_at=date(2026, 5, 25),
            feedback_deadline_at=date(2026, 6, 10),
        )

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_get_my_match_result(self):
        """Test retrieve current user's mentorship match result for a round."""
        mock_user = MagicMock(spec=UserContextDto)
        mock_round_id = 1
        mock_result = MagicMock()

        self.mock_participation_service.get_my_match_result_by_round_id = AsyncMock(
            return_value=mock_result
        )

        response = await self.controller.get_my_match_result(
            current_user=mock_user,
            round_id=mock_round_id,
        )

        self.mock_participation_service.get_my_match_result_by_round_id.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            round_id=mock_round_id,
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched match result.",
            data=mock_result,
        )

        self.assertEqual(response["data"], mock_result)

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

    async def test_get_partners_for_user_with_round_id(self):
        """Test retrieve partners with both sub and round_id."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_round_id = 1
        mock_data = [MagicMock(spec=PartnerDto)]
        self.mock_participation_service.get_partners_for_user.return_value = mock_data

        response = await self.controller.get_partners_for_user(
            current_user=mock_user, round_id=mock_round_id
        )

        self.mock_participation_service.get_partners_for_user.assert_awaited_once_with(
            session=self.mock_session, user_context=mock_user, round_id=mock_round_id
        )
        self.assertEqual(response["data"], mock_data)
        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched mentorship partners.", data=mock_data
        )

    async def test_get_partners_for_user_without_round_id(self):
        """Test retrieve partners with sub only."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_data = [MagicMock(spec=PartnerDto)]
        self.mock_participation_service.get_partners_for_user.return_value = mock_data

        response = await self.controller.get_partners_for_user(current_user=mock_user)

        self.mock_participation_service.get_partners_for_user.assert_awaited_once_with(
            session=self.mock_session, user_context=mock_user, round_id=None
        )
        self.assertEqual(response["data"], mock_data)

    async def test_get_registration_info(self):
        """Test retrieve registration info for a user."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_round_id = 1
        mock_data = MagicMock(spec=RegistrationDto)
        self.mock_registration_service.get_registration_info.return_value = mock_data

        response = await self.controller.get_registration_info(
            current_user=mock_user, round_id=mock_round_id
        )

        self.mock_registration_service.get_registration_info.assert_awaited_once_with(
            session=self.mock_session, user_context=mock_user, round_id=mock_round_id
        )
        self.assertEqual(response["data"], mock_data)
        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched mentorship round registration information.",
            data=mock_data,
        )

    async def test_update_registration_info(self):
        """Test update or create registration information for a user."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_round_id = 1
        mock_data = MagicMock(spec=RegistrationCreateDto)

        mock_dto = MagicMock(spec=RegistrationDto)
        self.mock_registration_service.update_registration_info.return_value = mock_dto

        response = await self.controller.update_registration_info(
            current_user=mock_user, round_id=mock_round_id, preferences_data=mock_data
        )

        self.mock_registration_service.update_registration_info.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            round_id=mock_round_id,
            preferences_data=mock_data,
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully updated mentorship round registration information.",
            data=mock_dto,
        )

        self.assertEqual(response["data"], mock_dto)
        self.assertEqual(
            response["message"],
            "Successfully updated mentorship round registration information.",
        )

    async def test_upsert_rounds_create(self):
        """Test creating a new mentorship round."""
        payload = RoundsCreateDto(
            name="2026-spring",
            mentee_average_score=4.5,
            mentor_average_score=5.0,
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        mock_entity = MagicMock()
        self.mock_rounds_service.upsert_rounds.return_value = mock_entity

        response = await self.controller.upsert_rounds(payload)

        self.mock_rounds_service.upsert_rounds.assert_awaited_once_with(
            session=self.mock_session, data=payload
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully created or updated the mentorship round.",
            data=mock_entity,
        )

        self.assertEqual(response["data"], mock_entity)

    async def test_upsert_rounds_error(self):
        """Test handling errors when updating or creating a mentorship round."""
        payload = RoundsCreateDto(
            name="2026-spring",
            mentee_average_score=4.5,
            mentor_average_score=5.0,
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        self.mock_rounds_service.upsert_rounds.side_effect = ValueError(
            "Round not found"
        )

        with self.assertRaises(ValueError):
            await self.controller.upsert_rounds(payload)

        self.mock_rounds_service.upsert_rounds.assert_awaited_once_with(
            session=self.mock_session, data=payload
        )


if __name__ == "__main__":
    unittest.main()
