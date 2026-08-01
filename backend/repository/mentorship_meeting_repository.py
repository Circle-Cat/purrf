from sqlalchemy import delete, func, nullslast, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MeetingSource
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity

# Shared ordering for both batch-agnostic reads below: start_datetime ascending
# (NULLs -- i.e. LEGACY rows -- last, since Postgres defaults NULLs to sort
# first on ASC), then created_datetime ascending to break ties between
# meetings sharing a start, then meeting_id as a final deterministic
# tiebreaker. created_datetime has no uniqueness guarantee either (it can
# collide within the same transaction), so meeting_id -- the primary key --
# is what actually makes the order deterministic.
_MEETING_ORDER_BY = (
    nullslast(MentorshipMeetingEntity.start_datetime.asc()),
    MentorshipMeetingEntity.created_datetime.asc(),
    MentorshipMeetingEntity.meeting_id.asc(),
)


class MentorshipMeetingRepository:
    """Data access for individual mentorship meeting rows.

    Caution for a future writer: ``late_user_ids`` (ARRAY(Integer)) and
    ``entry_points`` (JSONB) on MentorshipMeetingEntity are plain, unwrapped
    SQLAlchemy columns -- not ``MutableList``/``MutableDict``. Mutating a
    fetched instance in place (``meeting.late_user_ids.append(x)``, or item
    assignment into ``entry_points``) will NOT be detected by the unit of
    work and will silently fail to persist; a caller must assign a brand-new
    list/dict to the attribute instead (or call
    ``sqlalchemy.orm.attributes.flag_modified``). This codebase already has
    scar tissue from exactly this bug -- see
    ``backend/mentorship/meet_attendance_service.py``, which needs
    ``flag_modified(pair, "meeting_log")`` for the same reason on the old
    JSONB column these rows replace.
    """

    async def get_meetings_by_pair(
        self,
        session: AsyncSession,
        pair_id: int,
        include_legacy: bool = False,
    ) -> list[MentorshipMeetingEntity]:
        """Every meeting for one pair, oldest first.

        Args:
            session (AsyncSession): The active DB session.
            pair_id (int): The pair to fetch meetings for.
            include_legacy (bool): LEGACY rows carry no times, so they have
                nothing to show in a meeting list and are excluded by default.
                Pass True when the LEGACY rows themselves are wanted (e.g. to
                recompute a count), not just what can be displayed.

        Returns:
            list[MentorshipMeetingEntity]: Rows for the pair ordered by
                ``start_datetime`` ascending (NULLs -- LEGACY rows, when
                included -- last), then ``created_datetime`` ascending, then
                ``meeting_id`` ascending as a final tiebreaker.

        Note:
            The two admin display paths that currently render a pair's
            meeting log order by ``created_datetime`` instead, not
            ``start_datetime``
            (``backend/mentorship/mentorship_admin_service.py:330``,
            ``:337``, ``:534``, ``:542``). Whoever switches those call sites
            over to this method should choose the ordering deliberately --
            switching silently would reorder the admin meeting log.
        """
        stmt = select(MentorshipMeetingEntity).where(
            MentorshipMeetingEntity.pair_id == pair_id
        )
        if not include_legacy:
            stmt = stmt.where(MentorshipMeetingEntity.source != MeetingSource.LEGACY)
        stmt = stmt.order_by(*_MEETING_ORDER_BY)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_meetings_by_pairs(
        self,
        session: AsyncSession,
        pair_ids: list[int],
        include_legacy: bool = False,
    ) -> dict[int, list[MentorshipMeetingEntity]]:
        """Every meeting for a batch of pairs, one query, grouped in Python.

        For the admin CSV export, which pages up to 500 pairs and needs this
        batched -- calling ``get_meetings_by_pair`` once per pair would
        reintroduce an N+1 the rest of that page already avoids.

        Args:
            session (AsyncSession): The active DB session.
            pair_ids (list[int]): The pairs to fetch meetings for.
            include_legacy (bool): Same meaning as on ``get_meetings_by_pair``;
                LEGACY rows are excluded by default.

        Returns:
            dict[int, list[MentorshipMeetingEntity]]: Each pair's meetings,
                ordered the same as ``get_meetings_by_pair``. A pair with no
                matching rows is ABSENT from the dict -- it is not mapped to
                an empty list -- so a caller indexing with ``result[pair_id]``
                must be prepared for a ``KeyError``, e.g. via
                ``result.get(pair_id, [])``. Empty (``{}``) for empty input,
                without touching the database.
        """
        if not pair_ids:
            return {}
        stmt = select(MentorshipMeetingEntity).where(
            MentorshipMeetingEntity.pair_id.in_(pair_ids)
        )
        if not include_legacy:
            stmt = stmt.where(MentorshipMeetingEntity.source != MeetingSource.LEGACY)
        stmt = stmt.order_by(*_MEETING_ORDER_BY)
        result = await session.execute(stmt)
        grouped: dict[int, list[MentorshipMeetingEntity]] = {}
        for meeting in result.scalars().all():
            grouped.setdefault(meeting.pair_id, []).append(meeting)
        return grouped

    async def get_pending_google_meetings_by_pairs(
        self, session: AsyncSession, pair_ids: list[int]
    ) -> list[MentorshipMeetingEntity]:
        """GOOGLE meetings still awaiting completion, across a batch of pairs.

        Args:
            session (AsyncSession): The active DB session.
            pair_ids (list[int]): The pairs to search across.

        Returns:
            list[MentorshipMeetingEntity]: Rows with ``source='google'``,
                ``is_completed=False``, and a non-null
                ``google_meeting_code``. Empty for empty input.
        """
        if not pair_ids:
            return []
        result = await session.execute(
            select(MentorshipMeetingEntity).where(
                MentorshipMeetingEntity.pair_id.in_(pair_ids),
                MentorshipMeetingEntity.source == MeetingSource.GOOGLE,
                # ix_mentorship_meeting_pending has predicate
                # `is_completed = false`; Postgres cannot prove `IS false`
                # implies `= false`, so the `.is_(False)` form (which compiles
                # to `IS false`) makes the planner skip this index entirely.
                # The `== False` form is required to match the predicate.
                # A later PR copies this pattern into the attendance sweep --
                # do not "correct" it back to `.is_(False)`.
                MentorshipMeetingEntity.is_completed == False,  # noqa: E712
                MentorshipMeetingEntity.google_meeting_code.is_not(None),
            )
        )
        return list(result.scalars().all())

    async def get_meeting_by_google_meeting_code(
        self, session: AsyncSession, code: str
    ) -> MentorshipMeetingEntity | None:
        """The meeting whose Google Meet code matches, if any.

        Args:
            session (AsyncSession): The active DB session.
            code (str): The Meet meeting code to look up.

        Returns:
            MentorshipMeetingEntity | None: The matching row, or None.
        """
        result = await session.execute(
            select(MentorshipMeetingEntity).where(
                MentorshipMeetingEntity.google_meeting_code == code
            )
        )
        return result.scalars().first()

    async def insert_meeting(
        self, session: AsyncSession, meeting: MentorshipMeetingEntity
    ) -> MentorshipMeetingEntity:
        """Persist a new meeting row.

        Args:
            session (AsyncSession): The active DB session.
            meeting (MentorshipMeetingEntity): The row to insert.

        Returns:
            MentorshipMeetingEntity: The persisted row.
        """
        session.add(meeting)
        await session.flush()
        return meeting

    async def delete_meetings(
        self, session: AsyncSession, pair_id: int, meeting_ids: list[str]
    ) -> int:
        """Delete a batch of meetings belonging to one pair.

        Args:
            session (AsyncSession): The active DB session.
            pair_id (int): The pair the meetings must belong to; ids for any
                other pair are silently ignored.
            meeting_ids (list[str]): The meetings to delete.

        Returns:
            int: The number of rows deleted.
        """
        if not meeting_ids:
            return 0
        stmt = delete(MentorshipMeetingEntity).where(
            MentorshipMeetingEntity.pair_id == pair_id,
            MentorshipMeetingEntity.meeting_id.in_(meeting_ids),
        )
        result = await session.execute(stmt)
        return result.rowcount

    async def recalculate_completed_count(
        self, session: AsyncSession, pair_id: int
    ) -> int:
        """Recompute ``mentorship_pairs.completed_count`` from meeting rows.

        Counts every source, LEGACY included: historical rounds that recorded
        only a count have one LEGACY row per completed meeting precisely so
        this is safe to call for any pair -- excluding them would zero out a
        number nothing could rebuild.

        Args:
            session (AsyncSession): The active DB session.
            pair_id (int): The pair to recompute.

        Returns:
            int: The new ``completed_count`` value.

        Raises:
            sqlalchemy.exc.NoResultFound: If ``pair_id`` does not exist. The
                ``UPDATE ... RETURNING`` matches zero rows, and ``scalar_one()``
                raises rather than returning ``None`` or ``0`` -- this is not
                converted into a softer failure, so callers must not pass an
                unverified pair_id.
        """
        count_subquery = (
            select(func.count())
            .select_from(MentorshipMeetingEntity)
            .where(
                MentorshipMeetingEntity.pair_id == pair_id,
                MentorshipMeetingEntity.is_completed.is_(True),
            )
            .scalar_subquery()
        )
        stmt = (
            update(MentorshipPairsEntity)
            .where(MentorshipPairsEntity.pair_id == pair_id)
            .values(completed_count=count_subquery)
            .returning(MentorshipPairsEntity.completed_count)
        )
        result = await session.execute(stmt)
        return result.scalar_one()
