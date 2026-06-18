"""Read-side admin service for the permission system (PR1).

Orchestrates UsersRepository and UserPermissionsRepository to back the
read-only /admin endpoints. The permission catalog is the code enum; any
caller-supplied permission name is validated against it.
"""

from backend.common.permissions import Permission
from backend.dto.admin_permission_dto import (
    AdminUserDto,
    AuditListDto,
    GrantDto,
    UserListDto,
    UserPermissionsViewDto,
)

_VALID_PERMISSION_VALUES = frozenset(str(p) for p in Permission)


class PermissionAdminService:
    def __init__(self, users_repository, user_permissions_repository):
        self._users = users_repository
        self._perms = user_permissions_repository

    def list_permission_catalog(self) -> list[str]:
        """Every permission the admin UI can grant — the code enum, sorted."""
        return sorted(_VALID_PERMISSION_VALUES)

    async def list_users(
        self, session, *, search: str | None, limit: int, offset: int
    ) -> UserListDto:
        rows, total = await self._users.list_users(
            session, search=search, limit=limit, offset=offset
        )
        return UserListDto(
            users=[
                AdminUserDto(
                    user_id=u.user_id,
                    primary_email=u.primary_email,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    is_active=u.is_active,
                    is_super_admin=u.is_super_admin,
                )
                for u in rows
            ],
            total=total,
        )

    async def get_user_permissions(
        self, session, user_id: int
    ) -> UserPermissionsViewDto:
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        grants = await self._perms.get_grants_for_user(
            session, user_id, include_revoked=True
        )
        history = [self._to_grant_dto(g) for g in grants]
        active = [g.permission_name for g in history if g.is_active]
        return UserPermissionsViewDto(user_id=user_id, active=active, history=history)

    async def list_permission_users(
        self,
        session,
        permission_name: str,
        *,
        include_revoked: bool,
        granted_source: str | None,
    ) -> list[GrantDto]:
        if permission_name not in _VALID_PERMISSION_VALUES:
            raise ValueError("Unknown permission")
        rows = await self._perms.get_users_with_permission(
            session,
            permission_name,
            include_revoked=include_revoked,
            granted_source=granted_source,
        )
        return [self._to_grant_dto(r) for r in rows]

    async def list_audit(
        self,
        session,
        *,
        user_id: int | None,
        permission_name: str | None,
        action: str | None,
        limit: int,
        offset: int,
    ) -> AuditListDto:
        rows, total = await self._perms.list_audit(
            session,
            user_id=user_id,
            permission_name=permission_name,
            action=action,
            limit=limit,
            offset=offset,
        )
        return AuditListDto(entries=[self._to_grant_dto(r) for r in rows], total=total)

    @staticmethod
    def _to_grant_dto(row) -> GrantDto:
        return GrantDto(
            id=row.id,
            user_id=row.user_id,
            permission_name=row.permission_name,
            granted_source=row.granted_source,
            granted_by=row.granted_by,
            granted_timestamp=row.granted_timestamp,
            revoked_by=row.revoked_by,
            revoked_timestamp=row.revoked_timestamp,
            is_active=row.revoked_timestamp is None,
        )
