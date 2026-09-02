"""Course package objects, and what an unconfigured bucket says to whom."""

import unittest
from unittest.mock import MagicMock

from backend.training.training_storage import TrainingStorage

_BUCKET = "purrf-test-training"
_KEY = "training/9/package/scormcontent/index.html"


class TestUnconfiguredBucket(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.storage = TrainingStorage(None, logger=self.logger)

    def test_the_response_names_no_environment_variable(self):
        """This message is rendered in a browser by the shared error handler."""
        with self.assertRaises(ValueError) as caught:
            self.storage.get(_KEY)

        self.assertNotIn("TRAINING_BUCKET", str(caught.exception))

    def test_the_log_names_the_variable_that_is_missing(self):
        with self.assertRaises(ValueError):
            self.storage.put(_KEY, b"<html></html>", "text/html")

        template = self.logger.error.call_args.args[0]
        self.assertIn("TRAINING_BUCKET", template)


class TestConfiguredBucket(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.storage = TrainingStorage(
            _BUCKET, logger=MagicMock(), storage_client=self.client
        )

    def test_a_write_goes_to_the_named_bucket(self):
        self.storage.put(_KEY, b"<html></html>", "text/html")

        self.client.bucket.assert_called_once_with(_BUCKET)
        self.client.bucket.return_value.blob.assert_called_once_with(_KEY)


if __name__ == "__main__":
    unittest.main()
