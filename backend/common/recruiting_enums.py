from enum import StrEnum


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
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    CLOSED = "closed"
    PUBLISHED_PENDING_REVISION = "published_pending_revision"


class JobReviewStatus(StrEnum):
    """State of a single job-review request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class JobReviewKind(StrEnum):
    """Whether a review gates first publication or a later revision."""

    INITIAL = "initial"
    REVISION = "revision"


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
    OFFER_DECLINED = "offer_declined"
    BLACKLISTED = "blacklisted"


# Work-email domains whose holders are auto-approved as mentors (lowercased, no "@").
# Add Google subsidiaries (e.g. "youtube.com", "deepmind.com") here if they should qualify.
MENTOR_ALLOWED_EMAIL_DOMAINS: frozenset[str] = frozenset({"google.com"})
