/** True when a recorded answer satisfies a showWhen rule's `equals`. */
const matches = (answer, target) =>
  Array.isArray(answer) ? answer.includes(target) : answer === target;

/**
 * True when a rule states a condition at all — it has to name both the gate to
 * read and the value to compare against. Anything else (a missing rule, an
 * empty object, a half-written one, a non-object left by a hand-edited row)
 * expresses no condition, so the question it sits on is unconditional.
 *
 * A rule that names both but points at a question that is not on the form
 * *does* state a condition, one nothing can satisfy, and so hides its
 * question. The distinction matters because `form_visibility.py` deletes the
 * answers to whatever this module leaves out: an unreadable rule must not be
 * the reason an answer disappears.
 */
const isEvaluable = (rule) =>
  typeof rule === "object" &&
  rule !== null &&
  Object.hasOwn(rule, "questionId") &&
  Object.hasOwn(rule, "equals");

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
  const list = questions ?? [];
  const byId = new Map(list.map((q) => [q.id, q]));
  const resolved = new Map();
  const visible = (question) => {
    if (!isEvaluable(question.showWhen)) return true;
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
  return list.filter(visible);
};

/**
 * The answer keys this form still accounts for: one per visible question that
 * has a recorded value.
 *
 * This is the client-side statement of the rule `prune_answers` in
 * `backend/recruiting/form_visibility.py` enforces when it *deletes* the rest
 * at write time, and the shared vectors in
 * `tests/shared/form_visibility_vectors.json` run both against the same
 * expectations. It exists as production code, rather than as something each
 * caller re-derives, so that pinning is against the function the app actually
 * runs: a hand-written copy living only in a test would agree with Python on
 * whatever cases someone thought to write down and drift everywhere else.
 *
 * Property access is `Object.hasOwn`, not `in`, so a question id that happens
 * to name something on `Object.prototype` (`toString`, `constructor`) reports
 * no recorded answer — matching what a Python dict lookup does.
 *
 * @param {object[]} questions
 * @param {Record<string, unknown>} answers
 * @returns {Record<string, unknown>}
 */
export const pruneAnswers = (questions, answers) => {
  const kept = {};
  visibleQuestions(questions, answers).forEach((question) => {
    // A schema question with no id cannot own an answer; keying off it would
    // invent an "undefined" entry.
    if (question.id == null) return;
    if (Object.hasOwn(answers, question.id)) {
      kept[question.id] = answers[question.id];
    }
  });
  return kept;
};
