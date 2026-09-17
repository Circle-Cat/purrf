"""A run's Redis keys, and the service that orders the lock, the write and the job."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.exceptions import ConflictError
from backend.mentorship.matching_contract import RESULT_VERSION
from backend.mentorship.matching_run_service import MatchingRunService
from backend.mentorship.matching_storage import MatchingStorage


class _FakeRedis:
    """Enough Redis to exercise the key layout, with its ordering visible.

    ``calls`` records the write commands in order, because "the envelope goes
    last" is the whole reason a matcher can trust a run is complete.
    """

    def __init__(self):
        self.strings: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.expiries: dict[str, int] = {}
        self.calls: list[tuple] = []

    def set(self, key, value, nx=False, ex=None):
        self.calls.append(("set", key))
        if nx and key in self.strings:
            return None
        self.strings[key] = value
        if ex is not None:
            self.expiries[key] = ex
        return True

    def get(self, key):
        return self.strings.get(key)

    def delete(self, key):
        self.calls.append(("delete", key))
        self.strings.pop(key, None)

    def hset(self, key, mapping=None):
        self.calls.append(("hset", key, len(mapping or {})))
        self.hashes.setdefault(key, {}).update(mapping or {})

    def expire(self, key, seconds):
        self.expiries[key] = seconds

    def hlen(self, key):
        return len(self.hashes.get(key, {}))


def _person(user_id, size=32):
    person = MagicMock()
    person.user_id = user_id
    person.model_dump_json.return_value = json.dumps({
        "user_id": user_id,
        "p": "x" * size,
    })
    return person


def _matching_input(round_id=7, mentors=1, mentees=1):
    matching_input = MagicMock()
    matching_input.meta.round_id = round_id
    matching_input.meta.model_dump_json.return_value = '{"contract_version": 1}'
    matching_input.mentors = [_person(f"m{i}") for i in range(mentors)]
    matching_input.mentees = [_person(f"e{i}") for i in range(mentees)]
    return matching_input


def _reported(**overrides):
    body = dict(
        contract_version=RESULT_VERSION,
        run_id="r7-x-y",
        round_id=7,
        status="succeeded",
        started_at="2026-09-12T00:00:00+00:00",
        finished_at="2026-09-12T00:50:00+00:00",
        matcher_version="deadbee",
        run_date="2026-09-12",
        mentee_count=2,
    )
    body.update(overrides)
    return json.dumps(body)


class MatchingStorageTest(unittest.TestCase):
    def setUp(self):
        self.redis = _FakeRedis()
        self.storage = MatchingStorage(self.redis, MagicMock())

    def test_people_land_under_their_own_ids(self):
        self.storage.write_input("r7-x-y", _matching_input(mentors=2, mentees=3))

        self.assertEqual(
            sorted(self.redis.hashes["match:r7-x-y:in:mentors"]), ["m0", "m1"]
        )
        self.assertEqual(
            sorted(self.redis.hashes["match:r7-x-y:in:mentees"]), ["e0", "e1", "e2"]
        )

    def test_the_envelope_is_written_after_the_people(self):
        self.storage.write_input("r7-x-y", _matching_input(mentors=2, mentees=2))

        written = [call[1] for call in self.redis.calls]
        # A matcher that finds the envelope knows everybody arrived. Written
        # first, it would promise a round that is still filling up.
        self.assertLess(
            written.index("match:r7-x-y:in:mentees"),
            written.index("match:r7-x-y:meta"),
        )

    def test_the_pointer_names_the_run_for_the_review_screen(self):
        self.storage.write_input("r7-x-y", _matching_input(round_id=7))

        self.assertEqual(self.redis.strings["match:round:7:current"], "r7-x-y")
        self.assertEqual(self.storage.current_run_id(7), "r7-x-y")

    def test_every_key_expires(self):
        self.storage.write_input("r7-x-y", _matching_input())

        for key in (
            "match:r7-x-y:in:mentors",
            "match:r7-x-y:in:mentees",
            "match:r7-x-y:meta",
            "match:round:7:current",
        ):
            self.assertIn(key, self.redis.expiries, key)

    def test_a_large_group_is_written_in_several_calls(self):
        # Upstash refuses a request over 10 MB, and the batch is measured in
        # bytes because a person's record varies several-fold in size.
        with patch("backend.mentorship.matching_storage.MAX_WRITE_BYTES", 120):
            self.storage.write_input("r7-x-y", _matching_input(mentees=6))

        mentee_writes = [
            call
            for call in self.redis.calls
            if call[:2] == ("hset", "match:r7-x-y:in:mentees")
        ]
        self.assertGreater(len(mentee_writes), 1)
        self.assertEqual(
            sum(call[2] for call in mentee_writes), 6, "every mentee still written once"
        )

    def test_only_one_run_holds_a_round(self):
        self.assertTrue(self.storage.claim_round(7, "r7-first"))
        self.assertFalse(self.storage.claim_round(7, "r7-second"))
        self.assertEqual(self.storage.running_run_id(7), "r7-first")

    def test_a_run_that_never_started_gives_the_round_back(self):
        self.storage.claim_round(7, "r7-first")

        self.storage.release_round(7, "r7-first")

        self.assertIsNone(self.storage.running_run_id(7))
        self.assertTrue(self.storage.claim_round(7, "r7-second"))

    def test_a_release_does_not_take_another_run_s_turn(self):
        # A delete arriving after our own lock expired would otherwise let a
        # third run in while the second one is working.
        self.storage.claim_round(7, "r7-second")

        self.storage.release_round(7, "r7-first")

        self.assertEqual(self.storage.running_run_id(7), "r7-second")

    def test_no_result_until_the_matcher_reports_one(self):
        self.assertIsNone(self.storage.read_run_result("r7-x-y"))

    def test_a_reported_run_is_validated_not_trusted(self):
        self.redis.strings["match:r7-x-y:result_meta"] = _reported(contract_version=99)

        with self.assertRaises(ValueError):
            self.storage.read_run_result("r7-x-y")

    def test_a_complete_run_reads_back(self):
        self.redis.hashes["match:r7-x-y:in:mentees"] = {"e0": "{}", "e1": "{}"}
        self.redis.hashes["match:r7-x-y:out"] = {"e0": "{}", "e1": "{}"}
        self.redis.strings["match:r7-x-y:result_meta"] = _reported()

        result = self.storage.read_run_result("r7-x-y")

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.mentee_count, 2)

    def test_a_short_run_is_refused_rather_than_reviewed(self):
        # Publishing it would mark the missing people as unmatched.
        self.redis.hashes["match:r7-x-y:in:mentees"] = {"e0": "{}", "e1": "{}"}
        self.redis.hashes["match:r7-x-y:out"] = {"e0": "{}"}
        self.redis.strings["match:r7-x-y:result_meta"] = _reported()

        with self.assertRaises(ValueError):
            self.storage.read_run_result("r7-x-y")

    def test_a_failed_run_is_returned_without_counting_anything(self):
        # out is empty by definition, so the count check does not apply.
        self.redis.strings["match:r7-x-y:result_meta"] = _reported(
            status="failed", error="PayloadError: meta missing", mentee_count=0
        )

        result = self.storage.read_run_result("r7-x-y")

        self.assertEqual(result.status, "failed")


class MatchingRunServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.matching_input = _matching_input(mentors=2, mentees=3)
        self.payload_service = MagicMock()
        self.payload_service.build_matching_payload = AsyncMock(
            return_value=self.matching_input
        )
        self.storage = MagicMock()
        self.storage.claim_round.return_value = True
        self.job_client = MagicMock()
        self.job_client.start.return_value = "projects/p/l/jobs/j/executions/e"
        self.service = MatchingRunService(
            matching_payload_service=self.payload_service,
            matching_storage=self.storage,
            matching_job_client=self.job_client,
            logger=MagicMock(),
        )

    async def test_the_same_run_id_names_the_lock_the_input_and_the_job(self):
        result = await self.service.start_run(MagicMock(), 7, [1, 2])

        self.assertEqual(
            self.payload_service.build_matching_payload.await_args.kwargs["run_id"],
            result["run_id"],
        )
        self.assertEqual(self.storage.claim_round.call_args.args[1], result["run_id"])
        self.assertEqual(self.storage.write_input.call_args.args[0], result["run_id"])
        self.assertEqual(self.job_client.start.call_args.args[0], result["run_id"])

    async def test_the_round_is_taken_before_anything_is_built(self):
        order = []
        self.storage.claim_round.side_effect = lambda *a: order.append("claim") or True
        self.payload_service.build_matching_payload.side_effect = AsyncMock(
            side_effect=lambda *a, **k: order.append("build") or self.matching_input
        )

        await self.service.start_run(MagicMock(), 7, [1, 2])

        # Two admins pressing together would otherwise build two runs and let
        # the second overwrite the first one's people.
        self.assertEqual(order, ["claim", "build"])

    async def test_a_round_already_running_is_a_conflict(self):
        self.storage.claim_round.return_value = False
        self.storage.running_run_id.return_value = "r7-earlier"

        with self.assertRaises(ConflictError) as caught:
            await self.service.start_run(MagicMock(), 7, [1, 2])

        self.assertIn("r7-earlier", str(caught.exception))
        self.payload_service.build_matching_payload.assert_not_awaited()

    async def test_input_is_written_before_the_job_is_told_about_it(self):
        order = []
        self.storage.write_input.side_effect = lambda *a, **k: order.append("write")
        self.job_client.start.side_effect = lambda *a, **k: (
            order.append("start") or "execution"
        )

        await self.service.start_run(MagicMock(), 7, [1, 2])

        # The other order would leave a job looking for input never written.
        self.assertEqual(order, ["write", "start"])

    async def test_a_refused_selection_gives_the_round_straight_back(self):
        self.payload_service.build_matching_payload.side_effect = ValueError("nope")

        with self.assertRaises(ValueError):
            await self.service.start_run(MagicMock(), 7, [1, 2])

        # Waiting out the six-hour expiry is for a run that died working, not
        # for one that was refused before it began.
        self.storage.release_round.assert_called_once()
        self.storage.write_input.assert_not_called()
        self.job_client.start.assert_not_called()

    async def test_a_job_that_will_not_start_gives_the_round_back_too(self):
        self.job_client.start.side_effect = ValueError("no job configured")

        with self.assertRaises(ValueError):
            await self.service.start_run(MagicMock(), 7, [1, 2])

        self.storage.release_round.assert_called_once()

    async def test_run_date_reaches_the_job(self):
        await self.service.start_run(MagicMock(), 7, [1, 2], run_date="2026-06-01")

        self.assertEqual(
            self.job_client.start.call_args.kwargs["run_date"], "2026-06-01"
        )

    async def test_who_pressed_the_button_travels_with_the_run(self):
        await self.service.start_run(MagicMock(), 7, [1, 2], triggered_by_user_id=42)

        # Nothing outside the run records it, and the completion notice needs it.
        self.assertEqual(
            self.payload_service.build_matching_payload.await_args.kwargs[
                "triggered_by_user_id"
            ],
            "42",
        )


if __name__ == "__main__":
    unittest.main()
