"""Filters and rows for the audience search behind bulk training assignment."""

from typing import Literal

from backend.common.mentorship_enums import ParticipantRole, TrainingStatus
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
