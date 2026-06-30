import unittest

from pydantic import ValidationError

from backend.dto.job_config_dto import FormSchemaDto, QuestionDto, ShowWhenDto


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
            id="q1", type="multi_choice", label="L", options=["a", "b"], max_selections=2
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
        QuestionDto(id="q1", type="exact_text", label="Declare", expected_value="I confirm")
        with self.assertRaises(ValidationError):
            QuestionDto(id="q1", type="exact_text", label="Declare", expected_value="  ")

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
                QuestionDto(id="q1", type="single_choice", label="Pick", options=["Other", "X"]),
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


if __name__ == "__main__":
    unittest.main()
