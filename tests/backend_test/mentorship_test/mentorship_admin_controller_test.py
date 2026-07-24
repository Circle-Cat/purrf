import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from http import HTTPStatus
from backend.mentorship.mentorship_admin_controller import MentorshipAdminController
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto


class TestMentorshipAdminController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_admin_service = MagicMock()
        self.mock_admin_service.search_participants = AsyncMock()
        self.mock_admin_service.get_meeting_log = AsyncMock()
        self.mock_admin_service.stream_export_csv = MagicMock()

        self.mock_database = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.controller = MentorshipAdminController(
            mentorship_admin_service=self.mock_admin_service,
            database=self.mock_database,
        )

        self.patcher = patch(
            "backend.mentorship.mentorship_admin_controller.api_response"
        )
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
                "status_code": status_code,
                "success": success,
            }
        )

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_search_participants_delegates_to_service(self):
        """Delegates to service and wraps the result in api_response."""
        filters = ParticipantSearchFilterDto()
        mock_result = MagicMock()
        self.mock_admin_service.search_participants.return_value = mock_result

        await self.controller.search_participants(filters=filters)

        self.mock_admin_service.search_participants.assert_awaited_once_with(
            self.mock_session, filters, 100, 0, None, "asc"
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully retrieved participant search results.",
            data=mock_result,
        )

    async def test_search_participants_custom_pagination(self):
        """Custom limit and offset are forwarded to the service."""
        filters = ParticipantSearchFilterDto()
        mock_result = MagicMock()
        self.mock_admin_service.search_participants.return_value = mock_result

        await self.controller.search_participants(
            filters=filters,
            limit=50,
            offset=200,
        )

        self.mock_admin_service.search_participants.assert_awaited_once_with(
            self.mock_session, filters, 50, 200, None, "asc"
        )

    async def test_search_participants_custom_sort(self):
        """Custom sort_by and order are forwarded to the service."""
        filters = ParticipantSearchFilterDto()
        mock_result = MagicMock()
        self.mock_admin_service.search_participants.return_value = mock_result

        await self.controller.search_participants(
            filters=filters,
            sort_by="user_id",
            order="desc",
        )

        self.mock_admin_service.search_participants.assert_awaited_once_with(
            self.mock_session, filters, 100, 0, "user_id", "desc"
        )

    async def test_get_meeting_log_delegates_to_service(self):
        """Delegates to service and wraps the result in api_response."""
        mock_result = MagicMock()
        self.mock_admin_service.get_meeting_log.return_value = mock_result

        await self.controller.get_meeting_log(pair_id=1)

        self.mock_admin_service.get_meeting_log.assert_awaited_once_with(
            self.mock_session, 1
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully retrieved meeting log.",
            data=mock_result,
        )

    async def test_export_participants_returns_streaming_response(self):
        """Wraps the service's async generator in a StreamingResponse with CSV headers."""

        async def fake_stream():
            yield b"header\n"
            yield b"row\n"

        filters = ParticipantSearchFilterDto(participation_status="participant")
        self.mock_admin_service.stream_export_csv.return_value = fake_stream()

        response = await self.controller.export_participants(
            filters=filters, mode="summary"
        )

        self.mock_admin_service.stream_export_csv.assert_called_once_with(
            filters, "summary"
        )
        self.assertEqual(response.media_type, "text/csv")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("participant_summary_", response.headers["content-disposition"])

    async def test_export_participants_detailed_mode_filename(self):
        """Detailed mode's filename includes the 'detailed' marker."""

        async def fake_stream():
            yield b"header\n"

        filters = ParticipantSearchFilterDto(participation_status="participant")
        self.mock_admin_service.stream_export_csv.return_value = fake_stream()

        response = await self.controller.export_participants(
            filters=filters, mode="detailed"
        )

        self.assertIn("participant_detailed_", response.headers["content-disposition"])

    async def test_export_non_participant_filename_ignores_mode(self):
        """Non-participant filenames don't include mode."""

        async def fake_stream():
            yield b"header\n"

        filters = ParticipantSearchFilterDto(participation_status="non_participant")
        self.mock_admin_service.stream_export_csv.return_value = fake_stream()

        response = await self.controller.export_participants(
            filters=filters, mode="summary"
        )

        content_disposition = response.headers["content-disposition"]
        self.assertIn("non_participant_", content_disposition)
        self.assertNotIn("summary", content_disposition)

    async def test_export_non_participant_no_mode_filename(self):
        """mode is optional for a non-participant export; when omitted, the
        filename has no "None" segment in it."""

        async def fake_stream():
            yield b"header\n"

        filters = ParticipantSearchFilterDto(participation_status="non_participant")
        self.mock_admin_service.stream_export_csv.return_value = fake_stream()

        response = await self.controller.export_participants(filters=filters)

        self.mock_admin_service.stream_export_csv.assert_called_once_with(filters, None)
        content_disposition = response.headers["content-disposition"]
        self.assertIn("non_participant_", content_disposition)
        self.assertNotIn("None", content_disposition)


if __name__ == "__main__":
    unittest.main()
