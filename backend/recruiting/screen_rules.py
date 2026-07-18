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


def _email_domains(emails: list[str]) -> set[str]:
    """The distinct lowercased domains of the candidate's email addresses.

    Args:
        emails (list[str]): The candidate's confirmed email addresses.

    Returns:
        set[str]: Lowercased domains; empty when there are no addresses.
    """
    return {email.rsplit("@", 1)[-1].lower() for email in emails if email}


def _email_domain_matches(condition: dict, domains: set[str]) -> bool:
    """True when the candidate's email domains satisfy an email_domain
    condition.

    ``equals``/``in`` match when any of the candidate's domains is listed;
    ``not_in`` matches only when none of them is — holding a single address
    in a listed domain is enough to escape a ``not_in`` rule.

    Args:
        condition (dict): The rule's ``condition`` dict (camelCase keys).
        domains (set[str]): The candidate's lowercased email domains.

    Returns:
        bool: Whether the condition matches.
    """
    values = _normalized_values(condition.get("value", ""))
    operator = condition.get("operator")
    if operator == "equals":
        return values[0] in domains
    if operator == "in":
        return bool(domains.intersection(values))
    if operator == "not_in":
        return not domains.intersection(values)
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


def _rule_matches(rule: dict, domains: set[str], answers: dict) -> bool:
    """True when a single rule's condition is satisfied.

    Args:
        rule (dict): One entry of ``screen_rules["rules"]``.
        domains (set[str]): The candidate's lowercased email domains.
        answers (dict): The submission's question_id -> answer value map.

    Returns:
        bool: Whether the rule's condition matches.
    """
    condition = rule.get("condition") or {}
    source = condition.get("source")
    if source == "email_domain":
        return _email_domain_matches(condition, domains)
    if source == "answer":
        return _answer_matches(condition, answers)
    return False


def evaluate(screen_rules: dict | None, emails: list[str], answers: dict) -> dict:
    """Evaluate a job's screen_rules against one submission.

    Args:
        screen_rules (dict | None): The job's stored ``screen_rules`` JSONB
            value — ``{"rules": [{"id", "condition", "action"}, ...]}``,
            camelCase keys (per ``ScreenRulesDto``'s serialization) — or
            None/empty when unconfigured.
        emails (list[str]): All of the candidate's confirmed email
            addresses — email_domain rules match against any of them, not
            just the contact address.
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
    domains = _email_domains(emails)
    matched = {}
    for rule in rules:
        action = rule.get("action")
        if (
            action in _ACTION_PRIORITY
            and action not in matched
            and _rule_matches(rule, domains, answers)
        ):
            matched[action] = rule.get("id")
    for action in _ACTION_PRIORITY:
        if action in matched:
            return {"action": action, "rule_id": matched[action]}
    return {"action": None, "rule_id": None}
