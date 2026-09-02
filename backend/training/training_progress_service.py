"""Turning one LMSCommit into a row."""

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from backend.common.mentorship_enums import TrainingStatus
from backend.training.completion import next_training_status

# SCORM 1.2's CMITimespan needs at least two digits of hours. A single-digit
# hour is already outside the format, and is treated the same as any other
# unparseable value rather than guessed at.
_TIMESPAN = re.compile(r"^(\d{2,4}):([0-5]\d):([0-5]\d)(\.\d{1,2})?$")

_LESSON_STATUS = "cmi.core.lesson_status"
_LESSON_LOCATION = "cmi.core.lesson_location"
_SUSPEND_DATA = "cmi.suspend_data"
_SESSION_TIME = "cmi.core.session_time"
_TOTAL_TIME = "cmi.core.total_time"
_SCORE_COLUMNS = {
    "cmi.core.score.raw": "score_raw",
    "cmi.core.score.min": "score_min",
    "cmi.core.score.max": "score_max",
}
# Numeric(8, 2)'s largest storable magnitude.
_SCORE_LIMIT = Decimal("999999.99")

# The driver commits every 20 seconds whether or not anything changed, so an
# idle tab would otherwise rewrite the same row -- and the same tens of
# kilobytes of suspend_data -- forever. session_time_seconds is deliberately
# not compared: it is wall clock since the course loaded, so it grows on every
# commit and would make this never fire. An idle learner's time therefore lags
# until they do something, or until the page marks a save final -- which it
# does on unload, and which is written whether the content changed or not.
_CONTENT_COLUMNS = (
    "lesson_status",
    "lesson_location",
    "suspend_data",
    "score_raw",
    "score_min",
    "score_max",
)

# The columns behind these are unbounded text on purpose, and the endpoint is
# open to anyone holding the assignment, so without a cap one learner can grow
# the database without limit. The limits are far above anything a real course
# produces: the largest sample in this repo is about 1.3 KB, real packages that
# ignore SCORM 1.2's 4096-character convention still land nowhere near 64 KB,
# and a keepalive unload fetch cannot carry a body that big anyway. Passing one
# is refused with an error the page can show, never truncated or dropped: a
# write stored short, or discarded quietly, costs the learner their place with
# no signal at all -- which is the reason the column has no length.
_LENGTH_LIMITS = {
    _SUSPEND_DATA: 65536,
    _LESSON_LOCATION: 4096,
    _LESSON_STATUS: 64,
}


def _reject_oversized(cmi: dict) -> None:
    """Refuse a commit carrying a value no real course would send.

    Raises:
        ValueError: A CMI element is longer than the cap for it.
    """
    for key, limit in _LENGTH_LIMITS.items():
        value = cmi.get(key)
        if isinstance(value, str) and len(value) > limit:
            raise ValueError(f"{key} is {len(value)} characters; the limit is {limit}.")


def _content_unchanged(existing, columns: dict) -> bool:
    """Whether this commit reports the same content the row already holds.

    Only the keys actually present in ``columns`` are compared -- an absent
    key means the course did not report that element this time, not that it
    should read as blank.
    """
    if existing is None:
        return False
    return all(
        getattr(existing, name) == value
        for name, value in columns.items()
        if name in _CONTENT_COLUMNS
    )


def _timespan_seconds(value: str) -> int | None:
    """Seconds in a SCORM 1.2 CMITimespan, or None if it is not one.

    A course that reports its session time in a shape we cannot read must not
    cost the learner the rest of the commit -- and for a value that replaces
    rather than accumulates, None has to stay distinguishable from an actual
    zero so the caller can leave the stored value alone.
    """
    match = _TIMESPAN.match((value or "").strip())
    if not match:
        return None
    hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
    return hours * 3600 + minutes * 60 + seconds


def _score_decimal(value) -> Decimal | None:
    """A CMI score string as a Decimal, or None if it cannot be stored.

    Covers three ways a score can be unstorable: it does not parse, it is
    not finite (``NaN`` / ``Infinity`` both parse as a Decimal), or it
    overflows the column's Numeric(8, 2) precision. All three are dropped
    the same way an unparseable score already was, so one bad field does not
    cost the learner the rest of the commit. A score outside SCORM's 0-100
    is not clamped into range -- if the column can hold it, it is stored as
    reported, since silently coercing it would hide a broken course rather
    than surface one.
    """
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not parsed.is_finite() or abs(parsed) > _SCORE_LIMIT:
        return None
    return parsed


class TrainingProgressService:
    """Stores what a course reports, and stamps the course verified on completion."""

    def __init__(
        self,
        logger,
        training_repository,
        training_progress_repository,
        training_course_repository,
    ):
        """
        Args:
            logger: Injected logger.
            training_repository (TrainingRepository): The assignment being saved.
            training_progress_repository (TrainingProgressRepository): The row.
            training_course_repository (TrainingCourseRepository): Reads the
                course being finished, to stamp it on first completion.
        """
        self.logger = logger
        self.training_repository = training_repository
        self.training_progress_repository = training_progress_repository
        self.training_course_repository = training_course_repository

    async def save(
        self, session, training_id: int, user_id: int, cmi: dict, final: bool = False
    ):
        """Apply one commit to the caller's own assignment.

        Only the CMI elements actually present in ``cmi`` are written. A
        course that commits a partial payload must not blank out the fields
        it left out -- an empty string, though, is a value a course writes on
        purpose and is stored exactly like any other.

        Args:
            session: The active async database session.
            training_id (int): The assignment being learned.
            user_id (int): Who is learning it.
            cmi (dict): Flattened CMI from the course.
            final (bool): The page's last save of this session. Written even
                when the content matches what is stored, because the only
                thing such a save carries is the elapsed time the content
                comparison ignores.

        Returns:
            TrainingProgressEntity: The stored row.

        Raises:
            ValueError: No such assignment, or an element over its length cap.
            PermissionError: The assignment belongs to somebody else.
        """
        _reject_oversized(cmi)

        # Locked, because what follows reads the status, decides the next one
        # from it, and writes it back. A course reports `incomplete` and then
        # `completed` within the same second, and unlocked those two requests
        # both read TO_DO: whichever commits second wins, and half the time
        # that is the one holding the stale not-finished decision. The lock
        # makes the loser re-read the status the winner wrote, where
        # next_training_status leaves a finished assignment alone.
        assignment = await self.training_repository.get_training_by_id(
            session, training_id, for_update=True
        )
        if assignment is None:
            raise ValueError(f"No training assignment with id {training_id}.")
        if assignment.user_id != user_id:
            raise PermissionError("This training belongs to somebody else.")

        existing = await self.training_progress_repository.get_by_training_id(
            session, training_id
        )

        columns = {}
        # Set only on the session_time fallback path below, where
        # session_time_seconds is a delta added to the stored total rather
        # than a value recomputed fresh -- see the comment there.
        accumulates_session_time = False
        if _LESSON_STATUS in cmi:
            columns["lesson_status"] = cmi[_LESSON_STATUS]
        if _LESSON_LOCATION in cmi:
            columns["lesson_location"] = cmi[_LESSON_LOCATION]
        if _SUSPEND_DATA in cmi:
            # Stored whole. Only the abuse cap above bounds it, and that one
            # refuses the request rather than shortening what it stores.
            columns["suspend_data"] = cmi[_SUSPEND_DATA]

        if _TOTAL_TIME in cmi:
            # total_time is seeded total + elapsed wall time for this session
            # (scorm-again's getCurrentTotalTime), so it is already the right
            # number to store on every commit -- adding it again would count
            # the same session more than once.
            parsed_total = _timespan_seconds(cmi[_TOTAL_TIME])
            if parsed_total is not None:
                columns["session_time_seconds"] = parsed_total
            else:
                # Leave the stored value alone. A course that cannot format
                # its own elapsed time must not zero out what was already
                # banked -- but a course that never accumulates anything
                # should not do so silently forever.
                self.logger.warning(
                    "[TrainingProgressService] training %s sent an "
                    "unparseable cmi.core.total_time %r; leaving the stored "
                    "value alone",
                    training_id,
                    cmi[_TOTAL_TIME],
                )
        elif _SESSION_TIME in cmi:
            # No total_time to trust: fall back to accumulating the raw
            # session-to-date value onto what was already stored. Unlike
            # total_time (recomputed fresh from a stable seed every commit),
            # this is stateful: the delta only exists in this one commit, so
            # this commit must never be skipped -- a skip here would discard
            # the delta permanently, not just delay an accurate figure. Our
            # own player always sends total_time, so this path is dormant in
            # production today, but a dormant trap is the kind that fires
            # years later when somebody revives it.
            accumulates_session_time = True
            accumulated = getattr(existing, "session_time_seconds", 0) or 0
            parsed_session = _timespan_seconds(cmi[_SESSION_TIME])
            if parsed_session is None:
                self.logger.warning(
                    "[TrainingProgressService] training %s sent an "
                    "unparseable cmi.core.session_time %r; adding nothing "
                    "for this session",
                    training_id,
                    cmi[_SESSION_TIME],
                )
            columns["session_time_seconds"] = accumulated + (parsed_session or 0)

        for cmi_key, column in _SCORE_COLUMNS.items():
            if cmi_key not in cmi:
                continue
            raw = cmi[cmi_key]
            if raw == "":
                # A course clears a score the way it clears any other field.
                # Numeric has no empty value, so the clear becomes NULL.
                columns[column] = None
                continue
            parsed_score = _score_decimal(raw)
            if parsed_score is not None:
                columns[column] = parsed_score
            else:
                # Dropped, not stored -- must not cost the learner the rest
                # of this commit, but must not vanish without a trace either.
                self.logger.warning(
                    "[TrainingProgressService] training %s sent an "
                    "unstorable %s %r; dropping it",
                    training_id,
                    cmi_key,
                    raw,
                )

        if not columns:
            self.logger.warning(
                "[TrainingProgressService] commit to training %s produced "
                "no storable columns; keys=%s",
                training_id,
                sorted(cmi.keys()),
            )

        moved = next_training_status(assignment.status, cmi.get(_LESSON_STATUS))

        unchanged = (
            _content_unchanged(existing, columns)
            and not accumulates_session_time
            and not final
        )
        if unchanged and moved is None:
            # Nothing to store and nothing to decide -- skip the write
            # entirely rather than rewrite a row a parked tab keeps
            # reporting. The course still sees a successful commit.
            #
            # last_accessed_at (stamped by upsert) does not advance while a
            # commit is skipped. That is accepted: touching it would require
            # the write this skip exists to avoid, and nothing reads the
            # column today.
            return existing

        row = existing
        if not unchanged:
            row = await self.training_progress_repository.upsert(
                session, training_id, **columns
            )

        if moved is not None:
            assignment.status = moved
            if moved is TrainingStatus.DONE:
                if assignment.completed_timestamp is None:
                    assignment.completed_timestamp = datetime.now(timezone.utc)
                await self._stamp_if_unverified(session, assignment, user_id)

        await session.commit()
        return row

    async def _stamp_if_unverified(self, session, assignment, user_id: int) -> None:
        """Record that somebody ran this course to the end.

        An unverified course cannot be assigned to anybody, so whoever holds
        an assignment on one got it from the trial run -- which is what makes
        this the trial's stamp without needing a flag to say so.
        """
        if assignment.course_id is None:
            return
        course = await self.training_course_repository.get_course_by_id(
            session, assignment.course_id
        )
        if course is None or course.verified_completable_at is not None:
            return
        course.verified_completable_at = datetime.now(timezone.utc)
        course.verified_by_user_id = user_id
        self.logger.info(
            "[TrainingProgressService] course %s verified completable by user %s",
            course.course_id,
            user_id,
        )
