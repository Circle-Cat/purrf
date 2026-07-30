class ConflictError(Exception):
    """Domain conflict — mapped to HTTP 409 Conflict."""


class RateLimitedError(Exception):
    """Rate limit exceeded — mapped to HTTP 429 Too Many Requests."""


class MeetingGoneError(Exception):
    """The Calendar event we tried to modify no longer exists.

    Distinct from a transport failure: the caller cannot fix this by
    retrying, only by dropping its stored event id and booking again.
    Deleting an absent event is fine (the end state is what matters), but
    *patching* one must not silently pretend to have succeeded — the stored
    time would drift from a calendar that has no such meeting.
    """
