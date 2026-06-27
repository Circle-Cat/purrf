from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.user_permissions_entity import UserPermissionsEntity
from backend.entity.users_entity import UsersEntity


class UserPermissionsRepository:
    """
    Repository for user_permissions grant rows. Grants are append-only
    and soft-deleted (revoked_timestamp), so the table is also the audit log.
    """

    async def get_active_permission_names(
        self, session: AsyncSession, user_id: int
    ) -> set[str]:
        """The user's currently-active permission names (revoked rows excluded)."""
        result = await session.execute(
            select(UserPermissionsEntity.permission_name).where(
                UserPermissionsEntity.user_id == user_id,
                UserPermissionsEntity.revoked_timestamp.is_(None),
            )
        )
        return set(result.scalars().all())

    async def grant(
        self,
        session: AsyncSession,
        user_id: int,
        permission_names: Iterable[str],
        granted_source: str,
        granted_by: int | None = None,
    ) -> None:
        """Insert a grant row per permission (no dedup; revoked rows are history)."""
        for name in permission_names:
            session.add(
                UserPermissionsEntity(
                    user_id=user_id,
                    permission_name=str(name),
                    granted_source=granted_source,
                    granted_by=granted_by,
                )
            )
        await session.flush()

    async def revoke(
        self,
        session: AsyncSession,
        user_id: int,
        permission_names: Iterable[str],
        revoked_by: int | None = None,
    ) -> None:
        """Soft-delete the user's active rows for the given permissions."""
        await session.execute(
            update(UserPermissionsEntity)
            .where(
                UserPermissionsEntity.user_id == user_id,
                UserPermissionsEntity.permission_name.in_([
                    str(n) for n in permission_names
                ]),
                UserPermissionsEntity.revoked_timestamp.is_(None),
            )
            .values(revoked_by=revoked_by, revoked_timestamp=datetime.now(timezone.utc))
        )
        await session.flush()

    async def get_grants_for_user(
        self, session: AsyncSession, user_id: int, *, include_revoked: bool = True
    ) -> list[UserPermissionsEntity]:
        """
        Fetch a user's grant rows, newest first.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user whose grants to fetch.
            include_revoked (bool): When True, return the full history (active
                plus soft-deleted rows); when False, only currently-active rows.

        Returns:
            list[UserPermissionsEntity]: Matching rows ordered by
            ``granted_timestamp`` descending.
        """
        stmt = select(UserPermissionsEntity).where(
            UserPermissionsEntity.user_id == user_id
        )
        if not include_revoked:
            stmt = stmt.where(UserPermissionsEntity.revoked_timestamp.is_(None))
        stmt = stmt.order_by(UserPermissionsEntity.granted_timestamp.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_users_with_permission(
        self,
        session: AsyncSession,
        permission_name: str,
        *,
        include_revoked: bool = False,
        granted_source: str | None = None,
    ) -> list[UserPermissionsEntity]:
        """
        Reverse lookup: grant rows holding a given permission, newest first.

        Args:
            session (AsyncSession): The active async database session.
            permission_name (str): The permission to look up holders of.
            include_revoked (bool): When True, include soft-deleted rows as well
                as active ones; when False, only currently-active grants.
            granted_source (str | None): When set, restrict to rows granted from
                this source (e.g. 'admin', 'system_internal'); None means any.

        Returns:
            list[UserPermissionsEntity]: Matching rows ordered by
            ``granted_timestamp`` descending.
        """
        stmt = select(UserPermissionsEntity).where(
            UserPermissionsEntity.permission_name == str(permission_name)
        )
        if not include_revoked:
            stmt = stmt.where(UserPermissionsEntity.revoked_timestamp.is_(None))
        if granted_source is not None:
            stmt = stmt.where(UserPermissionsEntity.granted_source == granted_source)
        stmt = stmt.order_by(UserPermissionsEntity.granted_timestamp.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_active_users_with_permission(
        self, session: AsyncSession, permission_name: str
    ) -> list[UsersEntity]:
        """
        Active users who currently hold the given permission, deduped.

        Returns active users who EITHER have at least one non-revoked explicit
        grant of ``permission_name`` OR are super-admins (who implicitly hold
        every permission regardless of grant rows). A user with multiple grant
        rows appears only once.

        Args:
            session (AsyncSession): The active async database session.
            permission_name (str): The permission to find holders of.

        Returns:
            list[UsersEntity]: Distinct active holders, including super-admins.
        """
        grant_exists = (
            select(UserPermissionsEntity.user_id)
            .where(
                UserPermissionsEntity.user_id == UsersEntity.user_id,
                UserPermissionsEntity.permission_name == str(permission_name),
                UserPermissionsEntity.revoked_timestamp.is_(None),
            )
            .exists()
        )
        stmt = select(UsersEntity).where(
            UsersEntity.is_active.is_(True),
            or_(UsersEntity.is_super_admin.is_(True), grant_exists),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def list_audit(
        self,
        session: AsyncSession,
        *,
        user_id: int | None = None,
        permission_name: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserPermissionsEntity], int]:
        """
        Global audit feed over the soft-delete grant rows, newest first.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int | None): When set, restrict to one user's rows.
            permission_name (str | None): When set, restrict to one permission.
            action (str | None): ``'granted'`` keeps currently-active rows,
                ``'revoked'`` keeps soft-deleted rows, ``None`` keeps both.
            limit (int): Max rows to return on this page.
            offset (int): Rows to skip (for pagination).

        Returns:
            tuple[list[UserPermissionsEntity], int]: (page rows ordered by
            ``granted_timestamp`` descending, total rows matching the filters
            across all pages).
        """
        filters = []
        if user_id is not None:
            filters.append(UserPermissionsEntity.user_id == user_id)
        if permission_name is not None:
            filters.append(
                UserPermissionsEntity.permission_name == str(permission_name)
            )
        if action == "revoked":
            filters.append(UserPermissionsEntity.revoked_timestamp.is_not(None))
        elif action == "granted":
            filters.append(UserPermissionsEntity.revoked_timestamp.is_(None))

        total = await session.scalar(
            select(func.count()).select_from(UserPermissionsEntity).where(*filters)
        )
        stmt = (
            select(UserPermissionsEntity)
            .where(*filters)
            .order_by(UserPermissionsEntity.granted_timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        return rows, int(total or 0)

    async def revoke_by_source(
        self,
        session: AsyncSession,
        user_id: int,
        granted_source: str,
        revoked_by: int | None = None,
    ) -> None:
        """
        Soft-delete all active rows for a user from one source — used when HR
        removes an internal identity to drop the system_internal grants.
        """
        await session.execute(
            update(UserPermissionsEntity)
            .where(
                UserPermissionsEntity.user_id == user_id,
                UserPermissionsEntity.granted_source == granted_source,
                UserPermissionsEntity.revoked_timestamp.is_(None),
            )
            .values(revoked_by=revoked_by, revoked_timestamp=datetime.now(timezone.utc))
        )
        await session.flush()
