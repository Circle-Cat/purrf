import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  listJobs,
  getJob,
  createJob,
  updateJob,
  closeJob,
  reopenJob,
  listApprovers,
  submitForReview,
  listMyReviews,
  decideReview,
} from "@/api/recruitingApi";

vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
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

  it("reopenJob POSTs the reopen endpoint", async () => {
    request.post.mockResolvedValue({ data: {} });
    await reopenJob(7);
    expect(request.post).toHaveBeenCalledWith("/recruiting/jobs/7/reopen");
  });

  it("listApprovers GETs /recruiting/approvers", async () => {
    request.get.mockResolvedValue({ data: [] });
    await listApprovers();
    expect(request.get).toHaveBeenCalledWith("/recruiting/approvers");
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
});
