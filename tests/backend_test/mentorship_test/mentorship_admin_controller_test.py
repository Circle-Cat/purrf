import unittest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from http import HTTPStatus
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.mentorship.mentorship_admin_controller import MentorshipAdminController
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.common.mentorship_enums import ParticipantRole
from backend.dto.matching_run_create_dto import MatchingRunCreateDto
from backend.dto.matching_run_dto import MatchingDraftChangesDto
from backend.dto.mentorship_approval_dto import (
    ApprovalDecisionDto,
    ApprovalReassignDto,
    ApprovalRequestCreateDto,
    EndPairRequestDto,
    ParticipantMarkRequestDto,
)
from backend.dto.participant_detail_dto import ParticipantNoteCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.exceptions import NotFoundError
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.common.permissions import Permission
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto


class TestMentorshipAdminController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_admin_service = MagicMock()
        self.mock_admin_service.search_participants = AsyncMock()
        self.mock_admin_service.get_meeting_log = AsyncMock()
        self.mock_admin_service.get_round_feedback = AsyncMock()
        self.mock_admin_service.search_unregistered = AsyncMock()
        self.mock_admin_service.apply_v2_meeting_batch = AsyncMock()
        self.mock_admin_service.get_participant_detail = AsyncMock()
        self.mock_admin_service.add_participant_note = AsyncMock()

        self.mock_matching_run_service = MagicMock()
        self.mock_matching_run_service.start_run = AsyncMock()

        self.mock_matching_run_read_service = MagicMock()
        self.mock_matching_run_read_service.read_overview = AsyncMock(
            return_value={"status": "succeeded"}
        )
        self.mock_matching_run_read_service.read_results = AsyncMock(
            return_value={"status": "succeeded", "total": 0, "items": []}
        )
        self.mock_matching_run_read_service.read_unmatched = AsyncMock(
            return_value={"status": "succeeded", "total": 0, "items": []}
        )

        self.mock_matching_draft_service = MagicMock()
        self.mock_matching_draft_service.take_lock = AsyncMock(
            return_value={
                "user_id": "9",
                "name": "Ada",
                "expires_at": "2026-10-06T10:30:00+00:00",
            }
        )
        self.mock_matching_draft_service.save_changes.return_value = {"draft_count": 2}

        self.mock_launchdarkly_service = MagicMock()
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = True

        self.mock_database = MagicMock()
        self.mock_session = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.approval = {
            "request_id": 31,
            "action": "publish_matching",
            "status": "pending",
            "round": {"round_id": 7, "name": "Spring 2026"},
            "target_id": "r7-x-y",
            "raised_by": {"user_id": 9, "name": "Ada Ng"},
            "reviewer": {"user_id": 8, "name": "Rae Kim"},
            "reason": "Reviewed every pair",
        }
        self.mock_approval_service = MagicMock()
        for name in (
            "request_publish",
            "request_exemption",
            "request_withdrawal",
            "request_mark",
            "request_end_pair",
            "reassign",
            "decide",
            "withdraw",
        ):
            setattr(
                self.mock_approval_service, name, AsyncMock(return_value=self.approval)
            )
        self.mock_approval_service.list_mine = AsyncMock(return_value=[self.approval])
        self.mock_approval_service.list_reviewers = AsyncMock(
            return_value=[{"user_id": 8, "name": "Rae Kim"}]
        )

        self.controller = MentorshipAdminController(
            mentorship_admin_service=self.mock_admin_service,
            matching_run_service=self.mock_matching_run_service,
            matching_run_read_service=self.mock_matching_run_read_service,
            matching_draft_service=self.mock_matching_draft_service,
            mentorship_approval_service=self.mock_approval_service,
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

    def test_notification_filter_is_read_from_camel_case_query_params(self):
        for dto in (ParticipantSearchFilterDto, UnregisteredFilterDto):
            with self.subTest(dto=dto.__name__):
                app = FastAPI()

                @app.get("/probe")
                async def probe(filters: dto = Depends()):
                    return filters.model_dump()

                response = TestClient(app).get(
                    "/probe",
                    params={
                        "notificationStage": "midterm_reminder",
                        "notificationState": "not_notified",
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    (
                        response.json()["notification_stage"],
                        response.json()["notification_state"],
                    ),
                    ("midterm_reminder", "not_notified"),
                )

    def test_notification_filter_rejects_unknown_values(self):
        for field, value in (
            ("notification_stage", "rejected"),
            ("notification_state", "replied"),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ParticipantSearchFilterDto(**{field: value})

    def test_filter_rejects_an_unknown_internal_value(self):
        with self.assertRaises(ValidationError):
            ParticipantSearchFilterDto(internal="contractor")

    def test_filter_no_longer_takes_name_email_or_matched_user(self):
        for field in ("name", "email", "matched_user"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ParticipantSearchFilterDto(**{field: "x"})

    def test_filter_no_longer_takes_participation_status(self):
        with self.assertRaises(ValidationError):
            ParticipantSearchFilterDto(participation_status="participant")

    def test_a_query_still_carrying_participation_status_is_not_refused(self):
        """The frontend sends participationStatus until its own change ships;
        an undeclared query parameter is dropped before the DTO sees it."""
        app = FastAPI()

        @app.get("/probe")
        async def probe(filters: ParticipantSearchFilterDto = Depends()):
            return filters.model_dump()

        response = TestClient(app).get(
            "/probe", params={"participationStatus": "participant", "q": "ada"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["q"], "ada")

    async def test_search_unregistered_delegates_to_service(self):
        filters = UnregisteredFilterDto(admitted_role=ParticipantRole.MENTOR)
        mock_result = MagicMock()
        self.mock_admin_service.search_unregistered.return_value = mock_result

        await self.controller.search_unregistered(
            round_id=7, filters=filters, limit=25, offset=50, order="desc"
        )

        self.mock_admin_service.search_unregistered.assert_awaited_once_with(
            self.mock_session, 7, filters, 25, 50, "desc"
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully retrieved people not registered for the round.",
            data=mock_result,
        )

    async def test_unregistered_route_is_registered_under_the_round(self):
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in self.controller.router.routes
        }

        self.assertIn(
            ("/mentorship/admin/rounds/{round_id}/unregistered", ("GET",)), routes
        )

    def test_unregistered_filter_rejects_approval_and_training(self):
        for field, value in (
            ("approval_status", "matched"),
            ("onboarding_status", "completed"),
            ("participant_role", "mentor"),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                UnregisteredFilterDto(**{field: value})

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
        self.assertEqual(response["data"].run_id, "r7-20260912T000000Z-abc123")

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
        self.assertIn(
            ("/mentorship/admin/match-runs/{round_id}/unmatched", ("GET",)), routes
        )
        for route in (
            ("/mentorship/admin/match-runs/{round_id}/edit-lock", ("POST",)),
            ("/mentorship/admin/match-runs/{round_id}/edit-lock", ("DELETE",)),
            ("/mentorship/admin/match-runs/{round_id}/draft", ("PATCH",)),
        ):
            self.assertIn(route, routes)

    async def test_the_overview_is_asked_for_by_round(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        response = await self.controller.get_matching_run(7, caller)

        self.mock_matching_run_read_service.read_overview.assert_awaited_once_with(
            self.mock_session, 7
        )
        self.assertEqual(response["data"].status, "succeeded")

    async def test_the_result_page_carries_the_paging_through(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.get_matching_run_results(
            7, caller, limit=25, offset=50, matched=False
        )

        self.mock_matching_run_read_service.read_results.assert_awaited_once_with(
            self.mock_session, 7, limit=25, offset=50, matched=False
        )

    async def test_the_unmatched_page_carries_the_paging_through(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.get_matching_run_unmatched(7, caller, limit=25, offset=50)

        self.mock_matching_run_read_service.read_unmatched.assert_awaited_once_with(
            self.mock_session, 7, limit=25, offset=50
        )

    async def test_reading_the_unmatched_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.get_matching_run_unmatched(7, caller)

        self.mock_matching_run_read_service.read_unmatched.assert_not_awaited()

    async def test_taking_the_edit_lock_is_for_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        response = await self.controller.take_matching_edit_lock(7, caller)

        self.mock_matching_draft_service.take_lock.assert_awaited_once_with(
            self.mock_session, 7, 9
        )
        self.assertEqual(response["data"].user_id, "9")

    async def test_releasing_the_edit_lock_is_for_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.release_matching_edit_lock(7, caller)

        self.mock_matching_draft_service.release_lock.assert_called_once_with(7, 9)

    async def test_saving_the_draft_passes_the_changes_through(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = MatchingDraftChangesDto.model_validate({
            "changes": [
                {"menteeId": "1", "mentorId": "11", "recommendationReason": "Moved"},
                {"menteeId": "2", "mentorId": None},
            ]
        })

        response = await self.controller.save_matching_draft(7, body, caller)

        round_id, user_id, changes = (
            self.mock_matching_draft_service.save_changes.call_args.args
        )
        self.assertEqual((round_id, user_id), (7, 9))
        self.assertEqual(
            [(c.mentee_id, c.mentor_id, c.recommendation_reason) for c in changes],
            [("1", "11", "Moved"), ("2", None, "")],
        )
        self.assertEqual(response["data"].draft_count, 2)

    async def test_requesting_publishing_names_the_round_reviewer_and_reason(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = ApprovalRequestCreateDto.model_validate({
            "reviewerId": 8,
            "reason": "Reviewed every pair",
        })

        response = await self.controller.request_publishing(7, body, caller)

        self.mock_approval_service.request_publish.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            actor_id=9,
            reviewer_id=8,
            reason="Reviewed every pair",
        )
        self.assertEqual(response["data"].request_id, 31)

    async def test_requesting_an_exemption_names_the_person_in_the_round(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = ApprovalRequestCreateDto(reviewer_id=8, reason="Her mentor left midway")

        await self.controller.request_exemption(7, 21, body, caller)

        self.mock_approval_service.request_exemption.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            user_id=21,
            actor_id=9,
            reviewer_id=8,
            reason="Her mentor left midway",
        )

    async def test_requesting_an_exemption_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.request_exemption(
                7, 21, ApprovalRequestCreateDto(reviewer_id=8, reason="x"), caller
            )
        self.mock_approval_service.request_exemption.assert_not_awaited()

    async def test_requesting_a_withdrawal_names_the_person_in_the_round(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = ApprovalRequestCreateDto(reviewer_id=8, reason="")

        response = await self.controller.request_withdrawal(7, 21, body, caller)

        self.mock_approval_service.request_withdrawal.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            user_id=21,
            actor_id=9,
            reviewer_id=8,
            reason="",
        )
        self.assertEqual(response["data"].request_id, 31)

    async def test_requesting_a_withdrawal_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        with self.assertRaises(PermissionError):
            await self.controller.request_withdrawal(
                7, 21, ApprovalRequestCreateDto(reviewer_id=8, reason=""), caller
            )
        self.mock_approval_service.request_withdrawal.assert_not_awaited()

    async def test_requesting_a_mark_names_the_person_tag_and_pair(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = ParticipantMarkRequestDto.model_validate({
            "tag": "no_show",
            "pairId": 501,
            "reviewerId": 8,
            "reason": "",
        })

        response = await self.controller.request_mark(7, 21, body, caller)

        self.mock_approval_service.request_mark.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            user_id=21,
            tag="no_show",
            pair_id=501,
            actor_id=9,
            reviewer_id=8,
            reason="",
        )
        self.assertEqual(response["data"].request_id, 31)

    def test_a_mark_body_takes_only_the_two_tags(self):
        self.assertIsNone(
            ParticipantMarkRequestDto.model_validate({
                "tag": "red_flag",
                "reviewerId": 8,
                "reason": "",
            }).pair_id
        )
        with self.assertRaises(ValidationError):
            ParticipantMarkRequestDto.model_validate({
                "tag": "matching_exemption",
                "reviewerId": 8,
                "reason": "",
            })

    async def test_requesting_a_mark_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = ParticipantMarkRequestDto.model_validate({
            "tag": "red_flag",
            "reviewerId": 8,
            "reason": "",
        })

        with self.assertRaises(PermissionError):
            await self.controller.request_mark(7, 21, body, caller)
        self.mock_approval_service.request_mark.assert_not_awaited()

    async def test_requesting_to_end_a_pair_names_the_person_and_pair(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = EndPairRequestDto.model_validate({
            "pairId": 501,
            "reviewerId": 8,
            "reason": "",
        })

        response = await self.controller.request_end_pair(7, 21, body, caller)

        self.mock_approval_service.request_end_pair.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            user_id=21,
            pair_id=501,
            actor_id=9,
            reviewer_id=8,
            reason="",
        )
        self.assertEqual(response["data"].request_id, 31)

    async def test_requesting_to_end_a_pair_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = EndPairRequestDto.model_validate({
            "pairId": 501,
            "reviewerId": 8,
            "reason": "",
        })

        with self.assertRaises(PermissionError):
            await self.controller.request_end_pair(7, 21, body, caller)
        self.mock_approval_service.request_end_pair.assert_not_awaited()

    async def test_the_approvers_leave_out_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        response = await self.controller.list_approvers(caller)

        self.mock_approval_service.list_reviewers.assert_awaited_once_with(
            self.mock_session, 9
        )
        self.assertEqual([r.user_id for r in response["data"]], [8])

    async def test_my_approvals_are_the_caller_s(self):
        caller = UserContextDto(sub="auth0|2", primary_email="rae@x.org", user_id=8)

        response = await self.controller.list_my_approvals(caller)

        self.mock_approval_service.list_mine.assert_awaited_once_with(
            self.mock_session, 8
        )
        self.assertEqual(response["data"][0].round.name, "Spring 2026")

    async def test_reassigning_is_done_as_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.reassign_approval(
            31, ApprovalReassignDto(reviewer_id=12), caller
        )

        self.mock_approval_service.reassign.assert_awaited_once_with(
            self.mock_session, request_id=31, actor_id=9, reviewer_id=12
        )

    async def test_a_decision_is_passed_through_as_approve_or_reject(self):
        caller = UserContextDto(sub="auth0|2", primary_email="rae@x.org", user_id=8)

        await self.controller.decide_approval(
            31,
            ApprovalDecisionDto(decision="reject", comment="Mentor 10 is away"),
            caller,
        )
        await self.controller.decide_approval(
            31, ApprovalDecisionDto(decision="approve"), caller
        )

        calls = self.mock_approval_service.decide.await_args_list
        self.assertEqual(
            [(c.kwargs["approve"], c.kwargs["comment"]) for c in calls],
            [(False, "Mentor 10 is away"), (True, None)],
        )
        self.assertEqual({c.kwargs["actor_id"] for c in calls}, {8})

    async def test_withdrawing_is_done_as_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)

        await self.controller.withdraw_approval(31, caller)

        self.mock_approval_service.withdraw.assert_awaited_once_with(
            self.mock_session, request_id=31, actor_id=9
        )

    async def test_approvals_are_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        create = ApprovalRequestCreateDto(reviewer_id=8, reason="Reviewed")

        for call in (
            self.controller.request_publishing(7, create, caller),
            self.controller.list_approvers(caller),
            self.controller.list_my_approvals(caller),
            self.controller.reassign_approval(
                31, ApprovalReassignDto(reviewer_id=12), caller
            ),
            self.controller.decide_approval(
                31, ApprovalDecisionDto(decision="approve"), caller
            ),
            self.controller.withdraw_approval(31, caller),
        ):
            with self.assertRaises(PermissionError):
                await call

        for name in (
            "request_publish",
            "list_reviewers",
            "list_mine",
            "reassign",
            "decide",
            "withdraw",
        ):
            getattr(self.mock_approval_service, name).assert_not_awaited()

    def test_the_approval_routes_carry_their_permissions(self):
        routes = {
            (route.path, tuple(sorted(route.methods))): route
            for route in self.controller.router.routes
        }
        expected = {
            ("/mentorship/admin/match-runs/{round_id}/publish-request", "POST"),
            (
                "/mentorship/admin/rounds/{round_id}/participants/{user_id}"
                "/exemption-request",
                "POST",
            ),
            (
                "/mentorship/admin/rounds/{round_id}/participants/{user_id}"
                "/withdraw-request",
                "POST",
            ),
            (
                "/mentorship/admin/rounds/{round_id}/participants/{user_id}"
                "/mark-request",
                "POST",
            ),
            (
                "/mentorship/admin/rounds/{round_id}/participants/{user_id}"
                "/end-pair-request",
                "POST",
            ),
            ("/mentorship/admin/approvals/approvers", "GET"),
            ("/mentorship/admin/approvals/mine", "GET"),
            ("/mentorship/admin/approvals/{request_id}/reassign", "POST"),
            ("/mentorship/admin/approvals/{request_id}/decide", "POST"),
            ("/mentorship/admin/approvals/{request_id}/withdraw", "POST"),
        }
        for path, method in expected:
            self.assertIn((path, (method,)), routes)

    async def test_editing_is_refused_while_the_flag_is_off(self):
        self.mock_launchdarkly_service.is_matching_run_enabled.return_value = False
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        body = MatchingDraftChangesDto(changes=[])

        for call in (
            self.controller.take_matching_edit_lock(7, caller),
            self.controller.release_matching_edit_lock(7, caller),
            self.controller.save_matching_draft(7, body, caller),
        ):
            with self.assertRaises(PermissionError):
                await call

        self.mock_matching_draft_service.take_lock.assert_not_awaited()
        self.mock_matching_draft_service.release_lock.assert_not_called()
        self.mock_matching_draft_service.save_changes.assert_not_called()

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

    async def test_get_participant_detail_delegates_to_service(self):
        mock_result = MagicMock()
        self.mock_admin_service.get_participant_detail.return_value = mock_result

        await self.controller.get_participant_detail(round_id=7, user_id=3104)

        self.mock_admin_service.get_participant_detail.assert_awaited_once_with(
            self.mock_session, 7, 3104
        )
        self.mock_api_response.assert_called_once_with(
            message="Successfully retrieved the participant.",
            data=mock_result,
        )

    async def test_add_participant_note_writes_as_the_caller(self):
        caller = UserContextDto(sub="auth0|1", primary_email="ada@x.org", user_id=9)
        mock_note = MagicMock()
        self.mock_admin_service.add_participant_note.return_value = mock_note

        await self.controller.add_participant_note(
            7, 3104, ParticipantNoteCreateDto(body="  Called her  "), caller
        )

        self.mock_admin_service.add_participant_note.assert_awaited_once_with(
            self.mock_session,
            round_id=7,
            user_id=3104,
            author_id=9,
            body="Called her",
        )
        self.mock_api_response.assert_called_once_with(
            message="Note added.", data=mock_note
        )

    def test_a_note_must_say_something_and_not_too_much(self):
        for body in ("", "   ", "x" * 5001):
            with self.subTest(length=len(body)):
                with self.assertRaises(ValidationError):
                    ParticipantNoteCreateDto(body=body)
        self.assertEqual(len(ParticipantNoteCreateDto(body="x" * 5000).body), 5000)


class TestParticipantDetailGates(unittest.TestCase):
    """The page's routes, through the real permission decorator."""

    def setUp(self):
        self.service = MagicMock()
        self.service.get_participant_detail = AsyncMock(return_value=None)
        self.service.add_participant_note = AsyncMock(return_value=None)

    def _client(self, permissions):
        database = MagicMock()
        database.session.return_value.__aenter__.return_value = AsyncMock()
        database.session.return_value.__aexit__.return_value = None
        controller = MentorshipAdminController(
            mentorship_admin_service=self.service,
            matching_run_service=MagicMock(),
            matching_run_read_service=MagicMock(),
            matching_draft_service=MagicMock(),
            mentorship_approval_service=MagicMock(),
            launchdarkly_service=MagicMock(),
            database=database,
        )
        app = FastAPI()

        @app.middleware("http")
        async def _inject(request: Request, call_next):
            # Explicit values, never a bare MagicMock: every attribute of one
            # is truthy.
            request.state.user = MagicMock(
                permissions={str(p) for p in permissions},
                user_id=9,
                is_super_admin=False,
                is_active=True,
                is_blocked=False,
                sub="auth0|9",
            )
            return await call_next(request)

        app.include_router(controller.router)
        register_exception_handlers(app)
        return TestClient(app, raise_server_exceptions=False)

    def test_reading_needs_read(self):
        detail = "/mentorship/admin/rounds/7/participants/3104"

        ok = self._client([Permission.MENTORSHIP_ADMIN_READ]).get(detail)
        write_only = self._client([Permission.MENTORSHIP_ADMIN_WRITE]).get(detail)

        self.assertEqual(ok.status_code, HTTPStatus.OK)
        self.assertEqual(write_only.status_code, HTTPStatus.FORBIDDEN)

    def test_writing_a_note_needs_write(self):
        notes = "/mentorship/admin/rounds/7/participants/3104/notes"

        ok = self._client([Permission.MENTORSHIP_ADMIN_WRITE]).post(
            notes, json={"body": "Called her"}
        )
        read_only = self._client([Permission.MENTORSHIP_ADMIN_READ]).post(
            notes, json={"body": "Called her"}
        )

        self.assertEqual(ok.status_code, HTTPStatus.OK)
        self.assertEqual(read_only.status_code, HTTPStatus.FORBIDDEN)
        self.service.add_participant_note.assert_awaited_once()

    def test_an_unknown_person_is_not_found(self):
        self.service.get_participant_detail.side_effect = NotFoundError(
            "User 3104 does not exist."
        )

        resp = self._client([Permission.MENTORSHIP_ADMIN_READ]).get(
            "/mentorship/admin/rounds/7/participants/3104"
        )

        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_an_empty_note_is_a_bad_request(self):
        resp = self._client([Permission.MENTORSHIP_ADMIN_WRITE]).post(
            "/mentorship/admin/rounds/7/participants/3104/notes", json={"body": "  "}
        )

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.service.add_participant_note.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
