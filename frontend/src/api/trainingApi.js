import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * Mint a content session for the caller's own training assignment.
 * @param {string|number} trainingId
 * @returns {Promise<{data: {contentBaseUrl: string, entryPath: string, playerPath: string, expiresAt: number, progress?: object}}>}
 */
export const openSession = (trainingId) =>
  request.post(API_ENDPOINTS.TRAINING_SESSION(trainingId));

/**
 * Store one commit reported by the course.
 * @param {string|number} trainingId
 * @param {{cmi: Object<string, string>}} payload
 */
export const saveProgress = (trainingId, payload) =>
  request.post(API_ENDPOINTS.TRAINING_PROGRESS(trainingId), payload);

/**
 * Open a trial assignment on a course under the caller's own identity, so an
 * admin can run it to completion before it is assignable to anyone else.
 * @param {string|number} courseId
 * @returns {Promise<{data: {trainingId: number, userId: number, courseId: number, created: boolean}}>}
 */
export const startTrial = (courseId) =>
  request.post(API_ENDPOINTS.TRAINING_COURSE_TRIAL(courseId));
