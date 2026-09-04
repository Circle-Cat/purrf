"""Read-side admin service for the permission system.

Orchestrates UsersRepository and UserPermissionsRepository to back the
read-only /admin endpoints. The permission catalog is the code enum; any
caller-supplied permission name is validated against it.
"""

from backend.common.identity_type import IdentityType
from backend.common.permission_descriptions import PERMISSION_DESCRIPTIONS
from backend.common.permissions import Permission
from backend.dto.admin_permission_dto import (
    AdminUserDto,
    AuditListDto,
    GrantDto,
    GrantPersonDto,
    PermissionCatalogEntryDto,
    UserListDto,
    UserPermissionsViewDto,
)

_VALID_PERMISSION_VALUES = frozenset(str(p) for p in Permission)
_ADMIN_SOURCE = "admin"
_SUPER_ADMIN_SOURCE = "super_admin_set"
_SUPER_ADMIN_MARKER = "*"
# granted_source value stamped on synthesized rows for a super admin who holds a
# permission purely by derivation (no real grant row). Distinct from the
# audit-marker source above.


class PermissionAdminService:
    def __init__(
        self, users_repository, user_permissions_repository, user_emails_repository
    ):
        """
        Args:
            users_repository (UsersRepository): Repository for user rows
                (list/search and single lookups).
            user_permissions_repository (UserPermissionsRepository): Repository
                for grant rows (active permissions, history, reverse lookup, audit).
            user_emails_repository (UserEmailsRepository): Contact-email
                resolution for the admin user views.
        """
        self._users = users_repository
        self._perms = user_permissions_repository
        self._user_emails = user_emails_repository

    def list_permission_catalog(self) -> list[PermissionCatalogEntryDto]:
        """Every permission the admin UI can grant, with its description."""
        return [
            PermissionCatalogEntryDto(
                name=name, description=PERMISSION_DESCRIPTIONS[Permission(name)]
            )
            for name in sorted(_VALID_PERMISSION_VALUES)
        ]

    async def list_users(
        self,
        session,
        *,
        search: str | None,
        user_id: int | None = None,
        limit: int,
        offset: int,
        sort_by: str | None = None,
        order: str = "asc",
        is_super_admin: bool | None = None,
        user_type: str | None = None,
        permission_name: str | None = None,
    ) -> UserListDto:
        """
        Paginated user list for the admin UI.

        Args:
            session (AsyncSession): The active async database session.
            search (str | None): Case-insensitive substring over name/email;
                None lists everyone.
            user_id (int | None): When not None, restricts results to the user
                with this exact ``user_id``.
            limit (int): Max users per page.
            offset (int): Users to skip (for pagination).
            sort_by (str | None): Column to sort by (whitelisted in the repo).
                Unknown values fall back to deterministic ``user_id`` order.
            order (str): ``"asc"`` or ``"desc"`` (default ``"asc"``).
            is_super_admin (bool | None): When not None, restricts to matching
                super-admin flag.
            user_type (str | None): ``"internal"`` / ``"external"`` / None.
            permission_name (str | None): When set, keeps only holders of that
                permission -- an unrevoked grant row, or super-admin status,
                which confers every permission without a grant row. This
                replaces the separate holders view: a permission is a filter on
                the population, not a second projection of it.

        Returns:
            UserListDto: The page of users plus the total match count.

        Raises:
            ValueError: If ``permission_name`` is not a known permission
                (surfaces as 400).
        """
        if (
            permission_name is not None
            and permission_name not in _VALID_PERMISSION_VALUES
        ):
            raise ValueError("Unknown permission")
        rows, total = await self._users.list_users(
            session,
            search=search,
            user_id=user_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
            is_super_admin=is_super_admin,
            user_type=user_type,
            permission_name=permission_name,
        )
        contact_by_user_id = await self._user_emails.get_contact_emails_by_user_ids(
            session, [u.user_id for u, _ in rows]
        )
        return UserListDto(
            users=[
                self._to_admin_user_dto(
                    u,
                    IdentityType.INTERNAL if is_internal else IdentityType.EXTERNAL,
                    contact_by_user_id.get(u.user_id, ""),
                )
                for u, is_internal in rows
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
        await self._resolve_grant_people(session, history)
        active = [g.permission_name for g in history if g.is_active]
        return UserPermissionsViewDto(user_id=user_id, active=active, history=history)

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
        entries = [self._to_grant_dto(r) for r in rows]
        await self._resolve_grant_people(session, entries)
        return AuditListDto(entries=entries, total=total)

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
        view = await self.get_user_permissions(session, user_id)
        await session.commit()
        return view

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
        view = await self.get_user_permissions(session, user_id)
        await session.commit()
        return view

    async def set_super_admin(
        self, session, user_id: int, *, granted_by: int
    ) -> AdminUserDto:
        """
        Promote a user to super-admin and record the audit marker row
        (``granted_source='super_admin_set', permission_name='*'``). Caller
        authorization (must itself be super-admin) is enforced in the controller.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user to promote.
            granted_by (int): The acting super-admin's user id.

        Returns:
            AdminUserDto: The refreshed user row (is_super_admin True).

        Raises:
            ValueError: If no user has ``user_id`` (400).
        """
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        await self._users.set_super_admin(session, user_id, True)
        await self._perms.grant(
            session,
            user_id,
            [_SUPER_ADMIN_MARKER],
            granted_source=_SUPER_ADMIN_SOURCE,
            granted_by=granted_by,
        )
        user.is_super_admin = True
        internal = await self._users.is_internal(session, user_id)
        contact_email = await self._user_emails.get_contact_email(session, user_id)
        dto = self._to_admin_user_dto(
            user,
            IdentityType.INTERNAL if internal else IdentityType.EXTERNAL,
            contact_email or "",
        )
        await session.commit()
        return dto

    async def revoke_super_admin(
        self, session, user_id: int, *, caller_user_id: int, revoked_by: int
    ) -> AdminUserDto:
        """
        Demote a super-admin and soft-delete the audit marker row. A caller may
        not revoke their own super-admin status.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user to demote.
            caller_user_id (int): The acting user's id (self-revoke guard).
            revoked_by (int): The acting user's id (audit attribution).

        Returns:
            AdminUserDto: The refreshed user row (is_super_admin False).

        Raises:
            ValueError: On self-revoke or unknown user (400).
        """
        if user_id == caller_user_id:
            raise ValueError("Cannot revoke your own super-admin status")
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        await self._users.set_super_admin(session, user_id, False)
        await self._perms.revoke_by_source(
            session, user_id, _SUPER_ADMIN_SOURCE, revoked_by=revoked_by
        )
        user.is_super_admin = False
        internal = await self._users.is_internal(session, user_id)
        contact_email = await self._user_emails.get_contact_email(session, user_id)
        dto = self._to_admin_user_dto(
            user,
            IdentityType.INTERNAL if internal else IdentityType.EXTERNAL,
            contact_email or "",
        )
        await session.commit()
        return dto

    @staticmethod
    def _to_admin_user_dto(user, user_type: str, primary_email: str) -> AdminUserDto:
        """
        Map a UsersEntity to an AdminUserDto.

        Args:
            user (UsersEntity): The user row.
            user_type (str): The user type ("internal" or "external").
            primary_email (str): The user's contact address from user_emails;
                empty when they have none.

        Returns:
            AdminUserDto: The serializable view.
        """
        return AdminUserDto(
            user_id=user.user_id,
            primary_email=primary_email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_super_admin=user.is_super_admin,
            preferred_name=user.preferred_name,
            user_type=user_type,
        )

    async def _resolve_grant_people(self, session, grants: list[GrantDto]) -> None:
        """
        Fill in the people behind every user id on a page of grants, in place.

        A grant row carries three ids -- the holder, whoever granted it and
        whoever revoked it -- and the views built on it rendered all of them as
        bare integers, so reading one row meant leaving the tab. Every distinct
        id on the page is resolved in **one** users lookup; doing it per row
        would be a query per id.

        An id with no users row leaves its field None rather than raising: a
        grant can outlive the account it names, and a super-admin-derived row
        seeded without a marker has no actor at all.

        Args:
            session (AsyncSession): The active async database session.
            grants (list[GrantDto]): The page to annotate. Mutated in place.
        """
        if not grants:
            return

        ids = set()
        for grant in grants:
            ids.update(
                i
                for i in (grant.user_id, grant.granted_by, grant.revoked_by)
                if i is not None
            )
        if not ids:
            return

        users = await self._users.get_all_by_ids(session, sorted(ids))
        person_by_id = {
            u.user_id: GrantPersonDto(
                user_id=u.user_id,
                first_name=u.first_name,
                last_name=u.last_name,
                preferred_name=u.preferred_name,
            )
            for u in users
        }

        for grant in grants:
            grant.user = person_by_id.get(grant.user_id)
            if grant.granted_by is not None:
                grant.granted_by_user = person_by_id.get(grant.granted_by)
            if grant.revoked_by is not None:
                grant.revoked_by_user = person_by_id.get(grant.revoked_by)

    @staticmethod
    def _to_grant_dto(row, *, is_super_admin: bool = False) -> GrantDto:
        """
        Map a UserPermissionsEntity row to a GrantDto, deriving ``is_active``
        from whether the row has been revoked.

        Args:
            row (UserPermissionsEntity): The grant row to map.
            is_super_admin (bool): Whether the holder is currently a super admin
                (annotates a real grant row that the user also derives via
                super-admin status). Defaults to False.

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
            is_super_admin=is_super_admin,
        )
