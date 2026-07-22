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
// `permissions` defaults to holding the blacklist grant (see beforeEach) so
// owner-flow tests exercise a fully-empowered owner; the permission-gating
// tests empty it explicitly.
const authState = vi.hoisted(() => ({ userId: 999, permissions: [] }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { userId: authState.userId },
    permissions: authState.permissions,
  }),
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
  kind: "employment",
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

/** A second job's snapshot, for another-application aggregation fixtures. */
const OTHER_SUBMISSION = {
  personal: { firstName: "Alice", lastName: "Smith" },
  education: [],
  experience: [],
  answers: { q9: "Yes" },
};

/** Build an OtherApplicationDto-shaped payload. */
const makeOtherApplication = ({
  id = 201,
  jobTitle = "Backend Engineer",
  jobKind = "employment",
  stage = "tech",
  resumeAvailable = false,
  evaluations = [],
  activity = [],
  comments = [],
} = {}) => ({
  application: {
    id,
    jobId: 2,
    userId: 5,
    stage,
    subStatus: "pending",
    tags: null,
    currentRound: 1,
    current: { version: 1, isFrozen: true, submission: OTHER_SUBMISSION },
    editable: false,
  },
  jobTitle,
  jobKind,
  resumeAvailable,
  evaluations,
  activity,
  comments,
});

/** Build an ApplicationDetailDto-shaped payload for a given role/stage. */
const makeDetail = ({
  isOwner = false,
  canView = isOwner,
  assigneeId = ASSIGNEE_ID,
  stage = "recruiter_screening",
  resumeAvailable = true,
  currentRound,
} = {}) => ({
  application: {
    id: 101,
    jobId: 1,
    userId: 5,
    stage,
    subStatus: "pending",
    tags: null,
    currentRound,
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
  canView,
  assigneeId,
});

/**
 * Build a confirmed evaluation row for a stage+round, as returned by
 * getEvaluationsForApplication — what the advance-without-evaluation soft
 * reminder checks for before letting an advance through silently.
 */
const confirmedEval = (stage, round = 1, evaluatorId = ASSIGNEE_ID) => ({
  id: 900 + round,
  applicationId: 101,
  stage,
  round,
  evaluatorId,
  responses: {},
  isConfirmed: true,
  confirmedAt: "2026-07-18T00:00:00Z",
});

beforeEach(() => {
  vi.clearAllMocks();
  authState.userId = 999;
  authState.permissions = ["recruiting.blacklist.write"];
  api.resumeUrl.mockImplementation(
    (id) => `/api/recruiting/applications/${id}/resume`,
  );
  api.listInterviewPool.mockResolvedValue({ data: INTERVIEW_POOL });
  api.getJob.mockResolvedValue({ data: JOB });
  api.getEvaluationsForApplication.mockResolvedValue({ data: [] });
  api.getApplicationActivity.mockResolvedValue({ data: [] });
  api.getApplicationComments.mockResolvedValue({ data: [] });
  api.getMentionableUsers.mockResolvedValue({ data: [] });
  api.getOtherApplications.mockResolvedValue({
    data: { otherJobs: [], previousSameJob: [] },
  });
});

/** Render the page at the detail route for a given application id. */
const renderPage = (applicationId = 101, search = "") => {
  const router = createMemoryRouter(
    [
      {
        path: "/recruiting/applications/:applicationId",
        element: <ApplicationDetailPage />,
      },
    ],
    { initialEntries: [`/recruiting/applications/${applicationId}${search}`] },
  );
  return { ...render(<RouterProvider router={router} />), router };
};

/** Render the page in the evaluator-only view (the My Evaluations link). */
const renderEvaluatorPage = (applicationId = 101) =>
  renderPage(applicationId, "?mode=evaluate");

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

  it("shows the current stage next to the applicant's name", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, stage: "recruiter_screening" }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Recruiter screening")).toBeInTheDocument();
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
          round: 1,
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

    // Evaluation summary built from the full list, in the (default-active)
    // Evaluations tab
    expect(
      screen.getByRole("tab", { name: "Evaluations" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Timeline" })).toBeInTheDocument();
    expect(screen.getByText(/solid background/)).toBeInTheDocument();
    expect(screen.getByText(/Evaluated by: Eve Evaluator/)).toBeInTheDocument();

    // No rubric form for a viewer who is not the current-stage assignee
    expect(
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();
  });

  it("owner at the Offer stage sees no Reassign button (Offer is not assignable)", async () => {
    authState.userId = OWNER_ID;
    // Offer carries no assignment, so the backend returns a null assigneeId.
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "offer", assigneeId: null }),
    });
    renderPage();
    await waitLoaded();

    // The decision footer still renders, but Offer has no rubric/assignee, so
    // the Reassign control is hidden (the backend rejects a reassign there).
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reassign" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/^Assigned to:/)).not.toBeInTheDocument();
  });

  it("owner-only viewer sees the How-it-works guide for reviewing applications", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "How it works" }));

    expect(
      screen.getByRole("heading", { name: "How application review works" }),
    ).toBeInTheDocument();
  });

  it("assignee-only viewer in evaluator mode sees the How-it-works guide for evaluating", async () => {
    const user = userEvent.setup();
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
          round: 1,
          evaluatorId: ASSIGNEE_ID,
          responses: {},
          isConfirmed: false,
        },
      ],
    });
    renderEvaluatorPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "How it works" }));

    expect(
      screen.getByRole("heading", { name: "How evaluating works" }),
    ).toBeInTheDocument();
  });

  it("a viewer who is neither owner/read.all nor the current-stage assignee sees no How-it-works button", async () => {
    authState.userId = 999;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        canView: false,
        assigneeId: ASSIGNEE_ID,
      }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.queryByRole("button", { name: "How it works" }),
    ).not.toBeInTheDocument();
  });

  it("sorts evaluations newest-first by id", async () => {
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
          round: 1,
          evaluatorId: 10,
          responses: { bg_strength: { value: 2, notes: "older note" } },
          isConfirmed: true,
        },
        {
          id: 2,
          applicationId: 101,
          stage: "recruiter_screening",
          round: 1,
          evaluatorId: 11,
          responses: { bg_strength: { value: 5, notes: "newer note" } },
          isConfirmed: true,
        },
      ],
    });
    renderPage();
    await waitLoaded();

    const notes = screen.getAllByText(/note$/);
    expect(notes[0]).toHaveTextContent("newer note");
    expect(notes[1]).toHaveTextContent("older note");
  });

  it('falls back to "User {id}" when the evaluator isn\'t in the interview pool', async () => {
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
          round: 1,
          evaluatorId: 77,
          responses: { bg_strength: { value: 3, notes: "a note" } },
          isConfirmed: true,
        },
      ],
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText(/Evaluated by: User 77/)).toBeInTheDocument();
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
          round: 1,
          evaluatorId: ASSIGNEE_ID,
          responses: { bg_strength: { value: 3, notes: "draft note" } },
          isConfirmed: false,
        },
      ],
    });
    renderEvaluatorPage();
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
    // Owner-only follow-up fetches are skipped for a non-owner...
    expect(api.getJob).not.toHaveBeenCalled();
    // ...but the evaluator DOES fetch the candidate aggregate + (best-effort)
    // interview pool for the history panels.
    expect(api.getOtherApplications).toHaveBeenCalledWith("101");
    expect(api.listInterviewPool).toHaveBeenCalled();
  });

  it("an owner who is also the current-stage assignee sees only the decision footer on the plain detail link", async () => {
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
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();
  });

  it("the same owner+assignee sees only the rubric form via the evaluator link", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.queryByRole("button", { name: "Blacklist" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm & Submit" }),
    ).toBeInTheDocument();
  });

  it("a viewer in evaluator mode who isn't the current-stage assignee sees an explanatory message, not owner actions", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.getByText(
        "You are not currently assigned to evaluate this application.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Blacklist" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();
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
          round: 1,
          evaluatorId: ASSIGNEE_ID,
          responses: { bg_match: { value: true } },
          isConfirmed: true,
        },
      ],
    });
    renderEvaluatorPage();
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

  it("a round-1-confirmed evaluator on round 2 gets a fresh editable rubric, not the locked round-1 one", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        assigneeId: ASSIGNEE_ID,
        stage: "recruiter_screening",
        currentRound: 2,
      }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [
        {
          id: 4,
          applicationId: 101,
          stage: "recruiter_screening",
          round: 1,
          evaluatorId: ASSIGNEE_ID,
          responses: { bg_match: { value: true } },
          isConfirmed: true,
        },
      ],
    });
    renderEvaluatorPage();
    await waitLoaded();

    // Round 2 has no evaluation yet: the rubric must be fresh and editable,
    // not the round-1 confirmed row (which would render read-only).
    expect(
      screen.getByRole("button", { name: "Confirm & Submit" }),
    ).toBeInTheDocument();
    screen
      .getAllByRole("button", { name: "Pass" })
      .forEach((button) => expect(button).not.toBeDisabled());
  });

  it("submits a draft evaluation via submitEvaluation when the assignee saves", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.submitEvaluation.mockResolvedValue({ data: {} });
    renderEvaluatorPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(api.submitEvaluation).toHaveBeenCalledWith("101", {
        responses: {},
        confirm: false,
      }),
    );
  });

  it("disables Save draft and Confirm & Submit while a submission is in flight, to prevent a double-submit", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    let resolveSubmit;
    api.submitEvaluation.mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = resolve;
      }),
    );
    renderEvaluatorPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Confirm & Submit" }),
    ).toBeDisabled();

    resolveSubmit({ data: {} });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Save draft" }),
      ).not.toBeDisabled(),
    );
  });
});

describe("ApplicationDetailPage — advance-time assignee dialog", () => {
  beforeEach(() => {
    // These tests exercise the assignee dialog itself; seed confirmed
    // evaluations for the stages advanced from so the no-evaluation
    // reminder (covered by its own describe) stays out of the way.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening"), confirmedEval("behavioral")],
    });
  });

  it("clicking Advance to Behavioral opens a dialog pre-filled with the configured default", async () => {
    const user = userEvent.setup();
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    // Advance target is "behavioral" (an interview stage): the dialog's
    // radio list is pre-filled with behavioral's configured default
    // assignee (Ivan, id 11), but a pick isn't required so Confirm is
    // enabled either way.
    expect(
      screen.getByRole("radio", { name: /ivan interviewer/i }),
    ).toBeChecked();
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "behavioral",
        assigneeId: 11,
      }),
    );
  });

  it("advances with no assignee when the picker is left blank, instead of blocking the confirm", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "behavioral",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    // Advance target is "tech" (interview stage, no configured default): the
    // radio list starts on "Decide later", and Confirm advance is not
    // blocked on it — leaving it there just advances the stage unassigned,
    // to be picked up later via Reassign.
    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));
    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Confirm advance" }));
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "tech",
        assigneeId: undefined,
      }),
    );
  });

  it("Cancel closes the dialog without calling the API", async () => {
    const user = userEvent.setup();
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
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
    // (Ivan, id 11).
    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("radio", { name: /ivan interviewer/i }),
      ).toBeChecked(),
    );
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));

    // The page reloads in place onto "behavioral"; its next target is "tech",
    // which carries no configured default. Reopening the dialog must NOT
    // still show behavioral's stale "Ivan Interviewer" pick.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Advance to Tech" }),
      ).toBeInTheDocument(),
    );
    // The stage badge confirms the advance actually landed on "behavioral".
    expect(screen.getByText("Behavioral")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));
    expect(
      screen.getByRole("radio", { name: /ivan interviewer/i }),
    ).not.toBeChecked();
  });
});

describe("ApplicationDetailPage — reassign dialog", () => {
  it("opens on a radio list with no pick and Confirm reassign disabled, and no 'decide later' option", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reassign" }));

    expect(
      screen.getByRole("radio", { name: /eve evaluator/i }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("radio", { name: /ivan interviewer/i }),
    ).not.toBeChecked();
    expect(
      screen.queryByRole("radio", { name: /decide later/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm reassign" }),
    ).toBeDisabled();
  });

  it("picking someone enables Confirm reassign and calls reassignApplication", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.reassignApplication.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reassign" }));
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    expect(
      screen.getByRole("button", { name: "Confirm reassign" }),
    ).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Confirm reassign" }));
    await waitFor(() =>
      expect(api.reassignApplication).toHaveBeenCalledWith("101", 11),
    );
  });

  it("Cancel closes the dialog without calling the API", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reassign" }));
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm reassign" }),
    ).not.toBeInTheDocument();
    expect(api.reassignApplication).not.toHaveBeenCalled();
  });
});

describe("ApplicationDetailPage — operate row", () => {
  it("labels the decision row Operate, with Blacklist/Reject/Advance on it", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Operate:")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Blacklist" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    ).toBeInTheDocument();
  });

  it("disables Blacklist for an owner without recruiting.blacklist.write", async () => {
    authState.userId = OWNER_ID;
    authState.permissions = [];
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    const blacklistButton = screen.getByRole("button", { name: "Blacklist" });
    expect(blacklistButton).toBeDisabled();
    expect(blacklistButton).toHaveAttribute(
      "title",
      "Requires the blacklist permission",
    );
  });

  it("keeps Blacklist enabled for an owner holding recruiting.blacklist.write", async () => {
    authState.userId = OWNER_ID;
    authState.permissions = ["recruiting.blacklist.write"];
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Blacklist" })).toBeEnabled();
  });

  it("shows a single Advance button that advances the round while one remains, not both round and stage buttons", async () => {
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: {
        ...JOB,
        pipelineConfig: {
          ...JOB.pipelineConfig,
          stages: JOB.pipelineConfig.stages.map((s) =>
            s.stage === "recruiter_screening" ? { ...s, rounds: 2 } : s,
          ),
        },
      },
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "recruiter_screening",
        currentRound: 1,
      }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Advance to Behavioral" }),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — reject dialog", () => {
  it("opens on a reason picker with Confirm reject disabled until a reason is chosen", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(
      screen.getByRole("combobox", { name: /rejection reason/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm reject" }),
    ).toBeDisabled();
  });

  it("picking a reason and confirming calls changeApplicationStage with toStage rejected", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.click(
      screen.getByRole("combobox", { name: /rejection reason/i }),
    );
    await user.click(await screen.findByText("Insufficient experience"));
    await user.click(screen.getByRole("button", { name: "Confirm reject" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "rejected",
        reason: "Insufficient experience",
        note: undefined,
      }),
    );
  });

  it("Cancel closes the dialog without calling the API", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm reject" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });
});

describe("ApplicationDetailPage — advance round", () => {
  beforeEach(() => {
    // Round-advance mechanics under test, not the no-evaluation reminder:
    // seed a confirmed evaluation for the round being left.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("tech", 1)],
    });
  });

  /** The base JOB fixture with the tech stage's `rounds` overridden. */
  const jobWithTechRounds = (rounds) => ({
    ...JOB,
    pipelineConfig: {
      ...JOB.pipelineConfig,
      stages: JOB.pipelineConfig.stages.map((s) =>
        s.stage === "tech" ? { ...s, rounds } : s,
      ),
    },
  });

  it("shows the Advance Round button when the stage supports multiple rounds and the applicant hasn't reached the last one", async () => {
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    ).toBeInTheDocument();
  });

  it("hides the button for a single-round stage", async () => {
    authState.userId = OWNER_ID;
    // Default JOB fixture configures tech with rounds: 1.
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.queryByRole("button", { name: /Advance to Round/ }),
    ).not.toBeInTheDocument();
  });

  it("hides the button once the applicant is already on the last configured round", async () => {
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(2) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 2 }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.queryByRole("button", { name: /Advance to Round/ }),
    ).not.toBeInTheDocument();
  });

  it("clicking Advance Round opens a dialog instead of advancing immediately, defaulting to Decide later", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );

    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("button", { name: "Confirm advance round" }),
    ).not.toBeDisabled();
    expect(api.setApplicationRound).not.toHaveBeenCalled();
  });

  it("confirming without picking an assignee advances the round unassigned", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    api.setApplicationRound.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm advance round" }),
    );

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith("101", 2, undefined),
    );
  });

  it("picking an assignee and confirming calls setApplicationRound with the assignee and updates the displayed round", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    api.setApplicationRound.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    const confirmButton = screen.getByRole("button", {
      name: "Confirm advance round",
    });
    expect(confirmButton).not.toBeDisabled();
    await user.click(confirmButton);

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith("101", 2, 11),
    );
    // Local state patched in place: the button now reflects round 2 -> 3.
    expect(
      await screen.findByRole("button", { name: "Advance to Round 3" }),
    ).toBeInTheDocument();
  });

  it("Cancel in the round-advance picker reverts to the trigger button without calling the API", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm advance round" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    ).toBeInTheDocument();
    expect(api.setApplicationRound).not.toHaveBeenCalled();
  });

  it("surfaces a toast error when advancing the round fails", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    api.setApplicationRound.mockRejectedValue(new Error("Round update failed"));
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    await user.click(
      screen.getByRole("button", { name: "Confirm advance round" }),
    );
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Round update failed"),
    );
  });
});

describe("ApplicationDetailPage — activity timeline", () => {
  it("shows the activity timeline under its own tab, inactive by default", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "stage_changed",
          details: { fromStage: "recruiter_screening", toStage: "tech" },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    // Not shown until the Timeline tab is selected (Evaluations is default).
    expect(screen.queryByText(/Advanced from/)).not.toBeInTheDocument();
  });

  it("clicking the Timeline tab shows each entry described by actor and event", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "stage_changed",
          details: { fromStage: "recruiter_screening", toStage: "tech" },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T12:00:00Z",
        },
        {
          id: 2,
          eventType: "reassigned",
          details: {
            stage: "tech",
            fromAssigneeId: null,
            toAssigneeId: 11,
            toAssigneeName: "Ivan Interviewer",
          },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T11:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Advanced from Recruiter screening to Tech, by Owen Owner/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Reassigned on Tech to Ivan Interviewer, by Owen Owner/),
    ).toBeInTheDocument();
  });

  it("shows a rejection's reason and note in the timeline", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "stage_changed",
          details: {
            fromStage: "tech",
            toStage: "rejected",
            reason: "Did not meet the technical bar",
            note: "weak on systems design",
          },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Rejected from Tech: Did not meet the technical bar — weak on systems design/,
      ),
    ).toBeInTheDocument();
  });

  it("shows an empty state when there's no activity yet", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({ data: [] });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(screen.getByText("No activity yet.")).toBeInTheDocument();
  });

  it("does not fetch or render the timeline for a non-owner viewer", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(api.getApplicationActivity).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("tab", { name: "Timeline" }),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — activity timeline assignee names", () => {
  /** Render, open the Timeline tab, and return once it's visible. */
  const renderTimelineWith = async (entry) => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({ data: [entry] });
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Timeline" }));
  };

  it("shows the assignee name when advancing into a stage with one picked", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "stage_changed",
      details: {
        fromStage: "recruiter_screening",
        toStage: "tech",
        assigneeId: 11,
        assigneeName: "Ivan Interviewer",
      },
      actorId: OWNER_ID,
      actorName: "Owen Owner",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Advanced from Recruiter screening to Tech, assigned to Ivan Interviewer, by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });

  it("shows the assignee name when round-advancing with one picked", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "round_advanced",
      details: {
        stage: "tech",
        fromRound: 1,
        toRound: 2,
        assigneeId: 11,
        assigneeName: "Ivan Interviewer",
      },
      actorId: OWNER_ID,
      actorName: "Owen Owner",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Advanced to round 2 of Tech, assigned to Ivan Interviewer, by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });

  it("shows both names when reassigning from a previous assignee", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "reassigned",
      details: {
        stage: "tech",
        fromAssigneeId: 7,
        fromAssigneeName: "Eve Evaluator",
        toAssigneeId: 11,
        toAssigneeName: "Ivan Interviewer",
      },
      actorId: OWNER_ID,
      actorName: "Owen Owner",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Reassigned on Tech from Eve Evaluator to Ivan Interviewer, by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });

  it("shows the auto_assigned event with the assignee name and the candidate as actor", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "auto_assigned",
      details: {
        stage: "recruiter_screening",
        assigneeId: 11,
        assigneeName: "Ivan Interviewer",
      },
      actorId: 5,
      actorName: "Alice Smith",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Automatically assigned to Ivan Interviewer on Recruiter screening, by Alice Smith/,
      ),
    ).toBeInTheDocument();
  });

  it("applies the shared by-actor suffix to an event type with no assignee concept", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "sub_status_changed",
      details: {
        stage: "tech",
        fromSubStatus: "pending",
        toSubStatus: "in_progress",
      },
      actorId: OWNER_ID,
      actorName: "Owen Owner",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Status changed from Pending to In progress on Tech, by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });

  it("omits the assignee clause when advancing with no assignee picked", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "stage_changed",
      details: { fromStage: "recruiter_screening", toStage: "tech" },
      actorId: OWNER_ID,
      actorName: "Owen Owner",
      createdAt: "2026-07-04T12:00:00Z",
    });

    expect(
      screen.getByText(
        /Advanced from Recruiter screening to Tech, by Owen Owner/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/assigned to/)).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — comments", () => {
  it("owner view shows a Comments tab alongside Evaluations and Timeline", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationComments.mockResolvedValue({
      data: [
        {
          id: 1,
          authorId: OWNER_ID,
          authorName: "Owen Owner",
          body: "Strong candidate.",
          createdAt: "2026-07-07T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByRole("tab", { name: "Comments" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Comments" }));

    expect(
      screen.getByText(/Owen Owner: Strong candidate\./),
    ).toBeInTheDocument();
  });

  it("shows an empty state when there are no comments yet", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));

    expect(screen.getByText("No comments yet.")).toBeInTheDocument();
  });

  it("posting a comment prepends it to the list and clears the input", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.postComment.mockResolvedValue({
      data: {
        id: 2,
        authorId: OWNER_ID,
        authorName: "Owen Owner",
        body: "New note",
        createdAt: "2026-07-07T13:00:00Z",
        mentions: [],
      },
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));
    await user.type(screen.getByPlaceholderText("Add a comment…"), "New note");
    await user.click(screen.getByRole("button", { name: "Post" }));

    await waitFor(() =>
      expect(screen.getByText(/Owen Owner: New note/)).toBeInTheDocument(),
    );
    expect(api.postComment).toHaveBeenCalledWith("101", { body: "New note" });
    expect(screen.getByPlaceholderText("Add a comment…")).toHaveValue("");
  });

  it("typing @ opens a picker of mentionable users and inserts a token on selection", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getMentionableUsers.mockResolvedValue({
      data: [{ userId: ASSIGNEE_ID, name: "Eve Evaluator" }],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));
    await user.type(screen.getByPlaceholderText("Add a comment…"), "Hey @Ev");

    expect(await screen.findByText("Eve Evaluator")).toBeInTheDocument();
    await user.click(screen.getByText("Eve Evaluator"));

    expect(screen.getByPlaceholderText("Add a comment…")).toHaveValue(
      `Hey @[${ASSIGNEE_ID}] `,
    );
  });

  it("renders a resolved mention as highlighted text", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationComments.mockResolvedValue({
      data: [
        {
          id: 1,
          authorId: OWNER_ID,
          authorName: "Owen Owner",
          body: `cc @[${ASSIGNEE_ID}] please review`,
          createdAt: "2026-07-07T12:00:00Z",
          mentions: [{ userId: ASSIGNEE_ID, name: "Eve Evaluator" }],
        },
      ],
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));

    expect(screen.getByText("@Eve Evaluator")).toBeInTheDocument();
  });

  it("disables the Post button while a comment is being posted", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    let resolvePost;
    api.postComment.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      }),
    );
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));
    await user.type(screen.getByPlaceholderText("Add a comment…"), "In flight");
    await user.click(screen.getByRole("button", { name: "Post" }));

    expect(screen.getByRole("button", { name: "Post" })).toBeDisabled();

    resolvePost({
      data: {
        id: 3,
        authorId: OWNER_ID,
        authorName: "Owen Owner",
        body: "In flight",
        createdAt: "2026-07-07T14:00:00Z",
      },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Post" })).not.toBeDisabled(),
    );
  });

  it("assignee view shows Your evaluation and Comments tabs, and can post a comment", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.postComment.mockResolvedValue({
      data: {
        id: 4,
        authorId: ASSIGNEE_ID,
        authorName: "Eve Evaluator",
        body: "Scheduling now.",
        createdAt: "2026-07-07T15:00:00Z",
      },
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.getByRole("tab", { name: "Your evaluation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Comments" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Comments" }));
    await user.type(
      screen.getByPlaceholderText("Add a comment…"),
      "Scheduling now.",
    );
    await user.click(screen.getByRole("button", { name: "Post" }));

    await waitFor(() =>
      expect(
        screen.getByText(/Eve Evaluator: Scheduling now\./),
      ).toBeInTheDocument(),
    );
  });

  it("fetches comments (harmless) but shows no Comments tab in the not-currently-assigned explanatory branch", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(api.getApplicationComments).toHaveBeenCalled();
    expect(
      screen.queryByRole("tab", { name: "Comments" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "You are not currently assigned to evaluate this application.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the draft text in the textarea when posting a comment fails", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.postComment.mockRejectedValue(new Error("boom"));
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Comments" }));
    await user.type(
      screen.getByPlaceholderText("Add a comment…"),
      "Don't lose me",
    );
    await user.click(screen.getByRole("button", { name: "Post" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Add a comment…")).toHaveValue(
      "Don't lose me",
    );
  });
});

describe("ApplicationDetailPage — Scheduled requires an assignee", () => {
  it("blocks marking a behavioral application as Scheduled when unassigned and shows a warning", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: null,
        stage: "behavioral",
      }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Scheduled" }));

    expect(
      screen.getByText(
        "Please assign a reviewer before marking this as Scheduled.",
      ),
    ).toBeInTheDocument();
    expect(api.setApplicationSubStatus).not.toHaveBeenCalled();
  });

  it("OK closes the warning dialog", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: null,
        stage: "behavioral",
      }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Scheduled" }));
    await user.click(screen.getByRole("button", { name: "OK" }));

    expect(
      screen.queryByText(
        "Please assign a reviewer before marking this as Scheduled.",
      ),
    ).not.toBeInTheDocument();
  });

  it("allows marking a tech application as Scheduled once an assignee is set", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "tech",
      }),
    });
    api.setApplicationSubStatus.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Scheduled" }));

    await waitFor(() =>
      expect(api.setApplicationSubStatus).toHaveBeenCalledWith(
        "101",
        "scheduled",
      ),
    );
    expect(
      screen.queryByText(
        "Please assign a reviewer before marking this as Scheduled.",
      ),
    ).not.toBeInTheDocument();
  });

  it("does not guard other sub-status values even when unassigned", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: null,
        stage: "behavioral",
      }),
    });
    api.setApplicationSubStatus.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Scheduling" }));

    await waitFor(() =>
      expect(api.setApplicationSubStatus).toHaveBeenCalledWith(
        "101",
        "scheduling",
      ),
    );
    expect(
      screen.queryByText(
        "Please assign a reviewer before marking this as Scheduled.",
      ),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — advance dialog Scheduled hint", () => {
  beforeEach(() => {
    // The Scheduled hint lives inside the advance dialog; seed confirmed
    // evaluations so the no-evaluation reminder doesn't intercept the click.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [
        confirmedEval("recruiter_screening"),
        confirmedEval("behavioral"),
        confirmedEval("tech"),
      ],
    });
  });

  const HINT_TEXT =
    "You can leave this unassigned for now — an assignee will be required before marking this stage as Scheduled.";

  it("shows the hint when advancing into Behavioral", async () => {
    const user = userEvent.setup();
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();
  });

  it("shows the hint when advancing into Tech", async () => {
    const user = userEvent.setup();
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

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));

    expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();
  });

  it("does not show the hint when advancing into Board Review", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: {
        ...JOB,
        pipelineConfig: {
          ...JOB.pipelineConfig,
          stages: [
            ...JOB.pipelineConfig.stages,
            { stage: "board_review", rounds: 1 },
          ],
        },
      },
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "tech",
      }),
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Board review" }),
    );

    expect(screen.queryByText(HINT_TEXT)).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — Offer is a fixed step before Hired", () => {
  beforeEach(() => {
    // Advancing out of tech (the last interview stage here) would otherwise
    // trip the no-evaluation reminder.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("tech")],
    });
  });

  it("advances from the last configured stage to Offer, not Hired", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "tech",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Offer" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "offer",
        assigneeId: undefined,
      }),
    );
  });

  it("advances from Offer to Hired", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "offer",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Hired" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "hired",
        assigneeId: undefined,
      }),
    );
  });

  it("allows rejecting from Offer with the candidate-declined reason", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "offer",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.click(
      screen.getByRole("combobox", { name: /rejection reason/i }),
    );
    await user.click(await screen.findByText("Candidate declined the offer"));
    await user.click(screen.getByRole("button", { name: "Confirm reject" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "rejected",
        reason: "Candidate declined the offer",
        note: undefined,
      }),
    );
  });

  it("shows no Status selector for Offer", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "offer",
      }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.queryByText("Status:")).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — activity jobs have no Offer step", () => {
  const ACTIVITY_JOB = { ...JOB, kind: "activity" };

  beforeEach(() => {
    // Advancing tech -> Admitted would otherwise trip the no-evaluation
    // reminder (activity jobs get it too, by design).
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("tech")],
    });
  });

  it("advances from the last configured stage straight to Admitted (hired)", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: ACTIVITY_JOB });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "tech",
      }),
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Admitted" }),
    );

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "hired",
        assigneeId: undefined,
      }),
    );
  });

  it("shows the stage badge as Admitted for a hired application", async () => {
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: ACTIVITY_JOB });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "hired" }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Admitted")).toBeInTheDocument();
    expect(screen.queryByText("Hired")).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — read.all non-owner view", () => {
  it("fetches job config, interview pool, and activity for a canView viewer even when not the real owner", async () => {
    authState.userId = 42;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, canView: true }),
    });
    renderPage();
    await waitLoaded();

    expect(api.getJob).toHaveBeenCalled();
    expect(api.listInterviewPool).toHaveBeenCalled();
    expect(api.getApplicationActivity).toHaveBeenCalled();
  });

  it("shows the info panel with every actionable control absent or disabled", async () => {
    authState.userId = 42;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        canView: true,
        assigneeId: ASSIGNEE_ID,
      }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Status:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pending" })).toBeDisabled();
    expect(screen.getByText(/Assigned to: Eve Evaluator/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reassign" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Operate:")).not.toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Evaluations" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Timeline" })).toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — candidate aggregation", () => {
  it("does not render the other-applications section when there are none", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.queryByText("Other applications")).not.toBeInTheDocument();
  });

  it("lists the candidate's other applications inline, without needing a click first", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: {
        otherJobs: [
          makeOtherApplication({ jobTitle: "Backend Engineer", stage: "tech" }),
        ],
        previousSameJob: [],
      },
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Other applications")).toBeInTheDocument();
    expect(screen.getByText(/Backend Engineer — Tech/)).toBeInTheDocument();
  });

  it("expands a row inline to show its snapshot and evaluations, without navigating", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: {
        otherJobs: [
          makeOtherApplication({
            id: 201,
            evaluations: [
              {
                id: 900,
                applicationId: 201,
                stage: "tech",
                round: 1,
                evaluatorId: ASSIGNEE_ID,
                responses: { overall: { value: 5, notes: "Strong" } },
                isConfirmed: true,
              },
            ],
          }),
        ],
        previousSameJob: [],
      },
    });
    const { router } = renderPage();
    await waitLoaded();

    await user.click(screen.getByText(/Backend Engineer — Tech/));

    expect(screen.getByText("Strong")).toBeInTheDocument();
    // Expanding is in-place, not a route change: createMemoryRouter's own
    // location (not window.location, which it never touches) must still be
    // the currently-viewed application's detail route.
    expect(router.state.location.pathname).toBe("/recruiting/applications/101");
  });

  it("shows previous applications for the same posting", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: {
        otherJobs: [],
        previousSameJob: [makeOtherApplication({ id: 301, stage: "rejected" })],
      },
    });
    renderPage();
    await waitLoaded();

    expect(
      await screen.findByText("Previous applications for this posting"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Applied .* — Rejected/)).toBeInTheDocument();
  });

  it("still shows other-job applications alongside same-posting history", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: {
        otherJobs: [
          makeOtherApplication({ jobTitle: "Backend Mentor", stage: "tech" }),
        ],
        previousSameJob: [makeOtherApplication({ id: 301, stage: "rejected" })],
      },
    });
    renderPage();
    await waitLoaded();

    expect(await screen.findByText(/Backend Mentor — /)).toBeInTheDocument();
    expect(
      screen.getByText("Previous applications for this posting"),
    ).toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — history row timeline and comments", () => {
  /** Render as owner with one cross-job entry, expand it, return its <li>. */
  const renderAndExpand = async (user, entry) => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [entry], previousSameJob: [] },
    });
    renderPage();
    await waitLoaded();
    const label = screen.getByText(/Backend Engineer — /);
    await user.click(label);
    return label.closest("li");
  };

  it("shows Evaluations, Timeline and Comments tabs in an expanded row", async () => {
    const user = userEvent.setup();
    const row = await renderAndExpand(user, makeOtherApplication());

    expect(
      within(row).getByRole("tab", { name: "Evaluations" }),
    ).toBeInTheDocument();
    expect(
      within(row).getByRole("tab", { name: "Timeline" }),
    ).toBeInTheDocument();
    expect(
      within(row).getByRole("tab", { name: "Comments" }),
    ).toBeInTheDocument();
  });

  it("narrates the rejection reason in the row's Timeline tab", async () => {
    const user = userEvent.setup();
    const row = await renderAndExpand(
      user,
      makeOtherApplication({
        stage: "rejected",
        activity: [
          {
            id: 2,
            eventType: "stage_changed",
            details: {
              fromStage: "tech",
              toStage: "rejected",
              reason: "Not a fit",
              note: "Weak coding round",
            },
            actorId: OWNER_ID,
            actorName: "Olga Owner",
            createdAt: "2026-07-05T12:00:00Z",
          },
        ],
      }),
    );

    await user.click(within(row).getByRole("tab", { name: "Timeline" }));

    expect(
      within(row).getByText(
        /Rejected from Tech: Not a fit — Weak coding round/,
      ),
    ).toBeInTheDocument();
  });

  it("labels timeline stages by the row's own job kind, not the viewed job's", async () => {
    // The viewed job (JOB fixture) is employment-kind; this cross-job entry
    // is an activity posting, so its hired stage must narrate as "Admitted".
    const user = userEvent.setup();
    const row = await renderAndExpand(
      user,
      makeOtherApplication({
        jobKind: "activity",
        stage: "hired",
        activity: [
          {
            id: 3,
            eventType: "stage_changed",
            details: { fromStage: "tech", toStage: "hired" },
            actorId: OWNER_ID,
            actorName: "Olga Owner",
            createdAt: "2026-07-05T12:00:00Z",
          },
        ],
      }),
    );

    await user.click(within(row).getByRole("tab", { name: "Timeline" }));

    expect(
      within(row).getByText(/Advanced from Tech to Admitted/),
    ).toBeInTheDocument();
  });

  it("renders the row's comments read-only, with no input box", async () => {
    const user = userEvent.setup();
    const row = await renderAndExpand(
      user,
      makeOtherApplication({
        comments: [
          {
            id: 5,
            applicationId: 201,
            authorId: OWNER_ID,
            authorName: "Olga Owner",
            body: "Discussed with the panel.",
            createdAt: "2026-07-06T12:00:00Z",
            mentions: [],
          },
        ],
      }),
    );

    await user.click(within(row).getByRole("tab", { name: "Comments" }));

    expect(
      within(row).getByText(/Discussed with the panel\./),
    ).toBeInTheDocument();
    expect(
      within(row).queryByPlaceholderText("Add a comment…"),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — screen-rule activity messages", () => {
  it("distinguishes a screen-rule auto-reject from a blocked-applicant auto-reject", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "auto_rejected",
          details: { reason: "screen_rule", ruleId: "r1" },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(/Automatically rejected by screening rule/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Automatically rejected \(blocked applicant\)/),
    ).not.toBeInTheDocument();
  });

  it("notes a screen-rule auto-qualify on the submission entry", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "application_submitted",
          details: {
            stage: "recruiter_screening",
            screenQualifyRuleId: "r1",
          },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Submitted — landed on Recruiter screening \(auto-qualified by screening rule\)/,
      ),
    ).toBeInTheDocument();
  });

  it("shows which rule auto-qualified on the submission entry", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "application_submitted",
          details: {
            stage: "recruiter_screening",
            screenQualifyRuleId: "r2",
            screenQualifyRuleLabel: "answer to q_role equals mentor",
          },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      await screen.findByText(
        /Submitted — landed on Recruiter screening \(auto-qualified by screening rule "answer to q_role equals mentor"\)/,
      ),
    ).toBeInTheDocument();
  });

  it("notes a screen-rule auto-hire distinctly from auto-qualify", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "application_submitted",
          details: { stage: "hired", screenAutoHireRuleId: "r1" },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Submitted — auto-approved by screening rule \(landed on Hired\)/,
      ),
    ).toBeInTheDocument();
  });

  it("shows which rule auto-hired on the submission entry", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "application_submitted",
          details: {
            stage: "hired",
            screenAutoHireRuleId: "r1",
            screenAutoHireRuleLabel: "email domain in google.com",
          },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      await screen.findByText(
        /Submitted — auto-approved by screening rule "email domain in google\.com" \(landed on Hired\)/,
      ),
    ).toBeInTheDocument();
  });

  it("shows which rule auto-rejected in the timeline", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "auto_rejected",
          details: {
            reason: "screen_rule",
            ruleId: "r1",
            ruleLabel: "email domain not in google.com",
          },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      await screen.findByText(
        /Automatically rejected by screening rule "email domain not in google\.com"/,
      ),
    ).toBeInTheDocument();
  });

  it("falls back to generic text when no rule label is present", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "auto_rejected",
          details: { reason: "screen_rule", ruleId: "r1" },
          actorId: OWNER_ID,
          actorName: "Casey Candidate",
          createdAt: "2026-07-08T12:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      await screen.findByText(/Automatically rejected by screening rule,/),
    ).toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — advance-without-evaluation soft reminder", () => {
  const renderOwner = (detailOverrides = {}) => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, ...detailOverrides }),
    });
    return renderPage();
  };

  it("clicking Advance with no confirmed evaluation opens the reminder instead of the assignee dialog", async () => {
    const user = userEvent.setup();
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(
      screen.getByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });

  it("Advance anyway continues into the assignee dialog", async () => {
    const user = userEvent.setup();
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await user.click(screen.getByRole("button", { name: "Advance anyway" }));

    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).not.toBeInTheDocument();
  });

  it("Cancel closes the reminder without advancing", async () => {
    const user = userEvent.setup();
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });

  it("a confirmed evaluation for the current round skips the reminder", async () => {
    const user = userEvent.setup();
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening")],
    });
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(
      screen.queryByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).toBeInTheDocument();
  });

  it("a draft-only evaluation still triggers the reminder", async () => {
    const user = userEvent.setup();
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [{ ...confirmedEval("recruiter_screening"), isConfirmed: false }],
    });
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(
      screen.getByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).toBeInTheDocument();
  });

  it("Advance anyway on a direct advance (no assignee dialog) calls the API straight away", async () => {
    const user = userEvent.setup();
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderOwner({ stage: "tech" });
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Offer" }));
    await user.click(screen.getByRole("button", { name: "Advance anyway" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "offer",
        assigneeId: undefined,
      }),
    );
  });

  it("Advance Round shows the reminder and continues into the round dialog on Advance anyway", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: {
        ...JOB,
        pipelineConfig: {
          ...JOB.pipelineConfig,
          stages: JOB.pipelineConfig.stages.map((s) =>
            s.stage === "tech" ? { ...s, rounds: 3 } : s,
          ),
        },
      },
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Round 2" }),
    );
    expect(
      screen.getByText(
        "This round has no confirmed evaluation yet. Advance anyway?",
      ),
    ).toBeInTheDocument();
    expect(api.setApplicationRound).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Advance anyway" }));
    expect(
      screen.getByRole("button", { name: "Confirm advance round" }),
    ).toBeInTheDocument();
  });

  it("disables the Evaluated status button while the current round has no confirmed evaluation", async () => {
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Evaluated" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "In progress" }),
    ).not.toBeDisabled();
  });

  it("enables the Evaluated status button once the current round has a confirmed evaluation", async () => {
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening")],
    });
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Evaluated" }),
    ).not.toBeDisabled();
  });

  it("marks advances recorded without an evaluation in the timeline", async () => {
    const user = userEvent.setup();
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "stage_changed",
          details: {
            fromStage: "recruiter_screening",
            toStage: "tech",
            advancedWithoutEvaluation: true,
          },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-18T12:00:00Z",
        },
        {
          id: 2,
          eventType: "round_advanced",
          details: {
            stage: "tech",
            fromRound: 1,
            toRound: 2,
            advancedWithoutEvaluation: true,
          },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-18T11:00:00Z",
        },
      ],
    });
    renderOwner({ stage: "tech" });
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Advanced from Recruiter screening to Tech \(no evaluation recorded\), by Owen Owner/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Advanced to round 2 of Tech \(no evaluation recorded\), by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — evaluator candidate history", () => {
  // A previous attempt at THIS posting, carrying a prior evaluation.
  const previousAttempt = makeOtherApplication({
    id: 301,
    jobTitle: "Mentor",
    stage: "tech",
    evaluations: [
      {
        id: 50,
        stage: "tech",
        round: 1,
        evaluatorId: 77, // deliberately not in INTERVIEW_POOL
        // "correctness" (not "bg_strength") is a valid tech-rubric field id,
        // matching this fixture's "tech" stage (rubricFor("tech") has no
        // bg_strength field, so that id would silently render nothing).
        responses: { correctness: { value: 2, notes: "prior-attempt note" } },
        isConfirmed: true,
      },
    ],
    activity: [], // backend empties these for a pure assignee
    comments: [],
  });

  it("shows the history panels to the current-stage assignee in evaluate mode", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [], previousSameJob: [previousAttempt] },
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.getByText("Previous applications for this posting"),
    ).toBeInTheDocument();
    expect(api.getOtherApplications).toHaveBeenCalledWith("101");
    // Must NOT pull the current application's own audit timeline for an assignee.
    expect(api.getApplicationActivity).not.toHaveBeenCalled();
  });

  it("expands a history entry to show evaluations but no Timeline/Comments tabs", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [], previousSameJob: [previousAttempt] },
    });
    renderEvaluatorPage();
    await waitLoaded();

    const viewButton = screen.getByRole("button", { name: /View/ });
    await user.click(viewButton);
    // Scoped to the expanded row: the page's own rubric-form Tabs also has
    // a "Comments" tab trigger (unrelated to this history row), so an
    // unscoped query would find that one instead.
    const row = viewButton.closest("li");

    // Prior evaluation (with score/notes) is shown...
    expect(within(row).getByText(/prior-attempt note/)).toBeInTheDocument();
    // ...but the reduced view exposes no audit/comment tabs.
    expect(
      within(row).queryByRole("tab", { name: "Timeline" }),
    ).not.toBeInTheDocument();
    expect(
      within(row).queryByRole("tab", { name: "Comments" }),
    ).not.toBeInTheDocument();
  });

  it("does not show history to an evaluate-mode viewer who is not the current assignee", async () => {
    authState.userId = 999; // neither owner nor assignee
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        canView: false,
        assigneeId: ASSIGNEE_ID,
      }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [], previousSameJob: [previousAttempt] },
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.getByText(
        "You are not currently assigned to evaluate this application.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Previous applications for this posting"),
    ).not.toBeInTheDocument();
    expect(api.getOtherApplications).not.toHaveBeenCalled();
  });

  it("degrades to 'User {id}' and still loads when the interview pool is unreadable", async () => {
    const user = userEvent.setup();
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [], previousSameJob: [previousAttempt] },
    });
    api.listInterviewPool.mockRejectedValue(new Error("Forbidden"));
    renderEvaluatorPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: /View/ }));
    expect(screen.getByText(/Evaluated by: User 77/)).toBeInTheDocument();
  });

  it("renders no history panel when the candidate has none", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    // beforeEach already stubs getOtherApplications -> empty.
    renderEvaluatorPage();
    await waitLoaded();

    expect(
      screen.queryByText("Previous applications for this posting"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Other applications")).not.toBeInTheDocument();
  });
});
