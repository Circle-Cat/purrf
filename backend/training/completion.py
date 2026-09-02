"""Turning what a course reports into what the assignment says."""

from backend.common.mentorship_enums import TrainingStatus

# SCORM 1.2 lesson_status values, and what each means for the assignment.
# Both finishing values are here on purpose: which one a course reports is a
# per-course setting in the authoring tool, not something we may assume.
# Mentee onboarding reports "passed"; mentor onboarding reports "completed".
# A failed attempt is still in progress, not done -- the learner may retake it.
_FINISHED = frozenset({"passed", "completed"})
_STARTED = frozenset({"incomplete", "browsed", "failed"})


def next_training_status(
    current: TrainingStatus, lesson_status: str | None
) -> TrainingStatus | None:
    """The status to write, or None to leave the assignment alone.

    Nothing moves an assignment out of DONE. Reopening a finished course
    writes `incomplete` before it writes `completed`, so without that rule a
    learner reviewing their own completed course would close their mentorship
    matching gate on the first write of the session.

    Args:
        current (TrainingStatus): What the assignment says now.
        lesson_status (str | None): What the course just reported.

    Returns:
        TrainingStatus | None: The new status, or None for no change.
    """
    if current is TrainingStatus.DONE:
        return None

    reported = (lesson_status or "").strip()
    if reported in _FINISHED:
        return TrainingStatus.DONE
    if reported in _STARTED and current is not TrainingStatus.IN_PROGRESS:
        return TrainingStatus.IN_PROGRESS
    # "not attempted" and anything we do not recognise leave the row alone.
    return None
