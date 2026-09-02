"""Turning one LMSCommit into a row."""

import re

_TIMESPAN = re.compile(r"^(\d{2,4}):([0-5]\d):([0-5]\d)(\.\d{1,2})?$")

_LESSON_STATUS = "cmi.core.lesson_status"
_LESSON_LOCATION = "cmi.core.lesson_location"
_SUSPEND_DATA = "cmi.suspend_data"
_SESSION_TIME = "cmi.core.session_time"
_TOTAL_TIME = "cmi.core.total_time"


def _timespan_seconds(value: str) -> int:
    """Seconds in a SCORM 1.2 CMITimespan, or 0 if it is not one.

    A course that reports its session time in a shape we cannot read must not
    cost the learner the rest of the commit.
    """
    match = _TIMESPAN.match((value or "").strip())
    if not match:
        return 0
    hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
    return hours * 3600 + minutes * 60 + seconds


class TrainingProgressService:
    """Stores what a course reports, and nothing more."""

    def __init__(self, logger, training_repository, training_progress_repository):
        """
        Args:
            logger: Injected logger.
            training_repository (TrainingRepository): The assignment being saved.
            training_progress_repository (TrainingProgressRepository): The row.
        """
        self.logger = logger
        self.training_repository = training_repository
        self.training_progress_repository = training_progress_repository

    async def save(self, session, training_id: int, user_id: int, cmi: dict):
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

        Returns:
            TrainingProgressEntity: The stored row.

        Raises:
            ValueError: No such assignment.
            PermissionError: The assignment belongs to somebody else.
        """
        assignment = await self.training_repository.get_training_by_id(
            session, training_id
        )
        if assignment is None:
            raise ValueError(f"No training assignment with id {training_id}.")
        if assignment.user_id != user_id:
            raise PermissionError("This training belongs to somebody else.")

        columns = {}
        if _LESSON_STATUS in cmi:
            columns["lesson_status"] = cmi[_LESSON_STATUS]
        if _LESSON_LOCATION in cmi:
            columns["lesson_location"] = cmi[_LESSON_LOCATION]
        if _SUSPEND_DATA in cmi:
            # Never length-checked. A rejected write is invisible to the course.
            columns["suspend_data"] = cmi[_SUSPEND_DATA]

        if _TOTAL_TIME in cmi:
            # total_time is seeded total + elapsed wall time for this session
            # (scorm-again's getCurrentTotalTime), so it is already the right
            # number to store on every commit -- adding it again would count
            # the same session more than once.
            columns["session_time_seconds"] = _timespan_seconds(cmi[_TOTAL_TIME])
        elif _SESSION_TIME in cmi:
            # No total_time to trust: fall back to accumulating the raw
            # session-to-date value onto what was already stored.
            existing = await self.training_progress_repository.get_by_training_id(
                session, training_id
            )
            accumulated = getattr(existing, "session_time_seconds", 0) or 0
            columns["session_time_seconds"] = accumulated + _timespan_seconds(
                cmi[_SESSION_TIME]
            )

        row = await self.training_progress_repository.upsert(
            session, training_id, **columns
        )
        await session.commit()
        return row
