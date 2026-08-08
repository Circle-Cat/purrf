/**
 * What a posting draft has to satisfy before it is worth sending.
 *
 * Every rule here is one the API enforces too. That duplication is deliberate
 * — the server cannot trust a client, and a client that waits for the server
 * can only report the first failure, as a sentence naming an internal id, with
 * nothing on the page pointing at the field. But it is duplication, so two
 * things keep it honest: this side is never *stricter* than the server (an
 * author must never be blocked from a save the API would have accepted), and
 * every message here is anchored to the validator that produces the real
 * rejection, cited per rule below.
 *
 * Keys are built by the exported helpers rather than written out at each use.
 * The components render red from these keys and the tests assert on them, so a
 * hand-typed string that drifts by one character would silently stop matching
 * and quietly disable a rule.
 */

import { LONG_TEXT_MAX_LENGTH } from "@/pages/Recruiting/postings/questionLimits";

/** A field on the posting itself. */
export const basicsKey = (field) => `basics:${field}`;
/** A field on one question. */
export const questionKey = (questionId, field) => `q:${questionId}:${field}`;
/** One option of one question, by position — options have no id of their own. */
export const optionKey = (questionId, index) =>
  `q:${questionId}:option:${index}`;
/** A field on one machine-screening rule. */
export const ruleKey = (ruleId, field) => `rule:${ruleId}:${field}`;

const CHOICE_TYPES = new Set(["single_choice", "multi_choice"]);

/** Blank, or nothing but whitespace. */
const isBlank = (value) => !value || !String(value).trim();

/**
 * How a question is named in a message aimed at its author. Falls back to the
 * id, which is at least greppable, when the label is still empty — that case
 * carries its own error anyway.
 */
const nameOf = (question) => question?.label?.trim() || question?.id;

/**
 * Validate a whole posting draft.
 *
 * @param {{title?: string, cooldownDays?: number|null,
 *          formSchema?: {questions?: object[]},
 *          screenRules?: {rules?: object[]}}} draft
 * @returns {Record<string, string>} Message per field key; empty when valid.
 */
export const validatePosting = (draft) => {
  const errors = {};
  const questions = draft?.formSchema?.questions ?? [];

  // JobCreateDto.title is a bare `str`, so the API accepts "" today; the
  // server-side check lands with this one.
  if (isBlank(draft?.title)) {
    errors[basicsKey("title")] = "Title is required";
  }
  // Likewise unguarded server-side. `min={0}` on the input only governs the
  // spinner — a negative typed in reaches the draft.
  if (draft?.cooldownDays != null && draft.cooldownDays < 0) {
    errors[basicsKey("cooldownDays")] = "Cannot be negative";
  }

  questions.forEach((question) => {
    const options = question.options ?? [];

    // QuestionDto.label_nonempty
    if (isBlank(question.label)) {
      errors[questionKey(question.id, "label")] = "Question is required";
    }

    if (CHOICE_TYPES.has(question.type)) {
      // QuestionDto.validate_type_fields: "requires a non-empty options list"
      if (options.length === 0) {
        errors[questionKey(question.id, "options")] = "Add at least one option";
      }
      const seen = new Map();
      options.forEach((option, index) => {
        // "options entries must be non-empty"
        if (isBlank(option)) {
          errors[optionKey(question.id, index)] = "Option cannot be blank";
          return;
        }
        // Not a server rule — options are matched by their text, so two that
        // read the same are one option wearing two rows: `showWhen.equals` and
        // `otherOption` cannot tell them apart, and whichever the candidate
        // picks reveals both. Blocked here rather than left to confuse.
        if (seen.has(option)) {
          errors[optionKey(question.id, index)] =
            `Duplicate of option ${seen.get(option) + 1}`;
        } else {
          seen.set(option, index);
        }
      });
    }

    // "max_selections must be within [1, len(options)]"
    if (
      question.type === "multi_choice" &&
      question.maxSelections != null &&
      (question.maxSelections < 1 || question.maxSelections > options.length)
    ) {
      errors[questionKey(question.id, "maxSelections")] =
        `Must be between 1 and ${options.length}`;
    }

    if (question.type === "long_text") {
      // QuestionDto.validate_type_fields: "max_length must be within [1, N]".
      // The upper bound is the same ceiling an unbudgeted long text falls back
      // to -- a budget above it would promise the candidate room the submit
      // check will not give them.
      if (
        question.maxLength != null &&
        (question.maxLength < 1 || question.maxLength > LONG_TEXT_MAX_LENGTH)
      ) {
        errors[questionKey(question.id, "maxLength")] =
          `Must be between 1 and ${LONG_TEXT_MAX_LENGTH}`;
      }
    }

    // "exact_text requires a non-empty expected_value"
    if (question.type === "exact_text" && isBlank(question.expectedValue)) {
      errors[questionKey(question.id, "expectedValue")] =
        "Expected value is required";
    }

    // FormSchemaDto.validate_schema: "showWhen references unknown question".
    // Removing a question does not touch the ones it revealed, so this is what
    // a delete leaves behind. The editor also disables the delete that would
    // cause it; this catches a draft that already carries one.
    const gate = question.showWhen?.questionId;
    if (gate != null && !questions.some((q) => q.id === gate)) {
      errors[questionKey(question.id, "showWhen")] =
        "Shown by a question that no longer exists";
    }
  });

  const byId = new Map(questions.map((q) => [q.id, q]));
  (draft?.screenRules?.rules ?? []).forEach((rule) => {
    const condition = rule.condition ?? {};
    const values = Array.isArray(condition.value)
      ? condition.value
      : [condition.value];

    if (condition.source === "email_domain") {
      // ScreenRuleConditionDto: "email_domain condition requires a non-empty
      // value". Blank paired with "exclude" matches every domain, which on a
      // reject rule turns away every applicant.
      if (values.every(isBlank)) {
        errors[ruleKey(rule.id, "value")] = "Enter at least one domain";
      }
      return;
    }

    // "answer condition requires question_id"
    if (isBlank(condition.questionId)) {
      errors[ruleKey(rule.id, "questionId")] = "Pick a question";
      return;
    }
    // JobCreateDto: "references unknown question"
    const question = byId.get(condition.questionId);
    if (question === undefined) {
      errors[ruleKey(rule.id, "questionId")] = "This question no longer exists";
      return;
    }
    // A freshly added rule starts blank. Matched to the server's own
    // "answer condition requires a non-empty value", and kept ahead of the
    // options check so an unfinished rule does not report as `""` not being
    // an option, which reads like a bug rather than something left undone.
    if (values.every(isBlank)) {
      errors[ruleKey(rule.id, "value")] = "Pick a value";
      return;
    }
    // JobCreateDto: "value(s) ... not in options of ..."
    if (CHOICE_TYPES.has(question.type)) {
      const bad = values.filter((v) => !(question.options ?? []).includes(v));
      if (bad.length > 0) {
        errors[ruleKey(rule.id, "value")] =
          `"${bad[0]}" is not an option of "${nameOf(question)}"`;
      }
    }
  });

  return errors;
};
