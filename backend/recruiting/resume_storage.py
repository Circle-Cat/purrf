import hashlib
from google.api_core.exceptions import PreconditionFailed


class ResumeStorage:
    """Content-addressed résumé storage in Google Cloud Storage.

    The object key is the SHA-256 of the file bytes, so identical résumés are
    stored exactly once and shared across applications.

    Construction never touches Google Cloud: the GCS client is created lazily
    on first use (see ``_get_client``), so the app can boot in local
    development without GCS credentials, a project, or ``RESUME_BUCKET``
    configured. Missing configuration is only surfaced as an error when
    ``put`` is actually called.
    """

    def __init__(self, bucket_name: str | None, storage_client=None):
        """Initialize a ResumeStorage instance.

        Safe to call without any GCS configuration: no client is created and
        no Google Cloud APIs are touched here.

        Args:
            bucket_name (str | None): Target bucket (e.g.
                ``purrf-test-resumes``). May be ``None``/empty in
                environments without resume storage configured; in that
                case, ``put`` raises ``ValueError`` instead of touching GCS.
            storage_client: Optional pre-built ``google.cloud.storage.Client``
                (tests inject a mock here). When omitted, a real client is
                created lazily on first use.
        """
        self._client = storage_client
        self._bucket_name = bucket_name

    def _get_client(self):
        """Create (once) and return the GCS client on first use.

        Deferred so app startup never needs GCS credentials -- local dev
        without RESUME_BUCKET/ADC boots fine and only an actual upload
        requires configuration.
        """
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client

    def put(self, data: bytes) -> tuple[str, str]:
        """Store résumé bytes content-addressed; reuse if already present.

        Args:
            data (bytes): The raw PDF bytes.

        Returns:
            tuple[str, str]: ``(sha256_hex, object_key)``.

        Raises:
            ValueError: If resume storage is not configured (no bucket
                name), before any Google Cloud API is touched.
        """
        if not self._bucket_name:
            raise ValueError("Resume storage is not configured; set RESUME_BUCKET.")

        sha256_hex = hashlib.sha256(data).hexdigest()
        object_key = f"resumes/{sha256_hex}.pdf"
        blob = self._get_client().bucket(self._bucket_name).blob(object_key)
        try:
            # if_generation_match=0 creates only when the object is absent.
            blob.upload_from_string(
                data, content_type="application/pdf", if_generation_match=0
            )
        except PreconditionFailed:
            # Object already exists — identical content, reuse it.
            pass
        return sha256_hex, object_key
