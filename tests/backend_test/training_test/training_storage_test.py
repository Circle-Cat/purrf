"""Course package objects, and what an unconfigured bucket says to whom."""

import unittest
from unittest.mock import MagicMock

from google.api_core.exceptions import NotFound

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


class TestPartialReads(unittest.TestCase):
    """Serving a range must not download the object to slice it here."""

    def setUp(self):
        self.client = MagicMock()
        self.bucket = self.client.bucket.return_value
        self.blob = self.bucket.blob.return_value
        self.storage = TrainingStorage(
            _BUCKET, logger=MagicMock(), storage_client=self.client
        )

    def test_a_size_comes_back_without_reading_the_object(self):
        described = self.bucket.get_blob.return_value
        described.size = 3697276
        described.content_type = "video/mp4"

        self.assertEqual(self.storage.stat(_KEY), (3697276, "video/mp4"))
        self.blob.download_as_bytes.assert_not_called()

    def test_a_missing_object_has_no_size(self):
        self.bucket.get_blob.return_value = None

        self.assertIsNone(self.storage.stat(_KEY))

    def test_an_object_with_no_recorded_size_has_no_size(self):
        """Nothing a range could be measured against, so it reads as absent."""
        self.bucket.get_blob.return_value.size = None

        self.assertIsNone(self.storage.stat(_KEY))

    def test_a_size_falls_back_to_the_type_the_name_implies(self):
        described = self.bucket.get_blob.return_value
        described.size = 12
        described.content_type = None

        self.assertEqual(self.storage.stat(_KEY), (12, "text/html"))

    def test_only_the_requested_bytes_are_asked_of_the_bucket(self):
        self.blob.download_as_bytes.return_value = b"partial"

        self.assertEqual(self.storage.get_range(_KEY, 100, 199), b"partial")

        self.blob.download_as_bytes.assert_called_once_with(start=100, end=199)

    def test_the_end_offset_is_passed_through_inclusive(self):
        """The bucket reads `end` inclusive, exactly as HTTP writes it, so no
        offset arithmetic happens on the way."""
        self.storage.get_range(_KEY, 0, 0)

        self.blob.download_as_bytes.assert_called_once_with(start=0, end=0)

    def test_an_object_that_went_away_reads_as_absent(self):
        self.blob.download_as_bytes.side_effect = NotFound("gone")

        self.assertIsNone(self.storage.get_range(_KEY, 0, 10))


if __name__ == "__main__":
    unittest.main()
