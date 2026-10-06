"""Who goes into the matching pool: the rules, one example each."""

import unittest

from backend.mentorship.matching_eligibility import (
    Candidate,
    IneligibleReason,
    PastPair,
    PastRound,
    history_problems,
    ineligible_reasons,
)

ME = 1
REQUIRED = 5


def _candidate(**overrides):
    fields = dict(
        user_id=ME,
        is_blocked=False,
        is_active=True,
        is_taking_part=True,
        training_done=True,
        open_slots=1,
    )
    fields.update(overrides)
    return Candidate(**fields)


def _pair(mentor_id, mentee_id, meetings, *, active=True):
    return PastPair(
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        is_active=active,
        completed_count=meetings,
    )


def _round(*pairs, quitters=()):
    return PastRound(
        required_meetings=REQUIRED, pairs=tuple(pairs), quitters=frozenset(quitters)
    )


class IneligibleReasonsTest(unittest.TestCase):
    def test_someone_with_nothing_against_them_is_eligible(self):
        self.assertEqual(ineligible_reasons(_candidate(), []), [])

    def test_each_standing_condition_is_its_own_reason(self):
        cases = [
            (dict(is_blocked=True), IneligibleReason.BLOCKED),
            (dict(is_active=False), IneligibleReason.DEACTIVATED),
            (dict(is_taking_part=False), IneligibleReason.NOT_TAKING_PART),
            (dict(training_done=False), IneligibleReason.TRAINING_NOT_DONE),
            (dict(open_slots=0), IneligibleReason.NO_OPEN_SLOTS),
        ]
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(
                    ineligible_reasons(_candidate(**overrides), []), [reason]
                )

    def test_history_adds_to_the_standing_reasons(self):
        reasons = ineligible_reasons(
            _candidate(training_done=False), [_round(_pair(9, ME, 3))]
        )
        self.assertEqual(
            reasons,
            [IneligibleReason.TRAINING_NOT_DONE, IneligibleReason.MEETINGS_SHORT],
        )


class HistoryProblemsTest(unittest.TestCase):
    def test_never_paired_is_clean(self):
        self.assertEqual(history_problems(ME, []), [])

    def test_a_mentee_who_met_the_requirement_is_clean(self):
        self.assertEqual(history_problems(ME, [_round(_pair(9, ME, 5))]), [])

    def test_a_mentee_short_of_meetings_is_not(self):
        self.assertEqual(
            history_problems(ME, [_round(_pair(9, ME, 3))]),
            [IneligibleReason.MEETINGS_SHORT],
        )

    def test_no_meetings_on_record_counts_as_short(self):
        self.assertEqual(
            history_problems(ME, [_round(_pair(9, ME, 0))]),
            [IneligibleReason.MEETINGS_SHORT],
        )

    def test_a_mentor_is_short_when_any_one_mentee_is(self):
        self.assertEqual(
            history_problems(ME, [_round(_pair(ME, 21, 5), _pair(ME, 22, 2))]),
            [IneligibleReason.MEETINGS_SHORT],
        )

    def test_quitting_before_being_matched_neither_counts_nor_clears(self):
        # Last round: registered and quit, no pair. The round before: fine.
        clean_before = [_round(quitters={ME}), _round(_pair(9, ME, 5))]
        self.assertEqual(history_problems(ME, clean_before), [])
        # The same, but the round before was short: it still counts.
        short_before = [_round(quitters={ME}), _round(_pair(9, ME, 3))]
        self.assertEqual(
            history_problems(ME, short_before), [IneligibleReason.MEETINGS_SHORT]
        )

    def test_only_the_latest_paired_round_counts(self):
        rounds = [_round(_pair(9, ME, 5)), _round(_pair(9, ME, 1))]
        self.assertEqual(history_problems(ME, rounds), [])

    def test_quitting_after_being_matched_counts(self):
        self.assertEqual(
            history_problems(
                ME, [_round(_pair(9, ME, 1, active=False), quitters={ME})]
            ),
            [IneligibleReason.QUIT_AFTER_MATCH],
        )

    def test_a_mentor_who_quit_is_not_saved_by_the_mentee_going_on(self):
        rounds = [
            _round(
                _pair(ME, 21, 1, active=False),
                _pair(8, 21, 4),
                quitters={ME},
            )
        ]
        self.assertEqual(
            history_problems(ME, rounds), [IneligibleReason.QUIT_AFTER_MATCH]
        )

    def test_a_pair_the_partner_ended_does_not_count_against_the_one_left(self):
        # Her mentor quit after one meeting and nobody took her over.
        mentee_left = [_round(_pair(9, ME, 1, active=False), quitters={9})]
        self.assertEqual(history_problems(ME, mentee_left), [])
        # His mentee quit after one meeting.
        mentor_left = [_round(_pair(ME, 21, 1, active=False), quitters={21})]
        self.assertEqual(history_problems(ME, mentor_left), [])

    def test_a_mentee_counts_her_meetings_across_a_change_of_mentor(self):
        # 1 with the mentor who quit, 4 with the one who took her over.
        rounds = [_round(_pair(9, ME, 1, active=False), _pair(8, ME, 4), quitters={9})]
        self.assertEqual(history_problems(ME, rounds), [])

    def test_the_mentor_who_took_over_is_judged_by_her_total(self):
        took_over = [
            _round(_pair(9, 21, 1, active=False), _pair(ME, 21, 4), quitters={9})
        ]
        self.assertEqual(history_problems(ME, took_over), [])
        still_short = [
            _round(_pair(9, 21, 1, active=False), _pair(ME, 21, 3), quitters={9})
        ]
        self.assertEqual(
            history_problems(ME, still_short), [IneligibleReason.MEETINGS_SHORT]
        )

    def test_a_pair_an_admin_ended_counts_against_neither(self):
        # Both still in the round; she went on with a new mentor.
        rounds = [_round(_pair(9, ME, 1, active=False), _pair(8, ME, 4))]
        self.assertEqual(history_problems(ME, rounds), [])
        self.assertEqual(history_problems(9, rounds), [])

    def test_a_short_total_after_an_admin_change_counts_for_both_who_ran_to_the_end(
        self,
    ):
        rounds = [_round(_pair(9, ME, 1, active=False), _pair(8, ME, 3))]
        self.assertEqual(
            history_problems(ME, rounds), [IneligibleReason.MEETINGS_SHORT]
        )
        self.assertEqual(history_problems(8, rounds), [IneligibleReason.MEETINGS_SHORT])
        self.assertEqual(history_problems(9, rounds), [])

    def test_history_is_the_persons_whatever_their_role_was(self):
        # Short as a mentee last round; the role now does not matter here.
        self.assertEqual(
            ineligible_reasons(_candidate(), [_round(_pair(9, ME, 2))]),
            [IneligibleReason.MEETINGS_SHORT],
        )


if __name__ == "__main__":
    unittest.main()
