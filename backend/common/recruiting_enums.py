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
    """Posting publish state. MVP: draft -> published (-> closed). No review gate."""

    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


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
# PLACEHOLDER — replace with the real designated tech-company domains.
MENTOR_ALLOWED_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {"google.com", "microsoft.com", "amazon.com"}
)
