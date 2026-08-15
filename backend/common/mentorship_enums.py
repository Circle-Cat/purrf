from enum import Enum, StrEnum


class ApprovalStatus(str, Enum):
    SIGNED_UP = "signed_up"
    MATCHED = "matched"
    UN_MATCHED = "un_matched"
    REJECTED = "rejected"


class MatchStatus(str, Enum):
    """Enumeration of match statuses returned to the frontend"""

    UNREGISTERED = "unregistered"  # User has not signed up for the round
    PENDING = "pending"  # Signed up, but matching process has not started
    MATCHED = "matched"  # Successfully matched with partner(s)
    UNMATCHED = "unmatched"  # Matching process finished but no partner found
    REJECTED = "rejected"  # Application to participate was denied
    UNKNOWN = "unknown"  # Fallback for undefined internal states


class CommunicationMethod(str, Enum):
    EMAIL = "email"
    GOOGLE_CHAT = "google_chat"


class Degree(str, Enum):
    ASSOCIATE = "Associate"
    BACHELOR = "Bachelor"
    MASTER = "Master"
    DOCTORATE = "Doctorate"
    PROFESSIONAL = "Professional"


class PairStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MentorActionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class MenteeActionStatus(str, Enum):
    PENDING = "pending"
    TIME_PROPOSED = "time_proposed"
    CONFIRMED = "confirmed"


class MentorshipEvent(StrEnum):
    """Every mentorship event type that may be recorded on the event log.

    Same catalogue rule as ``RecruitingEvent``: a write site naming a member
    that does not exist fails at import, where a bare string would record the
    event and then resolve to nobody.
    """

    MENTOR_ADMITTED = "mentorship.mentor_admitted"


class ParticipantRole(Enum):
    MENTOR = "mentor"
    MENTEE = "mentee"


MEETING_SUMMARY_TEMPLATE = "Circlecat Mentorship - {current_user_name} / {partner_name}"


class TrainingCategory(str, Enum):
    MENTORSHIP_MENTEE_ONBOARDING = "mentorship_mentee_onboarding"
    MENTORSHIP_MENTOR_ONBOARDING = "mentorship_mentor_onboarding"
    RESIDENCY_PROGRAM_ONBOARDING = "residency_program_onboarding"
    CORPORATE_CULTURE_COURSE = "corporate_culture_course"


# Training categories used to identify a mentorship user.
MENTORSHIP_ONBOARDING_CATEGORIES: frozenset[TrainingCategory] = frozenset({
    TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
    TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
})


class TrainingStatus(str, Enum):
    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class MeetingNoteTag(str, Enum):
    INSUFFICIENT_DURATION = "insufficient_duration"
    UNKNOWN_ABSENT = "unknown_absent"
    MENTOR_ABSENT = "mentor_absent"
    MENTEE_ABSENT = "mentee_absent"
    UNKNOWN_LATE = "unknown_late"
    MENTOR_LATE = "mentor_late"
    MENTEE_LATE = "mentee_late"


class MeetingSource(str, Enum):
    """Where a mentorship meeting record came from.

    MANUAL entries are self-reported by the mentee. GOOGLE entries are Calendar
    events Purrf created, whose completion is decided by the attendance sweep
    rather than by a participant.

    LEGACY entries stand in for historical rounds that recorded only a
    completed-meeting count and no meetings at all. They carry no times,
    because none were ever recorded -- inventing one would surface in the admin
    log as a precise time and would pollute any statistic over meeting times.
    They exist so that `completed_count` equals the number of completed rows
    for every pair without exception, which is what makes recomputing that
    column safe everywhere instead of a rule someone has to remember.
    """

    MANUAL = "manual"
    GOOGLE = "google"
    LEGACY = "legacy"
