import { DEFAULT_LONG_TEXT_MAX_LENGTH } from "@/pages/Recruiting/postings/questionLimits";

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
 * Next unique question id for a form: `q` plus the persisted `nextSeq`, never
 * below one past the highest `q<n>` currently present.
 *
 * The counter is persisted on the schema because deriving it from the live
 * questions alone recycles ids — delete the last question and the next one
 * added reclaims its id, silently colliding with the answers every prior
 * application already recorded under it. The floor guards against a stale or
 * hand-edited counter.
 *
 * @param {{questions?: {id: string}[], nextSeq?: number}} formSchema
 * @returns {string} e.g. "q4"
 */
export const nextQuestionId = (formSchema) => {
  const questions = formSchema?.questions ?? [];
  const nums = questions
    .map((q) => /^q(\d+)$/.exec(q.id)?.[1])
    .filter(Boolean)
    .map(Number);
  const floor = nums.length ? Math.max(...nums) + 1 : 1;
  const seq = Number.isInteger(formSchema?.nextSeq)
    ? formSchema.nextSeq
    : floor;
  return `q${Math.max(seq, floor)}`;
};

/**
 * A form schema with one blank question of the given type appended and the
 * `nextSeq` counter advanced past it. Choice types start with an empty
 * options array, and a long text with the default character budget -- that one
 * is required, so it is seeded rather than left for the author to discover
 * through a validation error on a question they just added.
 *
 * @param {{questions?: object[], nextSeq?: number}} formSchema
 * @param {string} type One of `QUESTION_TYPES[].value`.
 * @returns {object} A new schema; the input is not mutated.
 */
export const addQuestion = (formSchema, type) => {
  const id = nextQuestionId(formSchema);
  const question = { id, type, label: "", required: false };
  if (CHOICE_TYPES.has(type)) question.options = [];
  if (type === "long_text") question.maxLength = DEFAULT_LONG_TEXT_MAX_LENGTH;
  return {
    ...formSchema,
    questions: [...(formSchema?.questions ?? []), question],
    nextSeq: Number(id.slice(1)) + 1,
  };
};

/** A schema with every question replaced by `fn(question)`; input untouched. */
const mapQuestions = (formSchema, fn) => ({
  ...formSchema,
  questions: (formSchema?.questions ?? []).map(fn),
});

/**
 * The questions one option of a choice question reveals, in form order.
 *
 * A reveal rule is stored on the question being revealed (`showWhen`), not on
 * the option, so this is the only way to read an option's rules back.
 *
 * @param {object[]} questions
 * @param {string} parentId The choice question the option belongs to.
 * @param {string} option The option's text.
 * @returns {object[]}
 */
export const revealedBy = (questions, parentId, option) =>
  (questions ?? []).filter(
    (q) => q.showWhen?.questionId === parentId && q.showWhen?.equals === option,
  );

/**
 * A schema where `questionId` is shown only when `parentId` answers `option`.
 *
 * A question carries at most one `showWhen`, so revealing an already-revealed
 * question moves it rather than adding a second rule.
 *
 * @param {{questions?: object[]}} formSchema
 * @param {string} questionId The question to reveal.
 * @param {string} parentId The choice question whose answer reveals it.
 * @param {string} option The option's text.
 * @returns {object} A new schema; the input is not mutated.
 */
export const revealQuestion = (formSchema, questionId, parentId, option) =>
  mapQuestions(formSchema, (q) =>
    q.id === questionId
      ? { ...q, showWhen: { questionId: parentId, equals: option } }
      : q,
  );

/**
 * A schema where `questionId` is shown unconditionally again.
 *
 * @param {{questions?: object[]}} formSchema
 * @param {string} questionId
 * @returns {object} A new schema; the input is not mutated.
 */
export const clearCondition = (formSchema, questionId) =>
  mapQuestions(formSchema, (q) => {
    if (q.id !== questionId) return q;
    const next = { ...q };
    delete next.showWhen;
    return next;
  });

/**
 * A schema with one blank option appended to choice question `parentId`.
 *
 * @param {{questions?: object[]}} formSchema
 * @param {string} parentId
 * @returns {object} A new schema; the input is not mutated.
 */
export const addOption = (formSchema, parentId) =>
  mapQuestions(formSchema, (q) =>
    q.id === parentId ? { ...q, options: [...(q.options ?? []), ""] } : q,
  );

/**
 * A schema with `parentId`'s option at `index` renamed, carrying every
 * reference to its old text along with it.
 *
 * An option is referenced by its text, not by an id: each question it reveals
 * stores that text in `showWhen.equals`, and `otherOption` stores it too. A
 * rename that left those behind would point them at text no answer can equal,
 * silently turning a revealed question into one that never appears.
 *
 * @param {{questions?: object[]}} formSchema
 * @param {string} parentId
 * @param {number} index Position of the option being renamed.
 * @param {string} value The new text.
 * @returns {object} A new schema; the input is not mutated.
 */
export const renameOption = (formSchema, parentId, index, value) => {
  const parent = (formSchema?.questions ?? []).find((q) => q.id === parentId);
  const from = parent?.options?.[index];
  return mapQuestions(formSchema, (q) => {
    if (q.id === parentId) {
      const next = {
        ...q,
        options: (q.options ?? []).map((o, i) => (i === index ? value : o)),
      };
      if (q.otherOption === from) next.otherOption = value;
      return next;
    }
    if (q.showWhen?.questionId === parentId && q.showWhen.equals === from) {
      return { ...q, showWhen: { ...q.showWhen, equals: value } };
    }
    return q;
  });
};

/**
 * A schema with `parentId`'s option at `index` dropped, and `otherOption`
 * cleared when it named that option.
 *
 * Questions the option revealed are deliberately left alone: the editor
 * blocks removal while any exist, since neither outcome is safe to pick
 * silently -- dropping their condition would show a follow-up to everyone,
 * and deleting them would take the author's questions with it.
 *
 * @param {{questions?: object[]}} formSchema
 * @param {string} parentId
 * @param {number} index
 * @returns {object} A new schema; the input is not mutated.
 */
export const removeOption = (formSchema, parentId, index) =>
  mapQuestions(formSchema, (q) => {
    if (q.id !== parentId) return q;
    const dropped = q.options?.[index];
    const next = {
      ...q,
      options: (q.options ?? []).filter((_, i) => i !== index),
    };
    if (q.otherOption === dropped) next.otherOption = undefined;
    return next;
  });
