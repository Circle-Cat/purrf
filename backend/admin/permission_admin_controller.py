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
    ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT,
    ADMIN_USER_PERMISSIONS_ENDPOINT,
    ADMIN_USER_REVOKE_PERMISSIONS_ENDPOINT,
    ADMIN_USER_SUPER_ADMIN_ENDPOINT,
    ADMIN_USERS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.admin_permission_dto import PermissionNamesRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

_GATE = [Permission.PERMISSION_MANAGE]
_SUPER_ADMIN_REVOKE_GATE = [Permission.SUPER_ADMIN_REVOKE]


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
        self.router.add_api_route(
            ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.grant_permissions),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_USER_REVOKE_PERMISSIONS_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.revoke_permissions),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_USER_SUPER_ADMIN_ENDPOINT,
            endpoint=authenticate(permissions=_GATE)(self.set_super_admin),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            ADMIN_USER_SUPER_ADMIN_ENDPOINT,
            endpoint=authenticate(permissions=_SUPER_ADMIN_REVOKE_GATE)(
                self.revoke_super_admin
            ),
            methods=["DELETE"],
            response_model=None,
        )

    async def list_permissions(self, current_user: UserContextDto):
        """
        Return the grantable permission catalog (the code enum).

        Args:
            current_user (UserContextDto): The authenticated caller (injected).

        Returns:
            A standardized API response wrapping ``{"permissions": [...]}``.
        """
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
        sort_by: str | None = None,
        order: str = "asc",
        is_super_admin: bool | None = None,
        user_type: str | None = None,
    ):
        """
        Paginated user list with optional email/name search, sorting, and
        filtering.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            search (str | None): Case-insensitive name/email substring filter.
            limit (int): Page size.
            offset (int): Rows to skip (pagination).
            sort_by (str | None): Column to sort by (whitelisted in the repo).
                Unknown values fall back to deterministic ``user_id`` order.
            order (str): ``"asc"`` or ``"desc"`` (default ``"asc"``).
            is_super_admin (bool | None): When not None, restricts to matching
                super-admin flag.
            user_type (str | None): ``"internal"`` / ``"external"`` / None.

        Returns:
            A standardized API response wrapping a ``UserListDto``.
        """
        async with self._database.session() as session:
            view = await self._service.list_users(
                session,
                search=search,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                order=order,
                is_super_admin=is_super_admin,
                user_type=user_type,
            )
        return api_response(message="Users", data=view)

    async def get_user_permissions(self, current_user: UserContextDto, user_id: int):
        """
        A user's active permissions plus full grant/revoke history.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response wrapping a ``UserPermissionsViewDto``.
            Unknown ``user_id`` surfaces as 400 from the service.
        """
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
        """
        Reverse lookup: who holds a given permission.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            permission_name (str): Permission to find holders of, from the path.
            include_revoked (bool): Include soft-deleted grants when True.
            granted_source (str | None): Restrict to one grant source, or any.

        Returns:
            A standardized API response wrapping ``{"grants": [GrantDto, ...]}``.
            Unknown ``permission_name`` surfaces as 400 from the service.
        """
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
        """
        Global permission-change audit feed (the soft-delete grant rows).

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int | None): Restrict to one user, or None for all.
            permission_name (str | None): Restrict to one permission, or None.
            action (str | None): 'granted' / 'revoked' / None.
            limit (int): Page size.
            offset (int): Rows to skip (pagination).

        Returns:
            A standardized API response wrapping an ``AuditListDto``.
        """
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

    async def grant_permissions(
        self,
        current_user: UserContextDto,
        user_id: int,
        payload: PermissionNamesRequestDto,
    ):
        """
        Grant a batch of permissions to a user.

        Args:
            current_user (UserContextDto): The authenticated admin (injected).
            user_id (int): Target user, from the path.
            payload (PermissionNamesRequestDto): Permission names to grant.

        Returns:
            A standardized API response wrapping the refreshed
            ``UserPermissionsViewDto``. Unknown names/user surface as 400.
        """
        async with self._database.session() as session:
            view = await self._service.grant_permissions(
                session,
                user_id,
                payload.permission_names,
                granted_by=current_user.user_id,
            )
        return api_response(message="Permissions granted", data=view)

    async def revoke_permissions(
        self,
        current_user: UserContextDto,
        user_id: int,
        payload: PermissionNamesRequestDto,
    ):
        """
        Revoke a batch of a user's permissions.

        Args:
            current_user (UserContextDto): The authenticated admin (injected).
            user_id (int): Target user, from the path.
            payload (PermissionNamesRequestDto): Permission names to revoke.

        Returns:
            A standardized API response wrapping the refreshed
            ``UserPermissionsViewDto``. Unknown names/user surface as 400.
        """
        async with self._database.session() as session:
            view = await self._service.revoke_permissions(
                session,
                user_id,
                payload.permission_names,
                revoked_by=current_user.user_id,
            )
        return api_response(message="Permissions revoked", data=view)

    async def set_super_admin(self, current_user: UserContextDto, user_id: int):
        """
        Promote a user to super-admin. Only an existing super-admin may call this.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response wrapping the refreshed ``AdminUserDto``.

        Raises:
            PermissionError: If the caller is not a super-admin (403).
        """
        if not current_user.is_super_admin:
            raise PermissionError("Only a super-admin can grant super-admin")
        async with self._database.session() as session:
            view = await self._service.set_super_admin(
                session, user_id, granted_by=current_user.user_id
            )
        return api_response(message="Super-admin granted", data=view)

    async def revoke_super_admin(self, current_user: UserContextDto, user_id: int):
        """
        Demote a super-admin. Gated by SUPER_ADMIN_REVOKE; cannot self-revoke.

        Args:
            current_user (UserContextDto): The authenticated caller (injected).
            user_id (int): Target user, from the path.

        Returns:
            A standardized API response wrapping the refreshed ``AdminUserDto``.
            Self-revoke surfaces as 400.
        """
        async with self._database.session() as session:
            view = await self._service.revoke_super_admin(
                session,
                user_id,
                caller_user_id=current_user.user_id,
                revoked_by=current_user.user_id,
            )
        return api_response(message="Super-admin revoked", data=view)
