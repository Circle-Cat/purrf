from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class RunningRoundWindow(NamedTuple):
    """A round whose meeting window is open, with that window's own bounds.

    ``window_start`` / ``window_end`` are the round's OWN meeting window --
    ``match_notification_at`` and ``meetings_completion_deadline_at`` -- NOT
    widened by the grace period. The grace only decides whether the round is
    still returned at all; meetings are filtered against the unwidened window,
    or a meeting scheduled after the deadline would be swept in by the very
    allowance meant to catch meetings scheduled before it.

    Both are timezone-aware.
    """

    round_id: int
    window_start: datetime
    window_end: datetime


class MentorshipRoundRepository:
    """
    Repository for handling database operations related to MentorshipRoundEntity.
    """

    async def get_all_rounds(
        self, session: AsyncSession
    ) -> list[MentorshipRoundEntity]:
        """
        Retrieve all mentorship round entities.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.

        Returns:
            list[MentorshipRoundEntity]: Every round, latest meetings deadline
                first; rounds without one come last, newest created first.
        """
        result = await session.execute(
            select(MentorshipRoundEntity).order_by(
                MentorshipRoundEntity.meetings_completion_deadline_at.desc().nulls_last(),
                MentorshipRoundEntity.created_datetime.desc(),
            )
        )

        return result.scalars().all()

    async def get_by_round_id(
        self, session: AsyncSession, round_id: int
    ) -> MentorshipRoundEntity | None:
        """
        Retrieve a mentorship round entity by its round ID.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): The ID of the mentorship round to retrieve.

        Returns:
            MentorshipRoundEntity | None: The mentorship round entity, otherwise None.
        """
        if not round_id:
            return None

        result = await session.execute(
            select(MentorshipRoundEntity).where(
                MentorshipRoundEntity.round_id == round_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_running_rounds(
        self, session: AsyncSession, grace: timedelta
    ) -> list[RunningRoundWindow]:
        """Rounds whose meeting window is open now, with their own bounds.

        Replaces ``get_running_round_id``, which returned only an id and used
        ``.first()`` with no ORDER BY -- so when two windows overlapped
        Postgres picked one arbitrarily and the other round went unsynced
        without a trace. Returning every match in a fixed order buys the
        caller a stable processing order across runs, not just a complete one.

        Args:
            session (AsyncSession): The active DB session.
            grace (timedelta): How long past ``meetings_completion_deadline_at``
                a round stays selectable, so a meeting held just before the
                deadline can still be reconciled afterwards. It widens ONLY
                the selection test -- the returned ``window_end`` is the
                un-widened deadline.

        Returns:
            list[RunningRoundWindow]: Matching rounds ordered by round_id
                ascending. Empty when no window is open.
        """
        now_utc = datetime.now(timezone.utc)
        # Equivalent to `window_end + grace >= now_utc`, computed on the
        # Python side so the column is compared against a plain aware
        # datetime rather than an interval expression.
        selection_cutoff = now_utc - grace
        window_start = MentorshipRoundEntity.match_notification_at
        window_end = MentorshipRoundEntity.meetings_completion_deadline_at
        result = await session.execute(
            select(MentorshipRoundEntity.round_id, window_start, window_end)
            .where(window_start <= now_utc, window_end >= selection_cutoff)
            .order_by(MentorshipRoundEntity.round_id.asc())
        )
        return [RunningRoundWindow(*row) for row in result.all()]

    async def get_open_registration_round(
        self, session: AsyncSession, now: datetime
    ) -> MentorshipRoundEntity | None:
        """The round open for registration at ``now``.

        A round qualifies only while it is open on BOTH ends: promotion has
        started and registration, which closes at ``onboarding_deadline_at``
        for mentors and mentees alike, has not. Of those, the one closing
        soonest wins, so while two windows overlap everyone -- the Personal
        Dashboard and the admission email alike -- is pointed at the one
        about to close.

        Returns None when no window is open. That is a normal state, not an
        error: the program is not always recruiting.

        Args:
            session (AsyncSession): The active async database session.
            now (datetime): The aware instant to evaluate at.

        Returns:
            MentorshipRoundEntity | None: The round closing soonest, or None.
        """
        deadline = MentorshipRoundEntity.onboarding_deadline_at
        result = await session.execute(
            select(MentorshipRoundEntity)
            .where(MentorshipRoundEntity.promotion_start_at <= now, deadline > now)
            .order_by(deadline.asc(), MentorshipRoundEntity.created_datetime.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_promoted_round(
        self, session: AsyncSession, now: datetime
    ) -> MentorshipRoundEntity | None:
        """The round whose promotion started most recently, as of ``now``.

        The dashboard falls back to it once no round is open for
        registration, to keep the last round viewable.

        Args:
            session (AsyncSession): The active async database session.
            now (datetime): The aware instant to evaluate at.

        Returns:
            MentorshipRoundEntity | None: That round, or None when no round
                has started promotion.
        """
        result = await session.execute(
            select(MentorshipRoundEntity)
            .where(MentorshipRoundEntity.promotion_start_at <= now)
            .order_by(
                MentorshipRoundEntity.promotion_start_at.desc(),
                MentorshipRoundEntity.created_datetime.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_round_in_feedback(self, session: AsyncSession, now: datetime) -> bool:
        """Whether any promoted round is between its meetings deadline and
        its feedback deadline, both inclusive, at ``now``.

        Args:
            session (AsyncSession): The active async database session.
            now (datetime): The aware instant to evaluate at.

        Returns:
            bool: True when at least one round is in its feedback phase.
        """
        result = await session.execute(
            select(
                exists().where(
                    MentorshipRoundEntity.promotion_start_at.isnot(None),
                    MentorshipRoundEntity.meetings_completion_deadline_at <= now,
                    MentorshipRoundEntity.feedback_deadline_at >= now,
                )
            )
        )
        return bool(result.scalar())

    async def update_mentee_average_score(
        self, session: AsyncSession, round_id: int, value: float | None
    ) -> None:
        """
        Update the mentee_average_score for a mentorship round.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): The ID of the mentorship round to update.
            value (float | None): The new average score, or None to clear it.
        """
        await session.execute(
            update(MentorshipRoundEntity)
            .where(MentorshipRoundEntity.round_id == round_id)
            .values(mentee_average_score=value)
        )
        await session.flush()

    async def update_mentor_average_score(
        self, session: AsyncSession, round_id: int, value: float | None
    ) -> None:
        """
        Update the mentor_average_score for a mentorship round.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): The ID of the mentorship round to update.
            value (float | None): The new average score, or None to clear it.
        """
        await session.execute(
            update(MentorshipRoundEntity)
            .where(MentorshipRoundEntity.round_id == round_id)
            .values(mentor_average_score=value)
        )
        await session.flush()

    async def upsert_round(
        self, session: AsyncSession, entity: MentorshipRoundEntity
    ) -> MentorshipRoundEntity:
        """
        Inserts or updates a MentorshipRoundEntity object in the database.

        This method using session.merge() handles data persistence, it will
        update the entity if the primary key exists, or inserts it otherwise

        Args:
            session (AsyncSession): The active async database session.
            entity: The MentorshipRound object containing the round data.

        Returns:
            MentorshipRound: The entity object synchronized with the database, reflecting
            the latest state, generated keys, and default values.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
