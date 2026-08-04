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
 * Whether the application form collected any personal input worth writing
 * back (first/last name, LinkedIn, or timezone). Used to skip the profile
 * fetch entirely when there is nothing personal AND no complete rows.
 *
 * @param {{firstName?: string, lastName?: string, linkedin?: string, timezone?: string}|undefined} personal
 * @returns {boolean}
 */
export const hasPersonalWriteBackInput = (personal) =>
  Boolean(
    personal?.firstName?.trim() ||
    personal?.lastName?.trim() ||
    personal?.linkedin?.trim() ||
    personal?.timezone?.trim(),
  );

/**
 * Merge the form's personal fields over the FETCHED profile user into the
 * full six-key `user` request object (mirroring PersonalEditModal's
 * payload; the backend UsersRequestDto requires firstName/lastName/
 * timezone/communicationMethod). Returns `null` when the merged object
 * doesn't actually differ from the fetched values, so no-op user writes
 * are never sent.
 *
 * Form values win per field only when non-empty; `preferredName` and
 * `communicationMethod` aren't collected by the form and pass through
 * fetched (communicationMethod defaulting to "email"). The form's timezone
 * is adopted whenever it is non-empty (there is no cooldown restriction).
 *
 * @param {object|undefined} fetchedUser - `profile.user` from `getMyProfile`.
 * @param {{firstName?: string, lastName?: string, linkedin?: string, timezone?: string}|undefined} personal
 * @returns {object|null} Six-key user request object, or null when unchanged.
 */
const mergeUserWriteBack = (fetchedUser, personal) => {
  const fetched = fetchedUser ?? {};
  const formTimezone = personal?.timezone?.trim();

  const merged = {
    firstName: personal?.firstName?.trim() || fetched.firstName,
    lastName: personal?.lastName?.trim() || fetched.lastName,
    preferredName: fetched.preferredName,
    timezone: formTimezone || fetched.timezone,
    linkedinLink: personal?.linkedin?.trim() || fetched.linkedinLink,
    communicationMethod: fetched.communicationMethod ?? "email",
  };

  const differs =
    merged.firstName !== fetched.firstName ||
    merged.lastName !== fetched.lastName ||
    merged.timezone !== fetched.timezone ||
    merged.linkedinLink !== fetched.linkedinLink ||
    merged.communicationMethod !== fetched.communicationMethod;
  return differs ? merged : null;
};

/**
 * Whether two request-shaped row lists hold the same rows by content key,
 * order-insensitive -- used to skip a no-op overwrite of an unchanged list.
 *
 * @param {object[]} a
 * @param {object[]} b
 * @param {(row: object) => string} keyFn - `educationKey` or `workKey`.
 * @returns {boolean}
 */
const sameRowSet = (a, b, keyFn) => {
  if (a.length !== b.length) return false;
  const bKeys = new Set(b.map(keyFn));
  return a.every((row) => bKeys.has(keyFn(row)));
};

/**
 * Build the profile PATCH payload from the application form's reviewed
 * write-back data, OVERWRITING the user's profile lists with what the form
 * shows -- the applicant reviewed their info while applying (opt-in via
 * "save to my profile"), so the reviewed version becomes their profile.
 *
 * The backend's profile upsert has full-overwrite semantics (a PATCHed list
 * fully replaces what's stored), so each written list is simply the form's
 * complete rows. Two deliberate guards:
 *
 * - A section the form has NO complete rows for is left out of the payload
 *   entirely -- an empty section means "not filled in here", never "clear my
 *   profile", so it never wipes a stored list to empty.
 * - A section whose form rows already match the stored ones (by content,
 *   order-insensitive) is omitted too, so no-op writes are never sent.
 *
 * The `user` key is included only when the merged personal fields differ
 * from the fetched ones (see `mergeUserWriteBack`).
 *
 * Note: overwriting a list drops any stored rows the form doesn't show
 * (what-you-see-is-what-your-profile-becomes) and assigns fresh ids to the
 * written rows, since the form's rows carry no profile-DB id.
 *
 * @param {object|undefined} fetchedProfile - Profile from `getMyProfile`
 *   ({user?: object, education?: object[], workHistory?: object[]} in
 *   backend field names).
 * @param {{education: object[], workHistory: object[]}} newRows - Output of
 *   `buildNewWriteBackRows`.
 * @param {{firstName?: string, lastName?: string, linkedin?: string, timezone?: string}|undefined} personal -
 *   The form's `profileValue.personal`.
 * @returns {{user?: object, education?: object[], workHistory?: object[]}|null}
 */
export const buildWriteBackPayload = (fetchedProfile, newRows, personal) => {
  const existingEducation = (fetchedProfile?.education ?? []).map(
    fetchedEducationToRequest,
  );
  const existingWork = (fetchedProfile?.workHistory ?? []).map(
    fetchedWorkToRequest,
  );

  const payload = {};
  const user = mergeUserWriteBack(fetchedProfile?.user, personal);
  if (user) {
    payload.user = user;
  }
  if (
    newRows.education.length &&
    !sameRowSet(newRows.education, existingEducation, educationKey)
  ) {
    payload.education = newRows.education;
  }
  if (
    newRows.workHistory.length &&
    !sameRowSet(newRows.workHistory, existingWork, workKey)
  ) {
    payload.workHistory = newRows.workHistory;
  }
  return Object.keys(payload).length > 0 ? payload : null;
};
