/**
 * Rendering for the dates and times a leave request carries.
 *
 * A business date is a Beijing calendar day with no time in it. Nothing here
 * constructs a Date: passing `2026-10-01` through the browser's clock renders
 * it as 30 September for anybody west of UTC, and the leave calendar is one
 * calendar for the whole company rather than each viewer's own.
 *
 * For the same reason none of this uses `resolveViewerTimezone()`. That helper
 * is right for a meeting, which happens at an instant, and wrong for a holiday,
 * which happens on a date.
 */

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Label for the one place per view that says which calendar these dates are on.
 *
 * The zone is named in IANA form, the way `utils/dateTime.js` prints one, so
 * every zone the app shows reads the same. An offset would also go stale the
 * moment a zone changed its rules -- Asia/Shanghai has no daylight saving
 * today, but the name stays right either way.
 */
export const LEAVE_CALENDAR_ZONE_LABEL = "Dates in Asia/Shanghai";

const parts = (iso) => {
  const [year, month, day] = iso.split("-");
  return { year, month: MONTHS[Number(month) - 1], day: String(Number(day)) };
};

/**
 * Renders one business date.
 *
 * @param {string|null|undefined} iso A `YYYY-MM-DD` date, or nothing.
 * @returns {string} e.g. `Oct 1, 2026`, or an empty string.
 */
export const formatBusinessDate = (iso) => {
  if (!iso) return "";
  const { year, month, day } = parts(iso);
  return `${month} ${day}, ${year}`;
};

/**
 * Renders a span of business dates, collapsing a single day.
 *
 * @param {string} startIso First day, `YYYY-MM-DD`.
 * @param {string} endIso Last day, `YYYY-MM-DD`.
 * @returns {string} e.g. `Aug 13 – Aug 15, 2026`.
 */
export const formatBusinessRange = (startIso, endIso) => {
  if (!startIso || !endIso) return formatBusinessDate(startIso || endIso);
  if (startIso === endIso) return formatBusinessDate(startIso);

  const start = parts(startIso);
  const end = parts(endIso);
  if (start.year === end.year) {
    return `${start.month} ${start.day} – ${end.month} ${end.day}, ${end.year}`;
  }
  return `${formatBusinessDate(startIso)} – ${formatBusinessDate(endIso)}`;
};

/**
 * Renders the hours a single-day request covers.
 *
 * These are wall-clock times with no zone attached -- the server only ever
 * subtracts one from the other -- so they are shown as they arrived.
 *
 * @param {string|null} startTime e.g. `09:00:00`.
 * @param {string|null} endTime e.g. `13:30:00`.
 * @returns {string} e.g. `09:00 – 13:30`, or an empty string for whole days.
 */
export const formatTimeSpan = (startTime, endTime) => {
  if (!startTime || !endTime) return "";
  return `${startTime.slice(0, 5)} – ${endTime.slice(0, 5)}`;
};
