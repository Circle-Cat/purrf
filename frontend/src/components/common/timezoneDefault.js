import timezones from "@/constants/Timezones";

/**
 * A sensible starting timezone for someone who has not picked one.
 *
 * `TimezoneSelector` is backed by a curated list of ~26 zones, not the IANA
 * database, so the zone a browser reports is often not on it -- `Asia/Taipei`
 * isn't, and some engines still report the pre-1993 `Asia/Calcutta` for a list
 * that carries `Asia/Kolkata`. Storing such a value would be worse than
 * storing nothing: the control would look empty while validation read the
 * field as answered.
 *
 * So an unlisted zone is mapped onto the first listed one at the same UTC
 * offset: Taipei lands on Shanghai, whose label already reads "Beijing,
 * Shanghai, Singapore, Hong Kong". When nothing shares the offset, this gives
 * up and returns "" -- an empty picker the candidate fills in beats a
 * confidently wrong one.
 *
 * Preferring an entry from the same area (`Asia/`, `Europe/`) was tried and
 * dropped: with this list it cannot change any answer, because the only
 * offsets with entries in two areas already have the plausible one first, and
 * an unlisted zone whose own area matches is one nothing reports.
 */

const OFFERED = Object.keys(timezones);

/**
 * Minutes east of UTC that `zone` is on at `at`.
 *
 * Read by formatting the instant in that zone and diffing, which needs only
 * timezone data and the always-present `en-US` locale -- not the full ICU
 * locale set, which a trimmed Node build may lack.
 *
 * @param {string} zone IANA zone name.
 * @param {Date} at The instant to measure at; offsets move with DST.
 * @returns {number|null} Null when the engine does not recognise the zone.
 */
const offsetMinutes = (zone, at) => {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).formatToParts(at);
    const read = Object.fromEntries(parts.map((p) => [p.type, p.value]));
    const asUtc = Date.UTC(
      Number(read.year),
      Number(read.month) - 1,
      Number(read.day),
      // Some engines render midnight as hour 24 under hour12: false.
      Number(read.hour) % 24,
      Number(read.minute),
    );
    return Math.round((asUtc - at.getTime()) / 60000);
  } catch {
    return null;
  }
};

/**
 * The listed zone to start someone in, given the zone they are actually in.
 *
 * @param {string|undefined} zone The zone to honour, or approximate.
 * @param {Date} [at] The instant offsets are compared at.
 * @returns {string} A key of the curated list, or "" when none fits.
 */
export const supportedTimezone = (zone, at = new Date()) => {
  if (!zone) return "";
  // `hasOwn`, so a name like "constructor" is not mistaken for a zone.
  if (Object.hasOwn(timezones, zone)) return zone;

  const wanted = offsetMinutes(zone, at);
  if (wanted === null) return "";

  return OFFERED.find((key) => offsetMinutes(key, at) === wanted) ?? "";
};

/**
 * The listed zone matching wherever this browser thinks it is.
 *
 * @param {Date} [at] The instant offsets are compared at.
 * @returns {string} A key of the curated list, or "" when none fits.
 */
export const browserTimezone = (at = new Date()) => {
  try {
    return supportedTimezone(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      at,
    );
  } catch {
    return "";
  }
};
