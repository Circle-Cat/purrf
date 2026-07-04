import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/** List every posting regardless of status (internal view). */
export const listJobs = () => request.get(API_ENDPOINTS.RECRUITING_JOBS);

/** Fetch one posting by id. */
export const getJob = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB(jobId));

/** Create a DRAFT posting. body: {title, description, kind, pipelineConfig, formSchema}. */
export const createJob = (body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOBS, body);

/** Update a posting's editable fields. */
export const updateJob = (jobId, body) =>
  request.put(API_ENDPOINTS.RECRUITING_JOB(jobId), body);

/** Close a draft posting directly (no review required). */
export const closeJob = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_CLOSE(jobId));

/** Request close of a published posting via review. body: {reviewerId, message}. */
export const requestClose = (jobId, body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_REQUEST_CLOSE(jobId), body);

/** Request reopen of a closed posting via review. body: {reviewerId, message}. */
export const requestReopen = (jobId, body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_REQUEST_REOPEN(jobId), body);

/** Delete a posting (only for never-published closed postings). */
export const deleteJob = (jobId) =>
  request.delete(API_ENDPOINTS.RECRUITING_JOB(jobId));

/** List active users who may approve postings. */
export const listApprovers = () =>
  request.get(API_ENDPOINTS.RECRUITING_APPROVERS);

/** Submit a posting for review. body: {reviewerId, message}. */
export const submitForReview = (jobId, body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_SUBMIT(jobId), body);

/** List the current reviewer's pending reviews. */
export const listMyReviews = () =>
  request.get(API_ENDPOINTS.RECRUITING_REVIEWS);

/** Approve or reject a review. body: {decision: "approve"|"reject", comment}. */
export const decideReview = (reviewId, body) =>
  request.patch(API_ENDPOINTS.RECRUITING_REVIEW(reviewId), body);

/** List active users assignable as interview evaluators (ApproverDto[]). */
export const listInterviewPool = () =>
  request.get(API_ENDPOINTS.RECRUITING_INTERVIEW_POOL);

/** List active users eligible to own a posting (ApproverDto[]). */
export const listJobOwners = () =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_OWNERS);

/** Fetch a public job posting (candidate view). */
export const getPublicJob = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_PUBLIC_JOB(jobId));

/** List published jobs as candidate-safe card summaries. */
export const listPublicJobs = () =>
  request.get(API_ENDPOINTS.RECRUITING_PUBLIC_JOBS);

/** Upload a resume file. Returns resume metadata. */
export const uploadResume = (file) => {
  const form = new FormData();
  form.append("file", file);
  return request.post(API_ENDPOINTS.RECRUITING_RESUMES, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

/** Submit a candidate application. body: {jobId, ...}. */
export const submitApplication = (body) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATIONS, body);

/** Update a candidate application. */
export const updateApplication = (applicationId, body) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION(applicationId), body);

/** Fetch the current user's application for a specific job. */
export const getMyApplication = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATIONS_MINE, {
    params: { job_id: jobId },
  });

/**
 * List all jobs accessible to the current recruiter on the board (job switcher).
 */
export const listBoardJobs = () =>
  request.get(API_ENDPOINTS.RECRUITING_BOARD_JOBS);

/**
 * Fetch a job's board with all applications grouped by stage/sub-status.
 */
export const getJobBoard = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_BOARD(jobId));

/**
 * Fetch detailed application information for the application detail view.
 */
export const getApplicationDetail = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION(id));

/**
 * Change an application's stage (e.g., "screening" → "hired", "rejected", etc.).
 * body: { toStage: "hired" | "rejected" | ..., reason?: string, note?: string }
 */
export const changeApplicationStage = (id, body) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_STAGE(id), body);

/**
 * Set an application's sub-status (e.g., "pending", "in_progress", etc.).
 * Wraps subStatus in the request body automatically.
 */
export const setApplicationSubStatus = (id, subStatus) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_SUB_STATUS(id), {
    subStatus,
  });

/**
 * Advance an application to a specific round within its current stage.
 * Wraps round and assigneeId in the request body automatically.
 */
export const setApplicationRound = (id, round, assigneeId) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_ROUND(id), {
    round,
    assigneeId,
  });

/**
 * Add a user to the recruiting blacklist.
 * body: { userId, reason? }
 */
export const blacklistUser = (body) =>
  request.post(API_ENDPOINTS.RECRUITING_BLACKLIST, body);

/** Reassign the interviewer responsible for an application's current stage. */
export const reassignApplication = (id, assigneeId) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_ASSIGNMENT(id), {
    assigneeId,
  });

/**
 * List every currently-blocked user, optionally filtered by a name/email/
 * reason substring.
 */
export const listBlacklist = (search) =>
  request.get(API_ENDPOINTS.RECRUITING_BLACKLIST, { params: { search } });

/** Clear a user's block state. */
export const unblockUser = (userId) =>
  request.delete(API_ENDPOINTS.RECRUITING_BLACKLIST_UNBLOCK(userId));

/**
 * Build the full URL to a candidate's resume PDF.
 * Used to construct href for direct file download links.
 * Mirrors the base URL logic from request.js to ensure consistency.
 */
export const resumeUrl = (id) => {
  const baseURL = import.meta.env.PROD
    ? import.meta.env.VITE_API_BASE_URL + "/api"
    : "/api";
  return baseURL + API_ENDPOINTS.RECRUITING_APPLICATION_RESUME(id);
};

/** List the current user's assigned evaluations (EvaluationSummaryDto[]). */
export const listMyEvaluations = () =>
  request.get(API_ENDPOINTS.RECRUITING_EVALUATIONS_MINE);

/** body: { responses: object, confirm: boolean } */
export const submitEvaluation = (id, body) =>
  request.put(API_ENDPOINTS.RECRUITING_APPLICATION_EVALUATION(id), body);

/** List every evaluation row for an application (owner or current-stage assignee). */
export const getEvaluationsForApplication = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_EVALUATIONS(id));

/** List an application's owner-facing audit timeline (ApplicationActivityDto[]), newest first. */
export const getApplicationActivity = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_ACTIVITY(id));
