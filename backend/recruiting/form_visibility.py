"""Which submission-form questions a candidate actually saw.

Python twin of ``frontend/src/pages/Recruiting/postings/questionVisibility.js``.
The two must agree exactly, because this side *deletes* what it leaves out:
the renderer decides what the candidate is shown, and this module decides
which answers survive the write. Were this side the stricter of the two, an
answer the candidate gave to a question the form displayed would be dropped
silently, with no earlier version to recover it from; were it the looser, a
key the renderer will not show would be stored and surface as a stray entry
in the reviewer's "Other recorded answers" group.

Form schemas live in a JSONB column and are stored camelCase — their contents
never pass through a request DTO's alias generator — so keys are read here as
``showWhen`` / ``questionId`` / ``otherOption``.

The two are pinned to one another by the shared cases in
``tests/shared/form_visibility_vectors.json``, which both test suites load.
"""

# Sibling-key suffix holding an "Other" option's free text.
OTHER_SUFFIX = "__other"


def _matches(answer, target) -> bool:
    """Whether a recorded answer satisfies a showWhen rule's ``equals``."""
    if isinstance(answer, list):
        return target in answer
    return answer == target


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

    Visibility is transitive: a question is shown when its own rule matches
    *and* the question that rule points at is itself shown. A rule may target
    another gated question, so resolving each rule in isolation would keep a
    question whose own gate is hidden, and would decide that from the stale
    answer still sitting under the hidden gate. Since ``prune_answers``
    deletes that stale answer, the next write would then resolve the same
    form differently and drop one more layer -- evaluating the chain through
    to its root is what makes pruning idempotent.

    Args:
        form_schema (dict | None): The job's live form schema.
        answers (dict): Answers keyed by question id.

    Returns:
        list[dict]: The visible subset of ``form_schema["questions"]``.
    """
    questions = (form_schema or {}).get("questions") or []
    by_id = {q.get("id"): q for q in questions}
    resolved: dict = {}

    def visible(question: dict) -> bool:
        show_when = question.get("showWhen")
        if not show_when:
            return True
        question_id = question.get("id")
        if question_id in resolved:
            return resolved[question_id]
        # Seed False before recursing so a cycle terminates. The schema
        # validator rejects a self-reference but not a longer loop, and
        # nothing in a loop has a reachable gate, so none of it is shown.
        resolved[question_id] = False
        gate = by_id.get(show_when.get("questionId"))
        shown = (
            gate is not None
            and visible(gate)
            and _matches(answers.get(gate.get("id")), show_when.get("equals"))
        )
        resolved[question_id] = shown
        return shown

    return [q for q in questions if visible(q)]


def prune_answers(form_schema: dict | None, answers: dict) -> dict:
    """Answers narrowed to what the form was showing when they were written.

    Applications stay editable until processing starts, and the client seeds
    its answer state from the previous version without cropping it, so a
    candidate who changes an answer that hides a dependent question — or who
    edits after an owner deletes a question — re-submits the stale value
    underneath. Only the current state is meaningful, so the stale keys are
    dropped at write time rather than stored and explained away later.

    Idempotent: pruning an already-pruned set of answers is a no-op. It has to
    be, because the client seeds the next edit from what this returned — a
    rule resolved against an answer this call removes would drop one further
    layer on every save until the chain was gone.

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
        # A schema question with no id cannot own an answer; keying off None
        # would write a literal "null" column key.
        if question_id is None:
            continue
        if question_id in answers:
            kept[question_id] = answers[question_id]
        other_key = f"{question_id}{OTHER_SUFFIX}"
        if other_key in answers and other_selected(question, answers.get(question_id)):
            kept[other_key] = answers[other_key]
    return kept
