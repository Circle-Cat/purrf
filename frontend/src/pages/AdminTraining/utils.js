/**
 * Copy and derivation for the course list. Both come straight from
 * `TrainingCourseLiveState` and `StagedPackageDto`
 * (backend/dto/training_course_dto.py) so the label a course wears and the
 * rule that grays out its Assign/Publish buttons never disagree.
 */

const LIVE_STATE_LABELS = {
  live: "Live",
  no_package: "No package",
  external_link: "External link",
};

/** The Status column's label for a `TrainingCourseLiveState` value. */
export const liveStateLabel = (liveState) =>
  LIVE_STATE_LABELS[liveState] ?? liveState;

/**
 * Why Assign cannot be clicked, or null when it can.
 * @param {{liveState: string, isActive: boolean}} course
 * @returns {string|null}
 */
export const assignBlockedReason = (course) => {
  if (course.liveState !== "live") {
    return "Publish a package to this course first";
  }
  if (!course.isActive) {
    return "This course is deactivated. Turn it back on to assign it.";
  }
  return null;
};

/**
 * Whether a course can be assigned. The API enforces this independently
 * (409 for anything else) -- this only decides what the button looks like.
 * @param {{liveState: string, isActive: boolean}} course
 */
export const canAssign = (course) => assignBlockedReason(course) === null;

/**
 * Why the staged package cannot be published yet, or null when it can.
 * @param {{staged: ?{verifiedCompletableAt: ?string}}} course
 * @returns {string|null}
 */
export const publishBlockedReason = (course) => {
  if (!course.staged) return "There is nothing staged to publish";
  if (!course.staged.verifiedCompletableAt) {
    return "Run this package to completion first";
  }
  return null;
};
