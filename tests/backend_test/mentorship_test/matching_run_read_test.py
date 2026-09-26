"""Reading a matching run back: what state it is in, and the result itself."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import MatchingRunStatus
from backend.mentorship.matching_contract import (
    RESULT_VERSION,
    Candidate,
    MatchingRunResult,
    MenteeResult,
)
from backend.mentorship.matching_run_read_service import MatchingRunReadService


def _reported(**overrides):
    body = dict(
        contract_version=RESULT_VERSION,
        run_id="r7-x-y",
        round_id=7,
        status="succeeded",
        # Deliberately apart from the envelope's generated_at below. The two
        # were once the same value here, and a fixture where every clock
        # agrees cannot catch one being read for another.
        started_at="2026-09-18T01:40:00+00:00",
        finished_at="2026-09-18T01:50:00+00:00",
        matcher_version="deadbee",
        run_date="2026-09-18",
        mentee_count=3,
    )
    body.update(overrides)
    return MatchingRunResult(**body)


def _user(user_id, first_name, last_name, preferred_name=None):
    person = MagicMock()
    person.user_id = user_id
    person.first_name = first_name
    person.last_name = last_name
    person.preferred_name = preferred_name
    return person


def _result(mentor_id=None, score=None, candidates=(), match_type=None, **overrides):
    """A mentee's outcome: unmatched by default, assigned when given a mentor.

    The three shapes the contract allows are not interchangeable -- a mutual
    choice carries no score and a scored assignment must have one -- so the
    score follows the match type rather than being set alongside it.
    """
    body = dict(
        mentor_id=mentor_id,
        candidates=[Candidate(**candidate) for candidate in candidates],
    )
    if mentor_id is not None:
        body["match_type"] = match_type or "hungarian"
        if body["match_type"] == "hungarian":
            body["score"] = 70 if score is None else score
    body.update(overrides)
    return MenteeResult(**body)


class MatchingRunOverviewTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = MagicMock()
        self.storage.current_run_id.return_value = None

        self.pairs = MagicMock()
        self.pairs.has_pairs_for_round = AsyncMock(return_value=False)

        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(return_value=[])

        self.service = MatchingRunReadService(
            matching_storage=self.storage,
            mentorship_pairs_repository=self.pairs,
            users_repository=self.users,
            logger=MagicMock(),
        )
        self.session = AsyncMock()

    def _running(self, run_id="r7-x-y"):
        """Point the round at a run whose envelope is there and result is not."""
        self.storage.current_run_id.return_value = run_id
        self.storage.read_meta.return_value = MagicMock(
            run_id=run_id,
            round_id=7,
            generated_at="2026-09-18T01:00:00+00:00",
            triggered_by_user_id="42",
        )
        self.storage.read_run_result.return_value = None

    def _succeeded(self, results=None, **overrides):
        """A run the matcher finished and reported on."""
        self._running()
        self.storage.read_run_result.return_value = _reported(**overrides)
        self.storage.read_all_results.return_value = results or {}

    async def test_a_round_that_was_never_matched_reports_no_run(self):
        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.NEVER_RUN)

    async def test_a_run_the_matcher_has_not_reported_on_is_still_running(self):
        self._running()

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.RUNNING)
        self.assertEqual(overview["started_at"], "2026-09-18T01:00:00+00:00")

    async def test_a_run_the_matcher_gave_up_on_reports_its_error(self):
        self._running()
        self.storage.read_run_result.return_value = _reported(
            status="failed", error="PayloadError: meta missing", mentee_count=0
        )

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.FAILED)
        self.assertEqual(overview["error"], "PayloadError: meta missing")

    async def test_a_run_missing_people_is_unusable_rather_than_an_error(self):
        self._running()
        self.storage.read_run_result.side_effect = ValueError(
            "Run r7-x-y is incomplete: 20 results, 22 reported, 22 mentees sent."
        )

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.UNUSABLE)
        self.assertIn("20 results", overview["error"])

    async def test_a_finished_run_counts_who_was_placed_and_who_was_not(self):
        self._running()
        self.storage.read_run_result.return_value = _reported(mentee_count=3)
        self.storage.read_all_results.return_value = {
            "1": _result(mentor_id="10"),
            "2": _result(mentor_id="10"),
            "3": _result(),
        }

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.SUCCEEDED)
        self.assertEqual(overview["mentee_count"], 3)
        self.assertEqual(overview["matched_count"], 2)
        self.assertEqual(overview["unmatched_count"], 1)

    async def test_a_finished_run_is_timed_by_the_matcher_s_own_clock(self):
        """Both timestamps have to come from the same place or the duration
        between them is meaningless. The envelope's is when Purrf wrote the
        input, which is not when the job began: on a real run seeded by hand
        the two were nineteen hours apart for work that took thirty-four
        seconds."""
        self._succeeded()

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["started_at"], "2026-09-18T01:40:00+00:00")
        self.assertEqual(overview["finished_at"], "2026-09-18T01:50:00+00:00")
        self.assertEqual(overview["input_written_at"], "2026-09-18T01:00:00+00:00")

    async def test_a_published_round_says_so(self):
        self._running()
        self.storage.read_run_result.return_value = _reported(mentee_count=0)
        self.storage.read_all_results.return_value = {}
        self.pairs.has_pairs_for_round.return_value = True

        overview = await self.service.read_overview(self.session, 7)

        self.assertTrue(overview["published"])

    async def test_the_mentors_nobody_was_given_are_named(self):
        self._succeeded(unmatched_mentor_ids=["10", "11"])
        self.users.get_all_by_ids.return_value = [
            _user(10, "Ada", "Lovelace"),
            _user(11, "Grace", "Hopper", preferred_name="Amazing Grace"),
        ]

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(
            overview["unmatched_mentors"],
            [
                {"user_id": "10", "name": "Ada Lovelace"},
                {"user_id": "11", "name": "Amazing Grace"},
            ],
        )

    async def test_every_name_on_a_page_comes_from_one_query(self):
        self._succeeded(unmatched_mentor_ids=["10", "11", "12"])
        self.users.get_all_by_ids.return_value = []

        await self.service.read_overview(self.session, 7)

        self.users.get_all_by_ids.assert_awaited_once_with(self.session, [10, 11, 12])

    async def test_a_mentor_the_database_has_lost_keeps_his_id(self):
        self._succeeded(unmatched_mentor_ids=["10"])
        self.users.get_all_by_ids.return_value = []

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(
            overview["unmatched_mentors"], [{"user_id": "10", "name": None}]
        )

    async def test_an_id_that_is_not_a_number_does_not_take_the_page_down(self):
        self._succeeded(unmatched_mentor_ids=["10", "not-an-id"])
        self.users.get_all_by_ids.return_value = [_user(10, "Ada", "Lovelace")]

        overview = await self.service.read_overview(self.session, 7)

        self.users.get_all_by_ids.assert_awaited_once_with(self.session, [10])
        self.assertEqual(
            overview["unmatched_mentors"],
            [
                {"user_id": "10", "name": "Ada Lovelace"},
                {"user_id": "not-an-id", "name": None},
            ],
        )

    async def test_a_pointer_whose_envelope_expired_reports_no_run(self):
        self.storage.current_run_id.return_value = "r7-x-y"
        self.storage.read_meta.return_value = None

        overview = await self.service.read_overview(self.session, 7)

        self.assertEqual(overview["status"], MatchingRunStatus.NEVER_RUN)


class MatchingRunResultsTest(MatchingRunOverviewTest):
    async def test_a_run_still_going_yields_no_results_and_says_why(self):
        self._running()

        page = await self.service.read_results(self.session, 7)

        self.assertEqual(page["status"], MatchingRunStatus.RUNNING)
        self.assertEqual(page["items"], [])
        self.assertEqual(page["total"], 0)

    async def test_a_mentee_is_listed_with_the_mentor_chosen_for_him(self):
        self._succeeded(results={"1": _result(mentor_id="10", score=88)})
        self.users.get_all_by_ids.return_value = [
            _user(1, "Mia", "Mentee"),
            _user(10, "Ada", "Lovelace"),
        ]

        page = await self.service.read_results(self.session, 7)

        self.assertEqual(
            page["items"][0],
            {
                "mentee": {"user_id": "1", "name": "Mia Mentee"},
                "mentor": {"user_id": "10", "name": "Ada Lovelace"},
                "score": 88,
                "match_type": "hungarian",
                "recommendation_reason": "",
                "diagnostic_reason": "",
                "candidates": [],
            },
        )

    async def test_a_mentee_nobody_was_found_for_has_no_mentor(self):
        self._succeeded(results={"1": _result()})
        self.users.get_all_by_ids.return_value = [_user(1, "Mia", "Mentee")]

        page = await self.service.read_results(self.session, 7)

        self.assertIsNone(page["items"][0]["mentor"])

    async def test_the_unplaced_come_first_and_the_rest_by_descending_score(self):
        self._succeeded(
            results={
                "1": _result(mentor_id="10", score=40),
                "2": _result(),
                "3": _result(mentor_id="11", score=90),
            }
        )

        page = await self.service.read_results(self.session, 7)

        self.assertEqual(
            [item["mentee"]["user_id"] for item in page["items"]], ["2", "3", "1"]
        )

    async def test_a_mutual_choice_sorts_below_the_scored_rather_than_at_zero(self):
        # A mutual choice carries no score -- the contract leaves it out because
        # the sentinel the matcher uses internally is not one. Reading that
        # absence as zero would file the pairs needing least review among the
        # weakest, which is the opposite of what the order is for.
        self._succeeded(
            results={
                "1": _result(mentor_id="10", score=20),
                "2": _result(mentor_id="11", match_type="mutual_yes"),
                "3": _result(),
            }
        )

        page = await self.service.read_results(self.session, 7)

        self.assertEqual(
            [item["mentee"]["user_id"] for item in page["items"]], ["3", "1", "2"]
        )

    async def test_a_page_is_the_slice_asked_for_and_the_total_is_everybody(self):
        self._succeeded(
            results={
                str(i): _result(mentor_id="10", score=100 - i) for i in range(1, 6)
            }
        )

        page = await self.service.read_results(self.session, 7, limit=2, offset=2)

        self.assertEqual(
            [item["mentee"]["user_id"] for item in page["items"]], ["3", "4"]
        )
        self.assertEqual(page["total"], 5)

    async def test_only_the_unplaced_can_be_asked_for(self):
        self._succeeded(
            results={
                "1": _result(mentor_id="10", score=40),
                "2": _result(),
                "3": _result(),
            }
        )

        page = await self.service.read_results(self.session, 7, matched=False)

        self.assertEqual(
            [item["mentee"]["user_id"] for item in page["items"]], ["2", "3"]
        )
        self.assertEqual(page["total"], 2)

    async def test_the_counts_describe_the_run_not_the_filter(self):
        self._succeeded(
            results={
                "1": _result(mentor_id="10", score=40),
                "2": _result(),
                "3": _result(),
            }
        )

        page = await self.service.read_results(self.session, 7, matched=False)

        self.assertEqual(page["matched_count"], 1)
        self.assertEqual(page["unmatched_count"], 2)

    async def test_one_query_names_the_mentees_mentors_and_candidates_on_a_page(self):
        self._succeeded(
            results={
                "1": _result(
                    mentor_id="10",
                    score=88,
                    candidates=[
                        {"mentor_id": "11", "score": 80},
                        {"mentor_id": "12", "score": 70},
                    ],
                )
            }
        )
        self.users.get_all_by_ids.return_value = [_user(11, "Grace", "Hopper")]

        page = await self.service.read_results(self.session, 7)

        self.users.get_all_by_ids.assert_awaited_once_with(
            self.session, [1, 10, 11, 12]
        )
        self.assertEqual(
            page["items"][0]["candidates"],
            [
                {"user_id": "11", "name": "Grace Hopper", "score": 80},
                {"user_id": "12", "name": None, "score": 70},
            ],
        )

    async def test_names_are_looked_up_for_the_page_only(self):
        self._succeeded(
            results={
                str(i): _result(mentor_id=str(100 + i), score=50) for i in range(1, 6)
            }
        )
        self.users.get_all_by_ids.return_value = []

        await self.service.read_results(self.session, 7, limit=1)

        self.users.get_all_by_ids.assert_awaited_once_with(self.session, [1, 101])


if __name__ == "__main__":
    unittest.main()
