from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.user_permissions_entity import UserPermissionsEntity


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
        """Grant rows for a user, newest first (active + history unless filtered)."""
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
        """Reverse lookup: grant rows holding a given permission, newest first."""
        stmt = select(UserPermissionsEntity).where(
            UserPermissionsEntity.permission_name == str(permission_name)
        )
        if not include_revoked:
            stmt = stmt.where(UserPermissionsEntity.revoked_timestamp.is_(None))
        if granted_source is not None:
            stmt = stmt.where(UserPermissionsEntity.granted_source == granted_source)
        stmt = stmt.order_by(UserPermissionsEntity.granted_timestamp.desc())
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

        ``action='granted'`` keeps active rows, ``'revoked'`` keeps soft-deleted
        rows, ``None`` keeps all. Returns (page rows, total matching count).
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
