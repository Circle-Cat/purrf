"""Block-request routes: raise, reassign, decide, and the pre-flight.

Not mounted under /admin, unlike the account console. The person raising a
request is standing on the domain page that holds the evidence and holds no
console permission at all -- the gates here say so: raising is bound to the
recruiting advance permission, deciding to ``USER_ADMIN``, and the two do not
overlap.

Two of these routes carry a second condition that is **identity, not
permission**: only the raiser may reassign, and only the named reviewer may
decide. A gate can only read permissions, so those live in the service and
surface here as ``PermissionError`` -> 403.
"""

from fastapi import APIRouter

from backend.common.api_endpoints import (
    BLOCK_REQUEST_REVIEWERS_ENDPOINT,
    BLOCK_PREFLIGHT_ENDPOINT,
    BLOCK_REQUEST_DECIDE_ENDPOINT,
    BLOCK_REQUEST_REASSIGN_ENDPOINT,
    BLOCK_REQUESTS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.block_dto import (
    BlockDecideDto,
    BlockReassignDto,
    BlockRequestCreateDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

# Raising is bound to standing on a domain page, never to the console
# permission: the evidence lives there, and someone who can already block
# directly has no use for a request.
#
# Deliberately NOT RECRUITING_INTERVIEW_EVALUATE. That permission only marks
# someone eligible to be assigned as an evaluator -- the row-level assignee
# check is what says they are actually on a given application -- so gating on
# it would let anyone in the interviewer pool raise a request about anyone.
_RAISE_GATE = [Permission.RECRUITING_APPLICATION_ADVANCE]
_DECIDE_GATE = [Permission.USER_ADMIN]
# The one OR gate in this design, and it earns it: both roles genuinely need
# the pre-flight before acting, and it is read-only and answers in counts and
# dates -- never in which job anyone applied to.
_PREFLIGHT_GATE = _DECIDE_GATE + _RAISE_GATE


class BlockController:
    def __init__(self, block_service, database):
        """
        Args:
            block_service (BlockService): The request flow and the pre-flight.
            database (Database): Provides the async session used per request.
        """
        self._service = block_service
        self._database = database
        self.router = APIRouter(tags=["blocks"])
        self.router.add_api_route(
            BLOCK_PREFLIGHT_ENDPOINT,
            endpoint=authenticate(permissions=_PREFLIGHT_GATE)(self.preflight),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            BLOCK_REQUESTS_ENDPOINT,
            endpoint=authenticate(permissions=_RAISE_GATE)(self.raise_request),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            BLOCK_REQUESTS_ENDPOINT,
            endpoint=authenticate(permissions=_DECIDE_GATE)(self.list_pending),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            BLOCK_REQUEST_REASSIGN_ENDPOINT,
            endpoint=authenticate(permissions=_RAISE_GATE)(self.reassign),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            BLOCK_REQUEST_DECIDE_ENDPOINT,
            endpoint=authenticate(permissions=_DECIDE_GATE)(self.decide),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            BLOCK_REQUEST_REVIEWERS_ENDPOINT,
            endpoint=authenticate(permissions=_RAISE_GATE)(self.list_user_admins),
            methods=["GET"],
            response_model=None,
        )

    async def preflight(self, current_user: UserContextDto, user_id: int):
        """
        What blocking this person is about to do, so it is never a surprise.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): The person about to be blocked, from the path.

        Returns:
            A standardized API response wrapping a ``BlockPreflightDto``.
        """
        async with self._database.session() as session:
            view = await self._service.preflight(session, user_id)
        return api_response(message="Block pre-flight", data=view)

    async def raise_request(
        self,
        current_user: UserContextDto,
        request_data: BlockRequestCreateDto,
        raised_from: str,
    ):
        """
        Ask a named reviewer to block someone.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            request_data (BlockRequestCreateDto): Target, reason, reviewer.
            raised_from (str): Which domain page this came from, e.g.
                ``"recruiting_board"``. A query parameter rather than a body
                field because it describes where the caller is standing, not
                what they are asking for -- and BaseRequestDto forbids extras.

        Returns:
            A standardized API response wrapping the new ``BlockRequestDto``.
            An already-pending request, an ineligible reviewer or an unknown
            target all surface as 400.
        """
        async with self._database.session() as session:
            view = await self._service.raise_request(
                session,
                actor_id=current_user.user_id,
                user_id=request_data.user_id,
                reason=request_data.reason,
                reviewer_id=request_data.reviewer_id,
                raised_from=raised_from,
            )
        return api_response(message="Block request raised.", data=view)

    async def list_pending(self, current_user: UserContextDto):
        """
        The requests waiting on this caller's decision.

        Scoped to the caller, not filtered by one: a request is addressed to
        the one reviewer it names, and nobody else may learn it exists.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).

        Returns:
            A standardized API response wrapping a list of ``BlockRequestDto``.
        """
        async with self._database.session() as session:
            view = await self._service.list_pending_for_reviewer(
                session, current_user.user_id
            )
        return api_response(message="Pending block requests", data=view)

    async def reassign(
        self,
        current_user: UserContextDto,
        request_id: int,
        reassign_data: BlockReassignDto,
    ):
        """
        Hand a pending request to a different reviewer.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
                Must be the request's raiser, checked in the service.
            request_id (int): The request to move, from the path.
            reassign_data (BlockReassignDto): The new reviewer.

        Returns:
            A standardized API response wrapping the updated
            ``BlockRequestDto``. A caller who did not raise it gets 403.
        """
        async with self._database.session() as session:
            view = await self._service.reassign(
                session,
                actor_id=current_user.user_id,
                request_id=request_id,
                reviewer_id=reassign_data.reviewer_id,
            )
        return api_response(message="Block request reassigned.", data=view)

    async def decide(
        self,
        current_user: UserContextDto,
        request_id: int,
        decide_data: BlockDecideDto,
    ):
        """
        Approve or reject a pending request.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
                Must be the named reviewer, checked in the service.
            request_id (int): The request to decide, from the path.
            decide_data (BlockDecideDto): The verdict and an optional note.

        Returns:
            A standardized API response wrapping the closed
            ``BlockRequestDto``. A caller who is not the named reviewer gets
            403; an already-decided request gets 400.
        """
        async with self._database.session() as session:
            view = await self._service.decide(
                session,
                actor_id=current_user.user_id,
                request_id=request_id,
                approved=decide_data.approved,
                note=decide_data.note,
            )
        return api_response(message="Block request decided.", data=view)

    async def list_user_admins(self, current_user: UserContextDto):
        """
        Who can be named as reviewer on a request.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).

        Returns:
            A standardized API response wrapping a list of
            ``ReviewerOptionDto``.
        """
        async with self._database.session() as session:
            view = await self._service.list_user_admins(session)
        return api_response(message="User admins", data=view)
