"""Machine-screening rule evaluation for a job's screen_rules.

Mirrors backend/recruiting/cooldown.py's shape: pure functions, no I/O,
independently unit-testable, called from ApplicationService.submit().
"""

_ACTION_PRIORITY = ("reject", "auto_hire", "qualify")


def _normalized_values(value: str | list[str]) -> list[str]:
    """A condition's value as a lowercased list, whether stored as a
    single string or a list of strings.

    Args:
        value (str | list[str]): The condition's raw ``value`` field.

    Returns:
        list[str]: Lowercased values, always a list.
    """
    values = value if isinstance(value, list) else [value]
    return [v.lower() for v in values]


def _email_domain_matches(condition: dict, email: str) -> bool:
    """True when ``email``'s domain satisfies an email_domain condition.

    Args:
        condition (dict): The rule's ``condition`` dict (camelCase keys).
        email (str): The candidate's primary email.

    Returns:
        bool: Whether the condition matches.
    """
    domain = email.rsplit("@", 1)[-1].lower() if email else ""
    values = _normalized_values(condition.get("value", ""))
    operator = condition.get("operator")
    if operator == "equals":
        return domain == values[0]
    if operator == "in":
        return domain in values
    return False


def _answer_matches(condition: dict, answers: dict) -> bool:
    """True when the candidate's answer satisfies an answer condition.

    A missing/unanswered question never matches — screening only acts on
    rules that can actually be evaluated.

    Args:
        condition (dict): The rule's ``condition`` dict (camelCase keys,
            e.g. ``questionId``).
        answers (dict): The submission's question_id -> answer value map.

    Returns:
        bool: Whether the condition matches.
    """
    question_id = condition.get("questionId")
    if question_id not in answers or answers[question_id] is None:
        return False
    answer = str(answers[question_id]).lower()
    values = _normalized_values(condition.get("value", ""))
    operator = condition.get("operator")
    if operator == "equals":
        return answer == values[0]
    if operator == "in":
        return answer in values
    if operator == "not_in":
        return answer not in values
    return False


def _rule_matches(rule: dict, email: str, answers: dict) -> bool:
    """True when a single rule's condition is satisfied.

    Args:
        rule (dict): One entry of ``screen_rules["rules"]``.
        email (str): The candidate's primary email.
        answers (dict): The submission's question_id -> answer value map.

    Returns:
        bool: Whether the rule's condition matches.
    """
    condition = rule.get("condition") or {}
    source = condition.get("source")
    if source == "email_domain":
        return _email_domain_matches(condition, email)
    if source == "answer":
        return _answer_matches(condition, answers)
    return False


def evaluate(screen_rules: dict | None, email: str, answers: dict) -> dict:
    """Evaluate a job's screen_rules against one submission.

    Args:
        screen_rules (dict | None): The job's stored ``screen_rules`` JSONB
            value — ``{"rules": [{"id", "condition", "action"}, ...]}``,
            camelCase keys (per ``ScreenRulesDto``'s serialization) — or
            None/empty when unconfigured.
        email (str): The candidate's primary email.
        answers (dict): The submission's question_id -> answer value map.

    Returns:
        dict: ``{"action": "reject" | "qualify" | "auto_hire" | None,
        "rule_id": str | None}``. Any matching ``"reject"`` rule wins
        outright; otherwise a matching ``"auto_hire"`` rule wins over a
        matching ``"qualify"`` rule; the first matching rule (list order)
        is returned within a tied action type. ``{"action": None,
        "rule_id": None}`` when nothing matches or ``screen_rules`` is
        empty/missing.
    """
    rules = (screen_rules or {}).get("rules") or []
    matched = {}
    for rule in rules:
        action = rule.get("action")
        if (
            action in _ACTION_PRIORITY
            and action not in matched
            and _rule_matches(rule, email, answers)
        ):
            matched[action] = rule.get("id")
    for action in _ACTION_PRIORITY:
        if action in matched:
            return {"action": action, "rule_id": matched[action]}
    return {"action": None, "rule_id": None}
