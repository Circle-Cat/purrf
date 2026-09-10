"""Filters and rows for the audience search behind bulk training assignment."""

from typing import Literal

from datetime import datetime

from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto


class TrainingAudienceFilterDto(BaseRequestDto):
    """Who to look for. Every field is one value, so filters only ever AND.

    The precondition is not a field: results are always confined to active,
    unblocked people, because anything a row reaches can be ticked and
    assigned.
    """

    search: str | None = None
    user_id: int | None = None
    user_type: Literal["internal", "external"] | None = None
    mentorship_role: ParticipantRole | None = None
    course_id: int | None = None
    course_status: Literal["assigned", "not_assigned"] | None = None


class TrainingAudienceRowDto(BaseDto):
    """One person the card may assign a course to.

    ``course_status`` answers the selected course and is None with no course
    in scope; the two counts answer the person's whole training list and are
    None once a course is selected. They are never both filled: the column
    that shows them is the same column.
    """

    user_id: int
    first_name: str | None
    last_name: str | None
    preferred_name: str | None
    contact_email: str | None
    is_internal: bool
    course_status: TrainingStatus | None
    assigned_course_count: int | None
    done_course_count: int | None


class TrainingAudienceSearchDto(BaseDto):
    """One page of the audience, and how many match in total."""

    rows: list[TrainingAudienceRowDto]
    total: int


class TrainingAudienceIdsDto(BaseDto):
    """Every id a search matches, for selecting a whole result set."""

    user_ids: list[int]
    total: int


class TrainingUserAssignmentDto(BaseDto):
    """One course a person holds, with whatever the runtime has reported.

    Only rows that exist in ``training`` are ever built into this: the
    catalogue is never padded with courses nobody assigned, which would grow
    with every new course and bury the two or three that matter.

    There is no percentage anywhere in the data, so there is none here. What
    exists is the status, the dates, and the SCORM values verbatim -- absent
    for an assignment nobody has opened.
    """

    training_id: int
    course_id: int | None
    course_name: str | None
    category: TrainingCategory | None
    status: TrainingStatus
    deadline: datetime | None
    completed_timestamp: datetime | None
    lesson_status: str | None
    score_raw: str | None
    score_max: str | None
    session_time_seconds: int | None
    last_accessed_at: datetime | None


class TrainingUserAssignmentsDto(BaseDto):
    """Everything one person holds, for the expanded row."""

    user_id: int
    rows: list[TrainingUserAssignmentDto]
