from enum import StrEnum


class GuideProgressStatus(StrEnum):
    """Where one user stands with one onboarding guide.

    No row at all means the user has never been shown the guide. ``SNOOZED``
    is closing it for now, and it comes back on a later visit until the
    user has snoozed it often enough to count as ``DISMISSED``. ``COMPLETED``
    and ``DISMISSED`` are both final: the guide is not offered again.
    """

    COMPLETED = "completed"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
