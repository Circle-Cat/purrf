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
_ADMIN_SOURCE = "admin"


class PermissionAdminService:
    def __init__(self, users_repository, user_permissions_repository):
        """
        Args:
            users_repository (UsersRepository): Repository for user rows
                (list/search and single lookups).
            user_permissions_repository (UserPermissionsRepository): Repository
                for grant rows (active permissions, history, reverse lookup, audit).
        """
        self._users = users_repository
        self._perms = user_permissions_repository

    def list_permission_catalog(self) -> list[str]:
        """Every permission the admin UI can grant — the code enum, sorted."""
        return sorted(_VALID_PERMISSION_VALUES)

    async def list_users(
        self, session, *, search: str | None, limit: int, offset: int
    ) -> UserListDto:
        """
        Paginated user list for the admin UI.

        Args:
            session (AsyncSession): The active async database session.
            search (str | None): Case-insensitive substring over name/email;
                None lists everyone.
            limit (int): Max users per page.
            offset (int): Users to skip (for pagination).

        Returns:
            UserListDto: The page of users plus the total match count.
        """
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
        """
        A user's active permissions plus their full grant/revoke history.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user to inspect.

        Returns:
            UserPermissionsViewDto: Active permission names and the ordered
            grant history.

        Raises:
            ValueError: If no user exists with ``user_id`` (surfaces as 400).
        """
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
        """
        Reverse lookup: the grants holding a given permission.

        Args:
            session (AsyncSession): The active async database session.
            permission_name (str): Permission to find holders of; validated
                against the code enum.
            include_revoked (bool): Include soft-deleted grants when True.
            granted_source (str | None): Restrict to one source, or None for any.

        Returns:
            list[GrantDto]: Matching grant rows, newest first.

        Raises:
            ValueError: If ``permission_name`` is not a known permission
                (surfaces as 400).
        """
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
        """
        Global permission-change audit feed.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int | None): Restrict to one user, or None for all.
            permission_name (str | None): Restrict to one permission, or None.
            action (str | None): 'granted' / 'revoked' / None (see repository).
            limit (int): Max entries per page.
            offset (int): Entries to skip (for pagination).

        Returns:
            AuditListDto: The page of audit entries plus the total match count.
        """
        rows, total = await self._perms.list_audit(
            session,
            user_id=user_id,
            permission_name=permission_name,
            action=action,
            limit=limit,
            offset=offset,
        )
        return AuditListDto(entries=[self._to_grant_dto(r) for r in rows], total=total)

    def _validate_names(self, permission_names: list[str]) -> list[str]:
        """
        Validate a batch of permission names against the code enum.

        Args:
            permission_names (list[str]): Requested permission names.

        Returns:
            list[str]: The same names, de-duplicated, order-preserved.

        Raises:
            ValueError: If the list is empty or contains an unknown name
                (surfaces as 400).
        """
        if not permission_names:
            raise ValueError("No permissions provided")
        seen = []
        for name in permission_names:
            if name not in _VALID_PERMISSION_VALUES:
                raise ValueError(f"Unknown permission: {name}")
            if name not in seen:
                seen.append(name)
        return seen

    async def grant_permissions(
        self, session, user_id: int, permission_names: list[str], *, granted_by: int
    ) -> UserPermissionsViewDto:
        """
        Grant a batch of permissions to a user (admin source), skipping any the
        user already holds. Idempotent: re-granting an active permission is a no-op.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The target user.
            permission_names (list[str]): Permissions to grant; each validated
                against the code enum.
            granted_by (int): The acting admin's user id (audit attribution).

        Returns:
            UserPermissionsViewDto: The user's refreshed active list and history.

        Raises:
            ValueError: Empty/unknown permission names, or unknown user (400).
        """
        names = self._validate_names(permission_names)
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        active = await self._perms.get_active_permission_names(session, user_id)
        to_grant = [n for n in names if n not in active]
        if to_grant:
            await self._perms.grant(
                session,
                user_id,
                to_grant,
                granted_source=_ADMIN_SOURCE,
                granted_by=granted_by,
            )
        return await self.get_user_permissions(session, user_id)

    async def revoke_permissions(
        self, session, user_id: int, permission_names: list[str], *, revoked_by: int
    ) -> UserPermissionsViewDto:
        """
        Soft-delete a batch of a user's active permission grants. Revoking a
        permission the user does not hold is a safe no-op.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The target user.
            permission_names (list[str]): Permissions to revoke; each validated
                against the code enum.
            revoked_by (int): The acting admin's user id (audit attribution).

        Returns:
            UserPermissionsViewDto: The user's refreshed active list and history.

        Raises:
            ValueError: Empty/unknown permission names, or unknown user (400).
        """
        names = self._validate_names(permission_names)
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        await self._perms.revoke(session, user_id, names, revoked_by=revoked_by)
        return await self.get_user_permissions(session, user_id)

    @staticmethod
    def _to_grant_dto(row) -> GrantDto:
        """
        Map a UserPermissionsEntity row to a GrantDto, deriving ``is_active``
        from whether the row has been revoked.

        Args:
            row (UserPermissionsEntity): The grant row to map.

        Returns:
            GrantDto: The serializable view of the grant.
        """
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
