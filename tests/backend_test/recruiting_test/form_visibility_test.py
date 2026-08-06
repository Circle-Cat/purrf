import unittest

from backend.recruiting import form_visibility


def _question(id, **kw):
    """A form-schema question, camelCase as it is stored in JSONB."""
    return {"id": id, "type": kw.pop("type", "short_text"), "label": id, **kw}


def _gated(id, on, equals, **kw):
    """A question shown only while question ``on`` answers ``equals``."""
    return _question(id, showWhen={"questionId": on, "equals": equals}, **kw)


class IsVisibleTest(unittest.TestCase):
    def test_question_without_a_rule_is_always_visible(self):
        self.assertTrue(form_visibility.is_visible(_question("q1"), {}))

    def test_rule_matches_a_scalar_answer(self):
        question = _gated("q2", "q1", "Yes")
        self.assertTrue(form_visibility.is_visible(question, {"q1": "Yes"}))
        self.assertFalse(form_visibility.is_visible(question, {"q1": "No"}))

    def test_rule_matches_membership_in_a_list_answer(self):
        question = _gated("q2", "q1", "Backend")
        self.assertTrue(
            form_visibility.is_visible(question, {"q1": ["Backend", "Frontend"]})
        )
        self.assertFalse(form_visibility.is_visible(question, {"q1": ["Frontend"]}))

    def test_unanswered_dependency_hides_the_question(self):
        self.assertFalse(form_visibility.is_visible(_gated("q2", "q1", "Yes"), {}))


class OtherSelectedTest(unittest.TestCase):
    def test_false_when_the_question_has_no_other_option(self):
        self.assertFalse(
            form_visibility.other_selected(
                _question("q1", type="single_choice", options=["A"]), "A"
            )
        )

    def test_single_choice_matches_the_value_itself(self):
        question = _question(
            "q1", type="single_choice", options=["A", "Other"], otherOption="Other"
        )
        self.assertTrue(form_visibility.other_selected(question, "Other"))
        self.assertFalse(form_visibility.other_selected(question, "A"))

    def test_multi_choice_matches_membership(self):
        question = _question(
            "q1", type="multi_choice", options=["A", "Other"], otherOption="Other"
        )
        self.assertTrue(form_visibility.other_selected(question, ["A", "Other"]))
        self.assertFalse(form_visibility.other_selected(question, ["A"]))

    def test_multi_choice_ignores_a_scalar_value(self):
        """A multi_choice answer is a list; a bare string never selects Other."""
        question = _question(
            "q1", type="multi_choice", options=["Other"], otherOption="Other"
        )
        self.assertFalse(form_visibility.other_selected(question, "Other"))


class VisibleQuestionsTest(unittest.TestCase):
    def test_no_schema_yields_nothing(self):
        self.assertEqual(form_visibility.visible_questions(None, {"q1": "x"}), [])

    def test_keeps_schema_order(self):
        schema = {"questions": [_question("q1"), _question("q2"), _question("q3")]}
        self.assertEqual(
            [q["id"] for q in form_visibility.visible_questions(schema, {})],
            ["q1", "q2", "q3"],
        )

    def test_chained_rule_resolves_in_one_pass(self):
        """q3 depends on q2, which is itself hidden but still holds a value.

        Evaluated in a single pass q3 stays visible, matching what
        ``questionVisibility.js`` renders. The two must not diverge: the
        read-only view derives "answers the renderer will not show" from the
        same rule, so a fixpoint here would hide q3's answer everywhere.
        """
        schema = {
            "questions": [
                _question("q1"),
                _gated("q2", "q1", "Yes"),
                _gated("q3", "q2", "Yes"),
            ]
        }
        visible = form_visibility.visible_questions(
            schema, {"q1": "No", "q2": "Yes", "q3": "kept"}
        )
        self.assertEqual([q["id"] for q in visible], ["q1", "q3"])


class PruneAnswersTest(unittest.TestCase):
    def test_drops_an_answer_whose_question_left_the_form(self):
        schema = {"questions": [_question("q1")]}
        self.assertEqual(
            form_visibility.prune_answers(schema, {"q1": "kept", "q5": "WeChat"}),
            {"q1": "kept"},
        )

    def test_drops_an_answer_under_a_now_hidden_question(self):
        schema = {"questions": [_question("q1"), _gated("q2", "q1", "Yes")]}
        self.assertEqual(
            form_visibility.prune_answers(schema, {"q1": "No", "q2": "F-1 OPT"}),
            {"q1": "No"},
        )

    def test_keeps_an_answer_under_a_still_visible_question(self):
        schema = {"questions": [_question("q1"), _gated("q2", "q1", "Yes")]}
        self.assertEqual(
            form_visibility.prune_answers(schema, {"q1": "Yes", "q2": "F-1 OPT"}),
            {"q1": "Yes", "q2": "F-1 OPT"},
        )

    def test_keeps_other_free_text_while_other_is_selected(self):
        schema = {
            "questions": [
                _question(
                    "q3",
                    type="multi_choice",
                    options=["Backend", "Other"],
                    otherOption="Other",
                )
            ]
        }
        answers = {"q3": ["Backend", "Other"], "q3__other": "Infrastructure"}
        self.assertEqual(form_visibility.prune_answers(schema, answers), answers)

    def test_drops_other_free_text_once_other_is_deselected(self):
        schema = {
            "questions": [
                _question(
                    "q3",
                    type="multi_choice",
                    options=["Backend", "Frontend", "Other"],
                    otherOption="Other",
                )
            ]
        }
        self.assertEqual(
            form_visibility.prune_answers(
                schema,
                {"q3": ["Backend", "Frontend"], "q3__other": "Infrastructure"},
            ),
            {"q3": ["Backend", "Frontend"]},
        )

    def test_unanswered_visible_question_adds_no_key(self):
        """Absent stays absent — pruning must not materialize empty answers."""
        schema = {"questions": [_question("q1"), _question("q2")]}
        self.assertEqual(
            form_visibility.prune_answers(schema, {"q1": "x"}), {"q1": "x"}
        )

    def test_keeps_a_falsy_answer(self):
        """Presence, not truthiness, decides: an empty answer was still given."""
        schema = {"questions": [_question("q1"), _question("q2")]}
        self.assertEqual(
            form_visibility.prune_answers(schema, {"q1": "", "q2": []}),
            {"q1": "", "q2": []},
        )

    def test_a_job_with_no_form_keeps_nothing(self):
        self.assertEqual(form_visibility.prune_answers(None, {"q1": "x"}), {})


if __name__ == "__main__":
    unittest.main()
