from unittest import TestCase, main

from redis.exceptions import ResponseError

from backend.common.exceptions import ActivityDataUnavailableError
from backend.internal_activity_service.pipeline_results import (
    checked_pipeline_results,
)


class TestCheckedPipelineResults(TestCase):
    def test_returns_results_when_every_command_answered(self):
        results = [1, {}, None, set()]

        self.assertIs(checked_pipeline_results(results, 4), results)

    def test_empty_pipeline_is_fine(self):
        self.assertEqual(checked_pipeline_results([], 0), [])

    def test_short_result_raises(self):
        with self.assertRaises(ActivityDataUnavailableError) as ctx:
            checked_pipeline_results([1, 2], 3)

        self.assertIn("2", str(ctx.exception.detail))
        self.assertIn("3", str(ctx.exception.detail))

    def test_long_result_raises(self):
        with self.assertRaises(ActivityDataUnavailableError):
            checked_pipeline_results([1, 2, 3], 2)

    def test_none_result_raises(self):
        with self.assertRaises(ActivityDataUnavailableError):
            checked_pipeline_results(None, 1)

    def test_exception_in_results_raises(self):
        with self.assertRaises(ActivityDataUnavailableError) as ctx:
            checked_pipeline_results([1, ResponseError("OOM")], 2)

        self.assertIn("OOM", ctx.exception.detail)

    def test_message_is_the_user_facing_one(self):
        with self.assertRaises(ActivityDataUnavailableError) as ctx:
            checked_pipeline_results([], 1)

        self.assertEqual(
            str(ctx.exception), "Activity data is temporarily unavailable."
        )


if __name__ == "__main__":
    main()
