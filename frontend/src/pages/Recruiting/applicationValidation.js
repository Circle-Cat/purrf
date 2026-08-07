import {
  OTHER_SUFFIX,
  otherSelected,
  visibleQuestions,
} from "@/pages/Recruiting/postings/questionVisibility";

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
 */

/** A question's own answer. */
export const answerKey = (questionId) => `answer:${questionId}`;
/** The free text beside a question's "Other" option. */
export const otherKey = (questionId) => `answer:${questionId}${OTHER_SUFFIX}`;
/** A profile section the posting requires. */
export const profileKey = (section) => `profile:${section}`;

/** Blank, or nothing but whitespace. */
const isBlank = (value) => !value || !String(value).trim();

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
      question.type === "long_text" &&
      question.maxLength != null &&
      String(value).length > question.maxLength
    ) {
      errors[key] = `Keep this under ${question.maxLength} characters`;
    } else if (
      question.type === "exact_text" &&
      String(value).trim() !== (question.expectedValue ?? "")
    ) {
      // Trimmed, because stray whitespace is never what the author is asking
      // the candidate to confirm; otherwise exact, since that is the point.
      errors[key] = `Type ${question.expectedValue} exactly`;
    }

    // The renderer puts a required marker on the "Other" free text whenever
    // that option is picked. Nothing used to hold it to that.
    if (
      otherSelected(question, value) &&
      isBlank(recorded[`${question.id}${OTHER_SUFFIX}`])
    ) {
      errors[otherKey(question.id)] = "Please describe your answer";
    }
  });

  const config = profile.profileConfig ?? {};
  const entered = profile.profile ?? {};
  if (
    config.education === "required" &&
    (entered.education ?? []).length === 0
  ) {
    errors[profileKey("education")] = "Add at least one education entry";
  }
  if (
    config.workExperience === "required" &&
    (entered.experience ?? []).length === 0
  ) {
    errors[profileKey("experience")] = "Add at least one experience entry";
  }

  return errors;
};
