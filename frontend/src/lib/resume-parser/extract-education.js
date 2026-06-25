import { getTextWithHighestScore } from "./feature-scoring";
import { lineText } from "./group-into-sections";
import {
  hasComma,
  hasDegree,
  hasLetter,
  hasNumber,
  hasSchool,
  matchGpa,
} from "./lib/features";
import { parseDates } from "./lib/dates";
import { splitIntoSubsections } from "./lib/subsections";

const SCHOOL_FEATURES = [
  [hasSchool, 4],
  [hasDegree, -4],
  [hasNumber, -4],
];
const DEGREE_FEATURES = [
  [hasDegree, 4],
  [hasSchool, -4],
  [hasNumber, -3],
];
const GPA_FEATURES = [
  [matchGpa, 4, true],
  [hasComma, -3],
  [hasLetter, -4],
];

// field_of_study regexes (§6.3), tried in order, case-insensitive.
const FIELD_RES = [
  /(?:Bachelor|Master|Associate|Doctor(?:ate)?)\s+of\s+\w+(?:\s+\w+)?\s+in\s+(.+)/i,
  /(?:B|M|A)\.?\s?[SA]\.?\s+in\s+(.+)/i,
  /\bin\s+(.+)/i,
  /\bof\s+(.+)/i,
];

// Generic degree-type nouns the bare "of" fallback can capture (e.g. "Bachelor
// of Science"). These name the degree, not a field of study, so they are not a
// usable field_of_study — leave it empty for the user to fill.
const DEGREE_TYPE_WORDS = new Set(["science", "arts"]);

/** Trim GPA, dates, "at <location>", and trailing comma clauses off a field. */
function cleanField(s) {
  return s
    .replace(/\b\d\.\d{1,2}\s*GPA\b.*/i, "")
    .replace(/\b(?:19|20)\d{2}.*/, "")
    .replace(/\bat\s+.*/i, "")
    .replace(/,.*/, "")
    .trim();
}

/**
 * Extract field_of_study from a line that already matched a degree keyword.
 * @param {string} degreeText
 * @returns {string} "" when no of/in field is found
 */
export function extractFieldOfStudy(degreeText) {
  for (const re of FIELD_RES) {
    const m = degreeText.match(re);
    if (!m) continue;
    const field = cleanField(m[1]);
    if (field && !DEGREE_TYPE_WORDS.has(field.toLowerCase())) return field;
  }
  return "";
}

/**
 * Extract education entries (one per subsection).
 * @param {Line[]} eduLines
 */
export function extractEducation(eduLines) {
  return splitIntoSubsections(eduLines).map((sub) => {
    const items = sub.flat();
    const degree = getTextWithHighestScore(items, DEGREE_FEATURES);
    const dates = parseDates(sub.map(lineText).join(" "));
    return {
      school: getTextWithHighestScore(items, SCHOOL_FEATURES),
      degree,
      fieldOfStudy: degree ? extractFieldOfStudy(degree) : "",
      gpa: getTextWithHighestScore(items, GPA_FEATURES),
      startDate: dates.startDate,
      endDate: dates.endDate,
    };
  });
}
