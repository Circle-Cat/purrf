from datetime import datetime
from enum import StrEnum

from pydantic import Field

from backend.common.mentorship_enums import ScormVersion, TrainingCategory
from backend.dto.base_dto import BaseDto


class TrainingCourseState(StrEnum):
    """What the course list shows in its Status column.

    Derived from ``storage_prefix`` and ``verified_completable_at``, never
    stored, so the admin page and the assignment check cannot disagree.
    """

    # The only state that can be assigned.
    VERIFIED = "verified"
    NEEDS_TRIAL_RUN = "needs_trial_run"
    # A seed course still pointing at its environment-variable link.
    EXTERNAL_LINK = "external_link"
    NO_PACKAGE = "no_package"


class TrainingCourseDto(BaseDto):
    """One row of the admin course list."""

    course_id: int
    name: str
    description: str | None = None
    category: TrainingCategory | None = None
    is_active: bool
    state: TrainingCourseState
    scorm_version: ScormVersion | None = None
    package_version: str | None = None
    reporting_mode: str | None = None
    package_uploaded_at: datetime | None = None
    verified_completable_at: datetime | None = None
    verified_by_user_id: int | None = None
    # Deactivating and overwriting both ask the admin to weigh this number
    # rather than answer "are you sure".
    assigned_count: int = 0


class TrainingCourseCreateDto(BaseDto):
    """Creating a course. A package is uploaded separately, afterwards."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TrainingCourseUpdateDto(BaseDto):
    """Renaming a course, or turning it off. There is no delete."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class TrainingAssignmentRequestDto(BaseDto):
    """Assigning one course to one person."""

    user_id: int
    course_id: int
    deadline: datetime | None = None


class TrainingAssignmentResultDto(BaseDto):
    """What an assignment call did.

    ``created`` is False when the person already held the course; assigning
    twice is a no-op, not an error.
    """

    training_id: int
    user_id: int
    course_id: int
    created: bool
