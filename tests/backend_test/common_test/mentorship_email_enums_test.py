import unittest

from backend.common.mentorship_email_enums import (
    MentorshipEmailFailure,
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
    MentorshipEmailStage,
)


class MentorshipEmailEnumsTest(unittest.TestCase):
    def test_stage_values_are_stable_strings(self):
        self.assertEqual(
            MentorshipEmailStage("match_result"), MentorshipEmailStage.MATCH_RESULT
        )
        self.assertEqual(len(MentorshipEmailStage), 9)

    def test_terminal_statuses(self):
        self.assertEqual(
            MentorshipEmailSendStatus.terminal(),
            frozenset({
                MentorshipEmailSendStatus.SENT,
                MentorshipEmailSendStatus.ABORTED,
                MentorshipEmailSendStatus.CANCELLED,
            }),
        )

    def test_failure_codes(self):
        self.assertEqual(len(MentorshipEmailFailure), 7)
        self.assertEqual(
            MentorshipEmailFailure("time_passed"), MentorshipEmailFailure.TIME_PASSED
        )

    def test_unreachable_results(self):
        self.assertEqual(
            MentorshipEmailRecipientResult.unreachable(),
            frozenset({
                MentorshipEmailRecipientResult.UNSUBSCRIBED,
                MentorshipEmailRecipientResult.BOUNCED,
                MentorshipEmailRecipientResult.IMPORT_FAILED,
            }),
        )


if __name__ == "__main__":
    unittest.main()
