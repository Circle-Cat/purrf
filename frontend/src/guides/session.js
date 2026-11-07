// Lives at module level, outside React, so a remounted GuideProvider (for
// example after an auth refresh) still knows a guide already auto-started.
// A page reload starts a new session.
let autoStarted = false;

/**
 * Whether a guide has already started on its own in this browser session.
 *
 * @returns {boolean}
 */
export const hasAutoStarted = () => autoStarted;

/**
 * Records that a guide started on its own, so no other one does this session.
 */
export const markAutoStarted = () => {
  autoStarted = true;
};

/**
 * Forgets the auto-start, as a page reload would. Used by tests.
 */
export const resetGuideSession = () => {
  autoStarted = false;
};
