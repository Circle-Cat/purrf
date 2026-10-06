"""The draft laid over a matcher's result, and what stands in the way of publishing."""

import unittest

from backend.mentorship.matching_contract import Candidate, MenteeResult
from backend.mentorship.matching_draft import (
    DraftEntry,
    allowed_mentors,
    apply_draft,
    assigned_counts,
    is_matchers_choice,
    problems,
)


def _scored(mentor_id, score, reason="Matched on skills", candidates=()):
    return MenteeResult(
        mentor_id=mentor_id,
        score=score,
        match_type="hungarian",
        recommendation_reason=reason,
        candidates=[Candidate(mentor_id=m, score=s) for m, s in candidates],
    )


def _draft(mentor_id, reason="Edited"):
    return DraftEntry(
        mentor_id=mentor_id,
        recommendation_reason=reason,
        edited_by="9",
        edited_at="2026-10-06T08:00:00+00:00",
    )


class ApplyDraftTest(unittest.TestCase):
    def test_a_mentee_nobody_changed_is_the_matchers(self):
        result = _scored("10", 80)

        row = apply_draft({"1": result}, {})["1"]

        self.assertEqual((row.mentor_id, row.score, row.edited), ("10", 80, False))
        self.assertEqual(row.recommendation_reason, "Matched on skills")
        self.assertIs(row.result, result)

    def test_a_mentee_moved_to_a_candidate_takes_the_candidate_s_score(self):
        result = _scored("10", 80, candidates=[("11", 70)])

        row = apply_draft({"1": result}, {"1": _draft("11")})["1"]

        self.assertEqual((row.mentor_id, row.score, row.edited), ("11", 70, True))
        self.assertEqual(row.recommendation_reason, "Edited")

    def test_a_reason_rewritten_for_the_same_mentor_keeps_his_score(self):
        row = apply_draft({"1": _scored("10", 80)}, {"1": _draft("10")})["1"]

        self.assertEqual((row.mentor_id, row.score, row.edited), ("10", 80, True))

    def test_a_mentee_given_nobody_has_no_score(self):
        row = apply_draft({"1": _scored("10", 80)}, {"1": _draft(None, "")})["1"]

        self.assertEqual((row.mentor_id, row.score, row.edited), (None, None, True))

    def test_draft_entries_for_mentees_not_in_the_run_are_ignored(self):
        rows = apply_draft({"1": _scored("10", 80)}, {"99": _draft("10")})

        self.assertEqual(list(rows), ["1"])


class AllowedMentorsTest(unittest.TestCase):
    def test_nobody_the_matcher_s_choice_and_the_candidates(self):
        result = _scored("10", 80, candidates=[("11", 70), ("12", 60)])

        self.assertEqual(allowed_mentors(result), {None, "10", "11", "12"})

    def test_an_unmatched_mentee_may_have_only_a_candidate_or_nobody(self):
        result = MenteeResult(candidates=[Candidate(mentor_id="11", score=40)])

        self.assertEqual(allowed_mentors(result), {None, "11"})

    def test_the_matcher_s_choice_means_mentor_and_reason_both(self):
        result = _scored("10", 80, reason="Matched on skills")

        self.assertTrue(is_matchers_choice(result, "10", "Matched on skills"))
        self.assertFalse(is_matchers_choice(result, "10", "Another reason"))
        self.assertFalse(is_matchers_choice(result, None, "Matched on skills"))


class ProblemsTest(unittest.TestCase):
    def test_a_clean_result_has_none(self):
        rows = apply_draft({"1": _scored("10", 80)}, {})

        self.assertEqual(problems(rows, {"10": 1}), [])

    def test_a_mentor_given_more_mentees_than_his_slots(self):
        rows = apply_draft(
            {"1": _scored("10", 80), "2": _scored("11", 70, candidates=[("10", 60)])},
            {"2": _draft("10")},
        )

        self.assertEqual(assigned_counts(rows), {"10": 2})
        self.assertEqual(
            problems(rows, {"10": 1, "11": 1}),
            [{"code": "over_slots", "mentor_id": "10", "assigned": 2, "slots": 1}],
        )

    def test_a_reason_over_the_limit_and_a_matched_mentee_with_none(self):
        rows = apply_draft(
            {
                "2": _scored("10", 80),
                "1": _scored("11", 70),
                "3": _scored("12", 60),
            },
            {"2": _draft("10", "x" * 301), "1": _draft("11", "   ")},
        )

        self.assertEqual(
            problems(rows, {"10": 1, "11": 1, "12": 1}),
            [
                {"code": "no_reason", "mentee_id": "1"},
                {"code": "reason_too_long", "mentee_id": "2"},
            ],
        )

    def test_a_mentee_with_nobody_needs_no_reason(self):
        rows = apply_draft({"1": _scored("10", 80)}, {"1": _draft(None, "")})

        self.assertEqual(problems(rows, {"10": 1}), [])


if __name__ == "__main__":
    unittest.main()
