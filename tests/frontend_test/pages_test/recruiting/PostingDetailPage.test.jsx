import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import PostingDetailPage from "@/pages/Recruiting/PostingDetailPage";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

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
    [
      { path: "/recruiting/postings/:id", element: <PostingDetailPage /> },
      { path: "/recruiting/postings", element: <div>Postings list</div> },
    ],
    { initialEntries: [`/recruiting/postings/${jobId}`] },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, router };
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
    // published_pending_revision now means a REVISION review is already
    // open (the flip happens at submit_for_review time, not edit time --
    // see JobService.update_job/submit_for_review) so there is no
    // submitter action left to take here, Edit included.
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
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });

  it("shows 'Revision pending review' badge for published_pending_revision with reviewerId: 9", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "published_pending_revision",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        reviewerId: 9,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Revision pending review")).toBeInTheDocument(),
    );
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

  it("shows an unresolved owner in red with a 'no permission, remove' suffix", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: { ownerIds: [42] },
        screenRules: null,
        profileConfig: null,
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByText("#42 — no permission, remove"),
      ).toBeInTheDocument(),
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

  it("shows the status badge alongside a reject-kind badge with the reject kind in the popover", async () => {
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
    fireEvent.click(
      screen.getByRole("button", { name: "Initial submission rejected" }),
    );
    // The badge and the popover title now share the same reject-kind label.
    expect(screen.getAllByText("Initial submission rejected")).toHaveLength(2);
  });

  it("falls back to the raw Rejected label in the popover for an unknown reject kind", async () => {
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
        lastRejectKind: "some_future_kind",
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() => expect(screen.getByText("Draft")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Sent back" }));
    expect(screen.getByText("Rejected")).toBeInTheDocument();
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
          details: {
            kind: "initial",
            decision: "rejected",
            comment: "Fix the title",
          },
          actorId: 9,
          actorName: "Yanpei Wang",
          createdAt: "2026-07-11T15:21:39Z",
        },
      ],
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("tab", { name: "Review history" }),
    );

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

  it("navigates to the postings list after Submit for review succeeds", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        // The submit gate requires >=1 stage and >=1 owner.
        pipelineConfig: {
          stages: [{ stage: "recruiter_screening", rounds: 1 }],
          ownerIds: [5],
        },
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    api.listApprovers.mockResolvedValue({ data: [{ userId: 9, name: "Bob" }] });
    api.submitForReview.mockResolvedValue({ data: { id: 1 } });
    authState.permissions = ["recruiting.job.write"];
    const { router } = renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Reviewer"), {
      target: { value: "9" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Submit for review" }),
    );

    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTINGS,
      ),
    );
  });

  it("disables Submit for review with a hint when the draft has no pipeline stage", async () => {
    // Default fixture ships pipelineConfig: null — no stage configured.
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeDisabled(),
    );
    expect(
      screen.getByText(
        "Add at least one pipeline stage before submitting for review.",
      ),
    ).toBeInTheDocument();
  });

  it("disables Submit for review with a hint when the draft has no manager", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: {
          stages: [{ stage: "recruiter_screening", rounds: 1 }],
          ownerIds: [],
        },
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeDisabled(),
    );
    expect(
      screen.getByText(
        "Add at least one manager (Managed by) before submitting for review.",
      ),
    ).toBeInTheDocument();
  });

  it("enables Submit for review when the draft has a stage and a manager", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: {
          stages: [{ stage: "recruiter_screening", rounds: 1 }],
          ownerIds: [5],
        },
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeEnabled(),
    );
  });

  it("accepts the legacy single-ownerId shape for the submit gate", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        status: "draft",
        pipelineConfig: {
          stages: [{ stage: "recruiter_screening", rounds: 1 }],
          ownerId: 7,
        },
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeEnabled(),
    );
  });

  it("gates the staged-edit Submit for review on the staged pipeline, not the live one", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published",
        pipelineConfig: {
          stages: [{ stage: "recruiter_screening", rounds: 1 }],
          ownerIds: [5],
        },
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: {
          title: "Senior Backend Engineer",
          pipelineConfig: { stages: [], ownerIds: [5] },
        },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Submit for review" }),
      ).toBeDisabled(),
    );
    expect(
      screen.getByText(
        "Add at least one pipeline stage before submitting for review.",
      ),
    ).toBeInTheDocument();
  });

  it("shows Submit for review and Discard draft (not Request close) for a published posting with a staged edit", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: { title: "Senior Backend Engineer" },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    // A pending edit switches Overview to a two-column Current/Proposed
    // comparison, so "Backend Engineer" now also renders inside the
    // Current column's PostingApplicantView (an <h2>) alongside the page
    // header's <h1> — disambiguate by heading level.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "Backend Engineer" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Submit for review" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Discard draft" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request close" }),
    ).not.toBeInTheDocument();
  });

  it("shows Request close (not Submit for review) for a published posting with no staged edit", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: null,
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Request close" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Submit for review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Discard draft" }),
    ).not.toBeInTheDocument();
  });

  it("shows Discard draft alongside Request reopen for a closed posting with a staged edit", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "closed",
        wasPublished: true,
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: { title: "Senior Backend Engineer" },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    // A pending edit switches Overview to a two-column Current/Proposed
    // comparison, so "Backend Engineer" now also renders inside the
    // Current column's PostingApplicantView (an <h2>) alongside the page
    // header's <h1> — disambiguate by heading level.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "Backend Engineer" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Request reopen" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Discard draft" }),
    ).toBeInTheDocument();
  });

  it("does not show any submitter action on a published_pending_revision posting", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published_pending_revision",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: { title: "Senior Backend Engineer" },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    // A pending edit switches Overview to a two-column Current/Proposed
    // comparison, so "Backend Engineer" now also renders inside the
    // Current column's PostingApplicantView (an <h2>) alongside the page
    // header's <h1> — disambiguate by heading level.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "Backend Engineer" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("Operate:")).not.toBeInTheDocument();
  });

  it("discards the staged edit and reloads when Discard draft is confirmed", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: { title: "Senior Backend Engineer" },
      },
    });
    api.discardPendingEdit.mockResolvedValue({ data: {} });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Discard draft" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Discard draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm discard" }));

    await waitFor(() =>
      // `id` comes from useParams (always a string) and every other
      // action dispatch in this component (submitForReview/requestClose/
      // requestReopen/deleteJob) forwards it unconverted, so match that
      // convention here rather than coercing to a number.
      expect(api.discardPendingEdit).toHaveBeenCalledWith("1"),
    );
    expect(api.getJob).toHaveBeenCalledTimes(2); // initial load + reload after discard
  });

  it("formats a rejected revision as keeping the staged edit, not discarding it", async () => {
    api.listJobActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          createdAt: "2026-07-14T00:00:00Z",
          actorName: "Alex",
          eventType: "review_decided",
          details: {
            kind: "revision",
            decision: "rejected",
            comment: "fix the title",
          },
        },
      ],
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("tab", { name: "Review history" }),
    );

    expect(
      screen.getByText(
        /Alex rejected the revision: "fix the title" — posting stays published/,
      ),
    ).toBeInTheDocument();
  });

  it("formats a discarded staged edit in the activity timeline", async () => {
    api.listJobActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          createdAt: "2026-07-14T00:00:00Z",
          actorName: "Alex",
          eventType: "pending_edit_discarded",
          details: {},
        },
      ],
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("tab", { name: "Review history" }),
    );

    expect(
      screen.getByText(/Alex discarded a staged edit/),
    ).toBeInTheDocument();
  });

  it("shows a two-column Current/Proposed comparison in Overview when a pending edit is staged", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "Original description.",
        kind: "employment",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        formSchema: { questions: [] },
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: {
          title: "Senior Backend Engineer",
          description: "Updated description.",
          cooldownDays: null,
          screenRules: null,
          formSchema: { questions: [] },
          pipelineConfig: null,
          profileConfig: null,
        },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Current")).toBeInTheDocument(),
    );
    expect(screen.getByText("Proposed")).toBeInTheDocument();
    expect(screen.getAllByText("Original description.")).toHaveLength(2);
    expect(screen.getByText("Updated description.")).toBeInTheDocument();
    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
  });

  it("does not show a Current/Proposed comparison when there is no pending edit", async () => {
    authState.permissions = ["recruiting.job.write"];
    renderAt(1);

    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Current")).not.toBeInTheDocument();
    expect(screen.queryByText("Proposed")).not.toBeInTheDocument();
  });

  it("shows a two-column Current/Proposed comparison in Configuration when a pending edit is staged", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 1,
        title: "Backend Engineer",
        description: "desc",
        kind: "employment",
        status: "published",
        pipelineConfig: null,
        screenRules: null,
        profileConfig: null,
        cooldownDays: 30,
        lastRejectComment: null,
        reviewerId: null,
        pendingPayload: {
          title: "Backend Engineer",
          description: "desc",
          cooldownDays: 60,
          screenRules: null,
          formSchema: null,
          pipelineConfig: null,
          profileConfig: null,
        },
      },
    });
    authState.permissions = ["recruiting.job.write"];
    const user = userEvent.setup();
    renderAt(1);

    await waitFor(() =>
      expect(
        screen.getByRole("tab", { name: "Configuration" }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("tab", { name: "Configuration" }));

    await waitFor(() =>
      expect(screen.getByText("Cooldown days: 30")).toBeInTheDocument(),
    );
    expect(screen.getByText("Cooldown days: 60")).toBeInTheDocument();
  });
});
