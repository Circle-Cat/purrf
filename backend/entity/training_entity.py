from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, TIMESTAMP, ForeignKey
from backend.common.mentorship_enums import TrainingStatus, TrainingCategory
from backend.common.base import Base


class TrainingEntity(Base):
    __tablename__ = "training"

    training_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    category: Mapped[TrainingCategory] = mapped_column(
        Enum(TrainingCategory, native_enum=False),
        nullable=False,
    )

    completed_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
    )

    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, native_enum=False),
        nullable=False,
    )

    deadline: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=True,
    )

    link: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )
