import { formatDateFromParts } from "@/pages/Profile/utils";
import {
  isCompleteEducationRow,
  isCompleteExperienceRow,
} from "@/pages/Profile/profileValidation";

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
  // One `now` for the whole build, and never handed to `filter` bare: the row
  // rules take `(row, now)` and `filter` calls back with (row, index, array),
  // so the second row would be judged against the number 1.
  const now = new Date();
  const education = (profileValue.education ?? [])
    .filter((row) => isCompleteEducationRow(row, now))
    .map((row) => ({
      school: row.institution,
      degree: row.degree,
      fieldOfStudy: row.field,
      startDate: formatDateFromParts(row.startMonth, row.startYear),
      endDate: formatDateFromParts(row.endMonth, row.endYear),
    }));

  const workHistory = (profileValue.experience ?? [])
    .filter((row) => isCompleteExperienceRow(row, now))
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
 * write-back data, replacing each block the posting SHOWED with what the
 * candidate has in it.
 *
 * The candidate is asked before this runs, so replacing -- deletions included
 * -- is what they agreed to. What makes that safe is the scope: only a block
 * that was on their screen can be written. `profileConfig` can narrow the form
 * to a subset of the profile or hide a section outright, and a block nobody
 * was shown is a block nobody reviewed.
 *
 * The backend's profile upsert replaces a PATCHed list wholesale, so each
 * written list is simply the form's rows. Two guards:
 *
 * - A block the posting did not show is never written, whatever the form is
 *   still holding for it.
 * - A list identical to the stored one is omitted, so a no-op write is never
 *   sent and untouched rows are not needlessly recreated.
 *
 * The `user` key is included only when the merged personal fields differ
 * from the fetched ones (see `mergeUserWriteBack`).
 *
 * Note: written rows carry no profile-DB id, so the rows of a list that did
 * change are recreated. Carrying the id through prefill is a separate change.
 *
 * @param {object|undefined} fetchedProfile - Profile from `getMyProfile`
 *   ({user?: object, education?: object[], workHistory?: object[]} in
 *   backend field names).
 * @param {{education: object[], workHistory: object[]}} newRows - Output of
 *   `buildNewWriteBackRows`.
 * @param {{firstName?: string, lastName?: string, linkedin?: string, timezone?: string}|undefined} personal -
 *   The form's `profileValue.personal`.
 * @param {{education: boolean, workExperience: boolean}} [shown] - Which
 *   blocks the posting rendered, and so which may be written.
 * @returns {{user?: object, education?: object[], workHistory?: object[]}|null}
 */
export const buildWriteBackPayload = (
  fetchedProfile,
  newRows,
  personal,
  shown = { education: true, workExperience: true },
) => {
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
  // A block is written when the posting showed it and the candidate's rows
  // differ from the stored ones. Showing decides it, not emptiness: a block
  // the candidate emptied on screen is a deletion they asked for, while a
  // block the posting never rendered was never theirs to change here.
  if (
    shown.education &&
    !sameRowSet(newRows.education, existingEducation, educationKey)
  ) {
    payload.education = newRows.education;
  }
  if (
    shown.workExperience &&
    !sameRowSet(newRows.workHistory, existingWork, workKey)
  ) {
    payload.workHistory = newRows.workHistory;
  }
  return Object.keys(payload).length > 0 ? payload : null;
};
