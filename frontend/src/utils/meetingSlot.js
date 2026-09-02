/**
 * The slot fields a meeting form collects, shared between the recruiting
 * interview dialog and the mentorship meeting dialogs.
 *
 * Only pure values live here. The forms themselves are deliberately NOT
 * shared: each domain's dialog owns its own markup and its own
 * derive-on-open effect. That effect exists because Radix unmounts
 * `DialogContent` while the dialog is closed but leaves the component that
 * owns the state mounted, so fields would otherwise carry over from one
 * open to the next.
 */

/**
 * Fallback duration for a fresh booking, and for an existing slot whose
 * length is not one of the offered options. Deliberately a fixed constant so
 * initial state does not vary with the machine running the app.
 */
export const DEFAULT_DURATION_MINUTES = 45;

/** The durations a meeting may be booked for; mirrors the backend's
 * `ALLOWED_DURATION_MINUTES`. */
export const DURATION_OPTIONS = Object.freeze([
  { value: "30", label: "30 minutes" },
  { value: "45", label: "45 minutes" },
  { value: "60", label: "1 hour" },
  { value: "90", label: "1.5 hours" },
]);

/**
 * Recover a booked meeting's duration so an edit form can preselect it.
 *
 * A length that is not one of `DURATION_OPTIONS` -- a legacy row, or a slot
 * booked before the options changed -- falls back to the default rather than
 * being returned as-is, which would leave the Select with no matching item
 * and an empty trigger. A missing or unparsable end yields NaN, and NaN is
 * in no option, so it takes the same path.
 *
 * @param {string} startIso - Slot start, UTC ISO-8601.
 * @param {string} endIso - Slot end, UTC ISO-8601.
 * @returns {number} Minutes, always one of `DURATION_OPTIONS`.
 */
export function durationFromRange(startIso, endIso) {
  const minutes = Math.round(
    (new Date(endIso).getTime() - new Date(startIso).getTime()) / 60000,
  );
  return DURATION_OPTIONS.some((opt) => Number(opt.value) === minutes)
    ? minutes
    : DEFAULT_DURATION_MINUTES;
}
