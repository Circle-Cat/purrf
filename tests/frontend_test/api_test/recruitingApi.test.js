import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  listJobs,
  getJob,
  createJob,
  updateJob,
  closeJob,
  requestClose,
  requestReopen,
  deleteJob,
  listApprovers,
  listInterviewPool,
  listJobOwners,
  submitForReview,
  listMyReviews,
  decideReview,
  getPublicJob,
  uploadResume,
  submitApplication,
  updateApplication,
  getMyApplication,
  listPublicJobs,
  listBoardJobs,
  getJobBoard,
  getApplicationDetail,
  changeApplicationStage,
  setApplicationRound,
  setApplicationSubStatus,
  blacklistUser,
  reassignApplication,
  resumeUrl,
} from "@/api/recruitingApi";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("recruitingApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listJobs GETs /recruiting/jobs", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listJobs();
    expect(request.get).toHaveBeenCalledWith("/recruiting/jobs");
  });

  it("getJob GETs the single job", async () => {
    request.get.mockResolvedValue({ data: {} });
    await getJob(5);
    expect(request.get).toHaveBeenCalledWith("/recruiting/jobs/5");
  });

  it("createJob POSTs the body", async () => {
    request.post.mockResolvedValue({ data: {} });
    const body = { title: "X", kind: "activity" };
    await createJob(body);
    expect(request.post).toHaveBeenCalledWith("/recruiting/jobs", body);
  });

  it("updateJob PUTs to the single job", async () => {
    request.put.mockResolvedValue({ data: {} });
    const body = { title: "Y" };
    await updateJob(7, body);
    expect(request.put).toHaveBeenCalledWith("/recruiting/jobs/7", body);
  });

  it("closeJob POSTs the close endpoint", async () => {
    request.post.mockResolvedValue({ data: {} });
    await closeJob(7);
    expect(request.post).toHaveBeenCalledWith("/recruiting/jobs/7/close");
  });

  it("requestClose POSTs the request-close endpoint with body", async () => {
    request.post.mockResolvedValue({ data: {} });
    await requestClose(7, { reviewerId: 2, message: "please close" });
    expect(request.post).toHaveBeenCalledWith(
      "/recruiting/jobs/7/request-close",
      { reviewerId: 2, message: "please close" },
    );
  });

  it("requestReopen POSTs the request-reopen endpoint with body", async () => {
    request.post.mockResolvedValue({ data: {} });
    await requestReopen(7, { reviewerId: 3, message: "reopen please" });
    expect(request.post).toHaveBeenCalledWith(
      "/recruiting/jobs/7/request-reopen",
      { reviewerId: 3, message: "reopen please" },
    );
  });

  it("deleteJob DELETEs /recruiting/jobs/{id}", async () => {
    request.delete.mockResolvedValue({ data: {} });
    await deleteJob(7);
    expect(request.delete).toHaveBeenCalledWith("/recruiting/jobs/7");
  });

  it("listApprovers GETs /recruiting/approvers", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listApprovers();
    expect(request.get).toHaveBeenCalledWith("/recruiting/approvers");
  });

  it("listInterviewPool GETs the interview-pool endpoint", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listInterviewPool();
    expect(request.get).toHaveBeenCalledWith("/recruiting/interview-pool");
  });

  it("listJobOwners GETs the job-owners endpoint", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listJobOwners();
    expect(request.get).toHaveBeenCalledWith("/recruiting/job-owners");
  });

  it("submitForReview POSTs reviewer + message", async () => {
    request.post.mockResolvedValue({ data: {} });
    await submitForReview(7, { reviewerId: 2, message: "hi" });
    expect(request.post).toHaveBeenCalledWith("/recruiting/jobs/7/submit", {
      reviewerId: 2,
      message: "hi",
    });
  });

  it("listMyReviews GETs /recruiting/reviews", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listMyReviews();
    expect(request.get).toHaveBeenCalledWith("/recruiting/reviews");
  });

  it("decideReview PATCHes decision + comment", async () => {
    request.patch.mockResolvedValue({ data: {} });
    await decideReview(9, { decision: "reject", comment: "no" });
    expect(request.patch).toHaveBeenCalledWith("/recruiting/reviews/9", {
      decision: "reject",
      comment: "no",
    });
  });

  it("getPublicJob GETs the public job endpoint", async () => {
    request.get.mockResolvedValue({});
    await getPublicJob(5);
    expect(request.get).toHaveBeenCalledWith("/recruiting/public/jobs/5");
  });

  it("submitApplication POSTs to /recruiting/applications", async () => {
    request.post.mockResolvedValue({});
    await submitApplication({ jobId: 5 });
    expect(request.post).toHaveBeenCalledWith("/recruiting/applications", {
      jobId: 5,
    });
  });

  it("updateApplication PATCHes the application endpoint", async () => {
    request.patch.mockResolvedValue({});
    await updateApplication(7, { answers: {} });
    expect(request.patch).toHaveBeenCalledWith("/recruiting/applications/7", {
      answers: {},
    });
  });

  it("uploadResume POSTs multipart form data", async () => {
    request.post.mockResolvedValue({});
    const file = new File(["x"], "cv.pdf", { type: "application/pdf" });
    await uploadResume(file);
    const [url, body, config] = request.post.mock.calls.at(-1);
    expect(url).toBe("/recruiting/resumes");
    expect(body).toBeInstanceOf(FormData);
    expect(config).toMatchObject({
      headers: { "Content-Type": "multipart/form-data" },
    });
  });

  it("getMyApplication GETs with job_id param", async () => {
    request.get.mockResolvedValue({});
    await getMyApplication(5);
    expect(request.get).toHaveBeenCalledWith("/recruiting/applications/mine", {
      params: { job_id: 5 },
    });
  });

  it("listPublicJobs GETs the public jobs endpoint", async () => {
    request.get.mockResolvedValue({});
    await listPublicJobs();
    expect(request.get).toHaveBeenCalledWith("/recruiting/public/jobs");
  });

  it("listBoardJobs GETs /recruiting/board/jobs", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listBoardJobs();
    expect(request.get).toHaveBeenCalledWith("/recruiting/board/jobs");
  });

  it("getJobBoard GETs the job board endpoint", async () => {
    request.get.mockResolvedValue({ data: {} });
    await getJobBoard(5);
    expect(request.get).toHaveBeenCalledWith("/recruiting/jobs/5/board");
  });

  it("getApplicationDetail GETs the application endpoint", async () => {
    request.get.mockResolvedValue({ data: {} });
    await getApplicationDetail(7);
    expect(request.get).toHaveBeenCalledWith("/recruiting/applications/7");
  });

  it("changeApplicationStage PATCHes the stage endpoint with body", async () => {
    request.patch.mockResolvedValue({ data: {} });
    await changeApplicationStage(7, { toStage: "hired" });
    expect(request.patch).toHaveBeenCalledWith(
      "/recruiting/applications/7/stage",
      { toStage: "hired" },
    );
  });

  it("setApplicationSubStatus PATCHes the sub-status endpoint with subStatus", async () => {
    request.patch.mockResolvedValue({ data: {} });
    await setApplicationSubStatus(7, "in_progress");
    expect(request.patch).toHaveBeenCalledWith(
      "/recruiting/applications/7/sub-status",
      { subStatus: "in_progress" },
    );
  });

  it("setApplicationRound PATCHes the round endpoint with round", async () => {
    request.patch.mockResolvedValue({ data: {} });
    await setApplicationRound(7, 2);
    expect(request.patch).toHaveBeenCalledWith(
      "/recruiting/applications/7/round",
      { round: 2 },
    );
  });

  it("blacklistUser POSTs to /recruiting/blacklist with body", async () => {
    request.post.mockResolvedValue({ data: {} });
    await blacklistUser({ userId: 42, reason: "spam" });
    expect(request.post).toHaveBeenCalledWith("/recruiting/blacklist", {
      userId: 42,
      reason: "spam",
    });
  });

  it("reassigns an application's interviewer", async () => {
    request.patch.mockResolvedValueOnce({ data: {} });
    await reassignApplication(9, 42);
    expect(request.patch).toHaveBeenCalledWith(
      "/recruiting/applications/9/assignment",
      { assigneeId: 42 },
    );
  });

  it("resumeUrl returns correctly formatted URL", () => {
    const url = resumeUrl(7);
    // In test (dev-mode), baseURL is "/api", so full URL should be exact
    expect(url).toBe("/api/recruiting/applications/7/resume");
  });
});
