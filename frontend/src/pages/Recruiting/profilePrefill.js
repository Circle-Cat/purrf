import { parseDateParts } from "@/pages/Profile/utils";

let uid = 0;
/**
 * Monotonic local row id (unique across this module's lifetime), prefixed
 * distinctly from `RecruitingProfileForm`'s own "rpf-" ids so the two
 * sources are never confused when debugging.
 */
const nextId = () => `ppf-${(uid += 1)}`;

/** A blank profile-form personal value, used to default missing input. */
const EMPTY_PERSONAL = {
  firstName: "",
  lastName: "",
  linkedin: "",
  timezone: "",
};

/**
 * Map a fetched profile (`getMyProfile`'s response shape, backend field
 * names) into `ApplicationForm`'s `profileValue` shape, for prefilling a
 * brand-new application. This is the reverse of `profileWriteBack.js`'s
 * `fetchedEducationToRequest`/`fetchedWorkToRequest` (which map the same
 * fetched shape into a profile PATCH request instead).
 *
 * Unlike `parsedResumeToProfile` (whose caller assigns row ids via
 * `RecruitingProfileForm`'s `withId` after merging), this function assigns
 * each row a fresh local id itself: its caller (`ApplicationForm`) sets
 * `profileValue` directly without going through that merge step, and
 * `ProfileSection` uses `row.id` both as a React key and as row identity
 * for edit/delete, so every row needs a genuinely unique id up front.
 *
 * Missing/absent fields degrade to the same empty defaults a blank form
 * already uses, so an empty or absent profile produces a no-op prefill.
 *
 * @param {object|undefined} fetchedProfile - `{user?, education?, workHistory?}`
 *   in backend field names, as returned by `getMyProfile`.
 * @returns {{
 *   personal: { firstName: string, lastName: string, linkedin: string, timezone: string },
 *   education: { id: string, institution: string, degree: string, field: string, startMonth: string, startYear: string, endMonth: string, endYear: string }[],
 *   experience: { id: string, title: string, company: string, isCurrentlyWorking: boolean, startMonth: string, startYear: string, endMonth: string, endYear: string }[],
 * }}
 */
export function profileToApplicationForm(fetchedProfile) {
  const { user = {}, education = [], workHistory = [] } = fetchedProfile ?? {};

  return {
    personal: {
      firstName: user.firstName ?? EMPTY_PERSONAL.firstName,
      lastName: user.lastName ?? EMPTY_PERSONAL.lastName,
      linkedin: user.linkedinLink ?? EMPTY_PERSONAL.linkedin,
      timezone: user.timezone ?? EMPTY_PERSONAL.timezone,
    },
    education: education.map((row) => {
      const start = parseDateParts(row.startDate);
      const end = parseDateParts(row.endDate);
      return {
        id: nextId(),
        institution: row.school ?? "",
        degree: row.degree ?? "",
        field: row.fieldOfStudy ?? "",
        startMonth: start.month,
        startYear: start.year,
        endMonth: end.month,
        endYear: end.year,
      };
    }),
    experience: workHistory.map((row) => {
      const isCurrentlyWorking = Boolean(row.isCurrentJob);
      const start = parseDateParts(row.startDate);
      // A current job's end date is meaningless (and hidden by the form's
      // "currently working" toggle) -- blank it regardless of what's
      // stored, mirroring `profileWriteBack.js`'s forward-direction
      // `endDate: row.isCurrentlyWorking ? null : ...`.
      const end = isCurrentlyWorking
        ? { month: "", year: "" }
        : parseDateParts(row.endDate);
      return {
        id: nextId(),
        title: row.title ?? "",
        company: row.companyOrOrganization ?? "",
        isCurrentlyWorking,
        startMonth: start.month,
        startYear: start.year,
        endMonth: end.month,
        endYear: end.year,
      };
    }),
  };
}
