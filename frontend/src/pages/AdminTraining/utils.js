/**
 * Copy and derivation for the course list. Both come straight from
 * `TrainingCourseState` (backend/dto/training_course_dto.py) so the label a
 * course wears and the rule that grays out its Assign button never disagree.
 */

const STATE_LABELS = {
  verified: "Verified",
  needs_trial_run: "Needs trial run",
  no_package: "No package",
  external_link: "External link",
};

/** The Status column's label for a `TrainingCourseState` value. */
export const statusLabel = (state) => STATE_LABELS[state] ?? state;

/**
 * Why Assign cannot be clicked, or null when it can. Both halves of the
 * backend gate, and one sentence each: a course nobody has run and a course
 * that has been turned off need different things done to them, so they
 * cannot share a reason.
 * @param {{state: string, isActive: boolean}} course
 * @returns {string|null}
 */
export const assignBlockedReason = (course) => {
  if (course.state !== "verified") return "Run this course to completion first";
  if (!course.isActive) {
    return "This course is deactivated. Turn it back on to assign it.";
  }
  return null;
};

/**
 * Whether a course can be assigned. The API enforces this independently
 * (409 for anything else) -- this only decides what the button looks like.
 * @param {{state: string, isActive: boolean}} course
 */
export const canAssign = (course) => assignBlockedReason(course) === null;
