"""Turning one LMSCommit into a row."""

import re

_TIMESPAN = re.compile(r"^(\d{2,4}):([0-5]\d):([0-5]\d)(\.\d{1,2})?$")


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

        existing = await self.training_progress_repository.get_by_training_id(
            session, training_id
        )
        accumulated = getattr(existing, "session_time_seconds", 0) or 0

        return await self.training_progress_repository.upsert(
            session,
            training_id,
            lesson_status=cmi.get("cmi.core.lesson_status"),
            lesson_location=cmi.get("cmi.core.lesson_location"),
            # Never length-checked. A rejected write is invisible to the course.
            suspend_data=cmi.get("cmi.suspend_data"),
            session_time_seconds=accumulated
            + _timespan_seconds(cmi.get("cmi.core.session_time")),
        )
