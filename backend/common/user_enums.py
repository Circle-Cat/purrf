from enum import StrEnum


class BlockRequestStatus(StrEnum):
    """Lifecycle of one block request.

    SUPERSEDED is not a decision: it is what happens when an operator blocks
    the target directly while a request is still pending. The request is
    closed because its outcome already happened, not because anyone judged it.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


# Event types whose subject is a user. Registered separately from the
# recruiting ones: resolve_recipients raises ValueError when an event's
# subject_type does not match its resolver's, and RecruitingEvent.BLACKLISTED
# is registered under subject_type="application".
USER_SUBJECT_TYPE = "user"


class UserEvent(StrEnum):
    """user-subject event types. See user_recipient_resolvers for who is told."""

    BLOCK_REQUESTED = "user.block_requested"
    BLOCK_REQUEST_REASSIGNED = "user.block_request_reassigned"
    BLOCK_REQUEST_DECIDED = "user.block_request_decided"
    BLOCKED = "user.blocked"
    UNBLOCKED = "user.unblocked"
    DEACTIVATED = "user.deactivated"
    REACTIVATED = "user.reactivated"
