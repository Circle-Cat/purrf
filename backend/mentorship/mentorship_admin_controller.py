from fastapi import APIRouter, Depends
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.dto.matching_run_create_dto import MatchingRunCreateDto
from backend.dto.matching_run_dto import (
    MatchingResultsPageDto,
    MatchingDraftChangesDto,
    MatchingDraftSavedDto,
    MatchingEditLockDto,
    MatchingRunOverviewDto,
    MatchingUnmatchedPageDto,
    MatchingRunStartedDto,
)
from backend.dto.mentorship_approval_dto import (
    ApprovalDecisionDto,
    ApprovalPersonDto,
    ApprovalReassignDto,
    ApprovalRequestCreateDto,
    EndPairRequestDto,
    MentorshipApprovalDto,
    ParticipantMarkRequestDto,
)
from backend.dto.participant_detail_dto import ParticipantNoteCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import (
    MENTORSHIP_ADMIN_PARTICIPANTS,
    MENTORSHIP_ADMIN_PAIRS_MEETINGS,
    MENTORSHIP_ADMIN_MATCH_RUNS,
    MENTORSHIP_ADMIN_MATCH_RUN,
    MENTORSHIP_ADMIN_MATCH_RUN_RESULTS,
    MENTORSHIP_ADMIN_MATCH_RUN_UNMATCHED,
    MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK,
    MENTORSHIP_ADMIN_MATCH_RUN_DRAFT,
    MENTORSHIP_ADMIN_MATCH_RUN_PUBLISH_REQUEST,
    MENTORSHIP_ADMIN_EXEMPTION_REQUEST,
    MENTORSHIP_ADMIN_WITHDRAW_REQUEST,
    MENTORSHIP_ADMIN_MARK_REQUEST,
    MENTORSHIP_ADMIN_END_PAIR_REQUEST,
    MENTORSHIP_ADMIN_APPROVERS,
    MENTORSHIP_ADMIN_APPROVALS_MINE,
    MENTORSHIP_ADMIN_APPROVAL_REASSIGN,
    MENTORSHIP_ADMIN_APPROVAL_DECIDE,
    MENTORSHIP_ADMIN_APPROVAL_WITHDRAW,
    MENTORSHIP_ADMIN_ROUND_FEEDBACK,
    MENTORSHIP_ADMIN_ROUND_UNREGISTERED,
    MENTORSHIP_ADMIN_PARTICIPANT_DETAIL,
    MENTORSHIP_ADMIN_PARTICIPANT_NOTES,
)
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate


class MentorshipAdminController:
    def __init__(
        self,
        mentorship_admin_service,
        matching_run_service,
        matching_run_read_service,
        matching_draft_service,
        mentorship_approval_service,
        launchdarkly_service,
        database,
    ):
        self.mentorship_admin_service = mentorship_admin_service
        self.matching_run_service = matching_run_service
        self.matching_run_read_service = matching_run_read_service
        self.matching_draft_service = matching_draft_service
        self.mentorship_approval_service = mentorship_approval_service
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
            MENTORSHIP_ADMIN_MATCH_RUN_UNMATCHED,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_matching_run_unmatched
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.take_matching_edit_lock
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN_EDIT_LOCK,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.release_matching_edit_lock
            ),
            methods=["DELETE"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN_DRAFT,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.save_matching_draft
            ),
            methods=["PATCH"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MATCH_RUN_PUBLISH_REQUEST,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.request_publishing
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_EXEMPTION_REQUEST,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.request_exemption
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_WITHDRAW_REQUEST,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.request_withdrawal
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_MARK_REQUEST,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.request_mark
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_END_PAIR_REQUEST,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.request_end_pair
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_APPROVERS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.list_approvers
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_APPROVALS_MINE,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_APPROVE])(
                self.list_my_approvals
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_APPROVAL_REASSIGN,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.reassign_approval
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_APPROVAL_DECIDE,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_APPROVE])(
                self.decide_approval
            ),
            methods=["POST"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_APPROVAL_WITHDRAW,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.withdraw_approval
            ),
            methods=["POST"],
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

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PARTICIPANT_DETAIL,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_participant_detail
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PARTICIPANT_NOTES,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_WRITE])(
                self.add_participant_note
            ),
            methods=["POST"],
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

    async def get_participant_detail(self, round_id: int, user_id: int):
        """
        Retrieve the admin console's page for one person in one round.

        Args:
            round_id (int): The round.
            user_id (int): The person.

        Returns:
            API response containing the page's data. An unknown round or
            person surfaces as 404.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.get_participant_detail(
                session, round_id, user_id
            )
        return api_response(
            message="Successfully retrieved the participant.",
            data=result,
        )

    async def add_participant_note(
        self,
        round_id: int,
        user_id: int,
        body: ParticipantNoteCreateDto,
        current_user: UserContextDto,
    ):
        """
        Write a plain note on a person in a round.

        Args:
            round_id (int): The round, which must be in progress.
            user_id (int): Who the note is about.
            body (ParticipantNoteCreateDto): The note's text.
            current_user (UserContextDto): Who is writing it.

        Returns:
            API response carrying the new note. A round not in progress
            surfaces as 409; an empty or overlong note as 400; an unknown
            round or person as 404.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.add_participant_note(
                session,
                round_id=round_id,
                user_id=user_id,
                author_id=current_user.user_id,
                body=body.body,
            )
        return api_response(message="Note added.", data=result)

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

    async def get_matching_run_unmatched(
        self,
        round_id: int,
        current_user: UserContextDto,
        limit: int = 100,
        offset: int = 0,
    ):
        """
        Return one page of the people the round's run left without a partner,
        mentees then mentors.

        Args:
            round_id (int): Round whose run is wanted.
            current_user (UserContextDto): Who is asking.
            limit (int): Maximum number of people to return.
            offset (int): Pagination offset.

        Returns:
            API response carrying the total and one page of people.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        async with self.database.session() as session:
            result = await self.matching_run_read_service.read_unmatched(
                session, round_id, limit=limit, offset=offset
            )
        return api_response(
            message="Successfully retrieved the people the matching run left unmatched.",
            data=MatchingUnmatchedPageDto.model_validate(result),
        )

    async def take_matching_edit_lock(
        self, round_id: int, current_user: UserContextDto
    ):
        """
        Take the round's matching result for editing, or renew the lock held.

        Args:
            round_id (int): Round whose result is edited.
            current_user (UserContextDto): The admin editing.

        Returns:
            API response carrying who holds the lock and until when.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ConflictError: Another admin is editing. Surfaces as 409.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        async with self.database.session() as session:
            result = await self.matching_draft_service.take_lock(
                session, round_id, current_user.user_id
            )
        return api_response(
            message="Successfully took the matching result for editing.",
            data=MatchingEditLockDto.model_validate(result),
        )

    async def release_matching_edit_lock(
        self, round_id: int, current_user: UserContextDto
    ):
        """
        Give the round's matching result back, if this admin was editing it.

        Args:
            round_id (int): Round whose result was edited.
            current_user (UserContextDto): The admin leaving.

        Returns:
            API response with no data.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        self.matching_draft_service.release_lock(round_id, current_user.user_id)
        return api_response(message="Successfully released the matching result.")

    async def save_matching_draft(
        self,
        round_id: int,
        body: MatchingDraftChangesDto,
        current_user: UserContextDto,
    ):
        """
        Save an editing session's changes to the round's matching draft.

        Args:
            round_id (int): Round whose result is edited.
            body (MatchingDraftChangesDto): The mentees changed this session.
            current_user (UserContextDto): The admin holding the lock.

        Returns:
            API response carrying how many mentees the draft now changes.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ConflictError: The admin no longer holds the lock. Surfaces as 409.
        """
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

        result = self.matching_draft_service.save_changes(
            round_id, current_user.user_id, body.changes
        )
        return api_response(
            message="Successfully saved the matching draft.",
            data=MatchingDraftSavedDto.model_validate(result),
        )

    def _require_matching(self, current_user: UserContextDto) -> None:
        """Approvals in the mentorship console sit behind the same flag as
        matching: publishing, exemptions, withdrawals and marks are all part of it."""
        if not self.launchdarkly_service.is_matching_run_enabled(current_user):
            raise PermissionError("Matching runs are not yet available.")

    async def request_publishing(
        self,
        round_id: int,
        body: ApprovalRequestCreateDto,
        current_user: UserContextDto,
    ):
        """
        Ask a reviewer to approve publishing the round's matching result.

        Args:
            round_id (int): Round whose current run is to be published.
            body (ApprovalRequestCreateDto): The reviewer named and the reason.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the new request.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ConflictError: The result cannot be published now, or is already
                waiting for approval. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.request_publish(
                session,
                round_id=round_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
                reason=body.reason,
            )
        return api_response(
            message="Successfully asked for approval to publish.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def request_exemption(
        self,
        round_id: int,
        user_id: int,
        body: ApprovalRequestCreateDto,
        current_user: UserContextDto,
    ):
        """
        Ask a reviewer to exempt a person from the matching history check in
        a round.

        Args:
            round_id (int): The round, which must be in progress.
            user_id (int): The person.
            body (ApprovalRequestCreateDto): The reviewer named and the reason.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the new request.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ConflictError: The person does not need an exemption in the round,
                or one is already waiting for approval. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.request_exemption(
                session,
                round_id=round_id,
                user_id=user_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
                reason=body.reason,
            )
        return api_response(
            message="Successfully asked for approval to exempt.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def request_withdrawal(
        self,
        round_id: int,
        user_id: int,
        body: ApprovalRequestCreateDto,
        current_user: UserContextDto,
    ):
        """
        Ask a reviewer to approve withdrawing a person from a round.

        Args:
            round_id (int): The round, which must be in progress.
            user_id (int): The person.
            body (ApprovalRequestCreateDto): The reviewer named and the reason.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the new request.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ValueError: The reviewer is the person, or cannot review it.
                Surfaces as 400.
            ConflictError: The person is not still in the round, or a
                withdrawal is already waiting. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.request_withdrawal(
                session,
                round_id=round_id,
                user_id=user_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
                reason=body.reason,
            )
        return api_response(
            message="Successfully asked for approval to withdraw.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def request_mark(
        self,
        round_id: int,
        user_id: int,
        body: ParticipantMarkRequestDto,
        current_user: UserContextDto,
    ):
        """
        Ask a reviewer to approve marking a person in a round as a no show,
        or raising a red flag on them.

        Args:
            round_id (int): The round, which must be in progress.
            user_id (int): The person.
            body (ParticipantMarkRequestDto): The mark, its pair, the reviewer
                named and the reason.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the new request.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ValueError: The reviewer is the person, or cannot review it.
                Surfaces as 400.
            ConflictError: The person may not carry the mark, the pair is not
                theirs, or the same mark already waits. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.request_mark(
                session,
                round_id=round_id,
                user_id=user_id,
                tag=body.tag,
                pair_id=body.pair_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
                reason=body.reason,
            )
        return api_response(
            message="Successfully asked for approval of the mark.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def request_end_pair(
        self,
        round_id: int,
        user_id: int,
        body: EndPairRequestDto,
        current_user: UserContextDto,
    ):
        """
        Ask a reviewer to approve ending one of a person's pairs in a round.

        Args:
            round_id (int): The round, which must be in progress.
            user_id (int): Whose page it is raised from; one of the pair.
            body (EndPairRequestDto): The pair, the reviewer named and the
                reason.
            current_user (UserContextDto): Who is asking.

        Returns:
            API response carrying the new request.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
            ValueError: The reviewer is one of the pair, or cannot review it.
                Surfaces as 400.
            ConflictError: The pair is not theirs or has ended, or a request
                to end it already waits. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.request_end_pair(
                session,
                round_id=round_id,
                user_id=user_id,
                pair_id=body.pair_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
                reason=body.reason,
            )
        return api_response(
            message="Successfully asked for approval to end the pair.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def list_approvers(self, current_user: UserContextDto):
        """
        List who a mentorship approval request can be sent to.

        Args:
            current_user (UserContextDto): The would-be raiser, left out.

        Returns:
            API response carrying the reviewers.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.list_reviewers(
                session, current_user.user_id
            )
        return api_response(
            message="Successfully retrieved the approvers.",
            data=[ApprovalPersonDto.model_validate(r) for r in result],
        )

    async def list_my_approvals(self, current_user: UserContextDto):
        """
        List the mentorship requests waiting on the caller's decision.

        Args:
            current_user (UserContextDto): The reviewer.

        Returns:
            API response carrying the pending requests, oldest first.

        Raises:
            PermissionError: The flag is off for this admin. Surfaces as 403.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.list_mine(
                session, current_user.user_id
            )
        return api_response(
            message="Successfully retrieved your pending approvals.",
            data=[MentorshipApprovalDto.model_validate(r) for r in result],
        )

    async def reassign_approval(
        self,
        request_id: int,
        body: ApprovalReassignDto,
        current_user: UserContextDto,
    ):
        """
        Hand a pending mentorship request to another reviewer.

        Args:
            request_id (int): The request.
            body (ApprovalReassignDto): The new reviewer.
            current_user (UserContextDto): Must be the raiser.

        Returns:
            API response carrying the request.

        Raises:
            PermissionError: The flag is off, or the caller did not raise it.
                Surfaces as 403.
            ConflictError: It is no longer pending. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.reassign(
                session,
                request_id=request_id,
                actor_id=current_user.user_id,
                reviewer_id=body.reviewer_id,
            )
        return api_response(
            message="Successfully reassigned the request.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def decide_approval(
        self,
        request_id: int,
        body: ApprovalDecisionDto,
        current_user: UserContextDto,
    ):
        """
        Approve or reject a mentorship request.

        Args:
            request_id (int): The request.
            body (ApprovalDecisionDto): The decision, and the reason for a
                rejection.
            current_user (UserContextDto): Must be the named reviewer.

        Returns:
            API response carrying the closed request.

        Raises:
            PermissionError: The flag is off, or the caller is not the named
                reviewer. Surfaces as 403.
            ConflictError: It is no longer pending, or what it asks for can no
                longer be done. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.decide(
                session,
                request_id=request_id,
                actor_id=current_user.user_id,
                approve=body.decision == "approve",
                comment=body.comment,
            )
        return api_response(
            message="Successfully decided the request.",
            data=MentorshipApprovalDto.model_validate(result),
        )

    async def withdraw_approval(self, request_id: int, current_user: UserContextDto):
        """
        Take back a mentorship request nobody has decided yet.

        Args:
            request_id (int): The request.
            current_user (UserContextDto): Must be the raiser.

        Returns:
            API response carrying the withdrawn request.

        Raises:
            PermissionError: The flag is off, or the caller did not raise it.
                Surfaces as 403.
            ConflictError: It is no longer pending. Surfaces as 409.
        """
        self._require_matching(current_user)
        async with self.database.session() as session:
            result = await self.mentorship_approval_service.withdraw(
                session, request_id=request_id, actor_id=current_user.user_id
            )
        return api_response(
            message="Successfully withdrew the request.",
            data=MentorshipApprovalDto.model_validate(result),
        )
