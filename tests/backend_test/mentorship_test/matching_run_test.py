"""Storage, and the service that puts it and the job trigger in order."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.mentorship.matching_run_service import MatchingRunService
from backend.mentorship.matching_storage import MatchingStorage


class _FakeBlob:
    def __init__(self, store, name):
        self._store, self.name = store, name

    def exists(self):
        return self.name in self._store

    def download_as_bytes(self):
        return self._store[self.name]

    def upload_from_string(self, data, content_type=None):
        self._store[self.name] = (
            data if isinstance(data, bytes) else data.encode("utf-8")
        )
        self.content_type = content_type


class _FakeStorageClient:
    def __init__(self):
        self.store = {}

    def bucket(self, name):
        client = self

        class _Bucket:
            def blob(self, blob_name):
                return _FakeBlob(client.store, blob_name)

        return _Bucket()


def _payload(mentors=1, mentees=1):
    payload = MagicMock()
    payload.mentors = [MagicMock()] * mentors
    payload.mentees = [MagicMock()] * mentees
    payload.model_dump_json.return_value = '{"contract_version": 2}'
    return payload


class MatchingStorageTest(unittest.TestCase):
    def test_payload_lands_under_the_run_prefix(self):
        client = _FakeStorageClient()
        storage = MatchingStorage("purrf-test-matching", MagicMock(), client)

        prefix = storage.write_payload("r7-x-y", _payload())

        self.assertIn("runs/r7-x-y/input/payload.json", client.store)
        self.assertEqual(prefix, "gs://purrf-test-matching/runs/r7-x-y")

    def test_result_is_absent_until_the_job_writes_one(self):
        client = _FakeStorageClient()
        storage = MatchingStorage("b", MagicMock(), client)

        self.assertIsNone(storage.read_result("r7-x-y"))

        client.store["runs/r7-x-y/output/result.json"] = json.dumps({
            "status": "succeeded"
        }).encode("utf-8")
        self.assertEqual(storage.read_result("r7-x-y")["status"], "succeeded")

    def test_missing_bucket_is_refused_rather_than_guessed(self):
        logger = MagicMock()
        storage = MatchingStorage(None, logger, _FakeStorageClient())

        with self.assertRaises(ValueError):
            storage.write_payload("r7-x-y", _payload())
        logger.error.assert_called_once()


class MatchingRunServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.payload = _payload(mentors=2, mentees=3)
        self.payload_service = MagicMock()
        self.payload_service.build_matching_payload = AsyncMock(
            return_value=self.payload
        )
        self.storage = MagicMock()
        self.storage.write_payload.return_value = "gs://b/runs/r7-x-y"
        self.job_client = MagicMock()
        self.job_client.start.return_value = "projects/p/l/jobs/j/executions/e"
        self.service = MatchingRunService(
            matching_payload_service=self.payload_service,
            matching_storage=self.storage,
            matching_job_client=self.job_client,
            logger=MagicMock(),
        )

    async def test_the_same_run_id_names_the_payload_and_the_execution(self):
        result = await self.service.start_run(MagicMock(), 7, [1, 2])

        built_with = self.payload_service.build_matching_payload.await_args
        stored_with = self.storage.write_payload.call_args
        started_with = self.job_client.start.call_args
        self.assertEqual(built_with.kwargs["run_id"], result["run_id"])
        self.assertEqual(stored_with.args[0], result["run_id"])
        self.assertEqual(started_with.args[0], result["run_id"])

    async def test_input_is_stored_before_the_job_is_told_about_it(self):
        order = []
        self.storage.write_payload.side_effect = lambda *a, **k: (
            order.append("store") or "gs://b/runs/x"
        )
        self.job_client.start.side_effect = lambda *a, **k: (
            order.append("start") or "execution"
        )

        await self.service.start_run(MagicMock(), 7, [1, 2])

        # The other order would leave a job looking for input never written.
        self.assertEqual(order, ["store", "start"])

    async def test_nothing_is_stored_when_the_selection_is_refused(self):
        self.payload_service.build_matching_payload.side_effect = ValueError("nope")

        with self.assertRaises(ValueError):
            await self.service.start_run(MagicMock(), 7, [1, 2])
        self.storage.write_payload.assert_not_called()
        self.job_client.start.assert_not_called()

    async def test_run_date_reaches_the_job(self):
        await self.service.start_run(MagicMock(), 7, [1, 2], run_date="2026-06-01")

        self.assertEqual(
            self.job_client.start.call_args.kwargs["run_date"], "2026-06-01"
        )


if __name__ == "__main__":
    unittest.main()
