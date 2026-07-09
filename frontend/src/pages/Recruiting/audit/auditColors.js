/**
 * Chart-fill color for each `ApplicationStage` value, as a CSS `var()`
 * reference into the tokens defined in `index.css` (`:root`/`.dark`).
 * Extends this codebase's existing `board/stageColors.js` hue families,
 * re-shaded for chart-fill contrast (see the implementation plan's
 * "Color values" section for the validation rationale).
 */
export const STAGE_COLORS = {
  recruiter_screening: "var(--stage-recruiter-screening)",
  behavioral: "var(--stage-behavioral)",
  tech: "var(--stage-tech)",
  board_review: "var(--stage-board-review)",
  offer: "var(--stage-offer)",
  hired: "var(--stage-hired)",
  rejected: "var(--stage-rejected)",
  offer_declined: "var(--stage-offer-declined)",
  blacklisted: "var(--stage-blacklisted)",
};

const CATEGORICAL_SLOTS = [
  "var(--categorical-1)",
  "var(--categorical-2)",
  "var(--categorical-3)",
  "var(--categorical-4)",
  "var(--categorical-5)",
  "var(--categorical-6)",
  "var(--categorical-7)",
  "var(--categorical-8)",
];

/**
 * A job's trend-chart line color, assigned by its position in the full,
 * unfiltered job list (sorted by id) — never by its position within a
 * currently-selected subset, so toggling one job's visibility never
 * repaints another job's color.
 *
 * @param {number} jobId - The job to color.
 * @param {number[]} allJobIds - Every job id from the API's unfiltered
 *   `jobs` list (any order — sorted internally for a stable assignment).
 * @returns {string} A `var(--categorical-N)` CSS reference.
 */
export function categoricalColor(jobId, allJobIds) {
  const sorted = [...allJobIds].sort((a, b) => a - b);
  const index = sorted.indexOf(jobId);
  return CATEGORICAL_SLOTS[index % CATEGORICAL_SLOTS.length];
}
