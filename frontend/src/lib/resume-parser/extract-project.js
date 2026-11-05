import { getTextWithHighestScore } from "./feature-scoring";
import { lineText } from "./group-into-sections";
import { isBold } from "./lib/features";
import { parseDates } from "./lib/dates";
import { splitIntoSubsections } from "./lib/subsections";

const DATE_HINT_RE = /(?:19|20)\d{2}|present|current/i;

// (Kept tiny and local rather than shared with extract-work to avoid coupling.)
/** Strip a trailing date range ("… Apr. 2026 – Present"). */
function stripDate(text) {
  return text
    .replace(/\s*(?:[A-Za-z]{3,9}\.?\s*)?(?:19|20)\d{2}\b.*$/i, "")
    .replace(/\s*(?:present|current)\b.*$/i, "")
    .trim();
}

/** Name candidates from the first line's items: drop date-only items. */
function nameCandidates(items) {
  const out = [];
  for (const item of items) {
    const text = stripDate(String(item.text).trim());
    if (text && !DATE_HINT_RE.test(text)) out.push({ ...item, text });
  }
  return out;
}

/**
 * Extract project / leadership / activity entries (one per subsection). The
 * name is the first line's bold-preferred non-date item; dates come from §6.5.
 * Display-only (Purrf has no project DTO) — used to surface entries from resumes
 * whose experience lives under Projects or Leadership rather than Work.
 * @param {Line[]} projectLines
 * @returns {{ name: string, startDate: string|null, endDate: string|null }[]}
 */
export function extractProjects(projectLines) {
  return splitIntoSubsections(projectLines)
    .map((sub) => {
      const dates = parseDates(sub.map(lineText).join(" "));
      const candidates = nameCandidates([...(sub[0] ?? [])]);
      const name =
        getTextWithHighestScore(candidates, [[isBold, 2]], {
          allowNonPositive: true,
        }) || stripDate(lineText(sub[0] ?? []));
      return {
        name: name.trim(),
        startDate: dates.startDate,
        endDate: dates.endDate,
      };
    })
    .filter((p) => p.name);
}
