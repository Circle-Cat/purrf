from enum import Enum, StrEnum


class UserType(StrEnum):
    """Distinguishes internal members from external candidates on users.user_type."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class JobKind(StrEnum):
    """Posting kind. MVP only creates ACTIVITY (mentorship) postings."""

    EMPLOYMENT = "employment"
    ACTIVITY = "activity"


class JobStatus(StrEnum):
    """Posting publish state, gated by review.

    Lifecycle: draft -> pending_review -> published (-> closed). An edit to a
    published posting's form/pipeline parks it in published_pending_revision
    (the live version stays public) until the revision is approved.

    Closing a published posting requires a review: published -> pending_close ->
    closed. Reopening a closed posting also requires a review: closed ->
    pending_reopen -> published.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    CLOSED = "closed"
    PUBLISHED_PENDING_REVISION = "published_pending_revision"
    PENDING_CLOSE = "pending_close"
    PENDING_REOPEN = "pending_reopen"


# Statuses at which a posting is live to candidates: it shows on the browse
# list, its detail page resolves, and it accepts applications. A posting whose
# revision or close is still under review keeps serving its last approved
# version, so it stays live until the reviewer decides. PENDING_REVIEW and
# PENDING_REOPEN are not live -- neither has an approved version on offer.
PUBLICLY_VISIBLE_JOB_STATUSES: frozenset[JobStatus] = frozenset({
    JobStatus.PUBLISHED,
    JobStatus.PUBLISHED_PENDING_REVISION,
    JobStatus.PENDING_CLOSE,
})


class JobReviewStatus(StrEnum):
    """State of a single job-review request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class JobReviewKind(StrEnum):
    """The gate a review covers: first publication, a later revision, or lifecycle transitions."""

    INITIAL = "initial"
    REVISION = "revision"
    CLOSE = "close"
    REOPEN = "reopen"


class ApplicationStage(StrEnum):
    """Full application lifecycle stage set (data-flow.md §0.3).

    The full set is created up front to avoid a later enum migration; the
    mentorship dogfood MVP only ever sets RECRUITER_SCREENING (on submit),
    HIRED, and REJECTED.
    """

    APPLIED = "applied"
    RECRUITER_SCREENING = "recruiter_screening"
    BEHAVIORAL = "behavioral"
    TECH = "tech"
    BOARD_REVIEW = "board_review"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"
    BLACKLISTED = "blacklisted"


class ApplicationLockReason(StrEnum):
    """Why a candidate can no longer edit their own application.

    ADVANCED and IN_REVIEW are about the application; CLOSED is about the
    posting it was made to, which stops taking submissions of any kind once
    it leaves ``PUBLICLY_VISIBLE_JOB_STATUSES``.

    IN_REVIEW covers two conditions, though: a sub_status the recruiter has
    moved on and a frozen submission are the same fact to the candidate --
    someone has started work -- and telling them apart would publish
    internal mechanics that change nothing the reader can do.

    The candidate-facing wording lives in the frontend glossary, not here,
    because the ADVANCED sentence names the stage and only the glossary holds
    stage labels. ``tests/shared/application_lock_reasons.json`` pins this set
    so a member added here without wording turns the frontend red.
    """

    ADVANCED = "advanced"
    IN_REVIEW = "in_review"
    CLOSED = "closed"


# Work-email domains whose holders are auto-approved as mentors (lowercased, no "@").
# Add Google subsidiaries (e.g. "youtube.com", "deepmind.com") here if they should qualify.
MENTOR_ALLOWED_EMAIL_DOMAINS: frozenset[str] = frozenset({"google.com"})


class RecruitingEvent(StrEnum):
    """Every recruiting event type that may be recorded on the event log.

    The catalogue exists so a type cannot be misspelled: a write site naming
    a member that does not exist fails at import, where a bare string would
    record the event and then resolve to nobody -- indistinguishable from a
    type that deliberately notifies no one.

    Membership here says nothing about notifications. Which types have
    recipients is decided by what registers a resolver in
    ``recipient_registry``; the four below that no resolver claims belong on
    the timeline and notify nobody, by design rather than by omission.
    """

    APPLICATION_SUBMITTED = "recruiting.application_submitted"
    AUTO_REJECTED = "recruiting.auto_rejected"
    BLACKLISTED = "recruiting.blacklisted"
    STAGE_CHANGED = "recruiting.stage_changed"
    ROUND_ADVANCED = "recruiting.round_advanced"
    REASSIGNED = "recruiting.reassigned"
    AUTO_ASSIGNED = "recruiting.auto_assigned"
    SUB_STATUS_CHANGED = "recruiting.sub_status_changed"
    EVALUATION_CONFIRMED = "recruiting.evaluation_confirmed"
    INTERVIEW_SCHEDULED = "recruiting.interview_scheduled"
    INTERVIEW_UPDATED = "recruiting.interview_updated"
    INTERVIEW_CANCELLED = "recruiting.interview_cancelled"
    REVIEW_OPENED = "recruiting.review_opened"
    REVIEW_DECIDED = "recruiting.review_decided"
    MENTIONED = "recruiting.mentioned"

    EMAIL_SENT = "recruiting.email_sent"
    EMAIL_RECEIVED = "recruiting.email_received"
    JOB_CREATED = "recruiting.job_created"
    PENDING_EDIT_DISCARDED = "recruiting.pending_edit_discarded"


class NotificationStatus(str, Enum):
    """Where a notification's email is in its delivery lifecycle.

    ``FAILED`` and ``EXPIRED`` are deliberately distinct: FAILED means this
    row can never succeed (no address on file, template blew up), EXPIRED
    means it could still succeed but no longer matters. Collapsing them
    loses the answer to "why did this never arrive".
    """

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    EXPIRED = "expired"
