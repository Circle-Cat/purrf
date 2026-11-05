"""Which course-reported status means the assignment is finished."""

import unittest

from backend.common.mentorship_enums import TrainingStatus
from backend.training.completion import next_training_status, reports_completion


class TestNextTrainingStatus(unittest.TestCase):
    def test_passed_finishes_it(self):
        """Mentee onboarding reports this one."""
        self.assertEqual(
            next_training_status(TrainingStatus.IN_PROGRESS, "passed"),
            TrainingStatus.DONE,
        )

    def test_completed_finishes_it_too(self):
        """Mentor onboarding reports this one. Neither may be hard-coded."""
        self.assertEqual(
            next_training_status(TrainingStatus.IN_PROGRESS, "completed"),
            TrainingStatus.DONE,
        )

    def test_incomplete_is_in_progress(self):
        self.assertEqual(
            next_training_status(TrainingStatus.TO_DO, "incomplete"),
            TrainingStatus.IN_PROGRESS,
        )

    def test_browsed_is_in_progress(self):
        self.assertEqual(
            next_training_status(TrainingStatus.TO_DO, "browsed"),
            TrainingStatus.IN_PROGRESS,
        )

    def test_failed_is_in_progress_so_it_can_be_retaken(self):
        self.assertEqual(
            next_training_status(TrainingStatus.TO_DO, "failed"),
            TrainingStatus.IN_PROGRESS,
        )

    def test_not_attempted_leaves_a_fresh_assignment_alone(self):
        self.assertIsNone(next_training_status(TrainingStatus.TO_DO, "not attempted"))

    def test_a_finished_assignment_never_moves_back(self):
        """Reopening mentor onboarding writes `incomplete` before `completed`.

        Without this rule a learner reviewing a course they already finished
        would close their own mentorship matching gate on the first write.
        """
        for reported in ("incomplete", "browsed", "failed", "not attempted", ""):
            with self.subTest(reported=reported):
                self.assertIsNone(next_training_status(TrainingStatus.DONE, reported))

    def test_a_finished_assignment_is_not_rewritten_by_another_completion(self):
        self.assertIsNone(next_training_status(TrainingStatus.DONE, "completed"))

    def test_an_unknown_status_changes_nothing(self):
        """A course we cannot read must not silently downgrade anybody."""
        for reported in (None, "", "weird", "COMPLETED"):
            with self.subTest(reported=reported):
                self.assertIsNone(
                    next_training_status(TrainingStatus.IN_PROGRESS, reported)
                )

    def test_it_does_not_repeat_a_status_the_row_already_has(self):
        self.assertIsNone(
            next_training_status(TrainingStatus.IN_PROGRESS, "incomplete")
        )

    def test_failed_does_not_rewrite_a_status_the_row_already_has(self):
        """A repeat status write would defeat the unchanged-commit skip."""
        self.assertIsNone(next_training_status(TrainingStatus.IN_PROGRESS, "failed"))


class TestReportsCompletion(unittest.TestCase):
    """Whether the course just said it was finished, whatever the row says.

    Separate from next_training_status because an assignment already DONE
    moves nowhere, and the course still has to be able to prove itself.
    """

    def test_both_finishing_values_count(self):
        self.assertTrue(reports_completion("passed"))
        self.assertTrue(reports_completion("completed"))

    def test_an_unfinished_status_does_not(self):
        for reported in ("incomplete", "browsed", "failed", "not attempted"):
            self.assertFalse(reports_completion(reported), msg=reported)

    def test_nothing_reported_does_not(self):
        self.assertFalse(reports_completion(None))


if __name__ == "__main__":
    unittest.main()
