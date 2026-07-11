import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import PostingDetailPage from "@/pages/Recruiting/PostingDetailPage";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "success").mockImplementation(() => {});

// useAuth() returns { permissions, user: {userId, ...} } (see AuthContext.js).
// A hoisted mutable holder lets each test flip who's viewing before render,
// mirroring ApplicationDetailPage.test.jsx's established convention.
const authState = vi.hoisted(() => ({ userId: 5, permissions: [] }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { userId: authState.userId },
    permissions: authState.permissions,
  }),
}));

const renderAt = (jobId) => {
  const router = createMemoryRouter(
    [{ path: "/recruiting/postings/:id", element: <PostingDetailPage /> }],
    { initialEntries: [`/recruiting/postings/${jobId}`] },
  );
  return render(<RouterProvider router={router} />);
};

describe("PostingDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.userId = 5;
    authState.permissions = [];
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "draft",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    api.listApprovers.mockResolvedValue({ data: [] });
    api.listJobOwners.mockResolvedValue({ data: [] });
    api.listInterviewPool.mockResolvedValue({ data: [] });
    api.listJobActivity.mockResolvedValue({ data: [] });
    api.listMyReviews.mockResolvedValue({ data: [] });
  });

  it("shows the Operate block for a canWrite viewer", async () => {
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Submit for review" }),
    ).toBeInTheDocument();
  });

  it("shows Edit in the Operate row for a draft posting", async () => {
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument(),
    );
  });

  it("hides Edit while a revision is pending re-review", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "published_pending_revision",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });

  it("renders the applicant-facing question form on Overview", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        reviewerId: null,
        formSchema: {
          questions: [{ id: "q1", type: "short_text", label: "Why us?" }],
        },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Why us?")).toBeInTheDocument(),
    );
  });

  it("hides the Operate block for a read-only viewer", async () => {
    authState.permissions = ["recruiting.job.read"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Submit for review" }),
    ).not.toBeInTheDocument();
  });

  it("shows the status badge alongside a Sent back badge with the reject kind in the popover", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: "Please tighten the screening rules.",
        lastRejectKind: "initial",
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() => expect(screen.getByText("Draft")).toBeInTheDocument());
    expect(
      screen.getByRole("button", { name: "Sent back" }),
    ).toBeInTheDocument();
  });

  it("shows Approve/Reject only for the assigned reviewer", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        status: "pending_review",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        reviewerId: 9,
      },
    });
    api.listMyReviews.mockResolvedValue({
      data: [
        {
          reviewId: 3,
          jobId: 1,
          jobTitle: "Backend Engineer",
          kind: "initial",
        },
      ],
    });
    authState.userId = 9;
    authState.permissions = ["recruiting.job.approve"];

    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Approve" }),
      ).toBeInTheDocument(),
    );
  });

  it("does not show Approve/Reject for a canApprove viewer who isn't the assigned reviewer", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        status: "pending_review",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        reviewerId: 9,
      },
    });
    api.listMyReviews.mockResolvedValue({ data: [] });
    authState.userId = 42;
    authState.permissions = ["recruiting.job.approve"];

    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();
  });

  it("opens the reviewer-picker dialog directly when Request close is clicked, no intermediate confirm dialog", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    api.listApprovers.mockResolvedValue({ data: [{ userId: 9, name: "Bob" }] });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Request close" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Request close" }));

    expect(
      screen.queryByText("Request to close this posting?"),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Request close" }),
      ).toBeInTheDocument(),
    );
  });

  it("formats the review history timeline into readable copy, not raw event types", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    api.listApprovers.mockResolvedValue({
      data: [{ userId: 9, name: "Yanpei Wang" }],
    });
    api.listJobActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "job_created",
          details: {},
          actorId: 3,
          actorName: "Yuanyuan Huang",
          createdAt: "2026-07-11T09:19:32Z",
        },
        {
          id: 2,
          eventType: "review_opened",
          details: { kind: "initial", reviewerId: 9, message: null },
          actorId: 3,
          actorName: "Yuanyuan Huang",
          createdAt: "2026-07-11T09:20:00Z",
        },
        {
          id: 3,
          eventType: "review_decided",
          details: { kind: "initial", decision: "rejected", comment: "Fix the title" },
          actorId: 9,
          actorName: "Yanpei Wang",
          createdAt: "2026-07-11T15:21:39Z",
        },
      ],
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Review history" }));

    await waitFor(() => {
      expect(
        screen.getByText(/Yuanyuan Huang created this posting as a draft/),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        /Yuanyuan Huang submitted for review, assigned to Yanpei Wang/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Yanpei Wang rejected the review.*Fix the title.*sent back to draft/,
      ),
    ).toBeInTheDocument();
  });
});
