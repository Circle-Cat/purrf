import { inferTimezone } from "./lib/timezone";

/**
 * @typedef {Object} ParsedResume
 * @property {{ firstName: string, lastName: string, phone?: string,
 *   linkedinLink?: string, timezoneSuggestion?: string }} user
 * @property {{ school: string, degree?: string, fieldOfStudy?: string,
 *   startDate?: string|null, endDate?: string|null }[]} education
 * @property {{ title: string, companyOrOrganization: string, startDate?: string|null,
 *   endDate?: string|null, isCurrentJob: boolean }[]} workHistory
 * @property {{ summary?: string }} unmapped
 */

const SUFFIXES = new Set(["jr", "sr", "ii", "iii", "iv", "phd"]);
const LINKEDIN_RE = /linkedin\.com/i;

/**
 * Split a full name: last token -> last_name, the rest -> first_name. A trailing
 * suffix (Jr/Sr/II/III/IV/PhD) is folded onto the last name first.
 * @param {string} name
 * @returns {{ firstName: string, lastName: string }}
 */
export function splitName(name) {
  if (!name || !name.trim()) return { firstName: "", lastName: "" };
  const tokens = name.trim().split(/\s+/);
  let suffix = null;
  if (tokens.length > 1) {
    const last = tokens[tokens.length - 1].replace(/\.$/, "").toLowerCase();
    if (SUFFIXES.has(last)) suffix = tokens.pop();
  }
  if (tokens.length === 1) {
    return { firstName: tokens[0], lastName: suffix ?? "" };
  }
  const lastName = tokens.pop();
  return {
    firstName: tokens.join(" "),
    lastName: suffix ? `${lastName} ${suffix}` : lastName,
  };
}

/**
 * Classify free-text degree to the Purrf Degree enum
 * (Associate/Bachelor/Master/Doctorate/Professional). Returns undefined when
 * not classifiable (e.g. High School / Certificate) so the user picks.
 * @param {string} text
 * @returns {string|undefined}
 */
export function classifyDegree(text) {
  const t = (text ?? "").toLowerCase();
  // Professional doctorates (Juris Doctor, M.D., …) also contain "doctor", so
  // they must be matched before the academic-doctorate check below.
  if (/\b(?:j\.?d|m\.?d|esq|juris|pharm\.?d|dds)\b/.test(t))
    return "Professional";
  if (/ph\.?\s?d|doctor/.test(t)) return "Doctorate";
  if (/master|\bm\.?\s?[sa]\b|mba|m\.?eng/.test(t)) return "Master";
  if (/bachelor|\bb\.?\s?[sa]\b|b\.?eng/.test(t)) return "Bachelor";
  if (/associate|\ba\.?\s?[sa]\b/.test(t)) return "Associate";
  return undefined;
}

/** @param {string} url */
export function isLinkedin(url) {
  return LINKEDIN_RE.test(url ?? "");
}

/**
 * Map extractor output to a ParsedResume for the confirmation form.
 * email is never mapped; location is consumed by timezone inference only.
 * @param {{ profile: object, education: object[], workHistory: object[], summary?: string }} raw
 * @returns {ParsedResume}
 */
export function toProfile(raw) {
  const { profile = {}, education = [], workHistory = [], summary } = raw;
  const { firstName, lastName } = splitName(profile.name ?? "");
  return {
    user: {
      firstName,
      lastName,
      phone: profile.phone || undefined,
      linkedinLink: isLinkedin(profile.url) ? profile.url : undefined,
      timezoneSuggestion: inferTimezone(profile.location) ?? undefined,
    },
    education: education.map((e) => ({
      school: e.school,
      degree: classifyDegree(e.degree),
      fieldOfStudy: e.fieldOfStudy || undefined,
      startDate: e.startDate ?? null,
      endDate: e.endDate ?? null,
    })),
    workHistory: workHistory.map((w) => ({
      title: w.title,
      companyOrOrganization: w.companyOrOrganization,
      startDate: w.startDate ?? null,
      endDate: w.endDate ?? null,
      isCurrentJob: Boolean(w.isCurrentJob),
    })),
    unmapped: { summary: summary || undefined },
  };
}
