import asyncio
import threading
from src.common.logger import get_logger

logger = get_logger()


class AsyncioEventLoopManager:
    """
    A thread-safe singleton manager for running a persistent background asyncio event loop.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """
        Create or return the singleton instance of the AsyncioEventLoopManager.

        Returns:
            AsyncioEventLoopManager: The singleton instance.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_loop()
            return cls._instance

    def _init_loop(self):
        """
        Initialize internal loop state.
        """
        self._loop = None
        self._thread = None
        self._loop_lock = threading.Lock()

    def _run_loop(self):
        """
        Internal target function for the loop thread.
        Sets and runs the asyncio event loop forever.
        """
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def get_loop(self):
        """
        Get or start the background asyncio event loop.

        If the loop does not exist or the managing thread has stopped,
        it creates a new event loop and runs it in a dedicated daemon thread.

        Returns:
            asyncio.AbstractEventLoop: The running background asyncio loop.
        """
        with self._loop_lock:
            if self._loop is None or not self._thread.is_alive():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
            return self._loop

    def stop_loop(self):
        """
        Stop the background event loop and clean up resources.

        If the loop is running, it safely stops the loop,
        waits for the thread to terminate, and then closes the loop.
        """
        with self._loop_lock:
            if self._loop is None:
                return
            try:
                if self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
                    self._thread.join(timeout=5)
            except Exception as e:
                logger.warning(f"Failed to stop event loop safely: {e}")
            finally:
                try:
                    self._loop.close()
                except Exception as close_err:
                    logger.warning(f"Failed to close event loop: {close_err}")
                self._loop = None
                self._thread = None

    def run_async_in_background_loop(self, coro):
        """
        Run an async coroutine in the background asyncio event loop from a synchronous context.

        This method will block the calling thread for a maximum of 2 seconds waiting for the coroutine to complete.

        Args:
            coro (Coroutine): The async coroutine to run.

        Returns:
            Any: The result returned by the coroutine.

        Raises:
            RuntimeError: If the background event loop is not available.
            TimeoutError: If the coroutine does not complete within 2 seconds.
            Exception: Reraises exceptions raised during coroutine execution.
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError("Expected a coroutine object, got: {}".format(type(coro)))

        loop = self.get_loop()
        if not loop or not loop.is_running():
            logger.error("Background event loop not available. Cannot run async task.")
            raise RuntimeError("Background event loop not available.")

        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            result = future.result(timeout=2)
            return result
        except Exception as e:
            logger.error(
                f"Exception occurred in background async task: {e}", exc_info=True
            )
            raise
