import { months } from "@/pages/Profile/utils";

/**
 * Adapter from the resume parser's `ParsedResume` (see
 * `@/lib/resume-parser`) to the shape the Profile page edit forms use.
 *
 * The parser emits month-precision dates as "YYYY-MM" strings, whereas the
 * Profile forms keep separate month-name + year fields, so dates are split
 * here. Fields the Profile model has no home for — `phone`, `projects`, and the
 * free-text `summary` — are intentionally dropped (recovered later if needed).
 *
 * `parsedResumeToProfile` is a pure mapping. `mergeParsedIntoProfile` then
 * overlays that result onto whatever profile the form already holds: existing
 * is the base, the incoming value wins per scalar field only when it is
 * non-empty, and each list is replaced wholesale only when incoming has entries.
 *
 * @module parsedResumeToProfile
 */

/** A blank profile-form value, used to default missing inputs. */
const EMPTY_PERSONAL = {
  firstName: "",
  lastName: "",
  linkedin: "",
  timezone: "",
};

/**
 * Split a parser "YYYY-MM" date into the Profile model's separate month-name
 * and year-string parts. Returns empty parts for null / empty / malformed
 * input so the Profile date selects render blank.
 *
 * @param {string|null|undefined} yearMonth - e.g. "2022-09".
 * @returns {{ month: string, year: string }} Month name ("September") + year ("2022").
 */
export function yearMonthToParts(yearMonth) {
  const match = /^(\d{4})-(\d{2})$/.exec(yearMonth ?? "");
  if (!match) return { month: "", year: "" };
  const monthName = months[Number(match[2]) - 1];
  if (!monthName) return { month: "", year: "" };
  return { month: monthName, year: match[1] };
}

/**
 * Map a `ParsedResume` to the Profile page's `{ personal, education,
 * experience }` shape. Missing arrays/fields degrade to empty values so the
 * caller always receives a fully-shaped object.
 *
 * @param {object} parsed - A `ParsedResume` from `parseResumeFromPdf`.
 * @returns {{
 *   personal: { firstName: string, lastName: string, linkedin: string, timezone: string },
 *   education: { institution: string, degree: string, field: string, startMonth: string, startYear: string, endMonth: string, endYear: string }[],
 *   experience: { title: string, company: string, isCurrentlyWorking: boolean, startMonth: string, startYear: string, endMonth: string, endYear: string }[],
 * }}
 */
export function parsedResumeToProfile(parsed) {
  const { user = {}, education = [], workHistory = [] } = parsed ?? {};

  return {
    personal: {
      firstName: user.firstName ?? "",
      lastName: user.lastName ?? "",
      linkedin: user.linkedinLink ?? "",
      timezone: user.timezoneSuggestion ?? "",
    },
    education: education.map((entry) => {
      const start = yearMonthToParts(entry.startDate);
      const end = yearMonthToParts(entry.endDate);
      return {
        institution: entry.school ?? "",
        degree: entry.degree ?? "",
        field: entry.fieldOfStudy ?? "",
        startMonth: start.month,
        startYear: start.year,
        endMonth: end.month,
        endYear: end.year,
      };
    }),
    experience: workHistory.map((entry) => {
      const start = yearMonthToParts(entry.startDate);
      const end = yearMonthToParts(entry.endDate);
      return {
        title: entry.title ?? "",
        company: entry.companyOrOrganization ?? "",
        isCurrentlyWorking: Boolean(entry.isCurrentJob),
        startMonth: start.month,
        startYear: start.year,
        endMonth: end.month,
        endYear: end.year,
      };
    }),
  };
}

/**
 * Overlay an `incoming` profile (typically `parsedResumeToProfile`'s output)
 * onto an `existing` profile that the form already holds. Existing is the base:
 *
 * - personal: per field, the incoming value wins only when it is non-empty;
 *   an empty incoming value leaves the existing one untouched.
 * - education / experience: the incoming list replaces the existing one
 *   wholesale, but only when it has at least one entry; an empty incoming list
 *   leaves the existing list untouched.
 *
 * Pure — neither argument is mutated. Missing arguments/fields degrade to empty.
 *
 * @param {object|undefined} existing - The profile currently in the form.
 * @param {object|undefined} incoming - The profile to overlay (e.g. parsed resume).
 * @returns {{ personal: object, education: object[], experience: object[] }}
 */
export function mergeParsedIntoProfile(existing, incoming) {
  const base = existing ?? {};
  const overlay = incoming ?? {};
  const basePersonal = { ...EMPTY_PERSONAL, ...(base.personal ?? {}) };
  const overlayPersonal = overlay.personal ?? {};

  const personal = {};
  for (const key of Object.keys(EMPTY_PERSONAL)) {
    personal[key] = overlayPersonal[key] || basePersonal[key] || "";
  }

  return {
    personal,
    education: overlay.education?.length
      ? overlay.education
      : (base.education ?? []),
    experience: overlay.experience?.length
      ? overlay.experience
      : (base.experience ?? []),
  };
}
