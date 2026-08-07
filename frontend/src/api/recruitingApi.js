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

/** Fetch a job posting's audit timeline, newest first. */
export const listJobActivity = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_ACTIVITY(jobId));

/** Request close of a published posting via review. body: {reviewerId, message}. */
export const requestClose = (jobId, body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_REQUEST_CLOSE(jobId), body);

/** Request reopen of a closed posting via review. body: {reviewerId, message}. */
export const requestReopen = (jobId, body) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_REQUEST_REOPEN(jobId), body);

/** Discard a posting's staged pending edit without changing its status. */
export const discardPendingEdit = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_DISCARD_PENDING_EDIT(jobId));

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
    // The shared instance allows 10s, which is a request/response round trip
    // budget, not an upload one: a few-megabyte PDF on a slow uplink aborts
    // partway and the candidate is told their résumé failed for no reason
    // they can act on.
    timeout: 120000,
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

/** Fetch every application the current user has ever submitted, any job kind. */
export const listMyApplications = () =>
  request.get(API_ENDPOINTS.RECRUITING_MY_APPLICATIONS);

/**
 * List all jobs accessible to the current recruiter on the board (job switcher).
 */
export const listBoardJobs = () =>
  request.get(API_ENDPOINTS.RECRUITING_BOARD_JOBS);

/**
 * Search applicants by name or email across the caller's boards.
 *
 * @param {string} q Search term; matched as a case-insensitive substring
 *   against the applicant's full name and every one of their email
 *   addresses.
 * @param {{jobId?: number|null, currentJobId?: number|null}} options
 *   `jobId` narrows the search to one posting; null/undefined searches every
 *   posting the caller can open. `currentJobId` only floats the open
 *   posting's hits to the front of the list.
 * @returns {Promise<object>} `{data: {hits, truncated}}`.
 */
export const searchBoardApplicants = (q, { jobId, currentJobId } = {}) =>
  request.get(API_ENDPOINTS.RECRUITING_BOARD_APPLICANTS, {
    params: {
      q,
      ...(jobId == null ? {} : { job_id: jobId }),
      ...(currentJobId == null ? {} : { current_job_id: currentJobId }),
    },
  });

/**
 * Fetch a job's board with all applications grouped by stage/sub-status.
 */
export const getJobBoard = (jobId) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_BOARD(jobId));

/**
 * Fetch one page of a terminal lane's applications (offset/limit).
 */
export const getJobBoardStagePage = (
  jobId,
  { stage, limit = 20, offset = 0 },
) =>
  request.get(API_ENDPOINTS.RECRUITING_JOB_BOARD_STAGE(jobId), {
    params: { stage, limit, offset },
  });

/**
 * Fetch detailed application information for the application detail view.
 */
export const getApplicationDetail = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION(id));

/**
 * Change an application's stage (e.g., "screening" → "hired", "rejected", etc.).
 * body: { toStage: "hired" | "rejected" | ..., reason?: string, note?: string,
 *         cancelInterview?: boolean }
 * `cancelInterview` also cancels the meeting booked on the stage+round being
 * left, which the UI can no longer reach once the application has moved on.
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
 * Wraps round, assigneeId and cancelInterview in the request body
 * automatically. `cancelInterview` also cancels the meeting booked on the
 * round being left (the backend ignores it when that round has no upcoming
 * meeting); leave it undefined to say nothing about meetings at all.
 */
export const setApplicationRound = (id, round, assigneeId, cancelInterview) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_ROUND(id), {
    round,
    assigneeId,
    cancelInterview,
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
 * Book a Calendar meeting for an application's current stage+round.
 * body: { assigneeId, date, startTime, durationMinutes, timezone }
 * (wall-clock terms -- see InterviewScheduleRequestDto on the backend).
 */
export const scheduleInterview = (id, body) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATION_INTERVIEW(id), body);

/**
 * Move an already-booked meeting's time and/or swap its interviewer.
 * Same body shape as scheduleInterview.
 */
export const updateInterview = (id, body) =>
  request.patch(API_ENDPOINTS.RECRUITING_APPLICATION_INTERVIEW(id), body);

/** Cancel an application's current stage+round's booked meeting. */
export const cancelInterview = (id) =>
  request.delete(API_ENDPOINTS.RECRUITING_APPLICATION_INTERVIEW(id));

/**
 * List every currently-blocked user, optionally filtered by a name/email/
 * reason substring.
 */
export const listBlacklist = (search) =>
  request.get(API_ENDPOINTS.RECRUITING_BLACKLIST, { params: { search } });

/**
 * List the interview meetings a blacklist of this user would cancel — every
 * still-upcoming one across all of their applications. Read by the blacklist
 * confirm dialog so the sanction never silently deletes a calendar invite.
 */
export const listBlacklistUpcomingInterviews = (userId) =>
  request.get(API_ENDPOINTS.RECRUITING_BLACKLIST_UPCOMING_INTERVIEWS(userId));

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

/** List every comment on an application (owner or current-stage assignee), newest first. */
export const getApplicationComments = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_COMMENTS(id));

/** body: { body: string } */
export const postComment = (id, body) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATION_COMMENTS(id), body);

export const getApplicationEmails = (id, { refresh = false } = {}) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_EMAILS(id), {
    params: refresh ? { refresh: true } : {},
  });

export const sendApplicationEmail = (id, body) =>
  request.post(API_ENDPOINTS.RECRUITING_APPLICATION_EMAILS(id), body);

/** Preset compose templates, already rendered for this application. */
export const getApplicationEmailTemplates = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_EMAIL_TEMPLATES(id));

/** Everyone who can currently be @-mentioned on this application. */
export const getMentionableUsers = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_MENTIONABLE_USERS(id));

/** List a candidate's other applications (OtherApplicationDto[]), for the cross-posting aggregation view. */
export const getOtherApplications = (id) =>
  request.get(API_ENDPOINTS.RECRUITING_APPLICATION_OTHER_APPLICATIONS(id));

/**
 * Fetch the cross-posting recruiting audit overview: open positions,
 * every job (for the selector), and the stage/daily-trend breakdown for
 * the given date range and job selection.
 *
 * @param {{startDate: string, endDate: string, jobIds?: number[]}} params
 *   `startDate`/`endDate` are "yyyy-MM-dd"; `jobIds` omitted/empty means
 *   every job.
 */
export const getAuditOverview = ({ startDate, endDate, jobIds = [] }) =>
  request.get(API_ENDPOINTS.RECRUITING_AUDIT_OVERVIEW, {
    params: { startDate, endDate, jobIds },
  });

/** List the current user's notifications (newest first) + unreadCount. */
export const listNotifications = () =>
  request.get(API_ENDPOINTS.RECRUITING_NOTIFICATIONS);

/** Dismiss (delete) one notification. Returns { unreadCount }. */
export const dismissNotification = (id) =>
  request.delete(API_ENDPOINTS.RECRUITING_NOTIFICATION(id));

/** Dismiss (delete) every notification. Returns { unreadCount }. */
export const dismissAllNotifications = () =>
  request.delete(API_ENDPOINTS.RECRUITING_NOTIFICATIONS);
