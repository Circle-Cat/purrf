import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import ApplicationDetailPage from "@/pages/Recruiting/applications/ApplicationDetailPage";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "success").mockImplementation(() => {});

// The current user id is read via useAuth(); a hoisted mutable holder lets
// each test flip who is viewing (owner / assignee / neither) before render.
const authState = vi.hoisted(() => ({ userId: 999 }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({ user: { userId: authState.userId } }),
}));

const OWNER_ID = 500;
const ASSIGNEE_ID = 10;

/** The interview-evaluator pool offered by the owner-side pickers. */
const INTERVIEW_POOL = [
  { userId: 10, name: "Eve Evaluator", email: "eve@example.com" },
  { userId: 11, name: "Ivan Interviewer", email: "ivan@example.com" },
];

/** The job whose pipeline config carries per-stage default assignees. */
const JOB = {
  id: 1,
  title: "Mentor",
  pipelineConfig: {
    ownerIds: [OWNER_ID],
    stages: [
      { stage: "recruiter_screening", rounds: 1, defaultAssigneeId: 10 },
      { stage: "behavioral", rounds: 1, defaultAssigneeId: 11 },
      { stage: "tech", rounds: 1 },
    ],
  },
};

const SUBMISSION = {
  personal: {
    firstName: "Alice",
    lastName: "Smith",
    linkedin: "https://linkedin.com/in/alice",
    timezone: "America/New_York",
  },
  education: [
    {
      institution: "State University",
      degree: "BS",
      field: "CS",
      startMonth: "August",
      startYear: "2016",
      endMonth: "May",
      endYear: "2020",
      isCurrentlyWorking: false,
    },
  ],
  experience: [
    {
      company: "Acme Corp",
      title: "Engineer",
      startMonth: "June",
      startYear: "2020",
      isCurrentlyWorking: true,
    },
  ],
  answers: { q1: "Yes", q2: "Remote" },
};

/** Build an ApplicationDetailDto-shaped payload for a given role/stage. */
const makeDetail = ({
  isOwner = false,
  assigneeId = ASSIGNEE_ID,
  stage = "recruiter_screening",
  resumeAvailable = true,
} = {}) => ({
  application: {
    id: 101,
    jobId: 1,
    userId: 5,
    stage,
    subStatus: "pending",
    tags: null,
    current: { version: 1, isFrozen: false, submission: SUBMISSION },
    editable: false,
  },
  applicantName: "Alice Smith",
  applicantEmail: "alice@example.com",
  resumeAvailable,
  formSchema: {
    questions: [{ id: "q1", label: "Are you authorized to work?" }],
  },
  isOwner,
  assigneeId,
});

beforeEach(() => {
  vi.clearAllMocks();
  authState.userId = 999;
  api.resumeUrl.mockImplementation(
    (id) => `/api/recruiting/applications/${id}/resume`,
  );
  api.listInterviewPool.mockResolvedValue({ data: INTERVIEW_POOL });
  api.getJob.mockResolvedValue({ data: JOB });
  api.getEvaluationsForApplication.mockResolvedValue({ data: [] });
});

/** Render the page at the detail route for a given application id. */
const renderPage = (applicationId = 101) => {
  const router = createMemoryRouter(
    [
      {
        path: "/recruiting/applications/:applicationId",
        element: <ApplicationDetailPage />,
      },
    ],
    { initialEntries: [`/recruiting/applications/${applicationId}`] },
  );
  return render(<RouterProvider router={router} />);
};

/** Wait until the applicant identity has rendered (page has loaded). */
const waitLoaded = () =>
  waitFor(() =>
    expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
  );

describe("ApplicationDetailPage — loading & snapshot", () => {
  it("shows a loading state before the detail resolves", () => {
    api.getApplicationDetail.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an error with Retry and recovers when the fetch fails", async () => {
    const user = userEvent.setup();
    api.getApplicationDetail
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue({ data: makeDetail({ isOwner: false }) });
    authState.userId = ASSIGNEE_ID;
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load this application."),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitLoaded();
  });

  it("renders the snapshot sections from detail.application.current.submission", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false }),
    });
    renderPage();

    await waitLoaded();
    expect(
      screen.getByRole("heading", { name: "Alice Smith" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/https:\/\/linkedin\.com\/in\/alice/),
    ).toBeInTheDocument();
    expect(screen.getByText(/America\/New_York/)).toBeInTheDocument();
    expect(screen.getByText(/State University/)).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();
    // Known question uses its label; removed question falls back to raw id.
    expect(
      screen.getByText(/Are you authorized to work\?/),
    ).toBeInTheDocument();
    expect(screen.getByText(/q2/)).toBeInTheDocument();
  });

  it("renders the resume iframe only when resumeAvailable is true", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, resumeAvailable: true }),
    });
    const { unmount } = renderPage();
    await waitLoaded();
    expect(screen.getByTitle("Résumé")).toHaveAttribute(
      "src",
      "/api/recruiting/applications/101/resume",
    );
    unmount();

    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, resumeAvailable: false }),
    });
    renderPage();
    await waitLoaded();
    expect(screen.queryByTitle("Résumé")).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — role-adaptive right column", () => {
  it("owner-only viewer sees the decision footer + evaluation summary, no rubric form", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [
        {
          id: 1,
          applicationId: 101,
          stage: "recruiter_screening",
          evaluatorId: ASSIGNEE_ID,
          responses: {
            bg_match: { value: true },
            bg_strength: { value: 4, notes: "solid background" },
          },
          isConfirmed: true,
        },
      ],
    });
    renderPage();
    await waitLoaded();

    // Decision footer (owner)
    expect(
      screen.getByRole("button", { name: "Blacklist" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reassign" }),
    ).toBeInTheDocument();

    // Evaluation summary built from the full list
    expect(
      screen.getByRole("heading", { name: /Evaluations/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/solid background/)).toBeInTheDocument();

    // No rubric form for a viewer who is not the current-stage assignee
    expect(
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();
  });

  it("assignee-only viewer sees the rubric form pre-filled from their draft, no decision footer", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [
        {
          id: 2,
          applicationId: 101,
          stage: "recruiter_screening",
          evaluatorId: ASSIGNEE_ID,
          responses: { bg_strength: { value: 3, notes: "draft note" } },
          isConfirmed: false,
        },
      ],
    });
    renderPage();
    await waitLoaded();

    // Rubric form present and editable
    expect(
      screen.getByRole("button", { name: "Confirm & Submit" }),
    ).toBeInTheDocument();
    // Pre-filled from the caller's own draft
    expect(screen.getByDisplayValue("draft note")).toBeInTheDocument();

    // No owner decision footer
    expect(
      screen.queryByRole("button", { name: "Blacklist" }),
    ).not.toBeInTheDocument();
    // Owner-only follow-up fetches are skipped for a non-owner
    expect(api.getJob).not.toHaveBeenCalled();
    expect(api.listInterviewPool).not.toHaveBeenCalled();
  });

  it("a viewer who is both owner and assignee sees both areas", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Blacklist" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm & Submit" }),
    ).toBeInTheDocument();
  });

  it("an already-confirmed assignee sees their rubric read-only", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [
        {
          id: 3,
          applicationId: 101,
          stage: "recruiter_screening",
          evaluatorId: ASSIGNEE_ID,
          responses: { bg_match: { value: true } },
          isConfirmed: true,
        },
      ],
    });
    renderPage();
    await waitLoaded();

    // Read-only: no draft/submit actions, and inputs disabled
    expect(
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save draft" }),
    ).not.toBeInTheDocument();
    screen
      .getAllByRole("button", { name: "Pass" })
      .forEach((button) => expect(button).toBeDisabled());
  });

  it("submits a draft evaluation via submitEvaluation when the assignee saves", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.submitEvaluation.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(api.submitEvaluation).toHaveBeenCalledWith("101", {
        responses: {},
        confirm: false,
      }),
    );
  });
});

describe("ApplicationDetailPage — advance-time assignee default", () => {
  it("pre-fills the picker with the configured default when advancing into behavioral", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "recruiter_screening",
      }),
    });
    renderPage();
    await waitLoaded();

    // Advance target is "behavioral" (an interview stage): the picker is
    // pre-filled with behavioral's configured default assignee (Ivan, id 11),
    // so Confirm advance is already enabled.
    const picker = screen.getByRole("combobox", { name: /assignee/i });
    expect(picker).toHaveTextContent("Ivan Interviewer");
    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).not.toBeDisabled();
  });

  it("advances with the pre-filled default assignee id", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "recruiter_screening",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Confirm advance" }));
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "behavioral",
        assigneeId: 11,
      }),
    );
  });

  it("clears a stale prefilled assignee after an in-page advance into a non-prefill stage", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    // First load lands on recruiter_screening (prefill target); after the
    // in-page advance, the SAME component instance reloads onto behavioral,
    // whose own next target is "tech" (not a prefill target).
    api.getApplicationDetail
      .mockResolvedValueOnce({
        data: makeDetail({
          isOwner: true,
          assigneeId: ASSIGNEE_ID,
          stage: "recruiter_screening",
        }),
      })
      .mockResolvedValue({
        data: makeDetail({
          isOwner: true,
          assigneeId: ASSIGNEE_ID,
          stage: "behavioral",
        }),
      });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    // Advancing out of recruiter_screening pre-fills behavioral's default
    // (Ivan, id 11), so Confirm advance is already enabled.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Confirm advance" }),
      ).not.toBeDisabled(),
    );
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));

    // The page reloads in place onto "behavioral"; its next target is "tech",
    // which carries no configured default. The picker must NOT still show
    // behavioral's stale "Ivan Interviewer" value, and Confirm advance must
    // NOT be left enabled by a leftover value from the previous stage.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Confirm advance" }),
      ).toBeDisabled(),
    );
    const picker = screen.getByRole("combobox", { name: /assignee/i });
    expect(
      within(picker).queryByText("Ivan Interviewer"),
    ).not.toBeInTheDocument();
  });

  it("leaves the picker unfilled when advancing into tech (no configured default)", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "behavioral",
      }),
    });
    renderPage();
    await waitLoaded();

    // Advance target is "tech" (interview stage, no default_assignee_id):
    // picker stays on "— none —", Confirm advance disabled.
    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).toBeDisabled();
    const picker = screen.getByRole("combobox", { name: /assignee/i });
    expect(
      within(picker).queryByText("Ivan Interviewer"),
    ).not.toBeInTheDocument();
  });
});
