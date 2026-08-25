/**
 * The data gaps the nightly sync records about somebody it still pays.
 *
 * A different class from the exclusion lists. Somebody excluded is not being
 * paid at all and shows up in the run's own report; these people are paid every
 * week and are broken anyway, which is why nothing else mentions them.
 *
 * `missing_hire_date` is deliberately absent: those people are excluded from
 * the run, so they never appear on a row here and the exclusion list already
 * names them. Listing it in both places would report them twice.
 */
export const PROFILE_PROBLEMS = [
  {
    key: "missing_manager",
    label: "No manager in Azure",
    consequence:
      "Accruing normally, but cannot file a single request — filing fails with a hard error.",
  },
  {
    key: "unparseable_job_title",
    label: "Job title carries no level",
    consequence:
      "Accruing zero hours a year. Indistinguishable from an L1 by the figure alone.",
  },
];

/**
 * Groups people by the problems recorded against them.
 *
 * Presentation only: the rows already carry their own problems, and this
 * gathers them so a reader can see all of one kind at once. Nothing is
 * recomputed.
 *
 * @param {Array<object>} people - Rows from the overview.
 * @returns {Record<string, Array<object>>} People by problem key.
 */
export const byProblem = (people) => {
  const grouped = {};
  for (const person of people) {
    for (const problem of person.problems ?? []) {
      grouped[problem] = grouped[problem] ?? [];
      grouped[problem].push(person);
    }
  }
  return grouped;
};

/**
 * Groups the people sitting below zero by their level.
 *
 * Never one list. An L1 has no annual entitlement and may still take paid
 * leave, so a long-running negative balance is the expected state for them --
 * and in one list they would fill the screen and bury everybody whose negative
 * balance is a genuine surprise.
 *
 * @param {Array<object>} people - Rows from the overview.
 * @returns {Array<{level: string, people: Array<object>}>} Sorted by level.
 */
export const negativeByLevel = (people) => {
  const grouped = new Map();
  for (const person of people) {
    if (Number(person.balanceHours) >= 0) continue;
    const level = person.level ?? "No level";
    grouped.set(level, [...(grouped.get(level) ?? []), person]);
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([level, group]) => ({ level, people: group }));
};
