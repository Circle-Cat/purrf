import { extractEducation } from "./extract-education";
import { extractProfile } from "./extract-profile";
import { extractWork } from "./extract-work";
import { groupIntoLines } from "./group-into-lines";
import { groupIntoSections, lineText } from "./group-into-sections";
import { readPdf } from "./read-pdf";
import { toProfile } from "./to-profile";

/** Run fn, returning fallback if it throws (graceful degradation). */
function safe(fn, fallback) {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

/** Find the first section whose title contains any keyword; [] if none. */
function findSection(sections, keywords) {
  for (const key of Object.keys(sections)) {
    if (key === "profile") continue;
    const lower = key.toLowerCase();
    if (keywords.some((k) => lower.includes(k))) return sections[key];
  }
  return [];
}

/**
 * Parse a resume PDF into a ParsedResume for the profile confirmation form.
 * Single public entry point — never throws; returns a shaped (possibly empty)
 * result so callers and the form can rely on the structure.
 *
 * @param {File|Blob|ArrayBuffer|Uint8Array} file
 * @returns {Promise<ParsedResume>}
 */
export async function parseResumeFromPdf(file) {
  const items = await readPdf(file); // already returns [] on failure
  const lines = safe(() => groupIntoLines(items), []);
  // If section detection fails, treat the whole doc as the profile.
  const sections = safe(() => groupIntoSections(lines), { profile: lines });

  const profile = safe(() => extractProfile(sections.profile ?? []), {});
  const education = safe(
    () => extractEducation(findSection(sections, ["education"])),
    [],
  );
  const workHistory = safe(
    () =>
      extractWork(findSection(sections, ["experience", "employment", "work"])),
    [],
  );

  const summarySection = findSection(sections, ["summary", "objective"]);
  // A dedicated Summary/Objective section takes precedence over the header-derived summary.
  const summary = summarySection.length
    ? summarySection.map(lineText).join(" ")
    : profile.summary;

  return safe(
    () =>
      toProfile({
        profile,
        education,
        workHistory,
        summary,
        location: profile.location,
      }),
    {
      user: { firstName: "", lastName: "" },
      education: [],
      workHistory: [],
      unmapped: {},
    },
  );
}
