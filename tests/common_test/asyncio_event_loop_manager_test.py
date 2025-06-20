import asyncio
from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from src.common.asyncio_event_loop_manager import AsyncioEventLoopManager


class TestAsyncioEventLoopManager(TestCase):
    def setUp(self):
        AsyncioEventLoopManager._instance = None

    def tearDown(self):
        if AsyncioEventLoopManager._instance:
            AsyncioEventLoopManager._instance.stop_loop()
        AsyncioEventLoopManager._instance = None

    def test_singleton_behavior(self):
        inst1 = AsyncioEventLoopManager()
        inst2 = AsyncioEventLoopManager()
        self.assertIs(inst1, inst2)

    def test_get_loop_creates_and_starts_loop(self):
        mgr = AsyncioEventLoopManager()
        loop = mgr.get_loop()
        self.assertIsInstance(loop, asyncio.AbstractEventLoop)
        self.assertTrue(mgr._thread.is_alive())

    def test_stop_loop_stops_and_cleans_up(self):
        mgr = AsyncioEventLoopManager()
        loop = mgr.get_loop()
        self.assertTrue(loop.is_running())

        mgr.stop_loop()

        self.assertIsNone(mgr._loop)
        self.assertIsNone(mgr._thread)

    def test_run_async_in_background_loop_success(self):
        mgr = AsyncioEventLoopManager()

        async def sample():
            return "hello"

        result = mgr.run_async_in_background_loop(sample())
        self.assertEqual(result, "hello")

    def test_run_async_in_background_loop_type_error(self):
        mgr = AsyncioEventLoopManager()

        with self.assertRaises(TypeError):
            mgr.run_async_in_background_loop("not-a-coro")

    @patch.object(AsyncioEventLoopManager, "get_loop")
    def test_run_async_in_background_loop_runtime_error_if_loop_not_running(
        self, mock_get_loop
    ):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_get_loop.return_value = mock_loop

        mgr = AsyncioEventLoopManager()

        async def coro():
            return 1

        with self.assertRaises(RuntimeError):
            mgr.run_async_in_background_loop(coro())

    def test_run_async_in_background_loop_propagates_exception(self):
        mgr = AsyncioEventLoopManager()

        async def faulty():
            raise ValueError("oops")

        with self.assertRaises(ValueError) as context:
            mgr.run_async_in_background_loop(faulty())

        self.assertIn("oops", str(context.exception))


if __name__ == "__main__":
    main()
