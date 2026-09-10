import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Mint a content session for the caller's own training assignment.
 * @param {string|number} trainingId
 * @returns {Promise<{data: {contentBaseUrl: string, sessionToken: string, entryPath: string, playerPath: string, expiresAt: number, progress?: object}}>}
 */
export const openSession = (trainingId) =>
  request.post(API_ENDPOINTS.TRAINING_SESSION(trainingId));

/**
 * Store one commit reported by the course.
 * @param {string|number} trainingId
 * @param {{cmi: Object<string, string>, sessionToken?: string, final?: boolean}} payload
 *   `sessionToken` is the one `openSession` handed back. It names the run this
 *   commit came from, which is what lets the server refuse a finishing status
 *   reported by a tab left open across a package replacement.
 * @returns {Promise<{data: {status: string, courseVerified?: boolean|null}}>}
 */
export const saveProgress = (trainingId, payload) =>
  request.post(API_ENDPOINTS.TRAINING_PROGRESS(trainingId), payload);

/**
 * Every course in the catalogue, with its state and how many people hold it.
 * @returns {Promise<{data: Array<Object>}>} `TrainingCourseDto` rows.
 */
export const listCourses = () => request.get(API_ENDPOINTS.TRAINING_COURSES);

/**
 * Rename a course, or turn it on or off. Deactivating closes the course to
 * everyone, the people already assigned included; their progress is kept.
 * @param {string|number} courseId
 * @param {{isActive?: boolean, name?: string, description?: string}} payload
 * @returns {Promise<{data: Object}>} the updated `TrainingCourseDto`.
 */
export const updateCourse = (courseId, payload) =>
  request.patch(API_ENDPOINTS.TRAINING_COURSE(courseId), payload);

/**
 * Open a trial assignment on a course under the caller's own identity, so an
 * admin can run it to completion before it is assignable to anyone else.
 * @param {string|number} courseId
 * @returns {Promise<{data: {trainingId: number, userId: number, courseId: number, created: boolean}}>}
 */
export const startTrial = (courseId) =>
  request.post(API_ENDPOINTS.TRAINING_COURSE_TRIAL(courseId));

/**
 * What the course's stored package says it takes to finish it. Re-read from
 * the package, so it survives the upload dialog that showed it once.
 * @param {string|number} courseId
 * @returns {Promise<{data: {completionPercentage: number|null, completesViaStoryline: boolean, completionConfigReadable: boolean}}>}
 */
export const readCompletionConfig = (courseId) =>
  request.get(API_ENDPOINTS.TRAINING_COURSE_PACKAGE(courseId));

/**
 * Upload (or replace) a course's SCORM package. A rejection's message is
 * meant to be forwarded verbatim to whoever exported the course -- callers
 * must not paraphrase it.
 * @param {string|number} courseId
 * @param {File} file
 * @returns {Promise<{data: Object}>} `TrainingPackageUploadResultDto`.
 */
/**
 * Assign a verified course to one person. Repeating an assignment for the
 * same (user, course) pair is a no-op on the backend, not an error --
 * `created` in the result says whether this call was the one that did it.
 * @param {{userId: number, courseId: number, deadline?: string}} payload
 *   `deadline` must be left out entirely when there is none: the request
 *   DTO forbids unknown fields and rejects an empty string for this one.
 * @returns {Promise<{data: {trainingId: number, userId: number, courseId: number, created: boolean}}>}
 */
export const assignCourse = (payload) =>
  request.post(API_ENDPOINTS.TRAINING_ASSIGNMENTS, payload);

/**
 * One page of the people a course may be assigned to. Only active, unblocked
 * accounts are ever returned -- that is a precondition of the search, not a
 * filter, since every row shown can be ticked and assigned.
 * @param {{search?: string, userId?: string|number, userType?: string,
 *   group?: string, mentorshipRole?: string, courseId?: string|number,
 *   courseStatus?: string, limit?: number, offset?: number}} params
 *   `group` only means something alongside `userType: "internal"`; the API
 *   answers 400 otherwise. `courseStatus` needs a `courseId` to be about.
 * @returns {Promise<{data: {rows: Array<Object>, total: number}}>}
 *   `TrainingAudienceRowDto` rows. `courseStatus` on a row is filled only
 *   when a course was named, and the two counts only when none was.
 */
export const searchAudience = ({
  search,
  userId,
  userType,
  group,
  mentorshipRole,
  courseId,
  courseStatus,
  limit,
  offset,
} = {}) =>
  request.get(API_ENDPOINTS.TRAINING_ASSIGNMENTS_AUDIENCE, {
    params: {
      search,
      userId,
      userType,
      group,
      mentorshipRole,
      courseId,
      courseStatus,
      limit,
      offset,
    },
  });

/**
 * Every id the same search matches, for ticking a whole result set at once.
 * Refused with a 409 above 1000 rather than trimmed: assigning a silently
 * truncated cohort cannot be undone.
 * @param {Object} params same facets as `searchAudience`, without paging.
 * @returns {Promise<{data: {userIds: Array<number>, total: number}}>}
 */
export const listAudienceIds = ({
  search,
  userId,
  userType,
  group,
  mentorshipRole,
  courseId,
  courseStatus,
} = {}) =>
  request.get(API_ENDPOINTS.TRAINING_ASSIGNMENTS_AUDIENCE_IDS, {
    params: {
      search,
      userId,
      userType,
      group,
      mentorshipRole,
      courseId,
      courseStatus,
    },
  });

/**
 * Assign one course to a whole cohort, in one transaction: either every row
 * lands or none does. Anybody who already holds the course is counted, not
 * rewritten, so re-running a batch is safe.
 * @param {{courseId: number, userIds: Array<number>, deadline?: string}} payload
 *   `deadline` must be left out entirely when there is none, the way
 *   `assignCourse` requires -- the request DTO forbids unknown fields and
 *   rejects an empty string.
 * @returns {Promise<{data: {courseId: number, createdCount: number,
 *   alreadyAssignedCount: number}}>}
 */
export const assignCourseBulk = (payload) =>
  request.post(API_ENDPOINTS.TRAINING_ASSIGNMENTS_BULK, payload);

/**
 * Publish a course's staged package, moving it into the live slot that
 * learners actually see.
 * @param {string|number} courseId
 * @returns {Promise<{data: Object}>} `TrainingPackagePublishResultDto`.
 */
export const publishPackage = (courseId) =>
  request.post(API_ENDPOINTS.TRAINING_COURSE_PUBLISH(courseId));

/**
 * Drop a course's staged package without publishing it. The live package,
 * if any, is untouched.
 * @param {string|number} courseId
 * @returns {Promise<{data: Object}>}
 */
export const discardPackage = (courseId) =>
  request.delete(API_ENDPOINTS.TRAINING_COURSE_PACKAGE(courseId));

/**
 * Mint a content session against a training's staged package, so an admin
 * can verify it before it is published.
 * @param {string|number} trainingId
 * @returns {Promise<{data: Object}>} same shape as `openSession`.
 */
export const openTrialSession = (trainingId) =>
  request.post(API_ENDPOINTS.TRAINING_TRIAL_SESSION(trainingId));

/**
 * Mint a content session for looking at a course's live package.
 *
 * Keyed by course, not by assignment: there is no run behind a preview, so
 * the token it hands back names no assignment and nothing it reports can be
 * stored.
 *
 * @param {string|number} courseId
 * @returns {Promise<{data: Object}>} same shape as `openSession`, with no
 *   `progress`.
 */
export const openPreviewSession = (courseId) =>
  request.post(API_ENDPOINTS.TRAINING_COURSE_PREVIEW_SESSION(courseId));

export const uploadPackage = (courseId, file, onProgress) => {
  const form = new FormData();
  form.append("file", file);
  return request.post(API_ENDPOINTS.TRAINING_COURSE_PACKAGE(courseId), form, {
    headers: { "Content-Type": "multipart/form-data" },
    // A zip upload is a bigger budget than the shared 10s request timeout.
    timeout: 120000,
    // Only the transfer is measurable, and only when the browser knows the
    // size. Everything the server does afterwards -- unzip, read the
    // manifest, store a couple of hundred files -- is silent, so this stops
    // at 100% rather than standing in for the whole wait.
    onUploadProgress: (event) => {
      if (!event.total) return;
      onProgress?.(Math.round((event.loaded / event.total) * 100));
    },
  });
};
