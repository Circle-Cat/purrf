import { matchPath } from "react-router-dom";
import { hasAutoStarted } from "@/guides/session";

/**
 * The progress key "Take the tour" writes (as completed) when a replay
 * starts. Its `updatedAt`, set by the server on every write, is the time of
 * the last replay: any `page-*` or `task-*` row older than it counts as never
 * seen, so page intros and tasks show again. No backend support is needed.
 */
export const RESET_KEY = "tour-reset";

const RESETTABLE_KEY = /^(page|task)-/;

/**
 * Whether a progress key is one a replay resets.
 *
 * @param {string} key
 * @returns {boolean}
 */
export const isResettableKey = (key) => RESETTABLE_KEY.test(key);

/**
 * The progress key a task segment's page intro is stored under.
 *
 * @param {{key: string}} segment
 * @returns {string}
 */
export const pageKey = (segment) => `page-${segment.key}`;

/**
 * Indexes the progress rows by key, leaving out the `page-*` and `task-*`
 * rows written before the last replay (see RESET_KEY).
 *
 * @param {Array<{guideKey: string, status: string, updatedAt?: string}>} rows
 * @returns {Map<string, Object>}
 */
export const indexProgress = (rows) => {
  const reset = rows.find((row) => row.guideKey === RESET_KEY);
  const resetAt = reset ? Date.parse(reset.updatedAt) : NaN;
  const byKey = new Map();
  for (const row of rows) {
    if (isResettableKey(row.guideKey) && Date.parse(row.updatedAt) < resetAt) {
      continue;
    }
    byKey.set(row.guideKey, row);
  }
  return byKey;
};

/**
 * Whether a row means the viewer is done with that guide.
 *
 * @param {{status: string} | undefined} row
 * @returns {boolean}
 */
export const isSeen = (row) =>
  row?.status === "completed" || row?.status === "dismissed";

/**
 * The tasks whose audience includes the viewer, highest priority first.
 *
 * @param {Array<Object>} guides - Every guide definition.
 * @param {Object} viewer - `{ permissions, flags, mentorshipRoles }`.
 * @returns {Array<Object>}
 */
export const qualifyingTasks = (guides, viewer) =>
  guides
    .filter((guide) => guide.type === "task" && guide.audience(viewer))
    .sort((a, b) => b.priority - a.priority);

/**
 * What may start on its own at `location`, in the order to try: first the
 * single-page guides (by priority), then the page intros taken from the
 * segments of the tasks the viewer qualifies for.
 *
 * A single-page guide qualifies when its trigger is "first-visit", its
 * audience includes the viewer, it has no row or a snoozed one, any
 * `requires.seen` guide is completed or dismissed, `trigger.skipIf` does not
 * reject the location, any `route` matches, and it has not started on its own
 * this session. A page intro qualifies when its segment's route matches, its
 * `page-*` row is absent or snoozed, its task is not completed (walking a task
 * counts as seeing its pages) and it has not started this session.
 *
 * @param {Array<Object>} guides - Every guide definition.
 * @param {Map<string, Object>} progress - From `indexProgress`.
 * @param {Object} viewer - `{ permissions, flags, mentorshipRoles }`.
 * @param {{pathname: string}} location - Where the viewer is.
 * @returns {Array<{guide: Object, segment?: Object}>} A page intro carries
 *   the segment it shows.
 */
export const autoStartCandidates = (guides, progress, viewer, location) => {
  const unseen = (key) =>
    !progress.has(key) || progress.get(key).status === "snoozed";

  const singles = guides
    .filter(
      (guide) =>
        guide.type === "tour" &&
        guide.trigger?.kind === "first-visit" &&
        !hasAutoStarted(guide.key) &&
        unseen(guide.key) &&
        (!guide.requires?.seen || isSeen(progress.get(guide.requires.seen))) &&
        !guide.trigger.skipIf?.(location) &&
        (!guide.route || matchPath(guide.route, location.pathname)) &&
        guide.audience(viewer),
    )
    .sort((a, b) => b.priority - a.priority)
    .map((guide) => ({ guide }));

  const intros = qualifyingTasks(guides, viewer)
    .filter((task) => progress.get(task.key)?.status !== "completed")
    .flatMap((task) =>
      task.segments
        .filter(
          (segment) =>
            matchPath(segment.route, location.pathname) &&
            !hasAutoStarted(pageKey(segment)) &&
            unseen(pageKey(segment)),
        )
        .map((segment) => ({ guide: task, segment })),
    );

  return [...singles, ...intros];
};
