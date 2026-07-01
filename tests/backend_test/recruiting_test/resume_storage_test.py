import hashlib
import unittest
from unittest.mock import MagicMock
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
        sha, key = ResumeStorage(client, "purrf-test-resumes").put(data)
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
        sha, key = ResumeStorage(client, "b").put(data)
        self.assertEqual(sha, expected)
        self.assertEqual(key, f"resumes/{expected}.pdf")
