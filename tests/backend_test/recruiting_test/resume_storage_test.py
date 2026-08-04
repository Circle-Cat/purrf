import hashlib
import unittest
from unittest.mock import MagicMock, patch
from google.api_core.exceptions import PreconditionFailed
from backend.recruiting.resume_storage import ResumeStorage


class TestResumeStorage(unittest.TestCase):
    def _storage(self, blob):
        bucket = MagicMock()
        bucket.blob.return_value = blob
        client = MagicMock()
        client.bucket.return_value = bucket
        return client, bucket

    def test_put_uploads_content_addressed_key(self):
        data = b"%PDF-1.4 hello"
        expected = hashlib.sha256(data).hexdigest()
        blob = MagicMock()
        client, bucket = self._storage(blob)
        sha, key = ResumeStorage("purrf-test-resumes", client).put(data)
        self.assertEqual(sha, expected)
        self.assertEqual(key, f"resumes/{expected}.pdf")
        bucket.blob.assert_called_once_with(f"resumes/{expected}.pdf")
        blob.upload_from_string.assert_called_once()
        _, kwargs = blob.upload_from_string.call_args
        self.assertEqual(kwargs.get("if_generation_match"), 0)

    def test_put_reuses_existing_object_on_precondition_failed(self):
        data = b"%PDF-1.4 dup"
        expected = hashlib.sha256(data).hexdigest()
        blob = MagicMock()
        blob.upload_from_string.side_effect = PreconditionFailed("exists")
        client, _ = self._storage(blob)
        sha, key = ResumeStorage("b", client).put(data)
        self.assertEqual(sha, expected)
        self.assertEqual(key, f"resumes/{expected}.pdf")

    def test_construction_without_bucket_does_not_raise(self):
        # Construction must never touch Google Cloud or require configuration.
        storage = ResumeStorage(None)
        self.assertIsNone(storage._bucket_name)
        self.assertIsNone(storage._client)

    def test_put_without_bucket_raises_before_touching_client(self):
        storage = ResumeStorage(None)
        with self.assertRaises(ValueError) as ctx:
            storage.put(b"%PDF-1.4 no bucket")
        self.assertIn("RESUME_BUCKET", str(ctx.exception))
        self.assertIsNone(storage._client)

    @patch("google.cloud.storage.Client")
    def test_client_is_created_lazily_and_reused(self, mock_client_cls):
        blob = MagicMock()
        client_instance, bucket = self._storage(blob)
        mock_client_cls.return_value = client_instance

        storage = ResumeStorage("purrf-test-resumes")
        mock_client_cls.assert_not_called()

        storage.put(b"%PDF-1.4 first")
        storage.put(b"%PDF-1.4 second")

        mock_client_cls.assert_called_once()
        self.assertEqual(bucket.blob.call_count, 2)

    def test_get_downloads_bytes_for_object_key(self):
        blob = MagicMock()
        blob.download_as_bytes.return_value = b"%PDF-1.4 content"
        client, bucket = self._storage(blob)

        result = ResumeStorage("purrf-test-resumes", client).get("resumes/abc.pdf")

        self.assertEqual(result, b"%PDF-1.4 content")
        bucket.blob.assert_called_once_with("resumes/abc.pdf")
        blob.download_as_bytes.assert_called_once()

    def test_get_without_bucket_raises_before_touching_client(self):
        storage = ResumeStorage(None)
        with self.assertRaises(ValueError) as ctx:
            storage.get("resumes/abc.pdf")
        self.assertIn("RESUME_BUCKET", str(ctx.exception))
        self.assertIsNone(storage._client)


if __name__ == "__main__":
    unittest.main()
