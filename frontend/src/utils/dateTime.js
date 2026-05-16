import { format } from "date-fns";
import { TZDate } from "@date-fns/tz";

/**
 * Format a UTC ISO string into the given IANA timezone using a date-fns pattern.
 * Returns null for null/empty/invalid iso inputs.
 * Falls back to UTC when tz is null or empty.
 *
 * @param {string|null|undefined} iso - UTC ISO datetime string (e.g. "2024-03-10T02:00:00Z").
 * @param {string|null|undefined} tz - IANA timezone string (e.g. "America/New_York").
 * @param {string} pattern - date-fns format pattern (e.g. "yyyy-MM-dd", "HH:mm").
 * @returns {string|null}
 */
export function formatInTz(iso, tz, pattern) {
  if (!iso) return null;
  const date = new Date(iso);
  if (isNaN(date.getTime())) return null;
  return format(new TZDate(date, tz || "UTC"), pattern);
}

/**
 * Format a JS Date object as a YYYY-MM-DD string using the browser's local time.
 * Avoids the UTC/local boundary issue of `.toISOString().split("T")[0]`.
 *
 * @param {Date} date
 * @returns {string} e.g. "2024-03-10"
 */
export function formatLocalYmd(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Returns a plain JS Date representing today (local midnight) in the given IANA timezone.
 * Use this to initialise date pickers that need "today" relative to a specific timezone.
 *
 * @param {string} tz - IANA timezone string (e.g. "America/New_York").
 * @returns {Date} Plain Date set to midnight local time for today in tz.
 */
export function todayInTz(tz) {
  const now = new TZDate(new Date(), tz);
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/**
 * Returns the current moment as a TZDate in the given IANA timezone.
 * The returned object's .getHours(), .getMinutes(), .getDate(), etc.
 * all reflect local time in tz rather than the browser's timezone.
 *
 * @param {string} tz - IANA timezone string.
 * @returns {TZDate}
 */
export function nowInTz(tz) {
  return new TZDate(new Date(), tz);
}

/**
 * Convert a local date + HH:mm time string in a given IANA timezone to a UTC ISO string.
 * Inverse of formatInTz — used when submitting user-selected local datetimes to the backend.
 *
 * @param {Date} dateObj - Plain Date whose getFullYear/Month/Date components are used.
 * @param {string} timeStr - "HH:mm" string (e.g. "14:30").
 * @param {string} tz - IANA timezone string.
 * @param {number} [addDays=0] - Optional day offset applied to dateObj's date.
 * @returns {string} UTC ISO string without milliseconds, e.g. "2024-03-15T12:00:00Z".
 */
export function localToUtcIso(dateObj, timeStr, tz, addDays = 0) {
  const [h, m] = timeStr.split(":").map(Number);
  const d = new TZDate(
    dateObj.getFullYear(),
    dateObj.getMonth(),
    dateObj.getDate() + addDays,
    h,
    m,
    0,
    tz,
  );
  return new Date(+d).toISOString().split(".")[0] + "Z";
}

/**
 * Return the number of calendar days elapsed since the given date string.
 * Returns 999 for null/undefined input (treated as "very long ago").
 *
 * @param {string|null|undefined} dateString - ISO date/datetime string.
 * @returns {number}
 */
export function getDaysSince(dateString) {
  if (!dateString) return 999;
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now - date);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

/**
 * Format an IANA timezone string as a human-readable label.
 * e.g. "Asia/Shanghai" → "Shanghai (UTC+8)"
 *
 * @param {string} tz - IANA timezone string.
 * @returns {string}
 */
export function formatTimezoneLabel(tz) {
  const city = tz.split("/")[1].replace(/_/g, " ");

  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    timeZoneName: "shortOffset",
  }).formatToParts(new Date());

  const offset =
    parts
      .find((p) => p.type === "timeZoneName")
      ?.value?.replace("GMT", "UTC") ?? "";

  return `${city} (${offset})`;
}
