export const months = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const currentYear = new Date().getFullYear();

// Generate an array of 50 years counting backward from the current year
export const years = Array.from({ length: 50 }, (v, i) => currentYear - i);

/**
 * Parse an API date string formatted as "YYYY-MM-DD" into
 * a more UI-friendly `{ month, year }` structure.
 *
 * This function avoids using `new Date()` to bypass timezone shifts
 * that may cause the parsed date to move backward by one day.
 *
 * @param {string} dateStr - Date string such as "2023-09-01".
 * @returns {{ month: string, year: string }} Parsed date parts.
 */
export const parseDateParts = (dateStr) => {
  if (!dateStr) return { month: "", year: "" };

  const regex = /^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;
  const match = dateStr.match(regex);

  if (!match) return { month: "", year: "" };

  const [_, year, month] = match;
  const monthIndex = parseInt(month, 10) - 1;

  return {
    month: months[monthIndex] || "",
    year: year || "",
  };
};

/**
 * Convert separate month/year selections into an API-friendly
 * "YYYY-MM-DD" string (defaulting to the 1st day of the month).
 *
 * @param {string} month - Month name (e.g., "September").
 * @param {string|number} year - Year value (e.g., "2023").
 * @returns {string|null} A formatted date string or null if invalid.
 */
export const formatDateFromParts = (month, year) => {
  if (!month || !year) return null;

  const monthIndex = months.indexOf(month);
  if (monthIndex === -1) return null;

  const m = String(monthIndex + 1).padStart(2, "0");
  return `${year}-${m}-01`;
};

/**
 * Format a human-readable duration for experience or education entries.
 *
 * Examples:
 * - "Sep 2020 - Present"
 * - "Sep 2020 - Jan 2022"
 *
 * @param {string} startMonth
 * @param {string|number} startYear
 * @param {string} endMonth
 * @param {string|number} endYear
 * @param {boolean} isCurrent - Whether the entry is ongoing.
 * @returns {string} Formatted duration string.
 */
export const formatTimeDuration = (
  startMonth,
  startYear,
  endMonth,
  endYear,
  isCurrent,
) => {
  const format = (month, year) =>
    month && year ? `${month.slice(0, 3)} ${year}` : "";

  const start = format(startMonth, startYear);
  const end = isCurrent ? "Present" : format(endMonth, endYear);

  if (start && end) {
    return `${start} - ${end}`;
  }
  return start || end || "";
};

/**
 * Calculate how many days have passed since the provided date.
 * Used to enforce a "30-day edit restriction".
 *
 * If no date is provided, a large fallback number (999) is returned,
 * indicating the entry is allowed to be edited.
 *
 * @param {string} dateString - The stored "last updated" timestamp.
 * @returns {number} Number of days since the given date.
 */
export const getDaysSince = (dateString) => {
  if (!dateString) return 999;

  const date = new Date(dateString);
  const now = new Date();

  const diffTime = Math.abs(now - date);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

/**
 * Validate whether the given string is in a basic email format.
 *
 * Note: This is a simple format validator and does NOT check whether
 * the domain or mailbox actually exists.
 *
 * @param {string} email
 * @returns {boolean} True if valid email format, otherwise false.
 */
export const isValidEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};
