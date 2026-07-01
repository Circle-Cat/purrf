import hashlib
from google.api_core.exceptions import PreconditionFailed


class ResumeStorage:
    """Content-addressed résumé storage in Google Cloud Storage.

    The object key is the SHA-256 of the file bytes, so identical résumés are
    stored exactly once and shared across applications.
    """

    def __init__(self, storage_client, bucket_name: str):
        """Initialize a ResumeStorage instance.

        Args:
            storage_client: A ``google.cloud.storage.Client`` instance.
            bucket_name (str): Target bucket (e.g. ``purrf-test-resumes``).
        """
        self._client = storage_client
        self._bucket_name = bucket_name

    def put(self, data: bytes) -> tuple[str, str]:
        """Store résumé bytes content-addressed; reuse if already present.

        Args:
            data (bytes): The raw PDF bytes.

        Returns:
            tuple[str, str]: ``(sha256_hex, object_key)``.
        """
        sha256_hex = hashlib.sha256(data).hexdigest()
        object_key = f"resumes/{sha256_hex}.pdf"
        blob = self._client.bucket(self._bucket_name).blob(object_key)
        try:
            # if_generation_match=0 creates only when the object is absent.
            blob.upload_from_string(
                data, content_type="application/pdf", if_generation_match=0
            )
        except PreconditionFailed:
            # Object already exists — identical content, reuse it.
            pass
        return sha256_hex, object_key
