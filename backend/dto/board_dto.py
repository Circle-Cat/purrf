"""Board-facing DTOs for the recruiting application board.

Holds the projections the board surfaces (job switcher entries, applicant
cards).
"""

from datetime import datetime

from pydantic import field_validator, model_validator

from backend.dto.application_dto import ApplicationDto
from backend.dto.evaluation_dto import EvaluationDto
from backend.dto.interview_dto import InterviewDto
from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import ApplicationStage, JobKind

# Fixed reject-reason list surfaced by the board's reject dialog. A reject
# stage change must supply one of these (see StageChangeDto's validator).
REJECT_REASONS = (
    "Insufficient experience",
    "Did not meet the technical bar",
    "Communication concerns",
    "Not aligned with our mission",
    "Accepted another offer",
    "Incomplete application",
    "Candidate declined the offer",
    "Other",
)


class PipelineStageInfoDto(BaseDto):
    """One of a job's configured pipeline stages, for the board's lane list."""

    stage: str
    rounds: int


class BoardJobDto(BaseDto):
    """A job the caller owns, for the board's job switcher."""

    id: int
    title: str
    kind: JobKind
    stages: list[PipelineStageInfoDto]  # configured stages + rounds, in global order


class BoardCardDto(BaseDto):
    """One applicant card on the board."""

    id: int  # application id
    applicant_name: str
    applicant_email: str
    stage: ApplicationStage
    sub_status: str | None = None
    tags: dict | None = None
    applied_at: datetime | None = None
    round: int = 1
    # Whether the applicant is CURRENTLY blocked org-wide (distinct from
    # tags["blacklisted"], which just records that this application was
    # rejected by a blacklist action at some point and never changes after).
    is_blocked: bool = False
    # The interviewer responsible for this card's current stage+round, for
    # interview-stage cards only (None for e.g. applied/offer/hired/rejected
    # — the board never renders a reviewer line for those). None also means
    # "nobody assigned yet" for an interview-stage card.
    reviewer_name: str | None = None


class BoardApplicantHitDto(BaseDto):
    """One hit in the board's applicant search.

    Deliberately NOT a ``BoardCardDto``: that projection carries ``tags``,
    ``is_blocked`` and ``reviewer_name``, each costing extra queries in
    ``BoardService._cards_for_rows``, and a search result row renders none of
    them. It carries ``job_title``/``job_kind`` instead, which a card doesn't
    need (the board already knows its job) but a cross-posting result list
    does — ``job_kind`` is what lets the frontend label an activity job's
    ``hired`` as "Admitted".
    """

    application_id: int
    applicant_name: str
    applicant_email: str
    job_id: int
    job_title: str
    job_kind: JobKind
    stage: ApplicationStage
    applied_at: datetime | None = None


class ApplicationDetailDto(BaseDto):
    """Owner-facing full view of one application."""

    application: ApplicationDto
    applicant_name: str
    applicant_email: str
    resume_available: bool
    form_schema: dict | None = (
        None  # the job's LIVE form_schema, so the dialog can label answers
    )
    # Role signals for the shared detail page: lets
    # the frontend decide which of the owner-decision area / evaluator-rubric
    # area to render, without a second round-trip.
    is_owner: bool = False
    # Whether the caller may view the owner-facing info panel at all — true
    # for a real owner or a RECRUITING_APPLICATION_READ_ALL holder. Distinct
    # from is_owner: a read.all viewer sees everything owners see, minus any
    # actionable control (those still gate on is_owner specifically).
    can_view: bool = False
    assignee_id: int | None = None
    interview: InterviewDto | None = None
    # The CALLER's IANA zone from their profile, for rendering the interview's
    # UTC instants as local wall clock. Per-request, not per-meeting: no zone is
    # stored alongside a meeting (see ApplicationInterviewEntity). None when the
    # viewer has set none, in which case the frontend falls back to their
    # browser zone.
    viewer_timezone: str | None = None


class ApplicationActivityDto(BaseDto):
    """One entry in an application's owner-facing audit timeline, newest first.

    ``event_type`` is the recorded event's own type, domain prefix included:
    ``"recruiting.application_submitted"``, ``"recruiting.auto_rejected"``
    (both recorded by ``ApplicationService.submit``), or
    ``"recruiting.stage_changed"``, ``"recruiting.reassigned"``,
    ``"recruiting.round_advanced"`` (recorded by the matching
    ``BoardService`` methods). ``details`` is a free-form, event-type-specific
    payload — see each writer's call site for its exact shape.

    ``actor_id`` is null when the system did it under its own rules rather
    than on someone's behalf; ``actor_name`` is null with it, and the reader
    words those entries impersonally. An actor who no longer resolves falls
    back to ``"User {id}"``, which is a different thing from nobody.
    """

    id: int
    event_type: str
    details: dict
    actor_id: int | None
    actor_name: str | None
    created_at: datetime


class StageChangeDto(BaseRequestDto):
    """Advance or reject one application."""

    to_stage: ApplicationStage
    reason: str | None = None
    note: str | None = None
    # Required when to_stage is an interview stage (screening/behavioral/
    # tech/board_review); ignored for terminal targets (hired/rejected).
    assignee_id: int | None = None
    # Opt in to cancelling the meeting booked on the stage+round being LEFT,
    # which the UI can no longer reach once the application has moved on (see
    # BoardService.change_stage). Defaults to False so a client that says
    # nothing about the meeting never deletes a candidate's calendar invite by
    # accident; the board's own dialogs default the checkbox to ticked.
    cancel_interview: bool = False

    @model_validator(mode="after")
    def reason_required_for_reject(self) -> "StageChangeDto":
        """Reject moves must carry a reason from the fixed REJECT_REASONS list."""
        if self.to_stage == ApplicationStage.REJECTED:
            if self.reason not in REJECT_REASONS:
                raise ValueError("a reject reason from the fixed list is required")
        return self


class SubStatusChangeDto(BaseRequestDto):
    """Manual sub-status switch within the current stage."""

    sub_status: str


class ReassignDto(BaseRequestDto):
    """Change who is responsible for an application's current stage."""

    assignee_id: int


class RoundChangeDto(BaseRequestDto):
    """Advance an application to a specific round within its current stage."""

    round: int
    # Optional even for an interview stage (INTERVIEW_STAGES in
    # board_service.py) -- a round can be left unassigned, to be picked up
    # later via reassign. Ignored entirely for a non-interview stage, e.g.
    # a multi-round OFFER stage, which has no rubric and is not assignable.
    assignee_id: int | None = None
    # Same opt-in as StageChangeDto's, for the round being left behind.
    # Ignored when `round` equals the application's current round, since then
    # no round is left behind at all.
    cancel_interview: bool = False

    @field_validator("round")
    @classmethod
    def round_positive(cls, v: int) -> int:
        """Require at least round 1.

        Args:
            v (int): The candidate round number.

        Returns:
            int: The validated round number.

        Raises:
            ValueError: If less than 1.
        """
        if v < 1:
            raise ValueError("round must be >= 1")
        return v


class UpcomingInterviewDto(BaseDto):
    """One still-to-happen interview meeting a blacklist is about to cancel.

    Read-only pre-flight for the confirm dialog (see
    ``BoardService.list_upcoming_interviews_for_user``), so it carries only
    what identifies the meeting to a human: which posting, which step, and
    when. No zone: the dialog renders ``start_at`` in the READER's own zone,
    like every other interview time (see ``ApplicationDetailDto``'s
    ``viewer_timezone``). The interviewer's name is deliberately left out too —
    resolving it would cost another user lookup for a warning list nobody acts
    on per-row.
    """

    application_id: int
    job_title: str
    stage: ApplicationStage
    round: int
    start_at: datetime


class BlacklistDto(BaseRequestDto):
    """Block a user org-wide and close out the triggering application."""

    user_id: int
    application_id: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        """A blacklist action must always carry a non-empty reason."""
        if not value.strip():
            raise ValueError("a reason is required")
        return value


class MentionedUserDto(BaseDto):
    """One user @-mentioned in a comment, or eligible to be."""

    user_id: int
    name: str


class CommentDto(BaseDto):
    """One free-text comment on an application, newest first.

    Independent of ApplicationActivityDto -- this is discussion, not the
    audit log. Readable/writable by an owner or the application's
    current-stage assignee (BoardService.list_comments/add_comment).
    """

    id: int
    application_id: int
    author_id: int
    author_name: str
    body: str
    created_at: datetime
    mentions: list[MentionedUserDto] = []


class OtherApplicationDto(BaseDto):
    """One of a candidate's other applications, for the cross-posting
    aggregation view surfaced on the shared application detail page.

    Returned in full (submission snapshot + every evaluation row) to any
    caller who already passed the entry gate on the application they're
    currently viewing — see BoardService.get_other_applications. ``activity``
    and ``comments`` are the exception: they're populated only for an
    owner/read.all caller (an assignee-only caller gets empty lists), since
    the timeline is an owner-facing audit view an assignee can't read even
    on the application they're grading. ``job_kind`` lets the frontend
    label stages for the entry's OWN job (activity: hired -> "Admitted"),
    which may differ in kind from the job being viewed.

    ``emails_visible`` follows the same owner/``read.all`` rule as
    ``activity``/``comments``: past correspondence is owner-facing history
    about the candidate, like the résumé and the timeline the same entry
    already carries. It holds no message bodies -- they would bloat a
    payload fetched eagerly for every row -- so it only tells the frontend
    whether to offer a read-only Emails tab, which fetches the threads from
    the emails endpoint when opened.
    """

    application: ApplicationDto
    job_title: str
    job_kind: JobKind
    resume_available: bool
    emails_visible: bool = False
    # That job's LIVE form_schema — these applications belong to *other*
    # postings, so the detail page's own schema cannot label their answers.
    # Only a fallback: submissions written after the snapshot change carry
    # their own schema inside `application.current.submission`.
    form_schema: dict | None = None
    evaluations: list[EvaluationDto]
    activity: list[ApplicationActivityDto] = []
    comments: list[CommentDto] = []


class ApplicationAggregateDto(BaseDto):
    """Candidate-wide aggregation for the application detail page: the
    candidate's applications to OTHER jobs, plus their PRIOR attempts on the
    same job (newest first) — the currently-viewed application appears in
    neither list. Same entry shape and visibility rule for both lists (see
    BoardService.get_other_applications)."""

    other_jobs: list[OtherApplicationDto]
    previous_same_job: list[OtherApplicationDto]


class CommentCreateDto(BaseRequestDto):
    """Post a free-text comment on an application."""

    body: str

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        """A comment must carry non-blank text, capped at a sane length."""
        if not value.strip():
            raise ValueError("comment text is required")
        if len(value) > 4000:
            raise ValueError("comment text must be 4000 characters or fewer")
        return value
