from datetime import datetime
from enum import StrEnum

from pydantic import Field

from backend.common.mentorship_enums import (
    ScormVersion,
    TrainingCategory,
    TrainingStatus,
)
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto


class TrainingCourseLiveState(StrEnum):
    """What a learner can open right now, read from the live slot alone.

    A staged package never moves this: it is invisible to learners by design,
    which is what makes uploading one mid-day safe. Whether the live package
    itself carries a verification stamp does not appear here either -- that
    lives on the package row (surfaced through the top-level
    ``verified_completable_at``/``verified_by_user_id`` fields below), because
    an unverified live package still serves learners fine; it only blocks new
    assignments.
    """

    LIVE = "live"
    # A seed course still pointing at its environment-variable link.
    EXTERNAL_LINK = "external_link"
    NO_PACKAGE = "no_package"


class StagedPackageDto(BaseDto):
    """The pending package behind a course, if one is sitting there.

    Exists only while a package occupies the pending slot: publishing moves
    its data into the live fields above and this goes back to None,
    discarding just drops the row. A course is never mid-way between having
    one and not.
    """

    package_id: int
    package_version: str | None = None
    uploaded_at: datetime
    uploaded_by_user_id: int | None = None
    verified_completable_at: datetime | None = None
    verified_by_user_id: int | None = None


class TrainingCourseDto(BaseDto):
    """One row of the admin course list.

    ``live_state`` and the package fields alongside it describe the live
    slot only -- what a learner can open today. ``staged`` is the other slot,
    kept in its own block rather than folded into the same fields: a pending
    package is not a variant of the live one, it is a second, unrelated
    upload that happens to share a course.
    """

    course_id: int
    name: str
    description: str | None = None
    category: TrainingCategory | None = None
    is_active: bool
    live_state: TrainingCourseLiveState
    # Where a course we do not host is served from, resolved from the
    # category's environment variable. Null once we host the course ourselves,
    # so the row never offers the place it used to be.
    link: str | None = None
    scorm_version: ScormVersion | None = None
    package_version: str | None = None
    reporting_mode: str | None = None
    package_uploaded_at: datetime | None = None
    verified_completable_at: datetime | None = None
    verified_by_user_id: int | None = None
    # Deactivating and overwriting both ask the admin to weigh this number
    # rather than answer "are you sure".
    assigned_count: int = 0
    # Everyone still counted here would be restarted by a replacement package.
    unfinished_count: int = 0
    staged: StagedPackageDto | None = None


class TrainingCourseCreateDto(BaseRequestDto):
    """Creating a course. A package is uploaded separately, afterwards."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TrainingCourseUpdateDto(BaseRequestDto):
    """Renaming a course, or turning it off. There is no delete."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class TrainingAssignmentRequestDto(BaseRequestDto):
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


class TrainingPackageUploadResultDto(BaseDto):
    """What an upload stored, and what the package says about finishing.

    ``completion_config_readable`` is False for a package built by a toolchain
    we cannot read. The upload dialog has to say so rather than show nothing:
    silence there reads as "nothing wrong", which is the mistake this whole
    box exists to prevent.
    """

    course_id: int
    storage_prefix: str
    entry_path: str
    scorm_version: ScormVersion
    file_count: int
    total_bytes: int
    package_version: str | None = None
    reporting_mode: str | None = None
    # How much of the course the driver requires before it reports completion.
    completion_percentage: float | None = None
    # Finishing the surrounding lessons will not complete such a course.
    completes_via_storyline: bool = False
    completion_config_readable: bool = False
    # Declared in the manifest but absent from the archive. A warning only.
    missing_declared_files: list[str] = Field(default_factory=list)


class TrainingPackagePublishResultDto(BaseDto):
    """What a publish put live.

    ``learners_reset`` counts every progress row cleared, finished ones
    included. The publish dialog's "N learners in progress will restart"
    comes from the course's own ``unfinished_count`` instead -- these two
    numbers are different and the smaller one is the honest one to show.
    """

    course_id: int
    package_id: int
    package_version: str | None = None
    learners_reset: int = 0


class TrainingProgressSaveDto(BaseDto):
    """Where the assignment stands after one commit.

    The server decides which lesson_status finishes a course, so it says so
    here rather than leaving the page to judge the same values a second time
    and disagree.
    """

    status: TrainingStatus
    # Whether the course carries its verification stamp, answered only by a
    # commit that reported completion -- the one path that already has the
    # package row in hand. None on every other commit, which is most of them:
    # the heartbeat arrives every twenty seconds and often stores nothing, so
    # it must not grow a query. The trial page needs this because the
    # assignment's own status cannot stand in for it: a verifier re-running a
    # replaced package was already DONE, so their run moves nothing.
    course_verified: bool | None = None


class TrainingCompletionConfigDto(BaseDto):
    """What the stored package says it takes to finish the course.

    Re-read from the package rather than stored on the course row: an
    overwrite would leave a stored copy describing the package it replaced.
    """

    # Whether this package has been run to the end by somebody who could
    # vouch for it. The one answer to "can this be assigned yet" -- an
    # assignment's own status cannot stand in for it, because a verifier
    # re-running a replaced package is still DONE on their row.
    verified: bool = False

    # How much of the course the driver requires before it reports completion.
    completion_percentage: float | None = None
    # Finishing the surrounding lessons will not complete such a course.
    completes_via_storyline: bool = False
    # False for a package built by a toolchain we cannot read. Saying nothing
    # reads as "nothing wrong", which is the mistake this answer prevents.
    completion_config_readable: bool = False


class TrainingProgressDto(BaseDto):
    """The learner's stored CMI state, seeded back into the course.

    Scores are strings, never numbers: a Decimal encoded as a float turns
    82.50 into 82.5, and a course reads back whatever it is handed.
    """

    lesson_status: str | None = None
    lesson_location: str | None = None
    suspend_data: str | None = None
    session_time_seconds: int = 0
    score_raw: str | None = None
    score_min: str | None = None
    score_max: str | None = None


class TrainingSessionDto(BaseDto):
    """Where one learner's course loads from, and what it resumes with.

    ``progress`` is None for an assignment nobody has opened yet, and also
    for a preview, which has no assignment behind it at all.
    """

    content_base_url: str
    # The same token the URL above carries, handed over on its own so the page
    # can name this session on every commit it posts back. That is what lets
    # the server refuse a commit from a tab that opened against a package
    # since replaced.
    session_token: str
    entry_path: str
    player_path: str
    expires_at: int
    progress: TrainingProgressDto | None = None
