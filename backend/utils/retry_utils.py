from tenacity import (
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    AsyncRetrying,
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

    def execute_pipeline(self, pipeline) -> list:
        """
        Executes a Redis pipeline, retrying transient errors with its commands intact.

        Do not pass ``pipeline.execute`` to ``get_retry_on_transient``: redis-py
        empties the command stack when ``execute`` finishes, failed or not, so a
        retry replays an empty pipeline and answers ``[]`` without sending
        anything. This puts the queued commands back before every attempt.

        Args:
            pipeline: A redis-py pipeline with its commands queued.

        Returns:
            list: What ``pipeline.execute()`` returned on the attempt that succeeded.
        """
        queued = list(pipeline.command_stack)

        def attempt():
            pipeline.command_stack = list(queued)
            return pipeline.execute()

        return self._retry_on_transient(attempt)

    @property
    def get_async_retry_on_transient(self) -> AsyncRetrying:
        """
        Returns a Tenacity AsyncRetrying instance configured for transient errors.
        Use with `async with` for awaitable callables.
        Retries up to 3 times with exponential backoff, excluding `ValueError`.
        """
        return AsyncRetrying(
            retry=retry_if_exception(lambda e: not isinstance(e, ValueError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=3),
            reraise=True,
        )
