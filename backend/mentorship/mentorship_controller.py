from http import HTTPStatus
from fastapi import APIRouter
from backend.dto.rounds_dto import RoundsDto
from backend.dto.rounds_create_dto import RoundsCreateDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RegistrationDto
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.dto.feedback_create_dto import FeedbackCreateDto
from backend.dto.feedback_dto import FeedbackDto
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import (
    MENTORSHIP_ROUNDS_ENDPOINT,
    MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
    MENTORSHIP_PARTNERS_ENDPOINT,
    MENTORSHIP_MATCH_RESULT_ENDPOINT,
    MENTORSHIP_MEETINGS_ENDPOINT,
    MENTORSHIP_MEETING_V2_ENDPOINT,
    MENTORSHIP_MEETING_V2_SINGLE_ENDPOINT,
    MENTORSHIP_MEETING_V2_BATCH_DELETE_ENDPOINT,
    MEET_ATTENDANCE_SYNC_ENDPOINT,
    MENTORSHIP_ROUNDS_FEEDBACK_ENDPOINT,
)
from backend.common.permissions import Permission
from backend.dto.google_meeting_create_dto import GoogleMeetingCreateDto
from backend.dto.google_meeting_delete_dto import GoogleMeetingDeleteDto


class MentorshipController:
    def __init__(
        self,
        rounds_service,
        participation_service,
        registration_service,
        meeting_service,
        launchdarkly_service,
        database,
        meet_attendance_sync_service,
    ):
        """
        Initialize the MentorshipController with required dependencies and register routes.

        Args:
            rounds_service: RoundsService instance.
            participation_service: ParticipationService instance.
            registration_service: RegistrationService instance.
            meeting_service: MeetingService instance.
            launchdarkly_service: LaunchDarklyService instance.
            database (Database): Database access object providing async session management.
            meet_attendance_sync_service: MeetAttendanceSyncService instance.
        """

        self.rounds_service = rounds_service
        self.participation_service = participation_service
        self.registration_service = registration_service
        self.meeting_service = meeting_service
        self.launchdarkly_service = launchdarkly_service
        self.database = database
        self.meet_attendance_sync_service = meet_attendance_sync_service

        self.router = APIRouter(tags=["mentorship"])

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_ENDPOINT,
            endpoint=authenticate()(self.get_all_rounds),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_PARTNERS_ENDPOINT,
            endpoint=authenticate()(self.get_partners_for_user),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
            endpoint=authenticate()(self.get_registration_info),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
            endpoint=authenticate()(self.update_registration_info),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ROUND_WRITE])(
                self.upsert_rounds
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            MENTORSHIP_MATCH_RESULT_ENDPOINT,
            endpoint=authenticate()(self.get_my_match_result),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_MEETINGS_ENDPOINT,
            endpoint=authenticate()(self.get_meetings_for_user),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_MEETINGS_ENDPOINT,
            endpoint=authenticate()(self.upsert_meetings),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_MEETING_V2_ENDPOINT,
            endpoint=authenticate()(self.create_google_meeting),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            MENTORSHIP_MEETING_V2_ENDPOINT,
            endpoint=authenticate()(self.get_meetings_for_user_v2),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            MENTORSHIP_MEETING_V2_BATCH_DELETE_ENDPOINT,
            endpoint=authenticate()(self.batch_delete_google_meetings),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            MENTORSHIP_MEETING_V2_SINGLE_ENDPOINT,
            endpoint=authenticate()(self.delete_single_google_meeting),
            methods=["DELETE"],
            response_model=None,
        )
        self.router.add_api_route(
            MEET_ATTENDANCE_SYNC_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_SYNC])(
                self.sync_meet_attendance
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_FEEDBACK_ENDPOINT,
            endpoint=authenticate()(self.get_program_feedback),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_FEEDBACK_ENDPOINT,
            endpoint=authenticate()(self.upsert_program_feedback),
            methods=["POST"],
            response_model=None,
        )

    async def sync_meet_attendance(
        self, current_user: UserContextDto, lookback_hours: int = 2
    ):
        """
        CronJob endpoint to sync Google Meet attendance for completed meetings.

        Args:
            lookback_hours: Number of hours to look back when querying the
                Meet API for ended conferences. Defaults to 2.
        """
        if self.launchdarkly_service.is_create_google_meeting_enabled(current_user):
            async with self.database.session() as session:
                result = await self.meet_attendance_sync_service.sync_attendance(
                    session=session, lookback_hours=lookback_hours
                )
            return api_response(
                success=True,
                message="Attendance sync completed",
                data=result,
            )
        raise PermissionError(
            "Creating Google meetings is not yet supported. No need to sync attendance."
        )

    async def get_my_match_result(self, current_user: UserContextDto, round_id: int):
        """
        Retrieve the current user's mentorship match result for a specific round.

        Args:
            current_user (UserContextDto): The context of the currently authenticated user.
            round_id (int): The mentorship round ID to retrieve the match result for.

        Returns:
            ApiResponse:
                A standardized API response containing the user's match result data.
        """
        async with self.database.session() as session:
            result = await self.participation_service.get_my_match_result_by_round_id(
                session=session, user_context=current_user, round_id=round_id
            )

        return api_response(
            message="Successfully fetched match result.",
            data=result,
        )

    async def get_all_rounds(
        self, current_user: UserContextDto, need_details: bool = False
    ):
        """
        Retrieve all mentorship rounds.

        Args:
            current_user (UserContextDto): The authenticated user context.
            need_details (bool): If True, returns participant and completed
                meeting counts per round for the mentorship admin dashboard.
                This detailed view requires the MENTORSHIP_ROUND_READ
                permission; the basic list (need_details=False) is open to any
                authenticated user.

        Return:
            API response containing a list of rounds DTOs.
        """
        if need_details and not current_user.has_permission(
            Permission.MENTORSHIP_ROUND_READ
        ):
            return api_response(
                success=False,
                message="Forbidden: Insufficient permissions",
                status_code=HTTPStatus.FORBIDDEN,
            )

        async with self.database.session() as session:
            rounds: list[RoundsDto] = await self.rounds_service.get_all_rounds(
                session, include_details=need_details
            )

        return api_response(
            message="Successfully fetched all mentorship rounds.",
            data=rounds,
        )

    async def get_partners_for_user(
        self, current_user: UserContextDto, round_id: int | None = None
    ):
        """
        Retrieve mentorship partners for the current user.

        Args:
            current_user (UserContextDto): The authenticated user context object
                                        containing the user's unique ID (sub),
                                        email, and assigned roles.
            round_id (int | None): Mentorship round ID to filter partners.

        Return:
            API response containing a list of partner DTOs.
        """
        async with self.database.session() as session:
            partners: list[
                PartnerDto
            ] = await self.participation_service.get_partners_for_user(
                session=session, user_context=current_user, round_id=round_id
            )

        return api_response(
            message="Successfully fetched mentorship partners.",
            data=partners,
        )

    async def get_registration_info(self, current_user: UserContextDto, round_id: int):
        """
        Fetch the registration information for the current user in a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The ID of the specific mentorship round the user is registering for.

        Returns:
            API response containing the unified RegistrationDto.
        """
        async with self.database.session() as session:
            registration_info: RegistrationDto = (
                await self.registration_service.get_registration_info(
                    session=session, user_context=current_user, round_id=round_id
                )
            )

        return api_response(
            message="Successfully fetched mentorship round registration information.",
            data=registration_info,
        )

    async def update_registration_info(
        self,
        current_user: UserContextDto,
        round_id: int,
        preferences_data: RegistrationCreateDto,
    ):
        """
        Update or create the registration information for the current user in a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The ID of the specific mentorship round the user is registering for.
            preferences_data (RegistrationDto): A DTO containing updated global and round-specific preferences.
        """
        async with self.database.session() as session:
            updated_registration_info: RegistrationDto = (
                await self.registration_service.update_registration_info(
                    session=session,
                    user_context=current_user,
                    round_id=round_id,
                    preferences_data=preferences_data,
                )
            )

        return api_response(
            message="Successfully updated mentorship round registration information.",
            data=updated_registration_info,
        )

    async def upsert_rounds(self, payload: RoundsCreateDto):
        """
        Create or update a mentorship round based on the provided data.

        Args:
            payload (RoundsCreateDto): The data for creating or updating a mentorship round.

        Returns:
            API response indicating success or failure.
        """
        async with self.database.session() as session:
            upsert_rounds: RoundsDto = await self.rounds_service.upsert_rounds(
                session=session, data=payload
            )

        return api_response(
            message="Successfully created or updated the mentorship round.",
            data=upsert_rounds,
        )

    async def get_meetings_for_user(self, current_user: UserContextDto, round_id: int):
        async with self.database.session() as session:
            meetings: MeetingDto = (
                await self.meeting_service.get_meetings_by_user_and_round(
                    session=session, user_context=current_user, round_id=round_id
                )
            )

        return api_response(
            message="Successfully fetched mentorship meeting logs.",
            data=meetings,
        )

    async def upsert_meetings(
        self, current_user: UserContextDto, payload: MeetingCreateDto
    ):
        if self.launchdarkly_service.is_manual_submit_meeting_enabled(current_user):
            async with self.database.session() as session:
                updated_meeting_log: MeetingDto = (
                    await self.meeting_service.upsert_meetings(
                        session=session, user_context=current_user, data=payload
                    )
                )
            return api_response(
                message="Successfully updated mentorship meeting logs.",
                data=updated_meeting_log,
            )

        raise PermissionError("Manual submit meeting feature is not yet available.")

    async def create_google_meeting(
        self, current_user: UserContextDto, payload: GoogleMeetingCreateDto
    ):
        """
        Create a Google Calendar meeting for a mentorship pair.

        Args:
            current_user (UserContextDto): The context of the currently authenticated user.
            payload (GoogleMeetingCreateDto): The meeting creation request containing
                partner_id, round_id, and UTC start/end times.

        Returns:
            ApiResponse: A standardized API response containing the created meeting details.
        """
        if self.launchdarkly_service.is_create_google_meeting_enabled(current_user):
            async with self.database.session() as session:
                result = await self.meeting_service.create_google_meeting(
                    session=session,
                    user_context=current_user,
                    partner_id=payload.partner_id,
                    round_id=payload.round_id,
                    start_datetime=payload.start_datetime,
                    end_datetime=payload.end_datetime,
                )

            return api_response(
                message="Successfully created mentorship meeting.",
                data=result,
            )
        raise PermissionError("Create Google meeting feature is not yet available.")

    async def delete_single_google_meeting(
        self,
        current_user: UserContextDto,
        meeting_id: str,
        round_id: int,
        partner_id: int,
    ):
        """
        Delete a single Google Calendar meeting for a mentorship pair.

        This endpoint removes the specified meeting from the local meeting_log
        and deletes the corresponding event from Google Calendar.

        Args:
            current_user (UserContextDto): The currently authenticated user.
            meeting_id (str): The Google Calendar event ID to delete.
            round_id (int): The mentorship round ID.
            partner_id (int): The partner user ID in the mentorship pair.

        Returns:
            ApiResponse: A standardized API response confirming deletion.
        """
        if self.launchdarkly_service.is_create_google_meeting_enabled(current_user):
            async with self.database.session() as session:
                result = await self.meeting_service.delete_google_meetings(
                    session=session,
                    user_context=current_user,
                    deletions=[
                        {
                            "round_id": round_id,
                            "partner_id": partner_id,
                            "meeting_ids": [meeting_id],
                        }
                    ],
                )
            return api_response(
                message="Meeting deletion processed.",
                data=result,
            )
        raise PermissionError("Google meeting feature is not yet available.")

    async def batch_delete_google_meetings(
        self,
        current_user: UserContextDto,
        payload: GoogleMeetingDeleteDto,
    ):
        """
        Delete one or more Google Calendar meetings selected by the user.

        This endpoint processes a batch deletion request, removing meetings from
        the local meeting_log and deleting corresponding events from Google Calendar.

        Args:
            current_user (UserContextDto): The context of the currently authenticated user.
            payload (GoogleMeetingDeleteDto): Request body containing the list of
                meeting deletions. Each entry includes round_id, partner_id, and meeting_ids.

        Returns:
            ApiResponse: A standardized API response confirming deletion.

        Raises:
            PermissionError: If the Google meeting feature is not enabled.
        """
        if self.launchdarkly_service.is_create_google_meeting_enabled(current_user):
            async with self.database.session() as session:
                result = await self.meeting_service.delete_google_meetings(
                    session=session,
                    user_context=current_user,
                    deletions=[d.model_dump() for d in payload.deletions],
                )
            return api_response(
                message="Meetings deletion processed.",
                data=result,
            )
        raise PermissionError("Google meeting feature is not yet available.")

    async def get_meetings_for_user_v2(
        self, current_user: UserContextDto, round_id: int, include_details: bool
    ):
        """
        Retrieve mentorship meeting logs for the current user in a specific round (v2).

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The mentorship round ID.
            include_details (bool): Whether detailed meeting fields are requested.

        Returns:
            API response containing the mentorship meeting logs.
        """
        if self.launchdarkly_service.is_create_google_meeting_enabled(current_user):
            async with self.database.session() as session:
                meetings: MeetingDto = (
                    await self.meeting_service.get_meetings_by_user_and_round_v2(
                        session=session,
                        user_context=current_user,
                        round_id=round_id,
                        include_details=include_details,
                    )
                )
            return api_response(
                message="Successfully fetched mentorship meeting logs.",
                data=meetings,
            )
        raise PermissionError("Google meeting feature is not yet available.")

    async def get_program_feedback(self, current_user: UserContextDto, round_id: int):
        """
        Retrieve the current user's program feedback for a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The mentorship round ID.
        """
        async with self.database.session() as session:
            result: FeedbackDto = await self.participation_service.get_program_feedback(
                session=session, user_context=current_user, round_id=round_id
            )

        return api_response(
            message="Successfully fetched program feedback.",
            data=result,
        )

    async def upsert_program_feedback(
        self,
        current_user: UserContextDto,
        round_id: int,
        feedback_data: FeedbackCreateDto,
    ):
        """
        Save or overwrite the current user's program feedback for a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The mentorship round ID.
            feedback_data (FeedbackCreateDto): The feedback payload.
        """
        async with self.database.session() as session:
            result: FeedbackDto = (
                await self.participation_service.upsert_program_feedback(
                    session=session,
                    user_context=current_user,
                    round_id=round_id,
                    feedback_data=feedback_data,
                )
            )

        return api_response(
            message="Successfully saved program feedback.",
            data=result,
        )
