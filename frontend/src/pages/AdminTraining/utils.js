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

/**
 * The Status column's label for a course.
 *
 * A deactivated course never wears its package's label: turning it off shuts
 * it to everybody already on it, part-way through included, so "Live" on one
 * is not a confusing label but a false one. Derived here beside
 * `assignBlockedReason` because both read `isActive` -- the badge a course
 * wears and the rule that greys out its buttons cannot be allowed to disagree.
 * @param {{liveState: string, isActive: boolean}} course
 * @returns {string}
 */
export const courseStateLabel = ({ liveState, isActive }) =>
  isActive ? (LIVE_STATE_LABELS[liveState] ?? liveState) : "Off";

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

/** The Target course value that means "do not scope the search to a course". */
export const ALL_COURSES = "";

const COURSE_STATUS_LABELS = {
  to_do: "To do",
  in_progress: "In progress",
  done: "Done",
};

/**
 * A person's status on the course in scope. A row with no training row for
 * that course reads "Not assigned" -- the absence is the answer.
 * @param {?string} status a `TrainingStatus` value, or null.
 * @returns {string}
 */
export const courseStatusLabel = (status) =>
  status ? (COURSE_STATUS_LABELS[status] ?? status) : "Not assigned";

/**
 * What a person holds overall, for the column that replaces the course
 * status when no course is in scope. Only rows that exist are counted; the
 * catalogue is never padded with courses nobody assigned.
 * @param {{assignedCourseCount: ?number, doneCourseCount: ?number}} row
 * @returns {string}
 */
export const coursesHeldLabel = ({ assignedCourseCount, doneCourseCount }) => {
  const held = assignedCourseCount ?? 0;
  if (held === 0) return "No courses";
  const noun = held === 1 ? "course" : "courses";
  return `${held} ${noun} \u00b7 ${doneCourseCount ?? 0} done`;
};

/**
 * Which people the course-status facet should start on once a course is
 * picked. Topping up is the main use of an assignable course, so it starts on
 * the people missing it; a course that cannot be assigned is only ever being
 * inspected, so it starts on the people already on it. Defaulting always to
 * "not assigned" would walk the operator into a full result set behind a
 * greyed-out button.
 * @param {?{liveState: string, isActive: boolean}} course
 * @returns {string} a `courseStatus` facet value.
 */
export const defaultCourseStatusFor = (course) => {
  if (!course) return "";
  return canAssign(course) ? "not_assigned" : "assigned";
};

/**
 * Why the bulk Assign button cannot be clicked, or null when it can. Not
 * having named a course is the first reason: the card searches without one.
 * @param {?{liveState: string, isActive: boolean}} course
 * @returns {string|null}
 */
export const bulkAssignBlockedReason = (course) => {
  if (!course) return "Pick a course to assign";
  return assignBlockedReason(course);
};

/**
 * Time spent in a course, from the seconds the runtime reported.
 *
 * An em dash for an assignment nobody has opened -- there is no progress row
 * to have a number in. Zero is not that: it is a course that was opened and
 * closed, and reads as 0s.
 * @param {?number} seconds
 * @returns {string}
 */
export const timeSpentLabel = (seconds) => {
  if (seconds === null || seconds === undefined) return "\u2014";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }
  const hours = Math.floor(seconds / 3600);
  return `${hours}h ${Math.floor((seconds % 3600) / 60)}m`;
};
