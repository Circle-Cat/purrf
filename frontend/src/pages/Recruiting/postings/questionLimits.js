/**
 * The character ceilings a text answer can never exceed, and the rule for
 * which one applies.
 *
 * Mirrors `SHORT_TEXT_MAX_LENGTH` / `LONG_TEXT_MAX_LENGTH` in
 * `backend/dto/job_config_dto.py`. The two copies must hold the same numbers:
 * this side decides what the candidate is warned about and the Python side
 * decides what is accepted, so a drift means a form that reports one limit and
 * a submit that enforces another.
 */

/**
 * What a short text is. There is no configuration for it -- choosing the type
 * is the author's statement about length -- and 255 is the VARCHAR(255)
 * default that holds a name, a job title, a company, a city, a URL or a
 * one-line answer.
 */
export const SHORT_TEXT_MAX_LENGTH = 255;

/**
 * The fallback for a long text question whose author set no budget, and the
 * upper bound on the budget they may set. Not an expected value.
 */
export const LONG_TEXT_MAX_LENGTH = 5000;

/**
 * The budget a long text question is created with.
 *
 * Every long text must state a budget, so the field can never be empty when
 * the author first sees it -- otherwise adding a question would spawn an error
 * the author did not cause. This is a starting point, not a ceiling: it is what
 * most written answers need, and the author raises or lowers it. Editor-side
 * only, deliberately: the server requires a value but has no opinion on which.
 */
export const DEFAULT_LONG_TEXT_MAX_LENGTH = 300;

/**
 * The character budget a text question enforces, and whether its author chose
 * it.
 *
 * `explicit` is what the renderer keys its counter off: a budget the author
 * set is information the candidate should have from the first keystroke,
 * while the fallback ceiling is a guard nobody should ever meet — putting
 * `0 / 255` under a name field would be noise.
 *
 * @param {object|undefined} question One question out of the form schema.
 * @returns {{cap: number, explicit: boolean}|null} Null for a question that is
 *   not text.
 */
export const textBudget = (question) => {
  const type = question?.type;
  if (type === "short_text") {
    return { cap: SHORT_TEXT_MAX_LENGTH, explicit: false };
  }
  if (type === "long_text") {
    const authored = question.maxLength;
    return authored == null
      ? { cap: LONG_TEXT_MAX_LENGTH, explicit: false }
      : { cap: authored, explicit: true };
  }
  return null;
};
