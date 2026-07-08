import unittest

from backend.recruiting import screen_rules


def _rule(id, source, operator, value, action, question_id=None):
    condition = {"source": source, "operator": operator, "value": value}
    if question_id is not None:
        condition["questionId"] = question_id
    return {"id": id, "condition": condition, "action": action}


class TestScreenRulesEvaluate(unittest.TestCase):
    def test_none_screen_rules_no_match(self):
        result = screen_rules.evaluate(None, "a@google.com", {})
        self.assertEqual(result, {"action": None, "rule_id": None})

    def test_empty_rules_list_no_match(self):
        result = screen_rules.evaluate({"rules": []}, "a@google.com", {})
        self.assertEqual(result, {"action": None, "rule_id": None})

    def test_email_domain_equals_matches(self):
        rules = {
            "rules": [_rule("r1", "email_domain", "equals", "google.com", "reject")]
        }
        result = screen_rules.evaluate(rules, "a@google.com", {})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_email_domain_equals_is_case_insensitive(self):
        rules = {
            "rules": [_rule("r1", "email_domain", "equals", "Google.com", "reject")]
        }
        result = screen_rules.evaluate(rules, "a@GOOGLE.COM", {})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_email_domain_equals_no_match(self):
        rules = {
            "rules": [_rule("r1", "email_domain", "equals", "google.com", "reject")]
        }
        result = screen_rules.evaluate(rules, "a@yahoo.com", {})
        self.assertEqual(result, {"action": None, "rule_id": None})

    def test_email_domain_in_matches(self):
        rules = {
            "rules": [
                _rule(
                    "r1",
                    "email_domain",
                    "in",
                    ["google.com", "circlecat.org"],
                    "qualify",
                )
            ]
        }
        result = screen_rules.evaluate(rules, "a@circlecat.org", {})
        self.assertEqual(result, {"action": "qualify", "rule_id": "r1"})

    def test_email_domain_not_in_matches_excluded_domain(self):
        rules = {
            "rules": [_rule("r1", "email_domain", "not_in", ["google.com"], "reject")]
        }
        result = screen_rules.evaluate(rules, "a@yahoo.com", {})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_email_domain_not_in_no_match_for_listed_domain(self):
        rules = {
            "rules": [_rule("r1", "email_domain", "not_in", ["google.com"], "reject")]
        }
        result = screen_rules.evaluate(rules, "a@google.com", {})
        self.assertEqual(result, {"action": None, "rule_id": None})

    def test_answer_equals_matches(self):
        rules = {
            "rules": [_rule("r1", "answer", "equals", "no", "reject", question_id="q1")]
        }
        result = screen_rules.evaluate(rules, "a@b.com", {"q1": "no"})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_answer_in_matches(self):
        rules = {
            "rules": [
                _rule("r1", "answer", "in", ["no", "maybe"], "reject", question_id="q1")
            ]
        }
        result = screen_rules.evaluate(rules, "a@b.com", {"q1": "maybe"})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_answer_not_in_matches(self):
        rules = {
            "rules": [
                _rule("r1", "answer", "not_in", ["yes"], "reject", question_id="q1")
            ]
        }
        result = screen_rules.evaluate(rules, "a@b.com", {"q1": "no"})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})

    def test_unanswered_question_never_matches(self):
        rules = {
            "rules": [_rule("r1", "answer", "equals", "no", "reject", question_id="q1")]
        }
        result = screen_rules.evaluate(rules, "a@b.com", {})
        self.assertEqual(result, {"action": None, "rule_id": None})

    def test_reject_wins_over_qualify_regardless_of_order(self):
        rules = {
            "rules": [
                _rule("r1", "email_domain", "equals", "google.com", "qualify"),
                _rule("r2", "answer", "equals", "no", "reject", question_id="q1"),
            ]
        }
        result = screen_rules.evaluate(rules, "a@google.com", {"q1": "no"})
        self.assertEqual(result, {"action": "reject", "rule_id": "r2"})

    def test_auto_hire_wins_over_qualify_when_no_reject(self):
        rules = {
            "rules": [
                _rule("r1", "email_domain", "equals", "google.com", "qualify"),
                _rule("r2", "answer", "equals", "no", "auto_hire", question_id="q1"),
            ]
        }
        result = screen_rules.evaluate(rules, "a@google.com", {"q1": "no"})
        self.assertEqual(result, {"action": "auto_hire", "rule_id": "r2"})

    def test_first_match_wins_within_same_action_type(self):
        rules = {
            "rules": [
                _rule("r1", "email_domain", "equals", "google.com", "reject"),
                _rule("r2", "email_domain", "in", ["google.com"], "reject"),
            ]
        }
        result = screen_rules.evaluate(rules, "a@google.com", {})
        self.assertEqual(result, {"action": "reject", "rule_id": "r1"})


if __name__ == "__main__":
    unittest.main()
