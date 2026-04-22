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
from backend.dto.google_meeting_create_dto import GoogleMeetingCreateDto
from backend.dto.feedback_create_dto import FeedbackCreateDto
from backend.dto.feedback_dto import FeedbackDto
from backend.mentorship.mentorship_controller import MentorshipController


class TestMentorshipController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_rounds_service = MagicMock()
        self.mock_rounds_service.get_all_rounds = AsyncMock()
        self.mock_rounds_service.upsert_rounds = AsyncMock()

        self.mock_participation_service = MagicMock()
        self.mock_participation_service.get_partners_for_user = AsyncMock()
        self.mock_participation_service.get_program_feedback = AsyncMock()
        self.mock_participation_service.upsert_program_feedback = AsyncMock()

        self.mock_registration_service = MagicMock()
        self.mock_registration_service.get_registration_info = AsyncMock()
        self.mock_registration_service.update_registration_info = AsyncMock()

        self.mock_meeting_service = MagicMock()
        self.mock_meeting_service.get_meetings_by_user_and_round = AsyncMock()
        self.mock_meeting_service.get_meetings_by_user_and_round_v2 = AsyncMock()
        self.mock_meeting_service.upsert_meetings = AsyncMock()
        self.mock_meeting_service.create_google_meeting = AsyncMock()

        self.mock_meet_attendance_sync_service = MagicMock()
        self.mock_meet_attendance_sync_service.sync_attendance = AsyncMock()

        self.mock_launchdarkly_service = MagicMock()
        self.mock_launchdarkly_service.is_manual_submit_meeting_enabled = MagicMock(
            return_value=True
        )
        self.mock_launchdarkly_service.is_create_google_meeting_enabled = MagicMock(
            return_value=False
        )

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
            meeting_service=self.mock_meeting_service,
            launchdarkly_service=self.mock_launchdarkly_service,
            database=self.mock_database,
            meet_attendance_sync_service=self.mock_meet_attendance_sync_service,
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

    async def test_get_meetings_for_user(self):
        """Test retrieve mentorship meeting logs for current user."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_round_id = 1
        mock_meeting_data = MagicMock()

        self.mock_meeting_service.get_meetings_by_user_and_round.return_value = (
            mock_meeting_data
        )

        response = await self.controller.get_meetings_for_user(
            current_user=mock_user, round_id=mock_round_id
        )

        self.mock_meeting_service.get_meetings_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session, user_context=mock_user, round_id=mock_round_id
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched mentorship meeting logs.",
            data=mock_meeting_data,
        )
        self.assertEqual(response["data"], mock_meeting_data)

    async def test_upsert_meetings(self):
        """Test update or create mentorship meeting logs."""
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_user.has_role = MagicMock(return_value=False)
        mock_payload = MagicMock()
        mock_updated_data = MagicMock()

        self.mock_meeting_service.upsert_meetings.return_value = mock_updated_data

        response = await self.controller.upsert_meetings(
            current_user=mock_user, payload=mock_payload
        )

        self.mock_meeting_service.upsert_meetings.assert_awaited_once_with(
            session=self.mock_session, user_context=mock_user, data=mock_payload
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully updated mentorship meeting logs.",
            data=mock_updated_data,
        )
        self.assertEqual(response["data"], mock_updated_data)

    async def test_upsert_meetings_flag_off_denied(self):
        """When flag is off, users are denied access."""
        self.mock_launchdarkly_service.is_manual_submit_meeting_enabled = MagicMock(
            return_value=False
        )
        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_payload = MagicMock()

        with self.assertRaises(PermissionError):
            await self.controller.upsert_meetings(
                current_user=mock_user, payload=mock_payload
            )

        self.mock_meeting_service.upsert_meetings.assert_not_awaited()

    async def test_create_google_meeting(self):
        """Test successful meeting creation delegates to service and returns response."""
        self.mock_launchdarkly_service.is_create_google_meeting_enabled.return_value = (
            True
        )
        mock_user = MagicMock(spec=UserContextDto)
        mock_result = MagicMock()
        self.mock_meeting_service.create_google_meeting.return_value = mock_result

        payload = GoogleMeetingCreateDto(
            partner_id=2,
            round_id=1,
            start_datetime="2026-03-20T10:00:00Z",
            end_datetime="2026-03-20T11:00:00Z",
        )

        response = await self.controller.create_google_meeting(
            current_user=mock_user, payload=payload
        )

        self.mock_meeting_service.create_google_meeting.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            partner_id=payload.partner_id,
            round_id=payload.round_id,
            start_datetime=payload.start_datetime,
            end_datetime=payload.end_datetime,
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully created mentorship meeting.",
            data=mock_result,
        )

        self.assertEqual(response["data"], mock_result)

    async def test_create_google_meeting_service_error(self):
        """Test that service errors propagate through the controller."""
        self.mock_launchdarkly_service.is_create_google_meeting_enabled.return_value = (
            True
        )
        mock_user = MagicMock(spec=UserContextDto)
        self.mock_meeting_service.create_google_meeting.side_effect = ValueError(
            "The specified partner could not be found."
        )

        payload = GoogleMeetingCreateDto(
            partner_id=999,
            round_id=1,
            start_datetime="2026-03-20T10:00:00Z",
            end_datetime="2026-03-20T11:00:00Z",
        )

        with self.assertRaises(ValueError):
            await self.controller.create_google_meeting(
                current_user=mock_user, payload=payload
            )

        self.mock_api_response.assert_not_called()

    async def test_create_google_meeting_feature_disabled(self):
        """Test that PermissionError is raised when feature flag is disabled."""
        self.mock_launchdarkly_service.is_create_google_meeting_enabled.return_value = (
            False
        )
        mock_user = MagicMock(spec=UserContextDto)

        payload = GoogleMeetingCreateDto(
            partner_id=2,
            round_id=1,
            start_datetime="2026-03-20T10:00:00Z",
            end_datetime="2026-03-20T11:00:00Z",
        )

        with self.assertRaises(PermissionError):
            await self.controller.create_google_meeting(
                current_user=mock_user, payload=payload
            )

        self.mock_meeting_service.create_google_meeting.assert_not_awaited()

    async def test_get_meetings_for_user_v2(self):
        """Test retrieve mentorship meeting logs for current user in v2."""
        self.mock_launchdarkly_service.is_create_google_meeting_enabled.return_value = (
            True
        )

        mock_user = MagicMock(spec=UserContextDto, sub="valid-sub")
        mock_round_id = 1
        mock_details = True
        mock_meeting_data = MagicMock()

        self.mock_meeting_service.get_meetings_by_user_and_round_v2.return_value = (
            mock_meeting_data
        )

        response = await self.controller.get_meetings_for_user_v2(
            current_user=mock_user, round_id=mock_round_id, include_details=mock_details
        )

        self.mock_meeting_service.get_meetings_by_user_and_round_v2.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            round_id=mock_round_id,
            include_details=mock_details,
        )

        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched mentorship meeting logs.",
            data=mock_meeting_data,
        )
        self.assertEqual(response["data"], mock_meeting_data)

    async def test_get_program_feedback(self):
        """Test retrieve current user's program feedback for a round."""
        mock_user = MagicMock(spec=UserContextDto)
        mock_round_id = 1
        mock_result = MagicMock(spec=FeedbackDto)
        self.mock_participation_service.get_program_feedback.return_value = mock_result

        response = await self.controller.get_program_feedback(
            current_user=mock_user,
            round_id=mock_round_id,
        )

        self.mock_participation_service.get_program_feedback.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            round_id=mock_round_id,
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully fetched program feedback.",
            data=mock_result,
        )
        self.assertEqual(response["data"], mock_result)

    async def test_get_program_feedback_service_error(self):
        """Test that ValueError from service propagates through the controller."""
        mock_user = MagicMock(spec=UserContextDto)
        self.mock_participation_service.get_program_feedback.side_effect = ValueError(
            "No participant record found."
        )

        with self.assertRaises(ValueError):
            await self.controller.get_program_feedback(
                current_user=mock_user,
                round_id=1,
            )

        self.mock_api_response.assert_not_called()

    async def test_upsert_program_feedback(self):
        """Test save program feedback for a round."""
        mock_user = MagicMock(spec=UserContextDto)
        mock_round_id = 1
        mock_payload = FeedbackCreateDto()
        mock_result = MagicMock(spec=FeedbackDto)
        self.mock_participation_service.upsert_program_feedback.return_value = (
            mock_result
        )

        response = await self.controller.upsert_program_feedback(
            current_user=mock_user,
            round_id=mock_round_id,
            feedback_data=mock_payload,
        )

        self.mock_participation_service.upsert_program_feedback.assert_awaited_once_with(
            session=self.mock_session,
            user_context=mock_user,
            round_id=mock_round_id,
            feedback_data=mock_payload,
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully saved program feedback.",
            data=mock_result,
        )
        self.assertEqual(response["data"], mock_result)

    async def test_upsert_program_feedback_service_error(self):
        """Test that ValueError from service propagates through the controller."""
        mock_user = MagicMock(spec=UserContextDto)
        mock_payload = FeedbackCreateDto()
        self.mock_participation_service.upsert_program_feedback.side_effect = (
            ValueError("No participant record found.")
        )

        with self.assertRaises(ValueError):
            await self.controller.upsert_program_feedback(
                current_user=mock_user,
                round_id=1,
                feedback_data=mock_payload,
            )

        self.mock_api_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
