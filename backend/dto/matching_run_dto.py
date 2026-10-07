"""What the matching run endpoints answer, serialised in camelCase like the rest."""

from backend.common.mentorship_enums import MatchingRunStatus
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto


class NamedUserDto(BaseDto):
    """A user id as a run carries it, with a display name when one resolved."""

    user_id: str
    name: str | None = None


class MatchingRunStartedDto(BaseDto):
    run_id: str


class MatchingEditLockDto(BaseDto):
    """Who is editing a run's result, and until when unless they renew."""

    user_id: str
    name: str | None = None
    expires_at: str


class MatchingMentorSlotsDto(BaseDto):
    user_id: str
    name: str | None = None
    slots: int
    assigned: int


class MatchingProblemDto(BaseDto):
    """Something in the way of publishing. ``code`` says which fields are set:
    over_slots has mentor, assigned and slots; reason_too_long and no_reason
    have mentee."""

    code: str
    mentor: NamedUserDto | None = None
    mentee: NamedUserDto | None = None
    assigned: int | None = None
    slots: int | None = None


class MatchingPublishRequestDto(BaseDto):
    """The request to publish this run that is waiting for a decision."""

    request_id: int
    reviewer: NamedUserDto
    raised_by: NamedUserDto
    reason: str | None = None
    created_at: str


class MatchingPublishRejectionDto(BaseDto):
    """Why the last request to publish this run was turned down."""

    comment: str | None = None
    decided_by: NamedUserDto
    decided_at: str | None = None


class MatchingRunOverviewDto(BaseDto):
    """A round's most recent run. Which fields are set depends on ``status``."""

    status: MatchingRunStatus
    run_id: str | None = None
    started_at: str | None = None
    input_written_at: str | None = None
    finished_at: str | None = None
    triggered_by_user_id: str | None = None
    triggered_by_name: str | None = None
    mentor_count: int | None = None
    mentee_count: int | None = None
    matcher_version: str | None = None
    run_date: str | None = None
    error: str | None = None
    matched_count: int | None = None
    unmatched_count: int | None = None
    unmatched_mentors: list[NamedUserDto] = []
    edit_lock: MatchingEditLockDto | None = None
    draft_count: int | None = None
    mentor_slots: list[MatchingMentorSlotsDto] = []
    problems: list[MatchingProblemDto] = []
    publish_request: MatchingPublishRequestDto | None = None
    last_publish_rejection: MatchingPublishRejectionDto | None = None


class MatchingEducationDto(BaseDto):
    degree: str = ""
    school: str = ""
    field_of_study: str = ""
    start_date: str | None = None
    end_date: str | None = None


class MatchingWorkHistoryDto(BaseDto):
    title: str = ""
    company: str = ""
    start_date: str | None = None
    end_date: str | None = None
    is_current_job: bool = False


class MatchingProfileDto(BaseDto):
    """A person as the run was given them. ``skills`` and
    ``specific_industry`` keep their keys as the matcher's codes."""

    user_id: str
    timezone: str = ""
    goal: str = ""
    skills: dict[str, bool] = {}
    education: list[MatchingEducationDto] = []
    work_history: list[MatchingWorkHistoryDto] = []
    specific_industry: dict[str, bool] | None = None
    max_partners: int | None = None
    career_transition: str | None = None
    career_transition_other: str | None = None
    development_region: str | None = None
    development_region_other: str | None = None
    external_mentoring_exp: str | None = None
    mentorship_rounds_participated: int | None = None
    mentorship_rounds_completed: int | None = None
    transition_type: str | None = None
    transition_type_other: str | None = None
    urgency: str | None = None
    job_market_region: str | None = None
    job_market_region_other: str | None = None
    mentee_stage: str | None = None
    expected_partners: list[NamedUserDto] = []
    unexpected_partners: list[NamedUserDto] = []


class MatchingCandidateDto(BaseDto):
    user_id: str
    name: str | None = None
    score: int


class MatchingResultItemDto(BaseDto):
    """One mentee's outcome."""

    mentee: NamedUserDto
    mentor: NamedUserDto | None = None
    score: int | None = None
    match_type: str | None = None
    recommendation_reason: str = ""
    diagnostic_reason: str = ""
    candidates: list[MatchingCandidateDto] = []
    mentee_profile: MatchingProfileDto | None = None
    mentor_profile: MatchingProfileDto | None = None
    edited: bool = False
    matcher_mentor: NamedUserDto | None = None
    matcher_reason: str = ""


class MatchingUnmatchedItemDto(BaseDto):
    """Somebody the run left without a partner. A mentor carries no
    diagnostic reason or candidates."""

    person: NamedUserDto
    role: str
    profile: MatchingProfileDto | None = None
    diagnostic_reason: str = ""
    candidates: list[MatchingCandidateDto] = []
    edited: bool = False
    matcher_mentor: NamedUserDto | None = None
    matcher_reason: str = ""
    recommendation_reason: str = ""


class MatchingUnmatchedPageDto(BaseDto):
    status: MatchingRunStatus
    total: int = 0
    items: list[MatchingUnmatchedItemDto] = []


class MatchingResultsPageDto(BaseDto):
    status: MatchingRunStatus
    matched_count: int = 0
    unmatched_count: int = 0
    total: int = 0
    items: list[MatchingResultItemDto] = []


class MatchingDraftChangeDto(BaseRequestDto):
    """One mentee as the admin left them; ``mentor_id`` None means nobody."""

    mentee_id: str
    mentor_id: str | None = None
    recommendation_reason: str = ""


class MatchingDraftChangesDto(BaseRequestDto):
    changes: list[MatchingDraftChangeDto]


class MatchingDraftSavedDto(BaseDto):
    draft_count: int
