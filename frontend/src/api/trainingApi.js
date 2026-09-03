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
 * Rename a course, or turn it on or off. Deactivating only stops new
 * assignments -- everyone already assigned keeps their access and progress.
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

export const uploadPackage = (courseId, file) => {
  const form = new FormData();
  form.append("file", file);
  return request.post(API_ENDPOINTS.TRAINING_COURSE_PACKAGE(courseId), form, {
    headers: { "Content-Type": "multipart/form-data" },
    // A zip upload is a bigger budget than the shared 10s request timeout.
    timeout: 120000,
  });
};
