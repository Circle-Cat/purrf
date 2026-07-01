/** Ordered, user-facing list of the five submission-form question types. */
export const QUESTION_TYPES = [
  { value: "short_text", label: "Short text" },
  { value: "long_text", label: "Long text" },
  { value: "single_choice", label: "Single choice" },
  { value: "multi_choice", label: "Multi choice" },
  { value: "exact_text", label: "Exact text" },
];

const CHOICE_TYPES = new Set(["single_choice", "multi_choice"]);

/**
 * Next unique question id within a form: one past the largest existing
 * `q<number>` suffix (so ids stay unique even after deletes).
 *
 * @param {{id: string}[]} questions
 * @returns {string} e.g. "q4"
 */
export const nextQuestionId = (questions) => {
  const nums = questions
    .map((q) => /^q(\d+)$/.exec(q.id)?.[1])
    .filter(Boolean)
    .map(Number);
  return `q${(nums.length ? Math.max(...nums) : 0) + 1}`;
};

/**
 * A blank question of the given type, with a freshly generated unique id.
 * Choice types start with an empty options array.
 *
 * @param {string} type
 * @param {{id: string}[]} questions  Existing questions (for id generation).
 * @returns {object}
 */
export const blankQuestion = (type, questions) => {
  const q = { id: nextQuestionId(questions), type, label: "", required: false };
  if (CHOICE_TYPES.has(type)) q.options = [];
  return q;
};
