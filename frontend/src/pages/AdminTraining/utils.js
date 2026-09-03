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
 * Whether a course can be assigned. The API enforces this independently
 * (409 for anything else) -- this only decides what the button looks like.
 * @param {{state: string}} course
 */
export const canAssign = (course) => course.state === "verified";
