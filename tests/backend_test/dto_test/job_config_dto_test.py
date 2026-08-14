import unittest

from pydantic import ValidationError

from backend.dto.job_config_dto import (
    FormSchemaDto,
    LONG_TEXT_MAX_LENGTH,
    PipelineConfigDto,
    PipelineStageDto,
    ProfileConfigDto,
    QuestionDto,
    ScreenRuleConditionDto,
    ScreenRuleDto,
    ScreenRulesDto,
    SHORT_TEXT_MAX_LENGTH,
    ShowWhenDto,
    question_seq_floor,
)


class TestQuestionDto(unittest.TestCase):
    def test_short_text_minimal(self):
        q = QuestionDto(id="q1", type="short_text", label="Name")
        self.assertEqual(q.id, "q1")
        self.assertFalse(q.required)

    def test_label_must_be_nonempty(self):
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="short_text", label="   ")

    def test_description_optional_and_allowed_on_any_type(self):
        # Absent by default.
        self.assertIsNone(
            QuestionDto(id="q1", type="short_text", label="Name").description
        )
        # Accepted on a plain text type...
        q = QuestionDto(
            id="q1", type="short_text", label="Name", description="Your legal name"
        )
        self.assertEqual(q.description, "Your legal name")
        # ...and on a choice type, without tripping the per-type foreign-field check.
        q2 = QuestionDto(
            id="q2",
            type="single_choice",
            label="Pick",
            options=["a", "b"],
            description="Choose one",
        )
        self.assertEqual(q2.description, "Choose one")

    def test_long_text_maxlength_and_maxwords_must_be_positive(self):
        QuestionDto(id="q1", type="long_text", label="Why", max_length=10)
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="long_text", label="Why", max_length=0)
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="long_text", label="Why", max_length=0)

    def test_long_text_requires_a_max_length(self):
        with self.assertRaisesRegex(ValidationError, "long_text requires a max_length"):
            QuestionDto(id="q1", type="long_text", label="Why")

    def test_long_text_max_length_must_not_exceed_the_hard_ceiling(self):
        QuestionDto(
            id="q1", type="long_text", label="Why", max_length=LONG_TEXT_MAX_LENGTH
        )
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="long_text",
                label="Why",
                max_length=LONG_TEXT_MAX_LENGTH + 1,
            )

    def test_the_two_text_ceilings_are_the_documented_values(self):
        # Pinned rather than derived: the JS mirror in questionLimits.js
        # carries the same two numbers and nothing else would catch a drift.
        self.assertEqual(SHORT_TEXT_MAX_LENGTH, 255)
        self.assertEqual(LONG_TEXT_MAX_LENGTH, 5000)

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
            id="q1",
            type="single_choice",
            label="Source",
            options=["Friend", "Others"],
            other_option="Others",
        )
        self.assertEqual(q.other_option, "Others")

    def test_other_option_valid_on_multi_choice(self):
        q = QuestionDto(
            id="q1",
            type="multi_choice",
            label="Source",
            options=["A", "Others"],
            other_option="Others",
        )
        self.assertEqual(q.other_option, "Others")

    def test_other_option_must_be_in_options(self):
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="single_choice",
                label="Source",
                options=["Friend", "LinkedIn"],
                other_option="Others",
            )

    def test_other_option_rejected_on_non_choice(self):
        with self.assertRaises(ValidationError):
            QuestionDto(
                id="q1",
                type="short_text",
                label="Name",
                other_option="Others",
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

    def test_next_seq_may_be_omitted(self):
        """Existing postings have no counter yet."""
        schema = FormSchemaDto(
            questions=[{"id": "q1", "type": "short_text", "label": "A"}]
        )
        self.assertIsNone(schema.next_seq)

    def test_next_seq_accepts_a_value_past_the_highest_id(self):
        """A counter that cannot collide with a live question is fine."""
        schema = FormSchemaDto(
            questions=[{"id": "q1", "type": "short_text", "label": "A"}],
            next_seq=5,
        )
        self.assertEqual(schema.next_seq, 5)

    def test_next_seq_rejects_a_value_that_would_recycle_an_id(self):
        """A stale client must not be able to rewind the counter."""
        with self.assertRaises(ValidationError):
            FormSchemaDto(
                questions=[
                    {"id": "q1", "type": "short_text", "label": "A"},
                    {"id": "q4", "type": "short_text", "label": "B"},
                ],
                next_seq=3,
            )

    def test_next_seq_accepts_exactly_the_floor(self):
        """The floor itself, not just past it, must be accepted."""
        schema = FormSchemaDto(
            questions=[{"id": "q1", "type": "short_text", "label": "A"}],
            next_seq=2,
        )
        self.assertEqual(schema.next_seq, 2)

    def test_next_seq_rejects_exactly_one_below_the_floor(self):
        """One below the floor, not just well below it, must be rejected."""
        with self.assertRaises(ValidationError):
            FormSchemaDto(
                questions=[{"id": "q1", "type": "short_text", "label": "A"}],
                next_seq=1,
            )

    def test_next_seq_floor_is_one_for_an_empty_form(self):
        """An empty form's counter may start at 1."""
        schema = FormSchemaDto(questions=[], next_seq=1)
        self.assertEqual(schema.next_seq, 1)

    def test_next_seq_rejects_zero_on_an_empty_form(self):
        """An empty form's floor is 1, so 0 must be rejected."""
        with self.assertRaises(ValidationError):
            FormSchemaDto(questions=[], next_seq=0)

    def test_next_seq_ignores_non_numeric_ids(self):
        """Hand-authored ids that aren't q<n> don't constrain the counter."""
        schema = FormSchemaDto(
            questions=[{"id": "custom", "type": "short_text", "label": "A"}],
            next_seq=1,
        )
        self.assertEqual(schema.next_seq, 1)


class TestPipelineConfigDto(unittest.TestCase):
    def test_minimal_stage(self):
        cfg = PipelineConfigDto(stages=[PipelineStageDto(stage="tech", rounds=2)])
        self.assertEqual(cfg.stages[0].rounds, 2)

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

    def test_owner_ids_accepts_list(self):
        dto = PipelineConfigDto.model_validate({"ownerIds": [1, 2], "stages": []})
        self.assertEqual(dto.owner_ids, [1, 2])

    def test_legacy_owner_id_merges_into_owner_ids(self):
        dto = PipelineConfigDto.model_validate({"ownerId": 5, "stages": []})
        self.assertEqual(dto.owner_ids, [5])

    def test_duplicate_owner_ids_rejected(self):
        with self.assertRaises(ValidationError):
            PipelineConfigDto.model_validate({"ownerIds": [1, 1], "stages": []})

    def test_offer_is_rejected_as_a_pipeline_stage(self):
        with self.assertRaises(ValidationError):
            PipelineStageDto(stage="offer", rounds=1)


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

    def test_auto_hire_action_accepted(self):
        ScreenRulesDto(
            rules=[
                ScreenRuleDto(
                    id="r1",
                    condition=ScreenRuleConditionDto(
                        source="email_domain", operator="equals", value="circlecat.org"
                    ),
                    action="auto_hire",
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

    def test_email_domain_not_in_accepted(self):
        ScreenRuleConditionDto(
            source="email_domain", operator="not_in", value=["g.com"]
        )

    def test_email_domain_invalid_operator_still_rejected(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(
                source="email_domain", operator="bogus", value=["g.com"]
            )

    def test_email_domain_empty_list_value_rejected(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(source="email_domain", operator="not_in", value=[])

    def test_email_domain_empty_string_value_rejected(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(source="email_domain", operator="equals", value="")

    def test_email_domain_blank_list_entries_rejected(self):
        with self.assertRaises(ValidationError):
            ScreenRuleConditionDto(
                source="email_domain", operator="in", value=["  ", ""]
            )


class TestQuestionSeqFloor(unittest.TestCase):
    """The floor rule, shared by the DTO validator and the service layer."""

    def test_one_past_the_highest_numbered_id(self):
        """Gaps don't matter; only the highest id does."""
        self.assertEqual(question_seq_floor(["q1", "q7", "q4"]), 8)

    def test_one_for_an_empty_form(self):
        """An empty form's first question is q1."""
        self.assertEqual(question_seq_floor([]), 1)

    def test_ignores_ids_the_counter_never_issued(self):
        """Hand-authored and malformed ids don't constrain the counter."""
        self.assertEqual(question_seq_floor(["custom", "q", "qx", None, 5]), 1)


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


class TestNewCrossChecks(unittest.TestCase):
    """Rules added with the posting editor's own validation."""

    @staticmethod
    def _gate(**kw):
        return {
            "id": "q1",
            "type": "single_choice",
            "label": "Need sponsorship?",
            "options": ["Yes", "No"],
            **kw,
        }

    def test_options_must_be_unique(self):
        """Options are matched by text, so a duplicate is one option twice."""
        with self.assertRaises(ValidationError):
            QuestionDto(**self._gate(options=["Yes", "No", "Yes"]))

    def test_show_when_value_must_be_an_option_of_its_gate(self):
        """Renaming the option a rule names would otherwise hide the question
        from every candidate, silently and for good."""
        with self.assertRaises(ValidationError) as ctx:
            FormSchemaDto(
                questions=[
                    self._gate(),
                    {
                        "id": "q2",
                        "type": "short_text",
                        "label": "Which visa?",
                        "showWhen": {"questionId": "q1", "equals": "Nope"},
                    },
                ]
            )
        self.assertIn("not in options of q1", str(ctx.exception))

    def test_show_when_value_matching_an_option_is_accepted(self):
        schema = FormSchemaDto(
            questions=[
                self._gate(),
                {
                    "id": "q2",
                    "type": "short_text",
                    "label": "Which visa?",
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
            ]
        )
        self.assertEqual(schema.questions[1].show_when.equals, "Yes")

    def test_show_when_on_a_free_text_gate_is_not_checked(self):
        """A text answer can be anything, so there is no option list to be in."""
        schema = FormSchemaDto(
            questions=[
                {"id": "q1", "type": "short_text", "label": "Country"},
                {
                    "id": "q2",
                    "type": "short_text",
                    "label": "Which visa?",
                    "showWhen": {"questionId": "q1", "equals": "Canada"},
                },
            ]
        )
        self.assertEqual(schema.questions[1].show_when.equals, "Canada")

    def test_answer_condition_rejects_an_empty_value(self):
        """An empty list reaches ``values[0]`` in screen_rules and 500s every
        application to the posting."""
        for value in ([], "", "  "):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ScreenRuleConditionDto(
                    source="answer",
                    operator="equals",
                    questionId="q1",
                    value=value,
                )


if __name__ == "__main__":
    unittest.main()
