import { getTextWithHighestScore } from "./feature-scoring";
import { lineText } from "./group-into-sections";
import { hasNumber, isBold } from "./lib/features";
import { parseDates } from "./lib/dates";
import { splitIntoSubsections } from "./lib/subsections";

// Common job-title nouns. A header candidate containing one of these (as a
// whole word) is the title; the other header candidate is the company.
const JOB_TITLES = [
  "accountant",
  "administrator",
  "advisor",
  "agent",
  "ambassador",
  "analyst",
  "apprentice",
  "architect",
  "assistant",
  "associate",
  "auditor",
  "bartender",
  "bookkeeper",
  "buyer",
  "captain",
  "cashier",
  "ceo",
  "cfo",
  "clerk",
  "consultant",
  "coordinator",
  "cto",
  "designer",
  "developer",
  "director",
  "driver",
  "editor",
  "engineer",
  "extern",
  "fellow",
  "founder",
  "freelancer",
  "head",
  "instructor",
  "intern",
  "journalist",
  "lawyer",
  "lead",
  "manager",
  "mechanic",
  "member",
  "nurse",
  "officer",
  "official",
  "operator",
  "photographer",
  "president",
  "producer",
  "programmer",
  "recruiter",
  "representative",
  "researcher",
  "sales",
  "scientist",
  "server",
  "specialist",
  "steward",
  "supervisor",
  "teacher",
  "technician",
  "trader",
  "trainee",
  "tutor",
  "volunteer",
  "vp",
  "worker",
];
const JOB_TITLE_RE = new RegExp(`\\b(?:${JOB_TITLES.join("|")})\\b`, "i");
const BULLET_LINE_RE = /^\s*[•‣◦▪·*]|^\s*[-–]\s/;

/** @param {TextItem} i */
const hasJobTitle = (i) => JOB_TITLE_RE.test(i.text);
/** @param {TextItem} i */
const hasManyWords = (i) => i.text.trim().split(/\s+/).length > 6;

const JOB_TITLE_FEATURES = [
  [hasJobTitle, 4],
  [hasNumber, -4],
  [hasManyWords, -2],
];

/** Index of the first bullet (description) line, else the header cap (2). */
function firstBulletIdx(lines) {
  const idx = lines.findIndex((l) => BULLET_LINE_RE.test(lineText(l)));
  return idx === -1 ? Math.min(2, lines.length) : idx;
}

/** Strip a trailing date range ("… May 2022 – Aug 2024" / "… Present"). */
function stripDate(text) {
  return text
    .replace(/\s*(?:[A-Za-z]{3,9}\.?\s*)?(?:19|20)\d{2}\b.*$/i, "")
    .replace(/\s*(?:present|current)\b.*$/i, "")
    .trim();
}

/**
 * Build company/title candidates from the header items: split each item on "|"
 * (many resumes write "Company | Title"), strip trailing dates, and drop items
 * that are only a date. Each candidate keeps its source item's styling (bold).
 * @param {TextItem[]} items
 * @returns {TextItem[]}
 */
function headerCandidates(items) {
  const out = [];
  for (const item of items) {
    for (const part of String(item.text).split("|")) {
      const text = stripDate(part.trim());
      if (text) out.push({ ...item, text });
    }
  }
  return out;
}

/**
 * Extract work-history entries (one per subsection). Within each subsection the
 * header is the lines above the bullet descriptions; the title is the candidate
 * bearing a job-title keyword, and the company is the remaining (bold-preferred)
 * candidate that is neither the date nor the title. Dates come from §6.5.
 * @param {Line[]} workLines
 */
export function extractWork(workLines) {
  return splitIntoSubsections(workLines).map((sub) => {
    const dates = parseDates(sub.map(lineText).join(" "));
    const header = sub.slice(0, firstBulletIdx(sub));
    const candidates = headerCandidates(header.flat());

    const title = getTextWithHighestScore(candidates, JOB_TITLE_FEATURES);
    const companyFeatures = [[isBold, 2]];
    if (title) companyFeatures.push([(i) => i.text.includes(title), -4]);
    const company = getTextWithHighestScore(candidates, companyFeatures, {
      allowNonPositive: true,
    });

    return {
      title,
      companyOrOrganization: company === title ? "" : company,
      startDate: dates.startDate,
      endDate: dates.endDate,
      isCurrentJob: dates.isCurrentJob,
    };
  });
}
