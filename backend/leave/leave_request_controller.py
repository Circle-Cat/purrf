"""FastAPI routes for filing and deciding leave requests."""

from backend.common.api_endpoints import (
    LEAVE_ME_ENDPOINT,
    LEAVE_REQUEST_DECISION_ENDPOINT,
    LEAVE_REQUEST_WITHDRAW_ENDPOINT,
    LEAVE_REQUESTS_ENDPOINT,
    LEAVE_REQUESTS_APPROVALS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.leave_coverage_dto import LeaveCoverageDto
from backend.dto.leave_request_dto import LeaveDecisionDto, LeaveRequestSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate
from fastapi import APIRouter


class LeaveRequestController:
    """Requests: filing, taking back, and deciding.

    Every route is open to any signed-in employee, and none carries a
    permission. Leave is not an administered feature -- everybody files their
    own and managers decide for their own reports -- so a permission here would
    have to be granted to every employee, which is the same as not having one.
    Who may act on which request is decided by ownership inside the service:
    only the person who filed it may take it back, and only the approver it was
    filed against may decide it.

    The acting user always comes from the token, never from the body. A user id
    in a payload would let anybody file leave against somebody else's balance.
    """

    def __init__(self, leave_request_service, database):
        """
        Args:
            leave_request_service (LeaveRequestService): Request lifecycle.
            database: Async session provider.
        """
        self.leave_request_service = leave_request_service
        self.database = database
        self.router = APIRouter(tags=["leave-requests"])

        # The signed-in account's own standing, alongside its own requests.
        # The rule behind it needs the corporate address, the nightly sync's
        # cache and the ledger, all of which this service already holds; giving
        # it a service of its own would copy four dependencies to answer one
        # boolean.
        self.router.add_api_route(
            LEAVE_ME_ENDPOINT,
            endpoint=authenticate()(self.coverage),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_REQUESTS_ENDPOINT,
            endpoint=authenticate()(self.submit),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_REQUESTS_ENDPOINT,
            endpoint=authenticate()(self.list_own),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_REQUESTS_APPROVALS_ENDPOINT,
            endpoint=authenticate()(self.list_approvals),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_REQUEST_WITHDRAW_ENDPOINT,
            endpoint=authenticate()(self.withdraw),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            LEAVE_REQUEST_DECISION_ENDPOINT,
            endpoint=authenticate()(self.decide),
            methods=["POST"],
            response_model=None,
        )

    async def coverage(self, current_user: UserContextDto):
        """Where the signed-in account stands: whether leave applies, and the
        three figures a dashboard answers "what can I spend" with."""
        async with self.database.session() as session:
            standing = await self.leave_request_service.standing(
                session, current_user.user_id
            )
        return api_response(
            message="Leave standing fetched.",
            data=LeaveCoverageDto.of(standing),
        )

    async def submit(
        self, payload: LeaveRequestSubmitDto, current_user: UserContextDto
    ):
        """File a leave or exchange request for the signed-in employee."""
        async with self.database.session() as session:
            request = await self.leave_request_service.submit(
                session,
                user_id=current_user.user_id,
                request_type=payload.type,
                start_date=payload.start_date,
                end_date=payload.end_date,
                start_time=payload.start_time,
                end_time=payload.end_time,
                reason=payload.reason,
            )
        return api_response(message="Leave request filed.", data=request)

    async def list_own(self, current_user: UserContextDto):
        """Return the signed-in employee's own requests, newest first."""
        async with self.database.session() as session:
            requests = await self.leave_request_service.list_own(
                session, current_user.user_id
            )
        return api_response(message="Leave requests fetched.", data=requests)

    async def list_approvals(self, current_user: UserContextDto):
        """Return every request ever filed against the signed-in employee.

        Decided ones included: an empty list is the only thing that says
        somebody does not approve for anybody, so the callers that decide
        whether to offer an approvals view at all read it off this.
        """
        async with self.database.session() as session:
            requests = await self.leave_request_service.list_for_approver(
                session, current_user.user_id
            )
        return api_response(message="Leave approvals fetched.", data=requests)

    async def withdraw(self, request_id: int, current_user: UserContextDto):
        """Take back one of the signed-in employee's undecided requests."""
        async with self.database.session() as session:
            request = await self.leave_request_service.withdraw(
                session, request_id, current_user.user_id
            )
        return api_response(message="Leave request withdrawn.", data=request)

    async def decide(
        self,
        request_id: int,
        payload: LeaveDecisionDto,
        current_user: UserContextDto,
    ):
        """Approve or reject a request filed against the signed-in employee."""
        async with self.database.session() as session:
            request = await self.leave_request_service.decide(
                session, request_id, current_user.user_id, approve=payload.approve
            )
        return api_response(message="Leave request decided.", data=request)
