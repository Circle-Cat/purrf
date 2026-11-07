// Lives at module level, outside React, so a remounted GuideProvider (for
// example after an auth refresh) still knows what already ran. A page reload
// starts a new session.
const autoStarted = new Set();
let blockedPath = null;

/**
 * Whether a guide (or a page intro, by its `page-*` key) has already started
 * on its own in this browser session.
 *
 * @param {string} key - The progress key.
 * @returns {boolean}
 */
export const hasAutoStarted = (key) => autoStarted.has(key);

/**
 * Records that a guide started on its own, so it does not start on its own
 * again this session.
 *
 * @param {string} key - The progress key.
 */
export const markAutoStarted = (key) => {
  autoStarted.add(key);
};

/**
 * Forgets the auto-starts whose key passes `predicate`, so they may start
 * again this session.
 *
 * @param {(key: string) => boolean} predicate
 */
export const forgetAutoStarts = (predicate) => {
  for (const key of [...autoStarted]) {
    if (predicate(key)) autoStarted.delete(key);
  }
};

/**
 * Keeps guides from starting on their own at `path` until the viewer is on
 * another page, so one guide never follows another on the same page.
 *
 * @param {string} path - The pathname a guide just ended on.
 */
export const blockAutoStartOn = (path) => {
  blockedPath = path;
};

/**
 * Called on every page change: lifts the block once the viewer has left the
 * page it was set on.
 *
 * @param {string} path - The pathname now shown.
 */
export const noteVisitedPath = (path) => {
  if (blockedPath !== path) blockedPath = null;
};

/**
 * Whether guides may not start on their own at `path` right now.
 *
 * @param {string} path
 * @returns {boolean}
 */
export const isAutoStartBlocked = (path) => blockedPath === path;

/**
 * Forgets everything above, as a page reload would. Used by tests.
 */
export const resetGuideSession = () => {
  autoStarted.clear();
  blockedPath = null;
};
