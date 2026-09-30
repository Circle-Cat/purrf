import unittest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from http import HTTPStatus
from pydantic import ValidationError
from backend.mentorship.mentorship_admin_controller import MentorshipAdminController
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.matching_run_create_dto import MatchingRunCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto


class TestMentorshipAdminController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_admin_service = MagicMock()
        self.mock_admin_service.search_participants = AsyncMock()
        self.mock_admin_service.get_meeting_log = AsyncMock()
        self.mock_admin_service.get_round_feedback = AsyncMock()
        self.mock_admin_service.apply_v2_meeting_batch = AsyncMock()

        self.mock_matching_run_service = MagicMock()
        self.mock_matching_run_service.start_run = AsyncMock()

        self.mock_matching_run_read_service = MagicMock()
        self.mock_matching_run_read_service.read_overview = AsyncMock(
            return_value={"status": "succeeded"}
        )
        self.mock_matching_run_read_service.read_results = AsyncMock(
            return_value={"total": 0, "items": []}
        )

        self.mock_launchdarkly_service = MagicMock()
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = True

        self.mock_database = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.controller = MentorshipAdminController(
            mentorship_admin_service=self.mock_admin_service,
            matching_run_service=self.mock_matching_run_service,
            matching_run_read_service=self.mock_matching_run_read_service,
            launchdarkly_service=self.mock_launchdarkly_service,
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

    async def test_get_round_feedback_delegates_to_service(self):
        """Delegates to service by round and wraps the result in api_response."""
        mock_result = MagicMock()
        self.mock_admin_service.get_round_feedback.return_value = mock_result

        await self.controller.get_round_feedback(round_id=7)

        self.mock_admin_service.get_round_feedback.assert_awaited_once_with(
            self.mock_session, 7
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully retrieved round feedback.",
            data=mock_result,
        )

    async def test_round_feedback_route_is_registered_under_the_round(self):
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in self.controller.router.routes
        }

        self.assertIn(
            ("/mentorship/admin/rounds/{round_id}/feedback", ("GET",)), routes
        )

    async def test_update_meeting_log_delegates_to_service(self):
        """Delegates to service and wraps the result in api_response."""
        batch = V2MeetingBatchUpdateDto(deletes=["m1"])
        mock_result = MagicMock()
        self.mock_admin_service.apply_v2_meeting_batch.return_value = mock_result

        await self.controller.update_meeting_log(pair_id=1, batch=batch)

        self.mock_admin_service.apply_v2_meeting_batch.assert_awaited_once_with(
            self.mock_session, 1, batch
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully updated meeting log.",
            data=mock_result,
        )

    async def test_participant_export_route_is_gone(self):
        paths = {route.path for route in self.controller.router.routes}

        self.assertIn("/mentorship/admin/participants", paths)
        self.assertNotIn("/mentorship/admin/participants/export", paths)

    async def test_search_participants_forwards_the_new_filters(self):
        filters = ParticipantSearchFilterDto(
            q="ada", account_status="blocked", internal="external"
        )
        self.mock_admin_service.search_participants.return_value = MagicMock()

        await self.controller.search_participants(filters=filters)

        forwarded = self.mock_admin_service.search_participants.await_args.args[1]
        self.assertEqual(forwarded.q, "ada")
        self.assertEqual(forwarded.account_status, "blocked")
        self.assertEqual(forwarded.internal, "external")

    def test_filter_rejects_an_unknown_account_status(self):
        with self.assertRaises(ValidationError):
            ParticipantSearchFilterDto(account_status="suspended")

    def test_filter_rejects_an_unknown_internal_value(self):
        with self.assertRaises(ValidationError):
            ParticipantSearchFilterDto(internal="contractor")

    def test_filter_no_longer_takes_name_email_or_matched_user(self):
        for field in ("name", "email", "matched_user"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ParticipantSearchFilterDto(**{field: "x"})

    async def test_start_matching_run_passes_the_selection_through(self):
        self.mock_matching_run_service.start_run.return_value = {
            "run_id": "r7-20260912T000000Z-abc123"
        }
        body = MatchingRunCreateDto(
            round_id=7, participant_ids=[1, 2], run_date="2026-06-01"
        )

        response = await self.controller.start_matching_run(
            body, UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        )

        # The caller's id travels with the run: the completion notice goes to
        # them, and nothing outside the run records who asked for it.
        self.mock_matching_run_service.start_run.assert_awaited_once_with(
            self.mock_session,
            7,
            [1, 2],
            run_date=date(2026, 6, 1),
            triggered_by_user_id=9,
        )
        self.assertEqual(response["data"]["run_id"], "r7-20260912T000000Z-abc123")

    def test_start_matching_run_refuses_a_date_it_cannot_read(self):
        # The job would otherwise start, fail on its own parsing, and hold the
        # round for six hours.
        with self.assertRaises(ValidationError):
            MatchingRunCreateDto(
                round_id=7, participant_ids=[1, 2], run_date="06/01/2026"
            )

    async def test_start_matching_run_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        body = MatchingRunCreateDto(round_id=7, participant_ids=[1, 2])
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.start_matching_run(body, caller)

        # Nothing is started, and the flag is read for this caller rather than
        # globally: one press costs an hour of a paid job.
        self.mock_matching_run_service.start_run.assert_not_awaited()
        self.mock_launchdarkly_service.is_matching_run_enabled.assert_called_once_with(
            caller
        )

    async def test_both_read_routes_are_registered_under_the_round(self):
        # add_api_route builds the dependant as it goes, so a path parameter the
        # handler does not declare fails here rather than on the first request.
        # Calling the handlers directly, as the tests below do, would not.
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in self.controller.router.routes
        }

        self.assertIn(("/mentorship/admin/match-runs/{round_id}", ("GET",)), routes)
        self.assertIn(
            ("/mentorship/admin/match-runs/{round_id}/results", ("GET",)), routes
        )

    async def test_the_overview_is_asked_for_by_round(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        response = await self.controller.get_matching_run(7, caller)

        self.mock_matching_run_read_service.read_overview.assert_awaited_once_with(
            self.mock_session, 7
        )
        self.assertEqual(response["data"]["status"], "succeeded")

    async def test_the_result_page_carries_the_paging_through(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.get_matching_run_results(
            7, caller, limit=25, offset=50, matched=False
        )

        self.mock_matching_run_read_service.read_results.assert_awaited_once_with(
            self.mock_session, 7, limit=25, offset=50, matched=False
        )

    async def test_reading_a_run_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.get_matching_run(7, caller)

        self.mock_matching_run_read_service.read_overview.assert_not_awaited()

    async def test_reading_a_result_page_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.get_matching_run_results(7, caller)

        self.mock_matching_run_read_service.read_results.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
