import { lineText } from "./group-into-sections";
import { isBold } from "./lib/features";
import { parseDates } from "./lib/dates";
import { splitIntoSubsections } from "./lib/subsections";

const BULLET_ONLY_RE = /^[•‣◦▪*\-–]+$/;
const DATE_HINT_RE = /(?:19|20)\d{2}|present|current/i;

function firstNonBullet(line) {
  return line.find((t) => !BULLET_ONLY_RE.test(t.text.trim())) ?? line[0];
}

/**
 * Extract work-history entries (one per subsection). Title and company are the
 * first two non-date bold-ish lines; dates come from §6.5.
 * @param {Line[]} workLines
 */
export function extractWork(workLines) {
  return splitIntoSubsections(workLines).map((sub) => {
    const dates = parseDates(sub.map(lineText).join(" "));
    const boldLines = sub.filter((line) => {
      const text = lineText(line);
      if (DATE_HINT_RE.test(text)) return false;
      const item = firstNonBullet(line);
      return item ? isBold(item) : false;
    });
    return {
      title: boldLines[0] ? lineText(boldLines[0]) : "",
      companyOrOrganization: boldLines[1] ? lineText(boldLines[1]) : "",
      startDate: dates.startDate,
      endDate: dates.endDate,
      isCurrentJob: dates.isCurrentJob,
    };
  });
}
