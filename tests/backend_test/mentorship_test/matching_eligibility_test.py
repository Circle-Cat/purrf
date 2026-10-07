"""Who goes into the matching pool: the rules, one example each."""

import unittest

from backend.mentorship.matching_eligibility import (
    HISTORY_REASONS,
    Candidate,
    HistoryFinding,
    IneligibleReason,
    PastPair,
    PastRound,
    history_findings,
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


def _round(*pairs, quitters=(), round_id=None):
    return PastRound(
        required_meetings=REQUIRED,
        pairs=tuple(pairs),
        quitters=frozenset(quitters),
        round_id=round_id,
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


class ExemptionTest(unittest.TestCase):
    """An exemption lifts the history check in its round and clears what came
    before it. Rounds are latest first: 30, then 20, then 10."""

    def test_an_exemption_this_round_lifts_history_but_nothing_else(self):
        reasons = ineligible_reasons(
            _candidate(exempt_this_round=True, training_done=False),
            [_round(_pair(9, ME, 1), round_id=20)],
        )

        self.assertEqual(reasons, [IneligibleReason.TRAINING_NOT_DONE])

    def test_an_exemption_clears_the_rounds_before_it(self):
        # Exempted in 20 and not paired there: 10's shortfall no longer counts.
        rounds = [
            _round(round_id=30),
            _round(round_id=20),
            _round(_pair(9, ME, 1), round_id=10),
        ]

        self.assertEqual(history_problems(ME, rounds, frozenset({20})), [])
        self.assertEqual(
            history_problems(ME, rounds), [IneligibleReason.MEETINGS_SHORT]
        )

    def test_the_round_of_the_exemption_itself_still_counts(self):
        # Exempted in 20, then quit after being matched in 20.
        rounds = [
            _round(_pair(9, ME, 0, active=False), quitters=[ME], round_id=20),
            _round(_pair(8, ME, 1), round_id=10),
        ]

        self.assertEqual(
            history_problems(ME, rounds, frozenset({20})),
            [IneligibleReason.QUIT_AFTER_MATCH],
        )

    def test_a_round_after_the_exemption_counts_as_usual(self):
        rounds = [
            _round(_pair(9, ME, 2), round_id=30),
            _round(round_id=20),
            _round(_pair(8, ME, 5), round_id=10),
        ]

        self.assertEqual(
            history_problems(ME, rounds, frozenset({20})),
            [IneligibleReason.MEETINGS_SHORT],
        )

    def test_history_reasons_are_the_two_an_exemption_lifts(self):
        self.assertEqual(
            HISTORY_REASONS,
            {IneligibleReason.QUIT_AFTER_MATCH, IneligibleReason.MEETINGS_SHORT},
        )


class HistoryFindingsTest(unittest.TestCase):
    def test_a_finding_names_its_round_and_her_meetings(self):
        rounds = [_round(_pair(9, ME, 3), round_id=20)]

        self.assertEqual(
            history_findings(ME, rounds),
            [HistoryFinding(IneligibleReason.MEETINGS_SHORT, 20, 3, REQUIRED)],
        )

    def test_a_mentor_short_with_two_mentees_carries_the_shortest(self):
        rounds = [_round(_pair(ME, 21, 4), _pair(ME, 22, 1), round_id=20)]

        self.assertEqual(
            history_findings(ME, rounds),
            [HistoryFinding(IneligibleReason.MEETINGS_SHORT, 20, 1, REQUIRED)],
        )

    def test_quitting_carries_no_counts(self):
        rounds = [_round(_pair(9, ME, 0, active=False), quitters=[ME], round_id=20)]

        self.assertEqual(
            history_findings(ME, rounds),
            [HistoryFinding(IneligibleReason.QUIT_AFTER_MATCH, 20)],
        )


if __name__ == "__main__":
    unittest.main()
