class ConflictError(Exception):
    """Domain conflict — mapped to HTTP 409 Conflict."""


class RateLimitedError(Exception):
    """Rate limit exceeded — mapped to HTTP 429 Too Many Requests."""
