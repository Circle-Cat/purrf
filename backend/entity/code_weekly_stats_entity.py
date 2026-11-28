from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class CodeWeeklyStatsEntity(Base):
    """One person's code activity in one repository for one week.

    Gerrit and GitHub share this table. Each keeps its own identifier in
    ``account``: the ldap for Gerrit, the numeric GitHub user id (as text) for
    GitHub. Nothing here names a Purrf user; the ``code_weekly_stats_by_ldap``
    view works out the ldap at query time, because which person a GitHub
    account belongs to changes when someone fills in or corrects their profile.

    Gerrit rows are a one-off archive and are never rewritten. GitHub rows for
    recent weeks are recomputed and overwritten by the daily sync.

    ``week_start`` is the Monday of the week (UTC), the same weeks Gerrit's
    Redis buckets used.
    """

    __tablename__ = "code_weekly_stats"

    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    account: Mapped[str] = mapped_column(String(255), primary_key=True)
    repo: Mapped[str] = mapped_column(String(255), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)

    merged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    loc_merged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviewed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    closed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("source IN ('gerrit', 'github')", name="source_check"),
        CheckConstraint(
            "EXTRACT(ISODOW FROM week_start) = 1",
            name="week_start_is_monday",
        ),
        # Every read is a date range across all accounts.
        Index("code_weekly_stats_week_start_idx", "week_start"),
    )
