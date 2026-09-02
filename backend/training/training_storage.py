"""Course package files in Google Cloud Storage.

Everything is served back through the backend rather than straight from GCS, so
the bucket needs no CORS configuration and no public access.
"""

import mimetypes
import posixpath

from google.api_core.exceptions import NotFound

# Extensions the standard table gets wrong or does not know, and that real
# course packages contain. A wrong Content-Type here is not cosmetic: a font or
# a media file served as text does not load.
_EXTRA_CONTENT_TYPES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".m4a": "audio/mp4",
    ".mjs": "text/javascript",
    ".webmanifest": "application/manifest+json",
}

DEFAULT_CONTENT_TYPE = "application/octet-stream"


def content_type_for(path: str) -> str:
    """Guess a Content-Type from a file name, defaulting to octet-stream.

    Unknown types are deliberately not guessed at: an octet-stream download is
    a visible failure, while a wrong type renders as garbage.
    """
    extension = posixpath.splitext(path)[1].lower()
    if extension in _EXTRA_CONTENT_TYPES:
        return _EXTRA_CONTENT_TYPES[extension]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or DEFAULT_CONTENT_TYPE


class TrainingStorage:
    """Reads and writes course package objects.

    Construction never touches Google Cloud -- the client is built on first use
    -- so the app boots in local development without credentials or a bucket,
    and a missing configuration surfaces when somebody uploads rather than at
    startup.
    """

    def __init__(self, bucket_name: str | None, logger, storage_client=None):
        """
        Args:
            bucket_name (str | None): Target bucket, e.g. ``purrf-test-training``.
                May be absent in environments without training storage.
            logger: Injected logger.
            storage_client: Optional pre-built client; tests inject a mock.
        """
        self._client = storage_client
        self._bucket_name = bucket_name
        self.logger = logger

    def _bucket(self):
        if not self._bucket_name:
            # Which variable is missing is for whoever runs the environment,
            # and the message travels to a browser: it is logged, not raised.
            self.logger.error(
                "[TrainingStorage] TRAINING_BUCKET is not set; no course "
                "package can be read or written."
            )
            raise ValueError("Training storage is not available.")
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self._bucket_name)

    def put(self, object_key: str, data: bytes, content_type: str) -> None:
        """Write one object, overwriting whatever is there."""
        self._bucket().blob(object_key).upload_from_string(
            data, content_type=content_type
        )

    def get(self, object_key: str) -> tuple[bytes, str] | None:
        """Read one object.

        Returns:
            tuple[bytes, str] | None: Bytes and Content-Type, or None if there
            is no such object. Absence is a normal answer here -- a course can
            reference a file it does not ship -- so it is not an exception.
        """
        blob = self._bucket().blob(object_key)
        try:
            data = blob.download_as_bytes()
        except NotFound:
            return None
        return data, blob.content_type or content_type_for(object_key)

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under a prefix.

        Returns:
            int: How many objects were deleted.
        """
        deleted = 0
        for blob in self._client_bucket_list(prefix):
            blob.delete()
            deleted += 1
        return deleted

    def _client_bucket_list(self, prefix: str):
        bucket = self._bucket()
        return bucket.client.list_blobs(bucket, prefix=prefix)
