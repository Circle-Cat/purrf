import json
import unittest
from pathlib import Path

from backend.recruiting import form_visibility

# Contract shared with questionVisibility.test.js. See the file's own comment:
# this module deletes the answers the renderer will not show, so both
# implementations are held to one definition rather than to each other's
# docstrings.
_VECTORS = json.loads(
    Path("tests/shared/form_visibility_vectors.json").read_text(encoding="utf-8")
)


def _question(id, **kw):
    """A form-schema question, camelCase as it is stored in JSONB."""
    return {"id": id, "type": kw.pop("type", "short_text"), "label": id, **kw}


def _gated(id, on, equals, **kw):
    """A question shown only while question ``on`` answers ``equals``."""
    return _question(id, showWhen={"questionId": on, "equals": equals}, **kw)


class SharedVectorTest(unittest.TestCase):
    """Every case in the cross-language fixture, run against this side."""

    def test_the_fixture_is_not_silently_empty(self):
        """A path typo would otherwise turn the whole contract into a no-op."""
        self.assertGreaterEqual(len(_VECTORS["cases"]), 27)

    def test_every_case_is_named_distinctly(self):
        """Two cases sharing a name once hid that they were the same case."""
        names = [case["name"] for case in _VECTORS["cases"]]
        self.assertCountEqual(set(names), names)

    def test_visible_questions_matches_every_vector(self):
        for case in _VECTORS["cases"]:
            with self.subTest(case["name"]):
                visible = form_visibility.visible_questions(
                    {"questions": case["questions"]}, case["answers"]
                )
                self.assertEqual([q.get("id") for q in visible], case["visible"])

    def test_prune_answers_matches_every_vector(self):
        for case in _VECTORS["cases"]:
            with self.subTest(case["name"]):
                self.assertEqual(
                    form_visibility.prune_answers(
                        {"questions": case["questions"]}, case["answers"]
                    ),
                    case["pruned"],
                )

    def test_pruning_every_vector_twice_changes_nothing(self):
        """Idempotence, over the whole corpus rather than one hand-picked form.

        The client seeds the next edit from the previous submission, so prune
        is applied to its own output on every save. A rule resolved against an
        answer the first pass removes would peel one more layer each time and
        silently delete answers the candidate never withdrew.

        Asserted against the vector rather than against the first pass, so an
        implementation that prunes nothing at all cannot satisfy it.
        """
        for case in _VECTORS["cases"]:
            with self.subTest(case["name"]):
                schema = {"questions": case["questions"]}
                once = form_visibility.prune_answers(schema, case["answers"])
                self.assertEqual(
                    form_visibility.prune_answers(schema, once), case["pruned"]
                )


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


class VisibleQuestionsTest(unittest.TestCase):
    def test_no_schema_yields_nothing(self):
        self.assertEqual(form_visibility.visible_questions(None, {"q1": "x"}), [])

    def test_a_null_questions_list_yields_nothing(self):
        """Hand-edited JSONB can hold null where the DTO would write a list."""
        self.assertEqual(
            form_visibility.visible_questions({"questions": None}, {"q1": "x"}), []
        )

    def test_keeps_schema_order(self):
        schema = {"questions": [_question("q1"), _question("q2"), _question("q3")]}
        self.assertEqual(
            [q["id"] for q in form_visibility.visible_questions(schema, {})],
            ["q1", "q2", "q3"],
        )

    def test_a_gate_hidden_by_its_own_gate_hides_what_it_gates(self):
        """The regression the shared chain vectors exist for.

        q3's rule reads q2's answer, and that answer is still recorded even
        though q2 is hidden. Resolving q3's rule alone would show q3 on this
        pass, then hide it on the next one once q2's answer had been pruned.
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
        self.assertEqual([q["id"] for q in visible], ["q1"])

    def test_a_gate_declared_after_the_question_it_gates_still_resolves(self):
        """Resolution follows the rules, not the order questions appear in."""
        schema = {
            "questions": [_gated("q2", "q1", "Yes"), _question("q1")],
        }
        visible = form_visibility.visible_questions(schema, {"q1": "Yes"})
        self.assertEqual([q["id"] for q in visible], ["q2", "q1"])


class PruneAnswersTest(unittest.TestCase):
    def test_a_question_without_an_id_contributes_no_key(self):
        """Keying off a missing id would write a literal "null" JSONB key."""
        schema = {"questions": [{"type": "short_text", "label": "orphan"}]}
        self.assertEqual(form_visibility.prune_answers(schema, {"q1": "x"}), {})

    def test_a_job_with_no_form_keeps_nothing(self):
        self.assertEqual(form_visibility.prune_answers(None, {"q1": "x"}), {})

    def test_repeated_pruning_preserves_a_deep_satisfied_chain(self):
        """The answers stay put however many times the candidate re-saves."""
        schema = {
            "questions": [
                _question("q1"),
                _gated("q2", "q1", "Yes"),
                _gated("q3", "q2", "Yes"),
                _gated("q4", "q3", "Yes", type="long_text"),
            ]
        }
        answers = {"q1": "Yes", "q2": "Yes", "q3": "Yes", "q4": "an essay"}
        for _ in range(3):
            answers = form_visibility.prune_answers(schema, answers)
        self.assertEqual(
            answers, {"q1": "Yes", "q2": "Yes", "q3": "Yes", "q4": "an essay"}
        )


if __name__ == "__main__":
    unittest.main()
