/**
 * True when a question with a showWhen rule should be visible given answers.
 *
 * Exported so a read-only consumer can compute the same visible set and tell
 * which recorded answers this renderer will *not* display.
 *
 * @param {object} question
 * @param {Record<string, string|string[]>} answers
 * @returns {boolean}
 */
export const isVisible = (question, answers) => {
  if (!question.showWhen) return true;
  const dep = answers[question.showWhen.questionId];
  const target = question.showWhen.equals;
  return Array.isArray(dep) ? dep.includes(target) : dep === target;
};

/**
 * True when a question's recorded value selects its "Other" option, which is
 * what makes `FormRenderer` render the `${id}__other` sibling answer.
 *
 * Shared for the same reason `isVisible` is: the renderer and any consumer
 * computing which recorded answers the renderer will *not* show must agree
 * exactly, or the free text ends up either dropped from both views or
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
