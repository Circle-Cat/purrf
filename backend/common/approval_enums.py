from enum import StrEnum


class ApprovalRequestStatus(StrEnum):
    """Lifecycle of one approval request, whatever it asks for.

    WITHDRAWN is the raiser taking back a request nobody has decided yet.
    SUPERSEDED is not a decision either: the outcome was brought about
    directly while the request was still pending, so the request is closed
    without anyone judging it.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
