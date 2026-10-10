from enum import StrEnum

MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE = "mentorship_email_send"


class MentorshipEmailStage(StrEnum):
    """Which stage of the program a send belongs to. Chosen by the admin and
    independent of the Kit draft, since one draft can be reused across stages.
    Stored as a plain string so the list can change without a migration."""

    ROUND_RECRUITMENT = "round_recruitment"
    ADMISSION = "admission"
    ONBOARDING_REMINDER = "onboarding_reminder"
    MATCH_RESULT = "match_result"
    FIRST_CONTACT_REMINDER = "first_contact_reminder"
    MENTOR_CHECK_IN = "mentor_check_in"
    MIDTERM_REMINDER = "midterm_reminder"
    FINAL_FOLLOWUP = "final_followup"
    FEEDBACK_INVITE = "feedback_invite"


class MentorshipEmailNotificationState(StrEnum):
    """Where one stage stands for one person, as the Participants filter asks
    it. Not notified covers everyone Kit has neither sent nor is about to
    send this stage to, including people it could not reach."""

    NOT_NOTIFIED = "not_notified"
    SCHEDULED = "scheduled"
    NOTIFIED = "notified"


class MentorshipEmailSendStatus(StrEnum):
    DRAFT = "draft"
    PREPARING = "preparing"
    FAILED = "failed"
    SCHEDULED = "scheduled"
    SENT = "sent"
    ABORTED = "aborted"
    CANCELLED = "cancelled"

    @classmethod
    def terminal(cls) -> frozenset["MentorshipEmailSendStatus"]:
        return frozenset({cls.SENT, cls.ABORTED, cls.CANCELLED})


class MentorshipEmailFailure(StrEnum):
    """Why a confirmed send was not scheduled; decides what Retry does."""

    DRAFT_CHANGED = "draft_changed"
    DRAFT_TAMPERED = "draft_tampered"
    DRAFT_GONE = "draft_gone"
    COUNT_MISMATCH = "count_mismatch"
    TIME_PASSED = "time_passed"
    NO_RECIPIENTS = "no_recipients"
    KIT_ERROR = "kit_error"


class MentorshipEmailRecipientResult(StrEnum):
    PENDING = "pending"
    HANDED_TO_KIT = "handed_to_kit"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    IMPORT_FAILED = "import_failed"

    @classmethod
    def unreachable(cls) -> frozenset["MentorshipEmailRecipientResult"]:
        return frozenset({cls.UNSUBSCRIBED, cls.BOUNCED, cls.IMPORT_FAILED})
