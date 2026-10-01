class ConflictError(Exception):
    """Domain conflict — mapped to HTTP 409 Conflict.

    ``code`` is for a page that has to tell two conflicts on the same route
    apart and give different advice for each. The message is prose meant for
    a person, and branching on its wording would break the first time
    somebody rewords it.
    """

    def __init__(self, message: str = "", *, code: str | None = None):
        super().__init__(message)
        self.code = code


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
