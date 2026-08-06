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
 * options array.
 *
 * @param {{questions?: object[], nextSeq?: number}} formSchema
 * @param {string} type One of `QUESTION_TYPES[].value`.
 * @returns {object} A new schema; the input is not mutated.
 */
export const addQuestion = (formSchema, type) => {
  const id = nextQuestionId(formSchema);
  const question = { id, type, label: "", required: false };
  if (CHOICE_TYPES.has(type)) question.options = [];
  return {
    ...formSchema,
    questions: [...(formSchema?.questions ?? []), question],
    nextSeq: Number(id.slice(1)) + 1,
  };
};
