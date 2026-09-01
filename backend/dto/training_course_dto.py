from datetime import datetime
from enum import StrEnum

from pydantic import Field

from backend.common.mentorship_enums import ScormVersion, TrainingCategory
from backend.dto.base_dto import BaseDto


class TrainingCourseState(StrEnum):
    """What the course list shows in its Status column.

    Derived, never stored: every one of these is a reading of
    ``storage_prefix`` and ``verified_completable_at``, and deriving it in one
    place stops the admin page and the assignment check from disagreeing about
    whether a course is usable.
    """

    # Ran to completion at least once; the only state that can be assigned.
    VERIFIED = "verified"
    # Has a package nobody has finished yet.
    NEEDS_TRIAL_RUN = "needs_trial_run"
    # A seed course still pointing at its environment-variable link.
    EXTERNAL_LINK = "external_link"
    # Created but never given a package.
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
    # How many people hold an assignment to this course, active or finished.
    # Shown because deactivating and overwriting both ask the admin to weigh a
    # number of affected people rather than answer "are you sure".
    assigned_count: int = 0


class TrainingCourseCreateDto(BaseDto):
    """Creating a course. A package is uploaded separately, afterwards."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TrainingCourseUpdateDto(BaseDto):
    """Renaming a course, or turning it off.

    ``is_active=False`` stops new assignments and touches nothing else. There
    is no delete.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class TrainingAssignmentRequestDto(BaseDto):
    """Assigning one course to one person.

    ``deadline`` is optional. It has been nullable since July and
    ``ensure_for_admitted`` already creates rows without one, stamping it later
    on first registration.
    """

    user_id: int
    course_id: int
    deadline: datetime | None = None


class TrainingAssignmentResultDto(BaseDto):
    """What an assignment call did.

    ``created`` is False when the person already held this course: assigning
    twice is a no-op, not an error, so the caller is told which of the two
    happened rather than left to guess from a status code.
    """

    training_id: int
    user_id: int
    course_id: int
    created: bool
