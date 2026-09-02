from datetime import datetime

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

    async def get_pending_google_meetings_in_window(
        self,
        session: AsyncSession,
        pair_ids: list[int],
        ends_after: datetime,
        starts_before: datetime,
        round_window_start: datetime,
        round_window_end: datetime,
    ) -> list[MentorshipMeetingEntity]:
        """GOOGLE meetings awaiting attendance whose slot is worth checking now.

        Each returned row costs one Meet API call, so the set has to be
        bounded at BOTH ends:

        - Bounded below, because a meeting nobody joined produces no conference
          record and therefore never completes. Without a lower bound those
          dead rows accumulate for the whole round and are re-queried forever.
        - Bounded above, because a meeting that has not happened yet has
          nothing to reconcile.

        The two bounds land on different columns on purpose, which is what the
        parameter names say: a meeting is in scope when its own attendance
        affinity window overlaps the caller's lookback interval, and two
        intervals overlap when each one's start is no later than the other's
        end. The caller derives both values -- see
        ``MeetAttendanceService.sync_attendance``.

        Separately, ``round_window_start``/``round_window_end`` answer a
        different question: does this meeting belong to the round at all?
        Mentees may schedule as many meetings as they like, but only ones
        landing inside the round's own meeting window (from match
        notification through the completion deadline) are Purrf's to sync --
        anything after the deadline is a private arrangement. This pair is
        fixed for the whole round, while ``ends_after``/``starts_before``
        slide with ``now`` and the lookback on every run; the two pairs are
        not interchangeable and must not be merged into one.

        Args:
            session (AsyncSession): The active DB session.
            pair_ids (list[int]): The pairs to search across.
            ends_after (datetime): Keep rows whose ``end_datetime`` is at or
                after this. Inclusive.
            starts_before (datetime): Keep rows whose ``start_datetime`` is at
                or before this. Inclusive.
            round_window_start (datetime): Keep rows whose ``start_datetime``
                is at or after this round's window start (typically the match
                notification instant). Inclusive.
            round_window_end (datetime): Keep rows whose ``start_datetime`` is
                at or before this round's meeting-completion deadline.
                Inclusive.

        Returns:
            list[MentorshipMeetingEntity]: Rows with ``source='google'``,
                ``is_completed=False``, a non-null ``google_meeting_code``, and
                a slot inside both the sweep bounds and the round window,
                ordered like every other read here (``start_datetime``
                ascending, then ``created_datetime``, then ``meeting_id``).
                Empty for empty input, without touching the database.
        """
        if not pair_ids:
            return []
        stmt = (
            select(MentorshipMeetingEntity)
            .where(
                MentorshipMeetingEntity.pair_id.in_(pair_ids),
                MentorshipMeetingEntity.source == MeetingSource.GOOGLE,
                # `== False` rather than `.is_(False)` so the planner can match
                # ix_mentorship_meeting_pending's `is_completed = false`
                # predicate; Postgres cannot prove `IS false` implies
                # `= false`, so `.is_(False)` would make it skip the index.
                # Do not "correct" this back to `.is_(False)`.
                MentorshipMeetingEntity.is_completed == False,  # noqa: E712
                MentorshipMeetingEntity.google_meeting_code.is_not(None),
                MentorshipMeetingEntity.end_datetime >= ends_after,
                MentorshipMeetingEntity.start_datetime <= starts_before,
                MentorshipMeetingEntity.start_datetime >= round_window_start,
                MentorshipMeetingEntity.start_datetime <= round_window_end,
            )
            .order_by(*_MEETING_ORDER_BY)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

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

    async def update_schedule(
        self,
        session: AsyncSession,
        meeting: MentorshipMeetingEntity,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> MentorshipMeetingEntity:
        """Move one meeting to a new slot.

        Writes the two time columns and nothing else. `meeting_id` is the
        Calendar event id and a Calendar patch does not change it;
        `created_datetime` holds Google's own creation time and is the
        ordering tiebreaker when two meetings share a start; `meet_link` and
        `entry_points` describe a Meet space that a patch never re-opens.
        None of them may be rewritten here.

        Args:
            session (AsyncSession): The active DB session.
            meeting (MentorshipMeetingEntity): The row to move, already
                loaded and belonging to the caller's pair.
            start_datetime (datetime): New start, tz-aware UTC.
            end_datetime (datetime): New end, tz-aware UTC.

        Returns:
            MentorshipMeetingEntity: The updated row.
        """
        meeting.start_datetime = start_datetime
        meeting.end_datetime = end_datetime
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

    async def count_completed_by_pairs(
        self, session: AsyncSession, pair_ids: list[int]
    ) -> dict[int, int]:
        """Count each pair's completed meetings.

        Counts every source, LEGACY included: historical rounds recorded only
        a number, and the split migration stands one LEGACY row in for each of
        those meetings, so excluding them would report zero for every pairing
        that predates Purrf. This is the same rule
        ``mentorship_pairs.completed_count`` was maintained under, which is
        what lets this replace reads of that column.

        Flushes first, for the same reason ``recalculate_completed_count``
        does: production sessions are built with ``autoflush=False``
        (``backend/common/database.py``), so a caller that just set
        ``is_completed`` on a loaded row has written nothing the database can
        count yet.

        Args:
            session (AsyncSession): The active DB session. Pending changes on
                it are flushed before the count is taken.
            pair_ids (list[int]): The pairs to count. An empty list short-
                circuits without a query.

        Returns:
            dict[int, int]: pair_id -> completed meeting count. Every
                requested pair_id is present, 0 when nothing is completed
                (an id with no pair at all included), so no call site needs a
                KeyError guard.
        """
        if not pair_ids:
            return {}
        await session.flush()
        stmt = (
            select(
                MentorshipMeetingEntity.pair_id,
                func.count().label("completed"),
            )
            .where(
                MentorshipMeetingEntity.pair_id.in_(pair_ids),
                MentorshipMeetingEntity.is_completed.is_(True),
            )
            .group_by(MentorshipMeetingEntity.pair_id)
        )
        result = await session.execute(stmt)
        counts = {pair_id: 0 for pair_id in pair_ids}
        counts.update({row.pair_id: row.completed for row in result.all()})
        return counts

    async def recalculate_completed_count(
        self, session: AsyncSession, pair_id: int
    ) -> int:
        """Recompute ``mentorship_pairs.completed_count`` from meeting rows.

        Counts every source, LEGACY included: historical rounds that recorded
        only a count have one LEGACY row per completed meeting precisely so
        this is safe to call for any pair -- excluding them would zero out a
        number nothing could rebuild.

        Flushes first. The count comes from a scalar subquery evaluated inside
        the UPDATE, so it sees the database, never the session -- and
        production sessions are built with ``autoflush=False``
        (``backend/common/database.py``), so a caller that just set
        ``is_completed`` on a loaded row has written nothing yet. Both the
        attendance sweep and the admin meeting batch do exactly that before
        calling this. Flushing here rather than at each call site keeps the
        method's contract honest -- "recompute from this pair's meetings"
        means all of them, including the ones still pending in this session --
        and stops the next caller from having to rediscover the ordering.

        Args:
            session (AsyncSession): The active DB session. Pending changes on
                it are flushed before the count is taken.
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
        await session.flush()
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
