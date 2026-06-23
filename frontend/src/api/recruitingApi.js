import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/**
 * List all published job postings.
 * @returns {Promise} Resolves to an array of job posting objects.
 */
export const getJobs = () => request.get(API_ENDPOINTS.RECRUITING_JOBS);

/**
 * Fetch a single job posting by ID (candidate-facing via direct link).
 * @param {number|string} jobId - The ID of the job posting.
 * @returns {Promise} Resolves to a job posting object.
 */
export const getJob = (jobId) => request.get(API_ENDPOINTS.RECRUITING_JOB(jobId));

/**
 * Create a DRAFT job posting.
 * @param {object} payload - Job details: {title, description, kind, mentorshipRole, formSchema}.
 * @returns {Promise} Resolves to the newly created job posting object.
 */
export const createJob = (payload) =>
  request.post(API_ENDPOINTS.RECRUITING_JOBS, payload);

/**
 * Update an existing job posting (including its form schema).
 * @param {number|string} jobId - The ID of the job posting to update.
 * @param {object} payload - Updated job fields.
 * @returns {Promise} Resolves to the updated job posting object.
 */
export const updateJob = (jobId, payload) =>
  request.put(API_ENDPOINTS.RECRUITING_JOB(jobId), payload);

/**
 * Publish a job posting, making it visible to candidates.
 * @param {number|string} jobId - The ID of the job posting to publish.
 * @returns {Promise} Resolves when the posting is published.
 */
export const publishJob = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_PUBLISH(jobId));

/**
 * Close a job posting, stopping new applications.
 * @param {number|string} jobId - The ID of the job posting to close.
 * @returns {Promise} Resolves when the posting is closed.
 */
export const closeJob = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_CLOSE(jobId));

/**
 * Submit an application as the current candidate.
 * @param {number|string} jobId - The ID of the job posting to apply to.
 * @param {object} formAnswers - Candidate's answers to the job's form schema.
 * @returns {Promise} Resolves to the newly created application object.
 */
export const submitApplication = (jobId, formAnswers) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_APPLICATIONS(jobId), {
    formAnswers,
  });

/**
 * Fetch the screening board (active applications) for a job posting.
 * @param {number|string} jobId - The ID of the job posting.
 * @returns {Promise} Resolves to an array of application objects for screening.
 */
export const getBoard = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_BOARD(jobId));

/**
 * Record the first screener view of an application (locks and snapshots it).
 * @param {number|string} applicationId - The ID of the application to view.
 * @returns {Promise} Resolves when the view is recorded.
 */
export const viewApplication = (applicationId) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATION_VIEW(applicationId));

/**
 * Advance an application to a final decision stage.
 * @param {number|string} applicationId - The ID of the application to advance.
 * @param {string} targetStage - The target stage: "hired" or "rejected".
 * @returns {Promise} Resolves when the application is advanced.
 */
export const advanceApplication = (applicationId, targetStage) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATION_ADVANCE(applicationId), {
    targetStage,
  });
