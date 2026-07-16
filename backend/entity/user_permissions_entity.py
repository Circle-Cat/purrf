from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class UserPermissionsEntity(Base):
    """
    One row per granted permission. A row is soft-deleted by setting
    revoked_timestamp, so the table doubles as the audit log; granted_source
    distinguishes admin grants, lifecycle auto-injection, and migration seeds.
    permission_name holds a Permission enum value (validated in the app layer,
    not the DB).
    """

    __tablename__ = "user_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))

    permission_name: Mapped[str] = mapped_column(String(64))

    # 'admin' | 'system_internal' | 'migration'
    granted_source: Mapped[str] = mapped_column(String(32))

    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))

    granted_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))

    # NULL = currently active
    revoked_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("user_permissions_user_id_idx", "user_id"),
        Index("user_permissions_permission_name_idx", "permission_name"),
        # Hot path: active permissions for a user.
        Index(
            "user_permissions_active_idx",
            "user_id",
            postgresql_where=text("revoked_timestamp IS NULL"),
        ),
    )
