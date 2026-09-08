"""Account console routes, mounted under /api/admin.

Every route is gated by ``Permission.USER_ADMIN`` alone -- no OR gates. The
requirement it comes from is that specific recruiters and mentorship admins can
raise a block without being able to see the console at all, which an OR with
their own permissions would give away.

The caller is resolved by AuthMiddleware; handlers read the request context and
do not re-authenticate. DTOs are passed straight to api_response --
jsonable_encoder serializes them with their camelCase aliases for the frontend.

``PermissionError`` surfaces as 403 and ``ValueError`` as 400 through the
registered exception handlers.
"""

from fastapi import APIRouter

from backend.common.api_endpoints import (
    ADMIN_ACCOUNT_BLOCK_ENDPOINT,
    ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT,
    ADMIN_ACCOUNT_REACTIVATE_ENDPOINT,
    ADMIN_ACCOUNT_SIGN_IN_METHODS_ENDPOINT,
    ADMIN_ACCOUNT_UNBLOCK_ENDPOINT,
    ADMIN_ACCOUNTS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.block_dto import BlockDirectDto, DeactivateRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

_GATE = [Permission.USER_ADMIN]


class UserAccountController:
    def __init__(self, user_account_service, block_service, database):
        """
        Args:
            user_account_service (UserAccountService): The list, the sign-in
                methods view, and the deactivate/reactivate/unblock writes.
            block_service (BlockService): The direct block.
            database (Database): Provides the async session used per request.
        """
        self._service = user_account_service
        self._blocks = block_service
        self._database = database
        self.router = APIRouter(tags=["admin-accounts"])
        self.router.add_api_route(
            ADMIN_ACCOUNTS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.list_accounts),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_ACCOUNT_SIGN_IN_METHODS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.get_sign_in_methods),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_ACCOUNT_DEACTIVATE_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.deactivate),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_ACCOUNT_REACTIVATE_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.reactivate),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_ACCOUNT_UNBLOCK_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.unblock),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_ACCOUNT_BLOCK_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.block),
            methods=["POST"],
            response_model=None,
        )

    async def list_accounts(
        self,
        current_user: UserContextDto,
        search: str | None = None,
        user_id: int | None = None,
        status: str | None = None,
        user_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        """
        Paginated account list with state, the people behind it, and whether
        the caller has a block request waiting on each row.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
                Scopes ``hasPendingBlockRequest``: a request is visible only to
                the reviewer it names.
            search (str | None): Case-insensitive substring filter over name,
                email and block reason.
            user_id (int | None): When not None, exact-match filter on user_id.
            status (str | None): ``"active"`` / ``"deactivated"`` /
                ``"blocked"``, or None for no filter. Unknown values surface as
                400 from the service.
            user_type (str | None): ``"internal"`` / ``"external"`` / None.
            limit (int): Page size.
            offset (int): Rows to skip (pagination).

        Returns:
            A standardized API response wrapping
            ``{"accounts": [...], "total": n}``.
        """
        async with self._database.session() as session:
            accounts, total = await self._service.list_accounts(
                session,
                caller_id=current_user.user_id,
                search=search,
                user_id=user_id,
                status=status,
                user_type=user_type,
                # On for this endpoint only. The retired Blacklist page could
                # search by reason, and the default stays off so the older
                # permission-page endpoint keeps its exact result set.
                search_blocked_reason=True,
                limit=limit,
                offset=offset,
            )
        return api_response(
            message="Accounts", data={"accounts": accounts, "total": total}
        )

    async def get_sign_in_methods(self, current_user: UserContextDto, user_id: int):
        """
        Every way into one account: sign-in addresses and linked identities.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response wrapping a ``UserSignInMethodsDto``.
            Unknown ``user_id`` surfaces as 400 from the service.
        """
        async with self._database.session() as session:
            view = await self._service.get_sign_in_methods(session, user_id)
        return api_response(message="Sign-in methods", data=view)

    async def deactivate(
        self,
        current_user: UserContextDto,
        user_id: int,
        deactivate_data: DeactivateRequestDto,
    ):
        """
        Turn an account off at the user's own request.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.
            deactivate_data (DeactivateRequestDto): The optional note.

        Returns:
            A standardized API response with no data. Deactivating yourself
            surfaces as 403; an unknown user as 400.
        """
        async with self._database.session() as session:
            await self._service.deactivate(
                session,
                actor_id=current_user.user_id,
                user_id=user_id,
                note=deactivate_data.note,
            )
        return api_response(message="Account deactivated.")

    async def reactivate(self, current_user: UserContextDto, user_id: int):
        """
        Turn an account back on and clear the deactivation trio.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response with no data.
        """
        async with self._database.session() as session:
            await self._service.reactivate(
                session, actor_id=current_user.user_id, user_id=user_id
            )
        return api_response(message="Account reactivated.")

    async def unblock(self, current_user: UserContextDto, user_id: int):
        """
        Lift a block. Idempotent.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response with no data.
        """
        async with self._database.session() as session:
            await self._service.unblock(
                session, actor_id=current_user.user_id, user_id=user_id
            )
        return api_response(message="Account unblocked.")

    async def block(
        self, current_user: UserContextDto, user_id: int, block_data: BlockDirectDto
    ):
        """
        Block an account without going through a request.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.
            block_data (BlockDirectDto): The required, non-blank reason.

        Returns:
            A standardized API response with no data. Blocking yourself
            surfaces as 403; an unknown user as 400.
        """
        async with self._database.session() as session:
            await self._blocks.block_directly(
                session,
                actor_id=current_user.user_id,
                user_id=user_id,
                reason=block_data.reason,
            )
        return api_response(message="Account blocked.")
