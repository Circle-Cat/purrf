from fastapi import APIRouter, Depends
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.dto.matching_run_create_dto import MatchingRunCreateDto
from backend.dto.matching_run_dto import (
    MatchingResultsPageDto,
    MatchingRunOverviewDto,
    MatchingRunStartedDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import (
    MENTORSHIP_ADMIN_PARTICIPANTS,
    MENTORSHIP_ADMIN_PAIRS_MEETINGS,
    MENTORSHIP_ADMIN_MATCH_RUNS,
    MENTORSHIP_ADMIN_MATCH_RUN,
    MENTORSHIP_ADMIN_MATCH_RUN_RESULTS,
    MENTORSHIP_ADMIN_ROUND_FEEDBACK,
    MENTORSHIP_ADMIN_ROUND_UNREGISTERED,
)
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate


class MentorshipAdminController:
    def __init__(
        self,
        mentorship_admin_service,
        matching_run_service,
        matching_run_read_service,
        launchdarkly_service,
        database,
    ):
        self.mentorship_admin_service = mentorship_admin_service
        self.matching_run_service = matching_run_service
        self.matching_run_read_service = matching_run_read_service
        self.launchdarkly_service = launchdarkly_service
        self.database = database
        self.router = APIRouter(tags=["mentorship-admin"])

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PARTICIPANTS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.search_participants
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PAIRS_MEETINGS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_meeting_log
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PAIRS_MEETINGS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.update_meeting_log
            ),
            methods=["PATCH"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUNS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.start_matching_run
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_matching_run
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN_RESULTS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_matching_run_results
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_ROUND_FEEDBACK,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_round_feedback
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_ROUND_UNREGISTERED,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.search_unregistered
            ),
            methods=["GET"],
            response_model=None,
        )

    async def search_participants(
        self,
        filters: ParticipantSearchFilterDto = Depends(),
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ):
        """
        Search mentorship participants.

        Args:
            filters (ParticipantSearchFilterDto): Search filters.
            limit (int): Maximum number of rows to return.
            offset (int): Pagination offset.
            sort_by (str | None): Column to sort by.
            order (str): Sort direction ("asc" or "desc").

        Returns:
            API response containing matching participant records.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.search_participants(
                session, filters, limit, offset, sort_by, order
            )
        return api_response(
            message="Successfully retrieved participant search results.",
            data=result,
        )

    async def search_unregistered(
        self,
        round_id: int,
        filters: UnregisteredFilterDto = Depends(),
        limit: int = 100,
        offset: int = 0,
        order: str = "asc",
    ):
        """
        List people admitted as a mentor or mentee who have not registered
        for a round.

        Args:
            round_id (int): The mentorship round ID.
            filters (UnregisteredFilterDto): Person and admitted-role filters.
            limit (int): Maximum number of rows to return.
            offset (int): Pagination offset.
            order (str): Sort direction by user ID ("asc" or "desc").

        Returns:
            API response containing the rows and their total.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.search_unregistered(
                session, round_id, filters, limit, offset, order
            )
        return api_response(
            message="Successfully retrieved people not registered for the round.",
            data=result,
        )

    async def get_round_feedback(self, round_id: int):
        """
        Retrieve a round's feedback: everyone it is asked of, sent or not.

        Args:
            round_id (int): The mentorship round ID.

        Returns:
            API response containing the round's feedback.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.get_round_feedback(
                session, round_id
            )
        return api_response(
            message="Successfully retrieved round feedback.",
            data=result,
        )

    async def get_meeting_log(self, pair_id: int):
        """
        Retrieve the meeting log for a mentorship pair.

        Args:
            pair_id (int): The mentorship pair ID.

        Returns:
            API response containing the meeting log, or None if the pair does
            not exist.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.get_meeting_log(
                session, pair_id
            )
        return api_response(
            message="Successfully retrieved meeting log.",
            data=result,
        )

    async def update_meeting_log(self, pair_id: int, batch: V2MeetingBatchUpdateDto):
        """
        Apply incremental updates/deletes to a mentorship pair's v2 meeting log.

        Args:
            pair_id (int): The mentorship pair ID.
            batch (V2MeetingBatchUpdateDto): Meeting updates and deletions to apply.

        Returns:
            API response containing the pair's updated meeting log.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.apply_v2_meeting_batch(
                session, pair_id, batch
            )
        return api_response(
            message="Successfully updated meeting log.",
            data=result,
        )

    async def start_matching_run(
        self, body: MatchingRunCreateDto, current_user: UserContextDto
    ):
        """
        Start a matching run for a round over a chosen list of participants.

        Returns as soon as the job has started: it takes about an hour at present
        sizes, and how far along it is comes from what the matcher has written.

        Args:
            body (MatchingRunCreateDto): Round, participants, and optionally the
                date to score as though it were.
            current_user (UserContextDto): Who pressed the button. Travels with
                the run so the completion notice reaches them; nothing outside
                the run records who asked for it.

        Returns:
            API response carrying the run id.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            # Per-admin, and off by default: one press costs an hour of a paid
            # job, so the first real rounds are run by the people expecting to
            # pay for them rather than by anyone who finds the endpoint.
            raise PermissionError("Starting a matching run is not yet available.")

        async with self.database.session() as session:
            result = await self.matching_run_service.start_run(
                session,
                body.round_id,
                body.participant_ids,
                run_date=body.run_date,
                triggered_by_user_id=current_user.user_id,
            )
        return api_response(
            message="Successfully started the matching run.",
            data=MatchingRunStartedDto.model_validate(result),
        )

    async def get_matching_run(self, round_id: int, current_user: UserContextDto):
        """
        Describe the round's most recent matching run.

        Args:
            round_id (int): Round whose run is wanted.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the run's state and what that state carries.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        async with self.database.session() as session:
            result = await self.matching_run_read_service.read_overview(
                session, round_id
            )
        return api_response(
            message="Successfully retrieved the matching run.",
            data=MatchingRunOverviewDto.model_validate(result),
        )

    async def get_matching_run_results(
        self,
        round_id: int,
        current_user: UserContextDto,
        limit: int = 100,
        offset: int = 0,
        matched: bool | None = None,
    ):
        """
        Return one page of the round's matching result.

        Args:
            round_id (int): Round whose run is wanted.
            current_user (UserContextDto): Who is asking.
            limit (int): Maximum number of mentees to return.
            offset (int): Pagination offset.
            matched (bool | None): Keep only the placed or only the unplaced;
                everybody when absent.

        Returns:
            API response carrying the run's counts and one page of mentees.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        async with self.database.session() as session:
            result = await self.matching_run_read_service.read_results(
                session, round_id, limit=limit, offset=offset, matched=matched
            )
        return api_response(
            message="Successfully retrieved the matching run results.",
            data=MatchingResultsPageDto.model_validate(result),
        )
