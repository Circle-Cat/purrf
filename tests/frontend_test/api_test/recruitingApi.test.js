import { describe, it, expect, vi, beforeEach } from "vitest";
vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));
import request from "@/utils/request";
import {
  getJobs,
  getJob,
  createJob,
  updateJob,
  publishJob,
  closeJob,
  submitApplication,
  getBoard,
  viewApplication,
  advanceApplication,
} from "@/api/recruitingApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

describe("recruitingApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("getJobs GETs the jobs endpoint", () => {
    getJobs();
    expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.RECRUITING_JOBS);
  });

  it("getJob GETs a single job by id", () => {
    getJob(5);
    expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.RECRUITING_JOB(5));
  });

  it("createJob POSTs payload to jobs endpoint", () => {
    const p = { title: "x" };
    createJob(p);
    expect(request.post).toHaveBeenCalledWith(API_ENDPOINTS.RECRUITING_JOBS, p);
  });

  it("updateJob PUTs payload to job endpoint", () => {
    const p = { title: "y" };
    updateJob(5, p);
    expect(request.put).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_JOB(5),
      p,
    );
  });

  it("publishJob POSTs to publish path", () => {
    publishJob(7);
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_JOB_PUBLISH(7),
    );
  });

  it("closeJob POSTs to close path", () => {
    closeJob(7);
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_JOB_CLOSE(7),
    );
  });

  it("submitApplication POSTs formAnswers to applications endpoint", () => {
    submitApplication(7, { q: "a" });
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_JOB_APPLICATIONS(7),
      { formAnswers: { q: "a" } },
    );
  });

  it("getBoard GETs the board for a job", () => {
    getBoard(7);
    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_JOB_BOARD(7),
    );
  });

  it("viewApplication POSTs to view endpoint", () => {
    viewApplication(3);
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_APPLICATION_VIEW(3),
    );
  });

  it("advanceApplication POSTs targetStage to advance endpoint", () => {
    advanceApplication(3, "hired");
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.RECRUITING_APPLICATION_ADVANCE(3),
      { targetStage: "hired" },
    );
  });
});
