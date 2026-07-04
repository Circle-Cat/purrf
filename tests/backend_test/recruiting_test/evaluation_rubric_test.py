import unittest

from backend.common.recruiting_enums import ApplicationStage
from backend.recruiting.evaluation_rubric import (
    RubricField,
    rubric_for,
    validate_responses,
)


def _all_fields(stage):
    """Flatten a stage's rubric sections into a single list of fields."""
    fields = []
    for section in rubric_for(stage):
        fields.extend(section.fields)
    return fields


class TestRubricFor(unittest.TestCase):
    def test_screening_rubric_has_expected_sections_and_fields(self):
        sections = rubric_for(ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(len(sections), 3)

        titles = [s.title for s in sections]
        self.assertEqual(
            titles, ["Background Fitness", "Cultural Fitness", "Overall Evaluation"]
        )

        bg_fitness = sections[0]
        self.assertEqual(
            bg_fitness.fields,
            (
                RubricField(
                    "bg_match",
                    "Does the candidate's background match the role requirements?",
                    "pass_fail",
                ),
                RubricField(
                    "bg_consistency",
                    "Are the candidate's resume, LinkedIn, and application answers consistent?",
                    "pass_fail",
                ),
                RubricField(
                    "bg_strength", "Background strength", "score", has_notes=True
                ),
            ),
        )

        cultural_fitness = sections[1]
        self.assertEqual(
            cultural_fitness.fields,
            (
                RubricField(
                    "format_compliance",
                    "Did the candidate meet the required format instructions?",
                    "pass_fail",
                ),
                RubricField(
                    "mission_alignment",
                    "Does the candidate demonstrate alignment with the community's mission?",
                    "pass_fail",
                ),
                RubricField(
                    "writing_quality", "Writing quality", "score", has_notes=True
                ),
            ),
        )

        overall = sections[2]
        self.assertEqual(
            overall.fields,
            (
                RubricField(
                    "overall",
                    "Should this candidate proceed to the next stage?",
                    "score",
                    has_notes=True,
                ),
            ),
        )

    def test_raises_for_stage_with_no_rubric(self):
        with self.assertRaises(ValueError):
            rubric_for(ApplicationStage.OFFER)

    def test_raises_for_terminal_stage(self):
        with self.assertRaises(ValueError):
            rubric_for(ApplicationStage.HIRED)


class TestRubricFieldCounts(unittest.TestCase):
    def test_screening_field_count(self):
        self.assertEqual(len(_all_fields(ApplicationStage.RECRUITER_SCREENING)), 7)

    def test_behavioral_field_count(self):
        self.assertEqual(len(_all_fields(ApplicationStage.BEHAVIORAL)), 7)

    def test_tech_field_count(self):
        self.assertEqual(len(_all_fields(ApplicationStage.TECH)), 8)

    def test_board_review_field_count(self):
        self.assertEqual(len(_all_fields(ApplicationStage.BOARD_REVIEW)), 1)


class TestValidateResponsesComplete(unittest.TestCase):
    def _valid_screening_responses(self):
        return {
            "bg_match": {"value": True},
            "bg_consistency": {"value": False},
            "bg_strength": {"value": 4, "notes": "Strong background."},
            "format_compliance": {"value": True},
            "mission_alignment": {"value": True},
            "writing_quality": {"value": 3, "notes": "Clear writing."},
            "overall": {"value": 5, "notes": "Proceed."},
        }

    def test_accepts_fully_filled_valid_submission(self):
        validate_responses(
            ApplicationStage.RECRUITER_SCREENING,
            self._valid_screening_responses(),
            require_complete=True,
        )

    def test_accepts_tech_stage_fully_filled_submission(self):
        responses = {
            "data_structures": {"value": 4},
            "correctness": {"value": 5},
            "debugging": {"value": 3},
            "communication_clarity": {"value": 4},
            "problem_statement": {"notes": "Two-sum variant."},
            "candidate_approach": {"notes": "Used a hashmap."},
            "code_snippet": {"notes": "def two_sum(...): ..."},
            "overall": {"value": 4, "notes": "Solid performance."},
        }
        validate_responses(ApplicationStage.TECH, responses, require_complete=True)

    def test_rejects_pass_fail_field_given_non_bool(self):
        responses = self._valid_screening_responses()
        responses["bg_match"] = {"value": "yes"}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_match", str(ctx.exception))

    def test_rejects_score_field_out_of_range_high(self):
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": 6, "notes": "Too high."}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_score_field_out_of_range_low(self):
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": 0, "notes": "Too low."}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_score_field_given_non_int(self):
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": 3.5, "notes": "Fractional."}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_score_field_given_bool_value(self):
        # bool is technically an int subclass in Python; must be rejected.
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": True, "notes": "Sneaky bool."}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_has_notes_field_with_blank_notes(self):
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": 4, "notes": "   "}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_has_notes_field_with_missing_notes(self):
        responses = self._valid_screening_responses()
        responses["bg_strength"] = {"value": 4}
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("bg_strength", str(ctx.exception))

    def test_rejects_notes_field_blank(self):
        responses = {
            "data_structures": {"value": 4},
            "correctness": {"value": 5},
            "debugging": {"value": 3},
            "communication_clarity": {"value": 4},
            "problem_statement": {"notes": "  "},
            "candidate_approach": {"notes": "Used a hashmap."},
            "code_snippet": {"notes": "def two_sum(...): ..."},
            "overall": {"value": 4, "notes": "Solid performance."},
        }
        with self.assertRaises(ValueError) as ctx:
            validate_responses(ApplicationStage.TECH, responses, require_complete=True)
        self.assertIn("problem_statement", str(ctx.exception))

    def test_require_complete_rejects_missing_field(self):
        with self.assertRaises(ValueError) as ctx:
            validate_responses(ApplicationStage.BOARD_REVIEW, {}, require_complete=True)
        self.assertIn("final_decision", str(ctx.exception))

    def test_require_complete_rejects_submission_missing_one_field(self):
        responses = self._valid_screening_responses()
        del responses["overall"]
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING, responses, require_complete=True
            )
        self.assertIn("overall", str(ctx.exception))


class TestValidateResponsesDraft(unittest.TestCase):
    def test_empty_dict_accepted_as_draft(self):
        validate_responses(
            ApplicationStage.RECRUITER_SCREENING, {}, require_complete=False
        )

    def test_partial_dict_accepted_as_draft(self):
        validate_responses(
            ApplicationStage.RECRUITER_SCREENING,
            {"bg_match": {"value": True}},
            require_complete=False,
        )

    def test_present_malformed_field_still_rejected_in_draft(self):
        with self.assertRaises(ValueError) as ctx:
            validate_responses(
                ApplicationStage.RECRUITER_SCREENING,
                {"bg_match": {"value": "not a bool"}},
                require_complete=False,
            )
        self.assertIn("bg_match", str(ctx.exception))

    def test_board_review_final_decision_has_notes_true(self):
        sections = rubric_for(ApplicationStage.BOARD_REVIEW)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Final Decision")
        self.assertEqual(
            sections[0].fields,
            (
                RubricField(
                    "final_decision",
                    "Should this candidate proceed to the offer stage / be rejected?",
                    "pass_fail",
                    has_notes=True,
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
