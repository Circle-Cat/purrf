const MONTH_MAP = {
  january: 1,
  jan: 1,
  february: 2,
  feb: 2,
  march: 3,
  mar: 3,
  april: 4,
  apr: 4,
  may: 5,
  june: 6,
  jun: 6,
  july: 7,
  jul: 7,
  august: 8,
  aug: 8,
  september: 9,
  sep: 9,
  sept: 9,
  october: 10,
  oct: 10,
  november: 11,
  nov: 11,
  december: 12,
  dec: 12,
};
const SEASON_MAP = { spring: 3, summer: 6, fall: 9, autumn: 9, winter: 12 };
const PRESENT_RE = /present|current|now/i;
// Optional month/season word, then a 4-digit 19xx/20xx year — OR a present token.
const DATE_TOKEN_RE =
  /([A-Za-z]{3,9})?\.?\s*((?:19|20)\d{2})|present|current|now/gi;

function empty() {
  return {
    startDate: null,
    endDate: null,
    isCurrentJob: false,
    lowConfidence: false,
  };
}

/** Month precision is enough for resumes; emit "YYYY-MM" (no day). */
function toYearMonth(year, month) {
  return `${year}-${String(month ?? 1).padStart(2, "0")}`;
}

/**
 * Normalize a free-text date range to "YYYY-MM" start/end + an is-current flag.
 * Month precision only (no day). Never throws.
 * @param {string} text
 */
export function parseDates(text) {
  if (!text) return empty();
  const tokens = [];
  DATE_TOKEN_RE.lastIndex = 0;
  let m;
  while ((m = DATE_TOKEN_RE.exec(text))) {
    if (PRESENT_RE.test(m[0]) && !m[2]) {
      tokens.push({ present: true });
      continue;
    }
    const word = (m[1] ?? "").toLowerCase();
    const year = parseInt(m[2], 10);
    const month = MONTH_MAP[word] ?? SEASON_MAP[word] ?? null;
    tokens.push({ present: false, year, month });
  }
  if (tokens.length === 0) return empty();

  const start = tokens[0];
  const end = tokens[1];

  // Single token.
  if (!end) {
    if (start.present) return { ...empty(), isCurrentJob: true };
    return { ...empty(), startDate: toYearMonth(start.year, start.month) };
  }

  // Range. A present end means current job.
  if (end.present) {
    return {
      startDate: start.present ? null : toYearMonth(start.year, start.month),
      endDate: null,
      isCurrentJob: true,
      lowConfidence: false,
    };
  }

  let startDate = start.present ? null : toYearMonth(start.year, start.month);
  let endDate = toYearMonth(end.year, end.month);
  let lowConfidence = false;
  if (startDate && endDate && endDate < startDate) {
    [startDate, endDate] = [endDate, startDate];
    lowConfidence = true;
  }
  return { startDate, endDate, isCurrentJob: false, lowConfidence };
}
