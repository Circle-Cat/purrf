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
  // `field` maps to the backend's required `fieldOfStudy` (str) -- an
  // undefined key would 422; an empty string stays acceptable.
  row.field != null &&
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
 * Map a fetched profile education row (backend field names) into the
 * PATCH-request shape, KEEPING its real database `id` so the backend
 * updates the row in place instead of duplicating it.
 *
 * @param {object} row - Fetched row: {id, school, degree, fieldOfStudy, startDate, endDate}.
 * @returns {object} Request-shaped row.
 */
const fetchedEducationToRequest = (row) => ({
  id: row.id,
  school: row.school,
  degree: row.degree,
  fieldOfStudy: row.fieldOfStudy,
  startDate: row.startDate,
  endDate: row.endDate,
});

/**
 * Map a fetched profile work-history row (backend field names) into the
 * PATCH-request shape, KEEPING its real database `id`.
 *
 * @param {object} row - Fetched row: {id, title, companyOrOrganization, isCurrentJob, startDate, endDate}.
 * @returns {object} Request-shaped row.
 */
const fetchedWorkToRequest = (row) => ({
  id: row.id,
  title: row.title,
  companyOrOrganization: row.companyOrOrganization,
  isCurrentJob: row.isCurrentJob,
  startDate: row.startDate,
  endDate: row.endDate,
});

/**
 * Content-identity key for a request-shaped education row, used to skip
 * application rows that already exist in the profile.
 *
 * @param {object} row - Request-shaped education row.
 * @returns {string}
 */
const educationKey = (row) =>
  [row.school, row.degree, row.fieldOfStudy, row.startDate, row.endDate].join(
    "|",
  );

/**
 * Content-identity key for a request-shaped work-history row. End date and
 * is-current are deliberately excluded: the same title + company + start
 * date is the same job, even if one copy has since gained an end date.
 *
 * @param {object} row - Request-shaped work-history row.
 * @returns {string}
 */
const workKey = (row) =>
  [row.title, row.companyOrOrganization, row.startDate].join("|");

/**
 * Map `ApplicationForm`'s `profileValue` into candidate NEW rows for
 * profile write-back, in PATCH-request shape. Only complete rows are
 * included (see `isCompleteEducationRow`/`isCompleteExperienceRow`) -- the
 * backend's profile DTO requires those fields and would reject the whole
 * PATCH otherwise. Row `id`s are dropped: this form's rows carry local
 * `rpf-*` ids that don't exist in the profile DB, so omitting `id` makes
 * each row a fresh create. Personal fields are intentionally excluded --
 * this form never collects the timezone/communicationMethod the backend's
 * `user` object requires.
 *
 * @param {{education?: object[], experience?: object[]}} profileValue
 * @returns {{education: object[], workHistory: object[]}}
 */
export const buildNewWriteBackRows = (profileValue) => {
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

/**
 * Merge new application rows into the user's FETCHED profile lists,
 * producing the partial PATCH payload for `updateMyProfile` -- or `null`
 * when there is nothing to write.
 *
 * The backend's profile upsert has full-overwrite semantics (a PATCHed
 * list fully replaces what's stored), so each written list must carry ALL
 * existing rows -- mapped back to request shape with their real ids
 * preserved -- plus the appended new rows. A new row content-identical to
 * an existing one is skipped, and a list whose new rows all dedup away is
 * omitted from the payload entirely: unchanged lists are never sent.
 *
 * @param {object|undefined} fetchedProfile - Profile from `getMyProfile`
 *   ({education?: object[], workHistory?: object[]} in backend field names).
 * @param {{education: object[], workHistory: object[]}} newRows - Output of
 *   `buildNewWriteBackRows`.
 * @returns {{education?: object[], workHistory?: object[]}|null}
 */
export const mergeWriteBackPayload = (fetchedProfile, newRows) => {
  const existingEducation = (fetchedProfile?.education ?? []).map(
    fetchedEducationToRequest,
  );
  const existingWork = (fetchedProfile?.workHistory ?? []).map(
    fetchedWorkToRequest,
  );

  const educationKeys = new Set(existingEducation.map(educationKey));
  const workKeys = new Set(existingWork.map(workKey));
  const appendEducation = newRows.education.filter(
    (row) => !educationKeys.has(educationKey(row)),
  );
  const appendWork = newRows.workHistory.filter(
    (row) => !workKeys.has(workKey(row)),
  );

  const payload = {};
  if (appendEducation.length) {
    payload.education = [...existingEducation, ...appendEducation];
  }
  if (appendWork.length) {
    payload.workHistory = [...existingWork, ...appendWork];
  }
  return Object.keys(payload).length > 0 ? payload : null;
};
