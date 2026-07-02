import { formatDateFromParts } from "@/pages/Profile/utils";

/**
 * Whether an education row has enough data for the profile PATCH DTO
 * (school, degree, and a complete start + end date).
 *
 * @param {object} row
 * @returns {boolean}
 */
const isCompleteEducationRow = (row) =>
  Boolean(row.institution?.trim()) &&
  Boolean(row.degree?.trim()) &&
  Boolean(row.startMonth && row.startYear) &&
  Boolean(row.endMonth && row.endYear);

/**
 * Whether a work-experience row has enough data for the profile PATCH DTO
 * (title, company, and a start date; the end date is optional for an
 * ongoing role).
 *
 * @param {object} row
 * @returns {boolean}
 */
const isCompleteExperienceRow = (row) =>
  Boolean(row.title?.trim()) &&
  Boolean(row.company?.trim()) &&
  Boolean(row.startMonth && row.startYear);

/**
 * Map `ApplicationForm`'s `profileValue` into a partial profile PATCH
 * payload for write-back via `updateMyProfile`. Only complete rows are
 * included (see `isCompleteEducationRow`/`isCompleteExperienceRow`) -- the
 * backend's profile DTO requires those fields and would reject the whole
 * PATCH otherwise. Row `id`s are dropped: this form's rows carry local
 * `rpf-*` ids that don't exist in the profile DB, so omitting `id` makes
 * each row a fresh create rather than an attempted (and mismatching)
 * update. Personal fields are intentionally excluded -- this form never
 * collects the timezone/communicationMethod the backend's `user` object
 * requires.
 *
 * @param {{education?: object[], experience?: object[]}} profileValue
 * @returns {{education: object[], workHistory: object[]}}
 */
export const buildProfileWriteBackPayload = (profileValue) => {
  const education = (profileValue.education ?? [])
    .filter(isCompleteEducationRow)
    .map((row) => ({
      school: row.institution,
      degree: row.degree,
      fieldOfStudy: row.field,
      startDate: formatDateFromParts(row.startMonth, row.startYear),
      endDate: formatDateFromParts(row.endMonth, row.endYear),
    }));

  const workHistory = (profileValue.experience ?? [])
    .filter(isCompleteExperienceRow)
    .map((row) => ({
      title: row.title,
      companyOrOrganization: row.company,
      isCurrentJob: row.isCurrentlyWorking,
      startDate: formatDateFromParts(row.startMonth, row.startYear),
      endDate: row.isCurrentlyWorking
        ? null
        : formatDateFromParts(row.endMonth, row.endYear),
    }));

  return { education, workHistory };
};
