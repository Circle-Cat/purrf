import { visibleQuestions } from "@/pages/Recruiting/postings/questionVisibility";
import {
  validatePersonal,
  validateEducationRow,
  validateExperienceRow,
} from "@/pages/Profile/profileValidation";
import { textBudget } from "@/pages/Recruiting/postings/questionLimits";

/**
 * What a candidate's application has to satisfy before it is worth sending.
 *
 * The counterpart of `postingValidation` on the other side of the same form:
 * that one checks what a recruiter authored, this one checks what a candidate
 * answered. Both mirror rules the API enforces, and both are deliberately
 * never the stricter of the pair — being blocked from a submission the server
 * would have accepted is worse than the round trip it saves.
 *
 * Only the questions the form is *showing* are checked. A required question
 * behind a rule that no longer matches is not on screen, so demanding it would
 * block a form the candidate has filled in completely — the same reasoning
 * `_validate_submission` applies server-side.
 *
 * Keys come from the exported helpers rather than being written out at each
 * use, so a hand-typed string cannot drift by a character and quietly disable
 * a rule.
 *
 * The profile half of the form -- the personal fields and each education or
 * experience row -- is judged by `profileValidation`, the same module the
 * Profile page's edit modals use, so a row the candidate could not save on
 * their profile cannot be sent with an application either.
 *
 * Problems are collected profile-first and answers second, matching the order
 * they appear on screen: `PostingApplicantView` renders the profile block above
 * the questions, and the caller scrolls to whichever key comes out first.
 */

/** A question's own answer. */
export const answerKey = (questionId) => `answer:${questionId}`;
/** A personal field, or a profile section the posting requires. */
export const profileKey = (field) => `profile:${field}`;
/**
 * One field of one education or experience row.
 *
 * Namespaced by section rather than by row id alone: row ids come from
 * whatever produced the row -- a fresh add, a résumé parse, a stored
 * submission -- and nothing guarantees an education row and an experience row
 * cannot end up sharing one.
 *
 * @param {"education"|"experience"} section
 * @param {string|number} rowId
 * @param {string} field
 */
export const rowKey = (section, rowId, field) => `${section}:${rowId}:${field}`;

/**
 * Whether a question has an answer at all.
 *
 * Mirrors `_answered`: presence decides, not truthiness, so a recorded `0` or
 * `false` counts. An empty list is nothing selected, and whitespace is
 * nothing typed.
 */
const answered = (value) => {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "string") return value.trim() !== "";
  return true;
};

/**
 * Collect everything wrong with the profile half of the form, in the order it
 * is rendered: personal fields, then education, then experience.
 *
 * Only runs when the caller hands over a profile or its requirements; the
 * posting editor's preview and the answer-only unit paths pass neither and are
 * asking about answers alone.
 *
 * A section switched `off` is skipped entirely, rows included: it is not
 * rendered, so an error there could never be seen, let alone fixed. A section
 * left `optional` still has its rows checked — optional means "you need not add
 * one", not "a half-filled one is fine". The section-level "add at least one"
 * therefore only ever fires while the section is genuinely empty.
 *
 * @param {{profileConfig?: object, profile?: object, resume?: object}} given
 * @param {Record<string, string>} errors Accumulator, mutated in place.
 */
const collectProfileErrors = (given, errors) => {
  if (given.profile == null && given.profileConfig == null) return;

  const config = given.profileConfig ?? {};
  const entered = given.profile ?? {};
  // One `now` for the whole form, so two rows cannot be judged against
  // different months.
  const now = new Date();

  // First, because the résumé block is rendered above the personal fields.
  //
  // `=== "required"` exactly, never `!== "optional"`: `off` means the posting
  // collects no résumé at all and the server discards any file attached, so
  // demanding one there would ask the candidate for a file that is thrown
  // away. What counts is the stored key, whatever produced it -- a file picked
  // this session or one carried over from a previous application -- which is
  // also all `_validate_submission` looks at.
  if (config.resume === "required" && !given.resume?.objectKey) {
    errors[profileKey("resume")] = "A résumé is required";
  }

  Object.entries(validatePersonal(entered.personal)).forEach(
    ([field, message]) => {
      errors[profileKey(field)] = message;
    },
  );

  const sections = [
    {
      name: "education",
      level: config.education,
      rows: entered.education ?? [],
      rule: validateEducationRow,
      empty: "Add at least one education entry",
    },
    {
      name: "experience",
      level: config.workExperience,
      rows: entered.experience ?? [],
      rule: validateExperienceRow,
      empty: "Add at least one experience entry",
    },
  ];

  sections.forEach(({ name, level, rows, rule, empty }) => {
    if (level === "off") return;
    if (level === "required" && rows.length === 0) {
      errors[profileKey(name)] = empty;
      return;
    }
    rows.forEach((row) => {
      Object.entries(rule(row, now)).forEach(([field, message]) => {
        errors[rowKey(name, row.id, field)] = message;
      });
    });
  });
};

/**
 * Check a candidate's answers against the form they are looking at.
 *
 * @param {object[]} questions The posting's form schema questions.
 * @param {Record<string, unknown>} answers Everything the form is holding.
 * @param {{profileConfig?: object, profile?: object}} [profile] Section
 *   requirements plus what the candidate has entered, when the caller wants
 *   the profile blocks checked too.
 * @returns {Record<string, string>} Message per field key; empty when valid.
 */
export const validateApplication = (questions, answers, profile = {}) => {
  const errors = {};
  const recorded = answers ?? {};

  collectProfileErrors(profile, errors);

  visibleQuestions(questions ?? [], recorded).forEach((question) => {
    const value = recorded[question.id];
    const key = answerKey(question.id);
    const options = question.options ?? [];

    if (question.required && !answered(value)) {
      errors[key] = "This question is required";
      return;
    }
    if (!answered(value)) return;

    if (question.type === "single_choice" && !options.includes(value)) {
      // Not reachable by clicking, but the API accepts any string, and a
      // value outside the options also decides whether the questions this
      // one gates are shown at all.
      errors[key] = "Pick one of the listed options";
    } else if (question.type === "multi_choice") {
      if (!Array.isArray(value)) {
        errors[key] = "Pick from the listed options";
      } else if (value.some((v) => !options.includes(v))) {
        errors[key] = "Pick from the listed options";
      } else if (
        question.maxSelections != null &&
        value.length > question.maxSelections
      ) {
        errors[key] = `Pick at most ${question.maxSelections} ${
          question.maxSelections === 1 ? "option" : "options"
        }`;
      }
    } else if (
      textBudget(question) !== null &&
      String(value).length > textBudget(question).cap
    ) {
      // Both text types, and both the authored budget and the fallback
      // ceiling: no text question is unbounded, so this arm covers every one
      // of them.
      errors[key] = `Keep this under ${textBudget(question).cap} characters`;
    } else if (
      question.type === "exact_text" &&
      String(value).trim() !== (question.expectedValue ?? "")
    ) {
      // Trimmed, because stray whitespace is never what the author is asking
      // the candidate to confirm; otherwise exact, since that is the point.
      errors[key] = `Type ${question.expectedValue} exactly`;
    }
  });

  return errors;
};
