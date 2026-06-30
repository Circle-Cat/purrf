import unittest

from pydantic import ValidationError

from backend.dto.job_config_dto import (
    FormSchemaDto,
    PipelineConfigDto,
    PipelineStageDto,
    ProfileConfigDto,
    QuestionDto,
    ScreenRuleConditionDto,
    ScreenRuleDto,
    ScreenRulesDto,
    ShowWhenDto,
)


class TestQuestionDto(unittest.TestCase):
    def test_short_text_minimal(self):
        q = QuestionDto(id="q1", type="short_text", label="Name")
        self.assertEqual(q.id, "q1")
        self.assertFalse(q.required)

    def test_label_must_be_nonempty(self):
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="short_text", label="   ")

    def test_long_text_maxlength_and_maxwords_must_be_positive(self):
        QuestionDto(id="q1", type="long_text", label="Why", max_length=10, max_words=5)
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="long_text", label="Why", max_length=0)
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="long_text", label="Why", max_words=0)

    def test_single_choice_requires_nonempty_options(self):
        QuestionDto(id="q1", type="single_choice", label="Pick", options=["a", "b"])
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="single_choice", label="Pick", options=[])

    def test_multi_choice_max_selections_bounds(self):
        QuestionDto(
            id="q1",
            type="multi_choice",
            label="L",
            options=["a", "b"],
            max_selections=2,
        )
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="multi_choice",
                label="L",
                options=["a", "b"],
                max_selections=3,
            )
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="multi_choice",
                label="L",
                options=["a", "b"],
                max_selections=0,
            )

    def test_exact_text_requires_expected_value(self):
        QuestionDto(
            id="q1", type="exact_text", label="Declare", expected_value="I confirm"
        )
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1", type="exact_text", label="Declare", expected_value="  "
            )

    def test_field_must_match_type(self):
        # options only on choice types; expected_value only on exact_text
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="short_text", label="L", options=["a"])
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="single_choice",
                label="L",
                options=["a"],
                expected_value="x",
            )

    def test_other_option_valid_on_single_choice(self):
        q = QuestionDto(
            id="q1", type="single_choice", label="Source",
            options=["Friend", "Others"], other_option="Others",
        )
        self.assertEqual(q.other_option, "Others")

    def test_other_option_valid_on_multi_choice(self):
        q = QuestionDto(
            id="q1", type="multi_choice", label="Source",
            options=["A", "Others"], other_option="Others",
        )
        self.assertEqual(q.other_option, "Others")

    def test_other_option_must_be_in_options(self):
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1", type="single_choice", label="Source",
                options=["Friend", "LinkedIn"], other_option="Others",
            )

    def test_other_option_rejected_on_non_choice(self):
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1", type="short_text", label="Name", other_option="Others",
            )


class TestFormSchemaDto(unittest.TestCase):
    def test_empty_questions_allowed(self):
        self.assertEqual(FormSchemaDto(questions=[]).questions, [])

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValidationError):
            FormSchemaDto(
                questions=[
                    QuestionDto(id="q1", type="short_text", label="A"),
                    QuestionDto(id="q1", type="short_text", label="B"),
                ]
            )

    def test_showwhen_must_reference_existing_other_question(self):
        FormSchemaDto(
            questions=[
                QuestionDto(
                    id="q1", type="single_choice", label="Pick", options=["Other", "X"]
                ),
                QuestionDto(
                    id="q2",
                    type="short_text",
                    label="Explain",
                    show_when=ShowWhenDto(question_id="q1", equals="Other"),
                ),
            ]
        )
        with self.assertRaises(ValidationError):
            FormSchemaDto(
                questions=[
                    QuestionDto(
                        id="q2",
                        type="short_text",
                        label="Explain",
                        show_when=ShowWhenDto(question_id="missing", equals="Other"),
                    ),
                ]
            )

    def test_showwhen_self_reference_rejected(self):
        with self.assertRaises(ValidationError):
            FormSchemaDto(
                questions=[
                    QuestionDto(
                        id="q1",
                        type="short_text",
                        label="L",
                        show_when=ShowWhenDto(question_id="q1", equals="x"),
                    ),
                ]
            )


class TestPipelineConfigDto(unittest.TestCase):
    def test_minimal_stage(self):
        cfg = PipelineConfigDto(stages=[PipelineStageDto(stage="tech", rounds=2)])
        self.assertEqual(cfg.stages[0].rounds, 2)
        self.assertFalse(cfg.stages[0].referral_skippable)

    def test_rounds_must_be_positive(self):
        with self.assertRaises(ValidationError):
            PipelineStageDto(stage="tech", rounds=0)

    def test_duplicate_stage_rejected(self):
        with self.assertRaises(ValidationError):
            PipelineConfigDto(
                stages=[
                    PipelineStageDto(stage="tech", rounds=1),
                    PipelineStageDto(stage="tech", rounds=1),
                ]
            )

    def test_default_assignee_only_on_screening_or_behavioral(self):
        PipelineConfigDto(
            stages=[
                PipelineStageDto(stage="behavioral", rounds=1, default_assignee_id=9)
            ]
        )
        with self.assertRaises(ValidationError):
            PipelineConfigDto(
                stages=[PipelineStageDto(stage="tech", rounds=1, default_assignee_id=9)]
            )


class TestScreenRulesDto(unittest.TestCase):
    def test_email_domain_qualify(self):
        ScreenRulesDto(
            rules=[
                ScreenRuleDto(
                    id="r1",
                    condition=ScreenRuleConditionDto(
                        source="email_domain", operator="in", value=["google.com"]
                    ),
                    action="qualify",
                )
            ]
        )

    def test_answer_rule_requires_question_id(self):
        with self.assertRaises(ValidationError):
            ScreenRuleDto(
                id="r1",
                condition=ScreenRuleConditionDto(
                    source="answer", operator="equals", value="no"
                ),
                action="reject",
            )

    def test_email_domain_rejects_question_id(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(
                source="email_domain", operator="in", value=["g.com"], question_id="q1"
            )

    def test_duplicate_rule_id_rejected(self):
        with self.assertRaises(ValidationError):
            ScreenRulesDto(
                rules=[
                    ScreenRuleDto(
                        id="r1",
                        condition=ScreenRuleConditionDto(
                            source="email_domain", operator="equals", value="g.com"
                        ),
                        action="reject",
                    ),
                    ScreenRuleDto(
                        id="r1",
                        condition=ScreenRuleConditionDto(
                            source="email_domain", operator="equals", value="h.com"
                        ),
                        action="reject",
                    ),
                ]
            )

    def test_email_domain_operator_restricted(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(
                source="email_domain", operator="not_in", value=["g.com"]
            )


class TestProfileConfigDto(unittest.TestCase):
    def test_defaults_optional(self):
        c = ProfileConfigDto()
        self.assertEqual(
            (c.education, c.work_experience, c.resume),
            ("optional", "optional", "optional"),
        )

    def test_rejects_bad_level(self):
        with self.assertRaises(ValidationError):
            ProfileConfigDto(education="mandatory")


if __name__ == "__main__":
    unittest.main()
