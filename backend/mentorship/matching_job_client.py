"""Starts the Cloud Run job that does the matching.

The job is a separate deployment: matching runs a few times a year, takes about
an hour, and its dependencies cannot share a Python environment with this one.
All Purrf does is hand it a run id and let it read the rest from storage.

Called over REST rather than through google-cloud-run, because one method of
that library is all this needs and every version in requirements.txt is pinned
by hand -- the library would be one more thing that has to agree the next time
protobuf or google-api-core moves for an unrelated reason.

That reasoning holds for exactly one call. **If a second Cloud Run API call is
ever needed here, add google-cloud-run and move this to the library rather than
hand-rolling a second endpoint.** Owning the URL shape and response parsing is
cheap once and a liability twice, and at two calls the dependency has paid for
itself.

Construction never touches Google Cloud, matching the storage helper: a missing
configuration surfaces when somebody starts a run rather than at startup.
"""

RUN_ID_ENV = "RUN_ID"
RUN_DATE_ENV = "RUN_DATE"

_RUN_ENDPOINT = "https://run.googleapis.com/v2/{job_resource}:run"
_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class MatchingJobClient:
    """Triggers one execution of the matcher job."""

    def __init__(self, job_resource: str | None, logger, session=None):
        """
        Args:
            job_resource (str | None): ``projects/<p>/locations/<l>/jobs/<j>``.
                May be absent in environments with no matcher job.
            logger: Injected logger.
            session: Optional pre-built authorized session; tests inject a fake.
        """
        self._session = session
        self._job_resource = job_resource
        self.logger = logger

    def _authorized_session(self):
        if not self._job_resource:
            self.logger.error(
                "[MatchingJobClient] MATCHER_JOB_RESOURCE is not set; no matching "
                "run can be started."
            )
            raise ValueError("The matcher job is not available.")
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=[_SCOPE])
            self._session = AuthorizedSession(credentials)
        return self._session

    def start(self, run_id: str, run_date: str | None = None) -> str:
        """Start one execution and return its name.

        The run id is all that is passed: the job reads its input from storage
        under that id, so nothing about a run travels through the trigger.

        Args:
            run_id (str): Identifies the run, and locates its input.
            run_date (str | None): ``YYYY-MM-DD`` to score as though it were that
                day. Years of experience are measured from it, so a run only
                reproduces when its date comes with it; left unset the job uses
                today.

        Returns:
            str: The execution's resource name.

        Raises:
            ValueError: The job is not configured, or Cloud Run refused to start
                it.
        """
        env = [{"name": RUN_ID_ENV, "value": run_id}]
        if run_date:
            env.append({"name": RUN_DATE_ENV, "value": run_date})

        response = self._authorized_session().post(
            _RUN_ENDPOINT.format(job_resource=self._job_resource),
            json={"overrides": {"containerOverrides": [{"env": env}]}},
            timeout=30,
        )
        if response.status_code >= 400:
            self.logger.error(
                "[MatchingJobClient] Cloud Run refused run %s: %s %s",
                run_id,
                response.status_code,
                response.text,
            )
            raise ValueError(f"Could not start the matcher job: {response.status_code}")

        # The long-running operation names the execution straight away. Waiting
        # for it to finish would mean waiting out the whole run.
        execution_name = (response.json().get("metadata") or {}).get("name", "")
        self.logger.info(
            "[MatchingJobClient] Started %s for run %s",
            execution_name or "(unnamed execution)",
            run_id,
        )
        return execution_name
