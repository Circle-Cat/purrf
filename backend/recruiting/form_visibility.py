"""Which submission-form questions a candidate actually saw.

Python twin of ``frontend/src/pages/Recruiting/postings/questionVisibility.js``.
The two must agree exactly: the renderer decides what the candidate is shown,
this module decides what the server enforces as required and what it keeps.
A divergence either demands an answer to a question that was never displayed
or discards one that was.

Form schemas live in a JSONB column and are stored camelCase — their contents
never pass through a request DTO's alias generator — so keys are read here as
``showWhen`` / ``questionId`` / ``otherOption``.

Visibility is evaluated in a single pass against the answers as submitted,
exactly as the renderer evaluates it. A chained rule (q3 depends on q2, which
is itself hidden) is therefore resolved the same way in both places rather
than iterated to a fixpoint on one side only.
"""

# Sibling-key suffix holding an "Other" option's free text.
OTHER_SUFFIX = "__other"


def is_visible(question: dict, answers: dict) -> bool:
    """Whether a question's showWhen rule is satisfied by the given answers.

    Args:
        question (dict): One question out of a form schema.
        answers (dict): Answers keyed by question id.

    Returns:
        bool: True when the question has no showWhen rule, or the referenced
        question's answer matches ``equals`` (membership, for a list answer).
    """
    show_when = question.get("showWhen")
    if not show_when:
        return True
    dependency = answers.get(show_when.get("questionId"))
    target = show_when.get("equals")
    if isinstance(dependency, list):
        return target in dependency
    return dependency == target


def other_selected(question, value) -> bool:
    """Whether a recorded value selects the question's "Other" option.

    That selection is what makes the renderer display the ``<id>__other``
    sibling holding the free text, and so what makes that sibling worth
    keeping.

    Args:
        question (dict): One question out of a form schema.
        value: The question's own recorded value.

    Returns:
        bool: True when the question offers an "Other" option and the value
        picks it.
    """
    other = question.get("otherOption")
    if other is None:
        return False
    if question.get("type") == "multi_choice":
        return isinstance(value, list) and other in value
    return value == other


def visible_questions(form_schema: dict | None, answers: dict) -> list[dict]:
    """The questions the form displays for these answers, in schema order.

    Args:
        form_schema (dict | None): The job's live form schema.
        answers (dict): Answers keyed by question id.

    Returns:
        list[dict]: The visible subset of ``form_schema["questions"]``.
    """
    questions = (form_schema or {}).get("questions", [])
    return [q for q in questions if is_visible(q, answers)]


def prune_answers(form_schema: dict | None, answers: dict) -> dict:
    """Answers narrowed to what the form was showing when they were written.

    Applications stay editable until processing starts, and the client seeds
    its answer state from the previous version without cropping it, so a
    candidate who changes an answer that hides a dependent question — or who
    edits after an owner deletes a question — re-submits the stale value
    underneath. Only the current state is meaningful, so the stale keys are
    dropped at write time rather than stored and explained away later.

    Args:
        form_schema (dict | None): The job's live form schema.
        answers (dict): Answers keyed by question id, as submitted.

    Returns:
        dict: The kept answers — one entry per visible question that has a
        recorded value, plus its ``<id>__other`` free text while the value
        still selects the "Other" option.
    """
    kept = {}
    for question in visible_questions(form_schema, answers):
        question_id = question.get("id")
        if question_id in answers:
            kept[question_id] = answers[question_id]
        other_key = f"{question_id}{OTHER_SUFFIX}"
        if other_key in answers and other_selected(question, answers.get(question_id)):
            kept[other_key] = answers[other_key]
    return kept
