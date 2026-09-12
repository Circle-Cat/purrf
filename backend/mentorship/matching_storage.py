"""A matching run's files in Google Cloud Storage.

Purrf writes the payload; the matcher job writes everything else back under the
same run prefix. Construction never touches Google Cloud -- the client is built
on first use -- so the app boots without credentials or a bucket, and a missing
configuration surfaces when somebody starts a run rather than at startup.
"""

import json

PAYLOAD_PATH = "input/payload.json"
RESULT_PATH = "output/result.json"


def run_prefix(run_id: str) -> str:
    """Where everything belonging to one run lives."""
    return f"runs/{run_id}"


class MatchingStorage:
    """Reads and writes the objects of a matching run."""

    def __init__(self, bucket_name: str | None, logger, storage_client=None):
        """
        Args:
            bucket_name (str | None): Target bucket, e.g. ``purrf-prod-matching``.
                May be absent in environments with no matching storage.
            logger: Injected logger.
            storage_client: Optional pre-built client; tests inject a fake.
        """
        self._client = storage_client
        self._bucket_name = bucket_name
        self.logger = logger

    def _blob(self, path: str):
        if not self._bucket_name:
            # Which variable is missing is for whoever runs the environment, and
            # the message travels to a browser: it is logged, not raised.
            self.logger.error(
                "[MatchingStorage] MATCHING_BUCKET is not set; no matching run "
                "can be started."
            )
            raise ValueError("Matching storage is not available.")
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self._bucket_name).blob(path)

    def write_payload(self, run_id: str, payload) -> str:
        """Write a run's input and return the prefix everything else lands under.

        Args:
            run_id (str): Identifies the run.
            payload (MatchingPayload): What the matcher will be given.

        Returns:
            str: ``gs://<bucket>/runs/<run_id>``.
        """
        path = f"{run_prefix(run_id)}/{PAYLOAD_PATH}"
        self._blob(path).upload_from_string(
            payload.model_dump_json(indent=2), content_type="application/json"
        )
        self.logger.info("[MatchingStorage] Wrote gs://%s/%s", self._bucket_name, path)
        return f"gs://{self._bucket_name}/{run_prefix(run_id)}"

    def read_result(self, run_id: str) -> dict | None:
        """Return a run's result, or None while the job has yet to write one."""
        blob = self._blob(f"{run_prefix(run_id)}/{RESULT_PATH}")
        if not blob.exists():
            return None
        return json.loads(blob.download_as_bytes().decode("utf-8"))
