"""Helpers for reading `mentorship_pairs.meeting_log`.

The column holds two generations of meeting records under separate keys:
`meeting_time_list` for manually submitted meetings (v1) and `google_meetings`
for Purrf-created Google Meet meetings (v2). Which generation a user is on is
decided by feature flag, and a pair is not meant to hold both -- but that is an
operational guarantee, not one the code enforces, so anything derived from the
log reads both keys rather than assuming which one is populated.
"""

# The two keys under `meeting_log` that hold meeting entries.
MEETING_LIST_KEYS = ("meeting_time_list", "google_meetings")


def completed_count(meeting_log: dict | None) -> int:
    """
    Count the completed meetings recorded in a pair's meeting log.

    This is the single source of truth for `mentorship_pairs.completed_count`,
    which is a denormalized cache: it is summed per round in SQL and projected
    into participant search without loading the JSONB, so it cannot simply be
    computed at read time. Every writer of that column should call this.

    Args:
        meeting_log (dict | None): The pair's `meeting_log` value. Anything that
            is not a dict is treated as empty.

    Returns:
        int: Number of entries across both generations whose `is_completed` is truthy.
    """
    if not isinstance(meeting_log, dict):
        return 0
    return sum(
        1
        for key in MEETING_LIST_KEYS
        for entry in meeting_log.get(key) or []
        if isinstance(entry, dict) and entry.get("is_completed")
    )
