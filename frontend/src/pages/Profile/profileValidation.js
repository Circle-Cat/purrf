import { months, getDateScore } from "@/pages/Profile/utils";

/**
 * What a profile's personal block and education/experience rows have to
 * satisfy, in one place.
 *
 * These rules were written out three times over: once in each of the Personal
 * / Education / Experience edit modals, and a fourth, quietly laxer time in
 * `profileWriteBack` (which accepted an empty field of study and ignored end
 * dates entirely). The candidate application form needs the same rules again,
 * which would have made five. Whichever copy someone edited next, the others
 * would have drifted.
 *
 * Every function returns a plain `{field: message}` object rather than a list,
 * so a caller can key it however its own error scheme demands: the modals use
 * `${rowId}-${field}`, the application form uses namespaced keys. The rules
 * live here; the key shapes stay at the edges.
 *
 * `now` is a parameter rather than a `new Date()` read inside the rule, so
 * "cannot be in the future" is decided by the caller and a test does not
 * depend on the day it runs.
 */

/** Missing, or nothing but whitespace. */
const isBlank = (value) => !value || !String(value).trim();

/** The month `now` falls in, on the same scale as a row's start/end. */
const monthScore = (now) =>
  getDateScore(now.getFullYear(), months[now.getMonth()]);

/**
 * Check the personal block.
 *
 * First name, last name and timezone are required of everyone — not driven by
 * a posting's `profileConfig`, which is why the form marks them with a plain
 * asterisk rather than a configurable one.
 *
 * @param {object} personal Personal fields; a missing block reads as empty.
 * @returns {Record<string, string>} Message per field; empty when valid.
 */
export const validatePersonal = (personal) => {
  const entered = personal ?? {};
  const errors = {};
  if (isBlank(entered.firstName)) errors.firstName = "First name is required";
  if (isBlank(entered.lastName)) errors.lastName = "Last name is required";
  // Falsiness, not blankness: a timezone comes from a picker, never typed.
  if (!entered.timezone) errors.timezone = "Timezone is required";
  return errors;
};

/**
 * Check one education row.
 *
 * An end date is always required: there is no "currently studying" flag, and
 * the modal has always demanded one.
 *
 * @param {object} row One education row in form shape.
 * @param {Date} [now] What counts as today when rejecting a future start.
 * @returns {Record<string, string>} Message per field; empty when valid.
 */
export const validateEducationRow = (row, now = new Date()) => {
  const item = row ?? {};
  const errors = {};
  const startScore = getDateScore(item.startYear, item.startMonth);

  if (isBlank(item.institution)) errors.institution = "School is required";
  if (isBlank(item.degree)) errors.degree = "Degree is required";
  if (isBlank(item.field)) errors.field = "Field of study is required";

  if (!item.startMonth || !item.startYear) {
    errors.startDate = "Start date is required";
  } else if (startScore > monthScore(now)) {
    errors.startDate = "Start date cannot be in the future";
  }

  if (!item.endMonth || !item.endYear) {
    errors.endDate = "End date is required";
  } else if (getDateScore(item.endYear, item.endMonth) < startScore) {
    errors.endDate = "End date cannot be earlier than start date";
  }

  return errors;
};

/**
 * Check one work-experience row.
 *
 * The end date is skipped for a role marked current — that is the whole point
 * of the flag, and an ongoing job has no end to give.
 *
 * @param {object} row One experience row in form shape.
 * @param {Date} [now] What counts as today when rejecting a future start.
 * @returns {Record<string, string>} Message per field; empty when valid.
 */
export const validateExperienceRow = (row, now = new Date()) => {
  const item = row ?? {};
  const errors = {};
  const startScore = getDateScore(item.startYear, item.startMonth);

  if (isBlank(item.title)) errors.title = "Title is required";
  if (isBlank(item.company)) errors.company = "Company is required";

  if (!item.startMonth || !item.startYear) {
    errors.startDate = "Start date is required";
  } else if (startScore > monthScore(now)) {
    errors.startDate = "Start date cannot be in the future";
  }

  if (!item.isCurrentlyWorking) {
    if (!item.endMonth || !item.endYear) {
      errors.endDate = "End date is required";
    } else if (getDateScore(item.endYear, item.endMonth) < startScore) {
      errors.endDate = "End date cannot be earlier than start date";
    }
  }

  return errors;
};

/**
 * Whether an education row is worth sending to the profile PATCH DTO.
 *
 * @param {object} row One education row in form shape.
 * @param {Date} [now] Passed through to the rule.
 * @returns {boolean}
 */
export const isCompleteEducationRow = (row, now = new Date()) =>
  Object.keys(validateEducationRow(row, now)).length === 0;

/**
 * Whether a work-experience row is worth sending to the profile PATCH DTO.
 *
 * @param {object} row One experience row in form shape.
 * @param {Date} [now] Passed through to the rule.
 * @returns {boolean}
 */
export const isCompleteExperienceRow = (row, now = new Date()) =>
  Object.keys(validateExperienceRow(row, now)).length === 0;
