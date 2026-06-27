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

/** Close a posting. */
export const closeJob = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_CLOSE(jobId));

/** Reopen a CLOSED posting. */
export const reopenJob = (jobId) =>
  request.post(API_ENDPOINTS.RECRUITING_JOB_REOPEN(jobId));

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
