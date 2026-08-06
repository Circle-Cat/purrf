import {
  OTHER_SUFFIX,
  pruneAnswers,
} from "@/pages/Recruiting/postings/questionVisibility";

/**
 * Whether a recorded value is something the candidate would notice losing.
 *
 * A blank string or an empty selection is already nothing; warning that it is
 * about to be dropped would be noise on almost every save.
 */
const hasContent = (value) => {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "string") return value.trim() !== "";
  return true;
};

/** How to name the question an about-to-be-dropped answer key belonged to. */
const labelFor = (key, byId) => {
  const own = byId.get(key);
  if (own) return own.label || key;
  if (key.endsWith(OTHER_SUFFIX)) {
    const parent = byId.get(key.slice(0, -OTHER_SUFFIX.length));
    if (parent) return `${parent.label || parent.id} — your own answer`;
  }
  return "A question that is no longer on the form";
};

/**
 * The answers this save would destroy, with the question each belonged to.
 *
 * The server keeps only what the form was showing when the answers were
 * written (`prune_answers`), and it overwrites the submission in place — there
 * is no earlier version and no way back. So changing an answer that hides a
 * dependent question, or saving after an owner removes a question, silently
 * takes whatever was underneath. Because visibility is transitive, one flip at
 * the top of a chain takes the whole chain.
 *
 * Derived from `pruneAnswers`, the same function whose Python twin does the
 * deleting, so this cannot warn about a different set than the one that goes.
 *
 * @param {object[]} questions The form as it stands now.
 * @param {Record<string, unknown>} answers Everything the form is holding.
 * @returns {{key: string, label: string, value: unknown}[]} Empty when the
 *   save costs nothing, which is the common case.
 */
export const discardedAnswers = (questions, answers) => {
  const kept = pruneAnswers(questions, answers);
  const byId = new Map((questions ?? []).map((q) => [q.id, q]));
  return Object.entries(answers ?? {})
    .filter(([key, value]) => !Object.hasOwn(kept, key) && hasContent(value))
    .map(([key, value]) => ({ key, value, label: labelFor(key, byId) }));
};
