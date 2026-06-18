"""Admin permission routes (read-only, PR1), mounted under /api/admin.

All routes are gated by Permission.PERMISSION_MANAGE. The caller is resolved by
AuthMiddleware; handlers read the request context and do not re-authenticate.
DTOs are passed straight to api_response — jsonable_encoder serializes them with
their camelCase aliases for the frontend.
"""

from fastapi import APIRouter

from backend.common.api_endpoints import (
    ADMIN_AUDIT_PERMISSION_CHANGES_ENDPOINT,
    ADMIN_PERMISSION_USERS_ENDPOINT,
    ADMIN_PERMISSIONS_ENDPOINT,
    ADMIN_USER_PERMISSIONS_ENDPOINT,
    ADMIN_USERS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

_GATE = [Permission.PERMISSION_MANAGE]


class PermissionAdminController:
    def __init__(self, permission_admin_service, database):
        """
        Args:
            permission_admin_service (PermissionAdminService): Read-side logic.
            database (Database): Provides the async session used per request.
        """
        self._service = permission_admin_service
        self._database = database
        self.router = APIRouter(tags=["admin-permissions"])
        self.router.add_api_route(
            ADMIN_PERMISSIONS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.list_permissions),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_USERS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.list_users),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_USER_PERMISSIONS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.get_user_permissions),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_PERMISSION_USERS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.list_permission_users),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_AUDIT_PERMISSION_CHANGES_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.list_audit),
            methods=["GET"],
            response_model=None,
        )

    async def list_permissions(self, current_user: UserContextDto):
        """Return the grantable permission catalog (the code enum)."""
        return api_response(
            message="Permission catalog",
            data={"permissions": self._service.list_permission_catalog()},
        )

    async def list_users(
        self,
        current_user: UserContextDto,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        """Paginated user list with optional email/name search."""
        async with self._database.session() as session:
            view = await self._service.list_users(
                session, search=search, limit=limit, offset=offset
            )
        return api_response(message="Users", data=view)

    async def get_user_permissions(
        self, current_user: UserContextDto, user_id: int
    ):
        """A user's active permissions plus full grant/revoke history."""
        async with self._database.session() as session:
            view = await self._service.get_user_permissions(session, user_id)
        return api_response(message="User permissions", data=view)

    async def list_permission_users(
        self,
        current_user: UserContextDto,
        permission_name: str,
        include_revoked: bool = False,
        granted_source: str | None = None,
    ):
        """Reverse lookup: who holds a given permission."""
        async with self._database.session() as session:
            grants = await self._service.list_permission_users(
                session,
                permission_name,
                include_revoked=include_revoked,
                granted_source=granted_source,
            )
        return api_response(message="Users with permission", data={"grants": grants})

    async def list_audit(
        self,
        current_user: UserContextDto,
        user_id: int | None = None,
        permission_name: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """Global permission-change audit feed (the soft-delete grant rows)."""
        async with self._database.session() as session:
            view = await self._service.list_audit(
                session,
                user_id=user_id,
                permission_name=permission_name,
                action=action,
                limit=limit,
                offset=offset,
            )
        return api_response(message="Permission change audit", data=view)
