"""The Cloud Run trigger that starts a matching run."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from backend.common.matching_job_client import MatcherJobNotStarted, MatchingJobClient


class _FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _FakeSession:
    def __init__(self, response=None):
        self.response = response or _FakeResponse(
            body={"metadata": {"name": "projects/p/locations/l/jobs/j/executions/e"}}
        )
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.response


class MatchingJobClientTest(unittest.TestCase):
    def test_run_id_is_the_only_thing_the_trigger_carries(self):
        session = _FakeSession()
        client = MatchingJobClient(
            "projects/p/locations/l/jobs/j", MagicMock(), session
        )

        execution = client.start("r7-x-y")

        call = session.calls[0]
        self.assertEqual(
            call["url"],
            "https://run.googleapis.com/v2/projects/p/locations/l/jobs/j:run",
        )
        env = call["json"]["overrides"]["containerOverrides"][0]["env"]
        self.assertEqual(env, [{"name": "RUN_ID", "value": "r7-x-y"}])
        self.assertEqual(execution, "projects/p/locations/l/jobs/j/executions/e")

    def test_run_date_travels_only_when_given(self):
        session = _FakeSession()
        client = MatchingJobClient(
            "projects/p/locations/l/jobs/j", MagicMock(), session
        )

        client.start("r7-x-y", run_date=date(2026, 6, 1))

        env = session.calls[0]["json"]["overrides"]["containerOverrides"][0]["env"]
        self.assertIn({"name": "RUN_DATE", "value": "2026-06-01"}, env)

    def test_a_refusal_is_raised_rather_than_reported_as_started(self):
        session = _FakeSession(_FakeResponse(status_code=403, text="forbidden"))
        logger = MagicMock()
        client = MatchingJobClient("projects/p/locations/l/jobs/j", logger, session)

        with self.assertRaises(MatcherJobNotStarted):
            client.start("r7-x-y")
        logger.error.assert_called_once()

    def test_missing_job_resource_is_refused(self):
        logger = MagicMock()
        client = MatchingJobClient(None, logger, _FakeSession())

        with self.assertRaises(MatcherJobNotStarted):
            client.start("r7-x-y")
        logger.error.assert_called_once()

    def test_missing_credentials_are_a_refusal(self):
        client = MatchingJobClient("projects/p/locations/l/jobs/j", MagicMock())

        with patch(
            "backend.common.matching_job_client.default",
            side_effect=RuntimeError("no credentials"),
        ):
            with self.assertRaises(MatcherJobNotStarted):
                client.start("r7-x-y")

    def test_an_unreadable_body_still_counts_as_started(self):
        # Cloud Run accepted it; failing here would give back a round the job
        # is already working on.
        session = _FakeSession(_FakeResponse(body=ValueError("not json")))
        logger = MagicMock()
        client = MatchingJobClient("projects/p/locations/l/jobs/j", logger, session)

        self.assertEqual(client.start("r7-x-y"), "")
        logger.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
