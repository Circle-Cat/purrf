/** True when a recorded answer satisfies a showWhen rule's `equals`. */
const matches = (answer, target) =>
  Array.isArray(answer) ? answer.includes(target) : answer === target;

/**
 * The questions a form displays for the given answers, in schema order.
 *
 * Visibility is transitive: a question is shown when its own rule matches
 * *and* the question that rule points at is itself shown. A rule may target
 * another gated question, so resolving each rule in isolation would display a
 * question whose own gate is hidden, and would decide that from the stale
 * answer still sitting under the hidden gate. The server prunes stored
 * answers to this same set, so that stale answer disappears on the next save
 * and the identical form would then resolve differently — evaluating the
 * chain through to its root is what keeps the set stable across saves.
 *
 * Exported so a read-only consumer can compute the same visible set and tell
 * which recorded answers this renderer will *not* display. Mirrored in
 * `backend/recruiting/form_visibility.py`, which deletes the answers to
 * everything this leaves out; the two are pinned to one another by the shared
 * vectors in `tests/shared/form_visibility_vectors.json`.
 *
 * @param {object[]} questions
 * @param {Record<string, string|string[]>} answers
 * @returns {object[]}
 */
export const visibleQuestions = (questions, answers) => {
  const byId = new Map(questions.map((q) => [q.id, q]));
  const resolved = new Map();
  const visible = (question) => {
    if (!question.showWhen) return true;
    if (resolved.has(question.id)) return resolved.get(question.id);
    // Seed `false` before recursing so a cycle terminates. The schema
    // validator rejects a self-reference but not a longer loop, and nothing
    // in a loop has a reachable gate, so none of it is shown.
    resolved.set(question.id, false);
    const gate = byId.get(question.showWhen.questionId);
    const shown =
      gate !== undefined &&
      visible(gate) &&
      matches(answers[gate.id], question.showWhen.equals);
    resolved.set(question.id, shown);
    return shown;
  };
  return questions.filter(visible);
};

/**
 * True when a question's recorded value selects its "Other" option, which is
 * what makes `FormRenderer` render the `${id}__other` sibling answer.
 *
 * Shared for the same reason `visibleQuestions` is: the renderer and any
 * consumer computing which recorded answers the renderer will *not* show must
 * agree exactly, or the free text ends up either dropped from both views or
 * rendered twice.
 *
 * @param {object} question
 * @param {unknown} value The question's own recorded value.
 * @returns {boolean}
 */
export const otherSelected = (question, value) =>
  question.otherOption != null &&
  (question.type === "multi_choice"
    ? Array.isArray(value) && value.includes(question.otherOption)
    : value === question.otherOption);
