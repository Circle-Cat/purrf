from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    Retrying,
)


class RetryUtils:
    """
    A utility class that provides pre-configured Tenacity retry instances.
    """

    def __init__(self):
        self._retry_on_transient = Retrying(
            retry=retry_if_exception(lambda e: not isinstance(e, ValueError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=3),
            reraise=True,
        )

    @property
    def get_retry_on_transient(self) -> Retrying:
        """
        Returns a Tenacity Retrying instance configured for transient errors.
        This instance will retry up to 3 times with exponential backoff,
        excluding `ValueError` from the retry conditions.
        """
        return self._retry_on_transient
