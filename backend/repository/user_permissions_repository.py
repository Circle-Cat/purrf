from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy import select, update
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
