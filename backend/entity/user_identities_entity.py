from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class UserIdentitiesEntity(Base):
    __tablename__ = "user_identities"

    identity_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))

    subject_identifier: Mapped[str] = mapped_column(String(255), unique=True)

    email_claim: Mapped[str | None] = mapped_column(String(255))

    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("user_identities_user_id_idx", "user_id"),
        Index("user_identities_email_claim_idx", "email_claim"),
    )
