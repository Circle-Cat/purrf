"""The callback the matcher job makes, and what it turns into."""

import json
import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.mentorship_enums import MentorshipEvent
from backend.mentorship import notification_email_copy as copy
from backend.mentorship.matching_contract import RESULT_VERSION, MatchingRunResult
from backend.mentorship.matching_run_complete_controller import (
    MatchingRunCompleteController,
)


def _result(**overrides):
    body = dict(
        contract_version=RESULT_VERSION,
        run_id="r7-x-y",
        round_id=7,
        status="succeeded",
        started_at="2026-09-12T00:00:00+00:00",
        finished_at="2026-09-12T00:48:00+00:00",
        matcher_version="deadbee",
        run_date="2026-09-12",
        mentee_count=22,
    )
    body.update(overrides)
    return MatchingRunResult(**body)


def _request(token="Bearer good", body=None):
    request = MagicMock()
    request.headers = {"Authorization": token} if token else {}
    request.json = AsyncMock(
        return_value=body if body is not None else {"run_id": "r7-x-y"}
    )
    return request


class MatchingRunCompleteTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.auth = MagicMock()
        self.auth.verify_google_token.return_value = {"sub": "111"}

        self.storage = MagicMock()
        self.storage.already_notified.return_value = False
        self.storage.read_meta.return_value = MagicMock(
            round_id=7, triggered_by_user_id="42"
        )
        self.storage.read_run_result.return_value = _result()
        self.storage.mentor_count.return_value = 23

        # name= is MagicMock's own argument, so the round's name is set after.
        round_entity = MagicMock()
        round_entity.name = "Mentorship 2026 Fall"
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=round_entity)

        self.database = MagicMock()
        self.session = AsyncMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.controller = MatchingRunCompleteController(
            logger=MagicMock(),
            auth_service=self.auth,
            matcher_job_subs=frozenset({"111"}),
            matching_storage=self.storage,
            mentorship_round_repository=self.rounds,
            database=self.database,
        )

        self.patcher = patch(
            "backend.mentorship.matching_run_complete_controller.record_event",
            new=AsyncMock(),
        )
        self.record_event = self.patcher.start()

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_a_finished_run_is_announced_to_whoever_started_it(self):
        response = await self.controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.OK)
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["event_type"], MentorshipEvent.MATCHING_RUN_COMPLETED)
        self.assertEqual(kwargs["subject_type"], "mentorship_round")
        self.assertEqual(kwargs["subject_id"], 7)
        self.assertEqual(kwargs["details"]["triggeredByUserId"], "42")

    async def test_the_actor_is_nobody(self):
        await self.controller.complete(_request())

        # record_event discards the actor from the recipients, and the starter
        # is the only recipient there is: naming them sends nothing, silently.
        self.assertIsNone(self.record_event.await_args.kwargs["actor_id"])

    async def test_the_run_is_marked_only_after_it_has_been_announced(self):
        order = []
        self.record_event.side_effect = lambda *a, **k: order.append("announce")
        self.storage.mark_notified.side_effect = lambda *a: order.append("mark")

        await self.controller.complete(_request())

        # Reversed, a crash in between turns every retry away and the email is
        # lost for good.
        self.assertEqual(order, ["announce", "mark"])

    async def test_a_run_announced_already_is_left_alone(self):
        self.storage.already_notified.return_value = True

        response = await self.controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.record_event.assert_not_awaited()

    async def test_a_finished_run_gives_its_round_back(self):
        await self.controller.complete(_request())

        # The lock's six hours are for a run that dies working; this one is
        # over after one.
        self.storage.release_round.assert_called_once_with(7, "r7-x-y")

    async def test_the_round_is_given_back_before_the_announcement(self):
        order = []
        self.storage.release_round.side_effect = lambda *a: order.append("release")
        self.record_event.side_effect = lambda *a, **k: order.append("announce")

        await self.controller.complete(_request())

        # A failure announcing answers 500, which the job does not retry.
        self.assertEqual(order, ["release", "announce"])

    async def test_a_retry_after_the_announcement_still_gives_the_round_back(self):
        # A crash between announcing and releasing leaves only this path.
        self.storage.already_notified.return_value = True

        await self.controller.complete(_request())

        self.storage.release_round.assert_called_once_with(7, "r7-x-y")

    async def test_an_unusable_result_gives_the_round_back_too(self):
        self.storage.read_run_result.side_effect = ValueError("incomplete")

        await self.controller.complete(_request())

        self.storage.release_round.assert_called_once_with(7, "r7-x-y")

    async def test_a_run_still_writing_keeps_its_round(self):
        self.storage.read_run_result.return_value = None

        await self.controller.complete(_request())

        # The job is still working; a second run now would overlap it.
        self.storage.release_round.assert_not_called()

    async def test_a_run_whose_envelope_is_gone_releases_nothing(self):
        self.storage.read_meta.return_value = None

        await self.controller.complete(_request())

        self.storage.release_round.assert_not_called()

    async def test_a_run_that_has_not_reported_yet_asks_to_be_retried(self):
        # The job said it finished before its own last write landed.
        self.storage.read_run_result.return_value = None

        response = await self.controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.record_event.assert_not_awaited()
        self.storage.mark_notified.assert_not_called()

    async def test_an_unusable_result_is_announced_as_a_failure(self):
        # Waiting an hour and hearing nothing is worse than hearing what broke.
        self.storage.read_run_result.side_effect = ValueError(
            "Run r7-x-y is incomplete"
        )

        response = await self.controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.OK)
        details = self.record_event.await_args.kwargs["details"]
        self.assertEqual(details["status"], "failed")
        self.assertIn("incomplete", details["error"])

    async def test_a_run_whose_envelope_is_gone_is_accepted_and_dropped(self):
        self.storage.read_meta.return_value = None

        response = await self.controller.complete(_request())

        # Nobody to tell: who started it is what the envelope carried.
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.record_event.assert_not_awaited()

    async def test_a_caller_without_a_token_is_refused(self):
        response = await self.controller.complete(_request(token=None))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.record_event.assert_not_awaited()

    async def test_a_caller_that_is_not_the_matcher_job_is_refused(self):
        self.auth.verify_google_token.return_value = {"sub": "999"}

        response = await self.controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    async def test_an_unconfigured_allow_list_refuses_everybody(self):
        # Fails closed, like the delivery route: nothing else guards this one.
        controller = MatchingRunCompleteController(
            logger=MagicMock(),
            auth_service=self.auth,
            matcher_job_subs=frozenset(),
            matching_storage=self.storage,
            mentorship_round_repository=self.rounds,
            database=self.database,
        )

        response = await controller.complete(_request())

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    async def test_an_unreadable_body_is_accepted_rather_than_retried(self):
        request = _request()
        request.json = AsyncMock(side_effect=json.JSONDecodeError("nope", "", 0))

        response = await self.controller.complete(request)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.record_event.assert_not_awaited()


class MatchingRunCopyTest(unittest.TestCase):
    def test_the_success_email_says_nothing_is_published_yet(self):
        subject, body = copy.matching_run_succeeded(
            "Mentorship 2026 Fall", 22, 23, 2880
        )

        self.assertIn("Mentorship 2026 Fall", subject)
        self.assertIn("22 mentees against 23 mentors", body)
        self.assertIn("48 minutes", body)
        # The email lands an hour after the button was pressed, which is long
        # enough to assume the pairings are live.
        self.assertIn("Nothing has been published yet", body)

    def test_the_round_name_is_dropped_rather_than_left_dangling(self):
        subject, _ = copy.matching_run_succeeded("   ", 22, 23, 60)

        self.assertNotIn("  for", subject)
        self.assertTrue(subject.endswith("finished"))

    def test_an_impossible_duration_is_left_out(self):
        _, body = copy.matching_run_succeeded("Fall", 22, 23, -5)

        # Better silent than telling somebody it finished in -3 minutes.
        self.assertNotIn("took", body)

    def test_the_failure_email_carries_what_the_matcher_said(self):
        subject, body = copy.matching_run_failed("Fall", "PayloadError: meta missing")

        self.assertIn("did not finish", subject)
        self.assertIn("PayloadError", body)
        self.assertIn("Nothing was changed", body)

    def test_a_failure_with_no_reason_still_reads_as_a_sentence(self):
        _, body = copy.matching_run_failed("Fall", None)

        self.assertIn("It did not say why", body)

    def test_the_reported_error_is_escaped(self):
        _, body = copy.matching_run_failed("Fall", "<script>alert(1)</script>")

        self.assertNotIn("<script>", body)


if __name__ == "__main__":
    unittest.main()
