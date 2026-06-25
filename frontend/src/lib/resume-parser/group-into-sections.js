import { isAllUpperWithLetter, isBold, isContactLine } from "./lib/features";

const HEADER_MAX_LINES = 5;
const TITLE_KEYWORDS = [
  "experience",
  "education",
  "project",
  "skill",
  "job",
  "course",
  "extracurricular",
  "objective",
  "summary",
  "award",
  "honor",
  "certification",
  "certificate",
  "leadership",
  "activit",
  "language",
  "interest",
  "volunteer",
];
const TITLE_FALLBACK_RE = /^[A-Za-z\s&]+$/;

/** Join a line's items into a single string. @param {Line} line */
export function lineText(line) {
  return line.map((t) => t.text).join(" ");
}

/**
 * A section title occupies its own single-item line and is either bold+ALLCAPS
 * (primary) or a short keyword-bearing capitalized phrase (fallback).
 * @param {Line} line
 * @returns {boolean}
 */
export function isSectionTitle(line) {
  if (line.length !== 1) return false;
  const item = line[0];
  if (isContactLine(item.text)) return false;
  if (isBold(item) && isAllUpperWithLetter(item)) return true;

  const text = item.text.trim();
  // Count words but ignore a standalone "&" ("Skills & Certifications" is two
  // words, not three) so multi-word title-case headers still qualify.
  const words = text.split(/\s+/).filter((w) => w && w !== "&");
  if (
    words.length <= 2 &&
    /^[A-Z]/.test(text) &&
    TITLE_FALLBACK_RE.test(text)
  ) {
    const lower = text.toLowerCase();
    if (TITLE_KEYWORDS.some((k) => lower.includes(k))) return true;
  }
  return false;
}

/**
 * Split lines into the profile header plus titled sections.
 * Header = line 0 (the name) plus any subsequent contact line within the first
 * N lines; section detection runs on the lines after the header.
 * @param {Line[]} lines
 * @returns {Sections}
 */
export function groupIntoSections(lines) {
  const profile = [];
  let bodyStart = 0;
  for (let idx = 0; idx < lines.length; idx++) {
    if (idx === 0) {
      profile.push(lines[idx]);
      bodyStart = 1;
      continue;
    }
    if (idx < HEADER_MAX_LINES && isContactLine(lineText(lines[idx]))) {
      profile.push(lines[idx]);
      bodyStart = idx + 1;
    } else {
      break;
    }
  }

  /** @type {Sections} */
  const sections = { profile };
  let currentName = null;
  let currentLines = [];
  const flush = () => {
    if (currentName !== null) sections[currentName] = currentLines;
  };
  for (let idx = bodyStart; idx < lines.length; idx++) {
    const line = lines[idx];
    if (isSectionTitle(line)) {
      flush();
      currentName = lineText(line);
      currentLines = [];
    } else if (currentName !== null) {
      currentLines.push(line);
    }
  }
  flush();
  return sections;
}
