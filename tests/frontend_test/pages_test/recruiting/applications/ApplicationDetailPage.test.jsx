import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
// The signature block the templates endpoint now ships on its own, so the
// composer can prefill it into an empty body.
const SIGNATURE_HTML =
  "<p>Best,<br><strong>Jane Smith</strong><br>Director of People Operations<br>Circle Cat Inc</p>";
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
  answers: { q1: "Yes", q2: "Remote", q3: "First line.\nSecond line." },
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
  formSchema: {
    questions: [{ id: "q9", type: "short_text", label: "Availability?" }],
  },
});

/** Build an ApplicationDetailDto-shaped payload for a given role/stage. */
const makeDetail = ({
  isOwner = false,
  canView = isOwner,
  assigneeId = ASSIGNEE_ID,
  stage = "recruiter_screening",
  resumeAvailable = true,
  currentRound,
  interview = null,
  viewerTimezone = "America/Los_Angeles",
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
    questions: [
      { id: "q1", type: "short_text", label: "Are you authorized to work?" },
      { id: "q3", type: "long_text", label: "Anything else?" },
    ],
  },
  isOwner,
  canView,
  assigneeId,
  interview,
  viewerTimezone,
});

/** An InterviewDto-shaped fixture, as the detail endpoint's `interview` field. */
const INTERVIEW_FIXTURE = {
  interviewId: 7,
  stage: "behavioral",
  round: 1,
  startAt: "2026-08-05T21:00:00Z",
  endAt: "2026-08-05T21:45:00Z",
  meetLink: "https://meet.google.com/abc-defg-hij",
  assigneeId: ASSIGNEE_ID,
  assigneeName: "Eve Evaluator",
  scheduledByName: "Jane Smith",
};

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
  api.getApplicationEmails.mockResolvedValue({
    data: { threads: [], defaultTo: null },
  });
  api.sendApplicationEmail.mockResolvedValue({
    data: { threads: [], defaultTo: null },
  });
  api.getApplicationEmailTemplates.mockResolvedValue({
    data: { templates: [], signatureHtml: "" },
  });
  api.scheduleInterview.mockResolvedValue({ data: {} });
  api.updateInterview.mockResolvedValue({ data: {} });
  api.cancelInterview.mockResolvedValue({ data: null });
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

/** Render the page in the evaluator-only view (the My Interview Evaluations link). */
const renderEvaluatorPage = (applicationId = 101) =>
  renderPage(applicationId, "?mode=evaluate");

/** Wait until the applicant identity has rendered (page has loaded). */
const waitLoaded = () =>
  waitFor(() =>
    expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
  );

describe("ApplicationDetailPage — interview times follow the viewer", () => {
  it("renders the meeting in the zone the payload says the viewer is in", async () => {
    // Same instant as every other fixture; a reader in Taipei sees 21:00Z as
    // 05:00 the NEXT day. Mutation check -- render a fixed zone and this fails.
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "behavioral",
        interview: INTERVIEW_FIXTURE,
        viewerTimezone: "Asia/Taipei",
      }),
    });
    renderPage();
    await waitLoaded();

    expect(await screen.findByText(/2026-08-06/)).toBeInTheDocument();
    expect(screen.getByText(/05:00 - 05:45/)).toBeInTheDocument();
    expect(screen.getByText(/Asia\/Taipei/)).toBeInTheDocument();
  });

  it("falls back to the browser zone when the viewer has set none", async () => {
    // A profile with no timezone must still read as local time, not as
    // somebody else's zone and not as UTC-by-accident.
    const resolved = Intl.DateTimeFormat().resolvedOptions();
    const spy = vi
      .spyOn(Intl, "DateTimeFormat")
      .mockImplementation((locale, options) =>
        options
          ? new Intl.DateTimeFormat.prototype.constructor(locale, options)
          : {
              resolvedOptions: () => ({ ...resolved, timeZone: "Asia/Taipei" }),
            },
      );
    try {
      authState.userId = OWNER_ID;
      api.getApplicationDetail.mockResolvedValue({
        data: makeDetail({
          isOwner: true,
          stage: "behavioral",
          interview: INTERVIEW_FIXTURE,
          viewerTimezone: null,
        }),
      });
      renderPage();
      await waitLoaded();

      expect(await screen.findByText(/Asia\/Taipei/)).toBeInTheDocument();
    } finally {
      spy.mockRestore();
    }
  });
});

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
    // A question still on the live form uses its label.
    expect(
      screen.getByText(/Are you authorized to work\?/),
    ).toBeInTheDocument();
    // An answer whose question was removed is kept, not dropped.
    expect(screen.getByText("Other recorded answers")).toBeInTheDocument();
    expect(screen.getByText("q2")).toBeInTheDocument();
    // A long answer keeps its line breaks.
    expect(screen.getByText(/First line\./).textContent).toBe(
      "First line.\nSecond line.",
    );
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

  it("owner-only viewer sees no How-it-works button", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.queryByRole("button", { name: "How it works" }),
    ).not.toBeInTheDocument();
  });

  // Wording lives in the glossary and is asserted there; what this pins is
  // that the Status label is a hint trigger at all.
  it("hangs the edit-lock hint on the Status label", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Status:" })).toBeInTheDocument();
  });

  it("states how far blacklisting reaches before it is confirmed", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    authState.permissions = [
      ...authState.permissions,
      "recruiting.blacklist.write",
    ];
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    // Opening the dialog also fetches the applicant's upcoming interviews to
    // list them; an empty list is what proves the blast-radius sentence is
    // unconditional rather than riding on that list.
    api.listBlacklistUpcomingInterviews.mockResolvedValue({ data: [] });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Blacklist" }));

    expect(
      await screen.findByText(/closes every other application they hold/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/including any that already reached Hired/),
    ).toBeInTheDocument();
  });

  it("assignee-only viewer in evaluator mode sees no How-it-works button", async () => {
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

    expect(
      screen.queryByRole("button", { name: "How it works" }),
    ).not.toBeInTheDocument();
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
  // Behavioral/tech are now excluded from this dialog entirely (their
  // interviewer is set via the interview meeting card's own dialog
  // instead -- see ASSIGNEE_VIA_CARD_STAGES), so these tests exercise it
  // via "board_review", the one remaining INTERVIEW_STAGES member whose
  // assignee is still picked here. board_review isn't a PREFILL_TARGET_STAGES
  // member either, so it always starts on "Decide later".
  const jobWithBoardReview = {
    ...JOB,
    pipelineConfig: {
      ...JOB.pipelineConfig,
      stages: [
        ...JOB.pipelineConfig.stages,
        { stage: "board_review", rounds: 1 },
      ],
    },
  };

  beforeEach(() => {
    api.getJob.mockResolvedValue({ data: jobWithBoardReview });
    // Exercise the assignee dialog itself; seed a confirmed evaluation for
    // the stage advanced from so the no-evaluation reminder (covered by its
    // own describe) stays out of the way.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("tech")],
    });
  });

  it("clicking Advance to Board review opens a dialog defaulting to Decide later", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
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

    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("button", { name: "Confirm advance" }),
    ).not.toBeDisabled();
  });

  it("advances with no assignee when the picker is left blank, instead of blocking the confirm", async () => {
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Board review" }),
    );
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "board_review",
        assigneeId: undefined,
      }),
    );
  });

  it("advances with a manually picked assignee", async () => {
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

    await user.click(
      screen.getByRole("button", { name: "Advance to Board review" }),
    );
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "board_review",
        assigneeId: 11,
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
        stage: "tech",
      }),
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Board review" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
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
      screen.getByRole("button", { name: "Advance to Session 2" }),
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

  /** The base JOB fixture with one stage's `rounds` overridden. */
  const jobWithStageRounds = (stage, rounds) => ({
    ...JOB,
    pipelineConfig: {
      ...JOB.pipelineConfig,
      stages: JOB.pipelineConfig.stages.map((s) =>
        s.stage === stage ? { ...s, rounds } : s,
      ),
    },
  });
  const jobWithTechRounds = (rounds) => jobWithStageRounds("tech", rounds);

  it("shows the Advance Round button when the stage supports multiple rounds and the applicant hasn't reached the last one", async () => {
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({ data: jobWithTechRounds(3) });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "tech", currentRound: 1 }),
    });
    renderPage();
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Advance to Session 2" }),
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
      screen.queryByRole("button", { name: /Advance to Session/ }),
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
      screen.queryByRole("button", { name: /Advance to Session/ }),
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
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );

    // Tech is card-managed (ASSIGNEE_VIA_CARD_STAGES): the round-advance
    // dialog still opens, but without a generic assignee picker.
    expect(
      screen.queryByRole("radio", { name: /decide later/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm advance session" }),
    ).not.toBeDisabled();
    expect(api.setApplicationRound).not.toHaveBeenCalled();
  });

  it("keeps the generic assignee picker for a round-advance on a non-card stage", async () => {
    // Recruiter screening isn't in ASSIGNEE_VIA_CARD_STAGES, so its
    // round-advance dialog keeps the generic PeoplePicker, defaulting to
    // "Decide later".
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: jobWithStageRounds("recruiter_screening", 3),
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "recruiter_screening",
        currentRound: 1,
      }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening", 1)],
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );

    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("button", { name: "Confirm advance session" }),
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
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm advance session" }),
    );

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith(
        "101",
        2,
        undefined,
        undefined,
      ),
    );
  });

  it("picking an assignee and confirming calls setApplicationRound with the assignee and updates the displayed round", async () => {
    // Uses recruiter_screening (not card-managed) so the round-advance
    // dialog's generic PeoplePicker is present to pick from.
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: jobWithStageRounds("recruiter_screening", 3),
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "recruiter_screening",
        currentRound: 1,
      }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening", 1)],
    });
    api.setApplicationRound.mockResolvedValue({ data: {} });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    const confirmButton = screen.getByRole("button", {
      name: "Confirm advance session",
    });
    expect(confirmButton).not.toBeDisabled();
    await user.click(confirmButton);

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith(
        "101",
        2,
        11,
        undefined,
      ),
    );
    // Local state patched in place: the button now reflects round 2 -> 3.
    expect(
      await screen.findByRole("button", { name: "Advance to Session 3" }),
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
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("button", { name: "Confirm advance session" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    ).toBeInTheDocument();
    expect(api.setApplicationRound).not.toHaveBeenCalled();
  });

  it("surfaces a toast error when advancing the round fails", async () => {
    // Uses recruiter_screening so the assignee picker is present to pick
    // from, mirroring the "picking an assignee" test above.
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getJob.mockResolvedValue({
      data: jobWithStageRounds("recruiter_screening", 3),
    });
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "recruiter_screening",
        currentRound: 1,
      }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening", 1)],
    });
    api.setApplicationRound.mockRejectedValue(new Error("Round update failed"));
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    await user.click(screen.getByRole("radio", { name: /ivan interviewer/i }));
    await user.click(
      screen.getByRole("button", { name: "Confirm advance session" }),
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
          eventType: "recruiting.stage_changed",
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
          eventType: "recruiting.stage_changed",
          details: { fromStage: "recruiter_screening", toStage: "tech" },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T12:00:00Z",
        },
        {
          id: 2,
          eventType: "recruiting.reassigned",
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

  it("narrates email_sent and email_received timeline entries", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "recruiting.email_sent",
          details: {
            subject: "Interview Availability",
            to: ["cand@x.com"],
            cc: ["boss@x.com"],
            direction: "outbound",
          },
          actorId: OWNER_ID,
          actorName: "Owen Owner",
          createdAt: "2026-07-04T12:00:00Z",
        },
        {
          id: 2,
          eventType: "recruiting.email_received",
          details: {
            subject: "Re: Interview Availability",
            from: "cand@x.com",
            direction: "inbound",
          },
          actorId: 3,
          actorName: "Cara Candidate",
          createdAt: "2026-07-04T13:00:00Z",
        },
      ],
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(
      screen.getByText(
        /Sent email "Interview Availability" to cand@x\.com, cc boss@x\.com, by Owen Owner/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Received reply "Re: Interview Availability" from cand@x\.com, by Cara Candidate/,
      ),
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
          eventType: "recruiting.stage_changed",
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
      eventType: "recruiting.stage_changed",
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
      eventType: "recruiting.round_advanced",
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
        /Advanced to session 2 of Tech, assigned to Ivan Interviewer, by Owen Owner/,
      ),
    ).toBeInTheDocument();
  });

  it("shows both names when reassigning from a previous assignee", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "recruiting.reassigned",
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
      eventType: "recruiting.auto_assigned",
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
      eventType: "recruiting.sub_status_changed",
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
      eventType: "recruiting.stage_changed",
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
        "Schedule this interview's meeting first — booking one (see the Interview Meeting card above) assigns the interviewer automatically.",
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
        "Schedule this interview's meeting first — booking one (see the Interview Meeting card above) assigns the interviewer automatically.",
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
        "Schedule this interview's meeting first — booking one (see the Interview Meeting card above) assigns the interviewer automatically.",
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
        "Schedule this interview's meeting first — booking one (see the Interview Meeting card above) assigns the interviewer automatically.",
      ),
    ).not.toBeInTheDocument();
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

  it("labels an expanded other application's answers with its own job's form", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    api.getOtherApplications.mockResolvedValue({
      data: { otherJobs: [makeOtherApplication({})], previousSameJob: [] },
    });
    renderPage();
    await waitLoaded();

    await userEvent.click(screen.getByRole("button", { name: /View/ }));

    expect(screen.getByText("Availability?")).toBeInTheDocument();
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
            eventType: "recruiting.stage_changed",
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
            eventType: "recruiting.stage_changed",
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
          eventType: "recruiting.auto_rejected",
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

  it("names the landing stage on an unscreened submission entry", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "recruiting.application_submitted",
          details: { stage: "recruiter_screening" },
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
      screen.getByText(/Submitted — landed on Recruiter screening/),
    ).toBeInTheDocument();
  });

  it("notes a screen-rule auto-hire on the submission entry", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.getApplicationActivity.mockResolvedValue({
      data: [
        {
          id: 1,
          eventType: "recruiting.application_submitted",
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
          eventType: "recruiting.application_submitted",
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
          eventType: "recruiting.auto_rejected",
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
          eventType: "recruiting.auto_rejected",
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
        "This session has no confirmed evaluation yet. Advance anyway?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });

  it("Advance anyway on a behavioral target (no assignee dialog) calls the API straight away", async () => {
    // Behavioral is now excluded from the assignee-picker dialog (its
    // interviewer is set via the interview meeting card instead), so
    // "Advance anyway" goes straight to the API, mirroring how a
    // non-interview target (e.g. Offer) already worked.
    const user = userEvent.setup();
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );
    await user.click(screen.getByRole("button", { name: "Advance anyway" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "behavioral",
        assigneeId: undefined,
      }),
    );
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
        "This session has no confirmed evaluation yet. Advance anyway?",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm advance" }),
    ).not.toBeInTheDocument();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });

  it("a confirmed evaluation for the current session skips the reminder", async () => {
    const user = userEvent.setup();
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening")],
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(
      screen.queryByText(
        "This session has no confirmed evaluation yet. Advance anyway?",
      ),
    ).not.toBeInTheDocument();
    // No reminder AND no assignee dialog for a behavioral target -- the
    // advance goes straight through.
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "behavioral",
        assigneeId: undefined,
      }),
    );
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
        "This session has no confirmed evaluation yet. Advance anyway?",
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
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    expect(
      screen.getByText(
        "This session has no confirmed evaluation yet. Advance anyway?",
      ),
    ).toBeInTheDocument();
    expect(api.setApplicationRound).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Advance anyway" }));
    expect(
      screen.getByRole("button", { name: "Confirm advance session" }),
    ).toBeInTheDocument();
  });

  it("disables the Evaluated status button while the current session has no confirmed evaluation", async () => {
    renderOwner({ stage: "recruiter_screening" });
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Evaluated" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "In progress" }),
    ).not.toBeDisabled();
  });

  it("enables the Evaluated status button once the current session has a confirmed evaluation", async () => {
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
          eventType: "recruiting.stage_changed",
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
          eventType: "recruiting.round_advanced",
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
        /Advanced to session 2 of Tech \(no evaluation recorded\), by Owen Owner/,
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

describe("ApplicationDetailPage — Emails tab", () => {
  const ownerViewing = () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
  };

  it("owner sees the Emails tab and stored threads render", async () => {
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: {
        defaultTo: "cand@x.com",
        threads: [
          {
            threadId: 1,
            subject: "Interview Availability",
            messages: [
              {
                messageId: 11,
                direction: "outbound",
                fromAddress: "recruiting@circlecat.org",
                bodyHtml: "<p>Hello there</p>",
                bodyText: "Hello there",
                createdAt: "2026-07-23T00:00:00Z",
              },
            ],
          },
        ],
      },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    expect(screen.getByText("Interview Availability")).toBeInTheDocument();
    expect(screen.getByText("Hello there")).toBeInTheDocument();
  });

  it("styles a received body so paragraphs, lists and links stay readable", async () => {
    // Tailwind's preflight zeroes <p> margins, drops list markers and strips
    // link underlines and colour. A mail body rendered without these hooks
    // arrives as one dense block with invisible bullets and links that look
    // exactly like ordinary text.
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: {
        defaultTo: "cand@x.com",
        threads: [
          {
            threadId: 1,
            subject: "Interview Availability",
            messages: [
              {
                messageId: 11,
                direction: "inbound",
                fromAddress: "cand@x.com",
                bodyHtml:
                  "<p>first para</p><p>second para</p><ul><li>bullet</li></ul>" +
                  '<p><a href="https://x.test">a link</a></p>',
                bodyText: "first para",
                createdAt: "2026-07-23T00:00:00Z",
              },
            ],
          },
        ],
      },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    const body = screen.getByText("first para").parentElement;
    expect(body.className).toContain("[&_p]:my-3");
    expect(body.className).toContain("[&_ul]:list-disc");
    expect(body.className).toContain("[&_ol]:list-decimal");
    expect(body.className).toContain("[&_a]:underline");
  });

  it("spaces the paragraphs of a template applied into the compose body", async () => {
    // Templates are paragraphs of HTML, and Tailwind's preflight zeroes <p>
    // margins — without a spacing hook an applied template collapses into one
    // block in the editor, even though the mail itself goes out fine.
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    await user.click(screen.getByRole("button", { name: "Send email" }));
    const editor = screen.getByRole("textbox", { name: "Message" });
    expect(editor.className).toContain("[&_p]:my-3");
  });

  it("owner composes and sends a new email", async () => {
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.type(screen.getByLabelText("Subject"), "Hi there");
    await user.type(screen.getByLabelText("Message"), "welcome");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(api.sendApplicationEmail).toHaveBeenCalledWith("101", {
        to: ["cand@x.com"],
        cc: [],
        subject: "Hi there",
        body: "welcome",
        threadId: null,
      }),
    );
    expect(toast.success).toHaveBeenCalledWith("Email sent.");
  });

  it("new compose prefills Cc from conversation defaultCc, editable", async () => {
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com", defaultCc: ["rec@x.com"] },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    await user.click(screen.getByRole("button", { name: "Send email" }));
    const ccField = screen.getByLabelText("Cc");
    expect(ccField).toHaveValue("rec@x.com");
    // still editable
    await user.type(ccField, ", extra@x.com");
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.type(screen.getByLabelText("Message"), "welcome");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(api.sendApplicationEmail).toHaveBeenCalledWith("101", {
        to: ["cand@x.com"],
        cc: ["rec@x.com", "extra@x.com"],
        subject: "Hi",
        body: "welcome",
        threadId: null,
      }),
    );
  });

  it("reply prefills Cc from the thread defaultCc", async () => {
    ownerViewing();
    api.getApplicationEmails.mockResolvedValue({
      data: {
        defaultTo: "cand@x.com",
        defaultCc: ["rec@x.com"],
        threads: [
          {
            threadId: 1,
            subject: "Interview Availability",
            defaultCc: ["rec@x.com", "boss@x.com"],
            messages: [
              {
                messageId: 11,
                direction: "outbound",
                fromAddress: "recruiting@circlecat.org",
                bodyHtml: "<p>Hello there</p>",
                bodyText: "Hello there",
                createdAt: "2026-07-23T00:00:00Z",
              },
            ],
          },
        ],
      },
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    await user.click(screen.getByRole("button", { name: "Reply" }));
    expect(screen.getByLabelText("Cc")).toHaveValue("rec@x.com, boss@x.com");
  });

  it("Refresh re-fetches with refresh=true", async () => {
    ownerViewing();
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    api.getApplicationEmails.mockClear();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() =>
      expect(api.getApplicationEmails).toHaveBeenCalledWith("101", {
        refresh: true,
      }),
    );
    expect(toast.success).toHaveBeenCalledWith("Refreshed.");
  });

  /**
   * Render the page as the application's owner, switch to the Emails tab and
   * open the compose dialog (Reply on the first thread when `replyThread`,
   * otherwise a fresh Send email). Query with `screen.*` afterwards.
   *
   * @param {{replyThread?: boolean}} [options]
   */
  const renderComposeOpen = async ({ replyThread = false } = {}) => {
    ownerViewing();
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    await user.click(
      screen.getByRole("button", {
        name: replyThread ? "Reply" : "Send email",
      }),
    );
    return user;
  };

  /**
   * Put HTML into the contenteditable body. There is no execCommand in jsdom
   * and userEvent cannot type markup, so write innerHTML and fire the input
   * event the component listens on.
   *
   * @param {string} html
   */
  const setEditorHtml = (html) => {
    const editor = screen.getByRole("textbox", { name: "Message" });
    editor.innerHTML = html;
    fireEvent.input(editor);
    return editor;
  };

  const editorEl = () => screen.getByRole("textbox", { name: "Message" });

  it("prefills the signature into a new email", async () => {
    // The signature only ever lived inside the eight templates, so anything
    // written from scratch went out unsigned.
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: { templates: [], signatureHtml: SIGNATURE_HTML },
    });
    await renderComposeOpen();
    await waitFor(() => expect(editorEl().innerHTML).toBe(SIGNATURE_HTML));
  });

  it("highlights an unfilled marker inside the prefilled signature", async () => {
    // A sender with no name anywhere gets [YOUR NAME] in the signature. The
    // send-time warning already counts it, but it has to be *visible* too —
    // that is the whole reason the backend renders a marker instead of a blank.
    const unnamed =
      "<p>Best,<br><strong>[YOUR NAME]</strong><br>Director of People Operations</p>";
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: { templates: [], signatureHtml: unnamed },
    });
    await renderComposeOpen();
    await waitFor(() =>
      expect(editorEl().innerHTML).toContain("<mark>[YOUR NAME]</mark>"),
    );
  });

  it("prefills the signature into a reply too", async () => {
    // Replies never apply a template (they keep their `Re:` subject), so
    // without this every single reply went out unsigned.
    api.getApplicationEmails.mockResolvedValue({
      data: {
        defaultTo: "cand@x.com",
        threads: [
          {
            threadId: 1,
            subject: "Interview Availability",
            messages: [
              {
                messageId: 11,
                direction: "inbound",
                fromAddress: "cand@x.com",
                bodyHtml: "<p>Hello there</p>",
                bodyText: "Hello there",
                createdAt: "2026-07-23T00:00:00Z",
              },
            ],
          },
        ],
      },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: { templates: [], signatureHtml: SIGNATURE_HTML },
    });
    await renderComposeOpen({ replyThread: true });
    await waitFor(() => expect(editorEl().innerHTML).toBe(SIGNATURE_HTML));
  });

  it("does not ask to overwrite when the body is only the prefilled signature", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "Your Application to Circle Cat",
            bodyHtml: `<p>Dear Ana,</p>${SIGNATURE_HTML}`,
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    await waitFor(() => expect(editorEl().innerHTML).toBe(SIGNATURE_HTML));
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));
    // Applied straight away: an untouched prefill is not the recruiter's draft.
    expect(
      screen.queryByRole("button", { name: "Replace" }),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(editorEl().textContent).toContain("Dear Ana,"));
  });

  it("keeps text typed before the signature arrives", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    let resolveTemplates;
    api.getApplicationEmailTemplates.mockReturnValue(
      new Promise((resolve) => {
        resolveTemplates = resolve;
      }),
    );
    await renderComposeOpen();
    setEditorHtml("<p>my own draft</p>");
    resolveTemplates({
      data: { templates: [], signatureHtml: SIGNATURE_HTML },
    });
    await waitFor(() => expect(editorEl().innerHTML).toContain("my own draft"));
    expect(editorEl().innerHTML).not.toContain("Director of People Operations");
  });

  it("sends the contenteditable HTML, not escaped text", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml(
      '<p>Hello <b>Ana</b>, see <a href="https://x.com">this</a></p>',
    );
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(api.sendApplicationEmail).toHaveBeenCalledWith("101", {
        to: ["cand@x.com"],
        cc: [],
        subject: "Hi",
        body: '<p>Hello <b>Ana</b>, see <a href="https://x.com">this</a></p>',
        threadId: null,
      }),
    );
  });

  it("strips disallowed markup before sending", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml('<p onclick="x()">Hi<script>bad()</script></p>');
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(api.sendApplicationEmail).toHaveBeenCalled());
    const sent = api.sendApplicationEmail.mock.calls[0][1].body;
    expect(sent).not.toContain("script");
    expect(sent).not.toContain("onclick");
    expect(sent).toContain("Hi");
  });

  it("keeps Send disabled while the editor has no text", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    await user.type(screen.getByLabelText("Subject"), "Hi");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    // Markup without text (an empty paragraph) still counts as no message.
    setEditorHtml("<p></p>");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    setEditorHtml("<p>Now there is text</p>");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("clears the editor between composes", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>First draft</p>");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Send email" }));
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveTextContent(
      "",
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("fills subject and body from the chosen template on a new email", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "Your Application to Circle Cat",
            bodyHtml: "<p>Dear Ana,</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));

    expect(screen.getByLabelText(/subject/i)).toHaveValue(
      "Your Application to Circle Cat",
    );
    expect(
      screen.getByRole("textbox", { name: /message/i }).innerHTML,
    ).toContain("Dear Ana,");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("keeps the reply subject when a template is applied", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: {
        defaultTo: "cand@x.com",
        threads: [
          {
            threadId: 9,
            subject: "Circle Cat Program - Interview Availability",
            defaultCc: [],
            messages: [
              {
                messageId: 1,
                direction: "inbound",
                fromAddress: "cand@x.com",
                bodyHtml: "<p>Hi</p>",
                bodyText: "Hi",
                createdAt: "2026-07-23T00:00:00Z",
              },
            ],
          },
        ],
      },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "offer_onboarding",
            label: "Offer and onboarding",
            subject: "Welcome to Circle Cat — Onboarding & Next Steps",
            bodyHtml: "<p>Dear Ana,</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen({ replyThread: true });
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(
      screen.getByRole("option", { name: "Offer and onboarding" }),
    );

    expect(screen.getByLabelText(/subject/i)).toHaveValue(
      "Re: Circle Cat Program - Interview Availability",
    );
  });

  it("asks before overwriting a body the sender already typed", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "S",
            bodyHtml: "<p>T</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    const editor = setEditorHtml("<p>my own draft</p>");

    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));

    expect(
      screen.getByText(/replace what you have written/i),
    ).toBeInTheDocument();
    expect(editor.innerHTML).toContain("my own draft");

    await user.click(screen.getByRole("button", { name: /replace/i }));
    expect(editor.innerHTML).toContain("T");
  });

  it("leaves the template trigger unchanged after Cancel", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "S",
            bodyHtml: "<p>T</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>my own draft</p>");

    const trigger = screen.getByRole("combobox", { name: /template/i });
    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: "Rejection" }));
    const confirmDialog = screen.getByRole("dialog", {
      name: /replace the current message/i,
    });

    await user.click(
      within(confirmDialog).getByRole("button", { name: "Cancel" }),
    );

    // The trigger is a pure action control now (its committed value never
    // leaves ""), so it can never name a template; the "Applied: <label>"
    // text beside it is the only thing that reports an application, and a
    // cancelled overwrite must not produce it either.
    expect(trigger).not.toHaveTextContent("Rejection");
    expect(screen.queryByText(/applied:/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/replace what you have written/i),
    ).not.toBeInTheDocument();
  });

  it("prompts again when the same template is re-picked after Cancel", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "S",
            bodyHtml: "<p>T</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>my own draft</p>");

    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));
    const firstConfirmDialog = screen.getByRole("dialog", {
      name: /replace the current message/i,
    });
    await user.click(
      within(firstConfirmDialog).getByRole("button", { name: "Cancel" }),
    );
    expect(
      screen.queryByText(/replace what you have written/i),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));

    expect(
      screen.getByText(/replace what you have written/i),
    ).toBeInTheDocument();
  });

  it("re-applies the same template when it is picked again after the body was edited", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "rejection",
            label: "Rejection",
            subject: "S",
            bodyHtml: "<p>Template body</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));
    expect(
      screen.getByRole("textbox", { name: /message/i }).innerHTML,
    ).toContain("Template body");
    expect(screen.getByText("Applied: Rejection")).toBeInTheDocument();

    // Hand-edit the applied template into something the sender wants thrown
    // away, then reach for the very same template again.
    const editor = setEditorHtml("<p>mangled draft</p>");
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Rejection" }));

    // The pick has to register even though the same template is already
    // applied: the Select's committed value is held at "", so Radix's
    // controlled-setter guard sees "rejection" !== "" and forwards
    // onValueChange. Were the applied key the Select's value, this pick would
    // be a silent no-op and the sender would be stuck with the mangled body.
    expect(
      screen.getByText(/replace what you have written/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /replace/i }));
    expect(editor.innerHTML).toContain("Template body");
    expect(editor.innerHTML).not.toContain("mangled draft");
    expect(screen.getByText("Applied: Rejection")).toBeInTheDocument();
  });

  it("highlights unfilled bracket markers in the editor", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "interview_rescheduled",
            label: "Interview rescheduled",
            subject: "S",
            bodyHtml: "<p>rescheduled to [INTERVIEW DATE/TIME].</p>",
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(
      screen.getByRole("option", { name: "Interview rescheduled" }),
    );

    const editor = screen.getByRole("textbox", { name: /message/i });
    expect(editor.querySelectorAll("mark")).toHaveLength(1);
    expect(editor.querySelector("mark").textContent).toBe(
      "[INTERVIEW DATE/TIME]",
    );
  });

  it("warns once before sending a body with unfilled markers", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>on [INTERVIEW DATE/TIME] with [MANAGER NAME]</p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(screen.getByText(/2 placeholders/i)).toBeInTheDocument();
    expect(api.sendApplicationEmail).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /send anyway/i }));
    expect(api.sendApplicationEmail).toHaveBeenCalledTimes(1);
  });

  it("uses singular wording when exactly one placeholder is left", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    // One marker is the common case: interview_rescheduled carries exactly one.
    setEditorHtml("<p>rescheduled to [INTERVIEW DATE/TIME]</p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(
      screen.getByText(/still has 1 placeholder in square brackets/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/1 placeholders/i)).not.toBeInTheDocument();
  });

  it("keeps Send disabled while the recipient or subject is empty, body text notwithstanding", async () => {
    // A candidate with no contact email: the composer opens with To empty.
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: null },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>Ready to go</p>");
    const send = screen.getByRole("button", { name: /^send$/i });
    expect(send).toBeDisabled();

    // Body plus subject is still not enough without a recipient — handleSubmit
    // would return silently, so the button must not invite the click.
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    expect(send).toBeDisabled();

    await user.type(screen.getByLabelText("To"), "cand@x.com");
    expect(send).toBeEnabled();

    await user.clear(screen.getByLabelText(/subject/i));
    expect(send).toBeDisabled();
  });

  it("does not strip the marker text itself when sending anyway", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>on <mark>[INTERVIEW DATE/TIME]</mark></p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));
    await user.click(screen.getByRole("button", { name: /send anyway/i }));

    const sent = api.sendApplicationEmail.mock.calls[0][1].body;
    expect(sent).not.toContain("<mark>");
    expect(sent).toContain("[INTERVIEW DATE/TIME]");
  });

  it("sends straight away when no markers remain", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml("<p>all filled in</p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(api.sendApplicationEmail).toHaveBeenCalledTimes(1);
  });

  it("recognizes only fully-uppercase brackets as markers, not ordinary bracketed prose", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const MUST_MATCH = [
      "[INTERVIEW DATE/TIME]",
      "[SOFTWARE ENGINEER VOLUNTEER / SOFTWARE ENGINEER INTERN]",
      "[MANAGER NAME]",
      "[MANAGER EMAIL]",
      "[START DATE]",
    ];
    const MUST_NOT_MATCH = [
      "[See attached resume]",
      "[Note: pending]",
      "[Re: interview]",
    ];
    api.getApplicationEmailTemplates.mockResolvedValue({
      data: {
        templates: [
          {
            key: "mixed",
            label: "Mixed brackets",
            subject: "S",
            bodyHtml: `<p>${[...MUST_MATCH, ...MUST_NOT_MATCH].join(" ")}</p>`,
          },
        ],
        signatureHtml: SIGNATURE_HTML,
      },
    });
    const user = await renderComposeOpen();
    await user.click(screen.getByRole("combobox", { name: /template/i }));
    await user.click(screen.getByRole("option", { name: "Mixed brackets" }));

    // highlightBrackets: only the 5 real markers get wrapped, in order, and
    // the regex's shared `lastIndex` (it carries the `g` flag) doesn't skip
    // any of them when they all appear in a single pass.
    const editor = screen.getByRole("textbox", { name: /message/i });
    const marks = Array.from(editor.querySelectorAll("mark"));
    expect(marks.map((m) => m.textContent)).toEqual(MUST_MATCH);

    // countUnfilledBrackets: sending should warn about exactly the 5 real
    // markers, not the 8 total bracketed phrases in the body.
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));
    expect(screen.getByText(/5 placeholders/i)).toBeInTheDocument();
  });

  it("does not warn when the body only has ordinary bracketed prose, no real markers", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    const user = await renderComposeOpen();
    setEditorHtml(
      "<p>[See attached resume] [Note: pending] [Re: interview]</p>",
    );
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    expect(api.sendApplicationEmail).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByText(/unfilled placeholders/i),
    ).not.toBeInTheDocument();
  });

  it("disables Send anyway while the send is in flight, to prevent a double-submit", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    let resolveSend;
    api.sendApplicationEmail.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );
    const user = await renderComposeOpen();
    setEditorHtml("<p>on [INTERVIEW DATE/TIME]</p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    const sendAnyway = screen.getByRole("button", { name: /send anyway/i });
    await user.click(sendAnyway);
    expect(sendAnyway).toBeDisabled();

    // A second click while the first send is still pending must not fire again.
    await user.click(sendAnyway);
    expect(api.sendApplicationEmail).toHaveBeenCalledTimes(1);

    resolveSend({ data: {} });
    await waitFor(() =>
      expect(
        screen.queryByText(/unfilled placeholders/i),
      ).not.toBeInTheDocument(),
    );
  });

  it("blocks Escape from dismissing the warning dialog while the send is in flight", async () => {
    api.getApplicationEmails.mockResolvedValue({
      data: { threads: [], defaultTo: "cand@x.com" },
    });
    let resolveSend;
    api.sendApplicationEmail.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );
    const user = await renderComposeOpen();
    setEditorHtml("<p>on [INTERVIEW DATE/TIME]</p>");
    await user.type(screen.getByLabelText(/subject/i), "Hi");
    await user.click(screen.getByRole("button", { name: /^send$/i }));
    await user.click(screen.getByRole("button", { name: /send anyway/i }));

    expect(
      screen.getByRole("dialog", { name: /unfilled placeholders/i }),
    ).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("dialog", { name: /unfilled placeholders/i }),
    ).toBeInTheDocument();

    resolveSend({ data: {} });
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: /unfilled placeholders/i }),
      ).not.toBeInTheDocument(),
    );
  });

  it("read.all viewer who is not an owner sees no compose control", async () => {
    authState.userId = 999;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, canView: true }),
    });
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Emails" }));
    expect(
      screen.queryByRole("button", { name: "Send email" }),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — interview meeting card & scheduling", () => {
  beforeEach(() => {
    // Interview-card tests exercise the card/dialog themselves, not the
    // no-evaluation reminder, which only intercepts a STAGE/round advance.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("recruiter_screening"), confirmedEval("tech")],
    });
  });

  it("renders the interview meeting card on a behavioral application", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "behavioral" }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText("Interview Meeting")).toBeInTheDocument();
    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
  });

  it("still renders the card with its terminal warning when the application was rejected with a meeting still on the calendar", async () => {
    // Defensive mount branch: the application moved off behavioral/tech
    // (rejected), but the interview row was never cancelled -- the card
    // must still mount (`showInterviewCard`'s `|| detail.interview != null`)
    // so the recruiter can see and cancel it, and it must show the
    // terminal warning with Edit dropped but Cancel kept.
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "rejected",
        interview: INTERVIEW_FIXTURE,
      }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByText(/still on the calendar/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });

  it("shows a read.all non-owner viewer the card's state with no controls", async () => {
    // Default authState.userId (999) is neither OWNER_ID nor the assignee --
    // a plain read.all (canView) viewer, same signal (`detail.isOwner`) the
    // rest of the page already uses to distinguish an owner from a read.all
    // holder (see canReassign, the Operate row, etc.).
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        canView: true,
        stage: "behavioral",
        interview: INTERVIEW_FIXTURE,
      }),
    });
    renderPage();
    await waitLoaded();

    // Same state an owner sees...
    expect(screen.getByText(/2026-08-05/)).toBeInTheDocument();
    expect(
      screen.getByText("meet.google.com/abc-defg-hij"),
    ).toBeInTheDocument();
    // ...none of the owner's controls.
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Schedule meeting" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the owner's controls on the same booked card", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "behavioral",
        interview: INTERVIEW_FIXTURE,
      }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("does not render the card on recruiter screening", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "recruiter_screening" }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.queryByText("Interview Meeting")).not.toBeInTheDocument();
  });

  it("does not render the card on board review", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "board_review" }),
    });
    renderPage();
    await waitLoaded();

    expect(screen.queryByText("Interview Meeting")).not.toBeInTheDocument();
  });

  it("does not render the card in the assignee's evaluate-mode view", async () => {
    // An explicit scope boundary: evaluate mode (the "My Interview
    // Evaluations" link)
    // is a reduced, rubric-only view for the current-stage assignee -- it
    // never renders the owner/read.all info panel the card lives in, even
    // when the assignee's own stage is behavioral/tech.
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: false,
        canView: false,
        assigneeId: ASSIGNEE_ID,
        stage: "behavioral",
      }),
    });
    renderEvaluatorPage();
    await waitLoaded();

    expect(screen.queryByText("Interview Meeting")).not.toBeInTheDocument();
  });

  it("hides Reassign on behavioral and tech", async () => {
    authState.userId = OWNER_ID;
    for (const stage of ["behavioral", "tech"]) {
      api.getApplicationDetail.mockResolvedValue({
        data: makeDetail({ isOwner: true, stage }),
      });
      const { unmount } = renderPage();
      await waitLoaded();
      expect(
        screen.queryByRole("button", { name: "Reassign" }),
      ).not.toBeInTheDocument();
      unmount();
    }
  });

  it("still shows Reassign on recruiter screening and board review", async () => {
    authState.userId = OWNER_ID;
    for (const stage of ["recruiter_screening", "board_review"]) {
      api.getApplicationDetail.mockResolvedValue({
        data: makeDetail({ isOwner: true, stage }),
      });
      const { unmount } = renderPage();
      await waitLoaded();
      expect(
        screen.getByRole("button", { name: "Reassign" }),
      ).toBeInTheDocument();
      unmount();
    }
  });

  it("omits the assignee picker when advancing into behavioral", async () => {
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

    // Target "behavioral" no longer opens the assignee-picker dialog at
    // all: the interviewer is now decided exclusively through the
    // interview card's own dialog, so the advance goes straight through,
    // mirroring how advancing into a non-interview stage already worked.
    await user.click(
      screen.getByRole("button", { name: "Advance to Behavioral" }),
    );

    expect(
      screen.queryByRole("radio", { name: /ivan interviewer/i }),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "behavioral",
        assigneeId: undefined,
      }),
    );
  });

  it("keeps the assignee picker when advancing into board review", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    const jobWithBoardReview = {
      ...JOB,
      pipelineConfig: {
        ...JOB.pipelineConfig,
        stages: [
          ...JOB.pipelineConfig.stages,
          { stage: "board_review", rounds: 1 },
        ],
      },
    };
    api.getJob.mockResolvedValue({ data: jobWithBoardReview });
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

    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("radio", { name: /ivan interviewer/i }),
    ).toBeInTheDocument();
  });

  it("schedules a meeting and refreshes the detail", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail
      .mockResolvedValueOnce({
        data: makeDetail({
          isOwner: true,
          assigneeId: null,
          stage: "behavioral",
        }),
      })
      .mockResolvedValue({
        data: makeDetail({
          isOwner: true,
          assigneeId: ASSIGNEE_ID,
          stage: "behavioral",
          interview: INTERVIEW_FIXTURE,
        }),
      });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Schedule meeting" }));
    await user.click(screen.getByRole("combobox", { name: "Interviewer" }));
    const listbox = await screen.findByRole("listbox");
    await user.click(
      within(listbox).getByText("Eve Evaluator (eve@example.com)"),
    );
    fireEvent.change(screen.getByLabelText("Date"), {
      target: { value: "2026-08-05" },
    });
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "14:00" },
    });
    await user.click(screen.getByRole("button", { name: "Schedule" }));

    await waitFor(() =>
      expect(api.scheduleInterview).toHaveBeenCalledWith("101", {
        assigneeId: ASSIGNEE_ID,
        date: "2026-08-05",
        startTime: "14:00",
        durationMinutes: 45,
        timezone: "America/Los_Angeles",
      }),
    );
    expect(toast.success).toHaveBeenCalled();
    // The refreshed detail carries the booked meeting.
    await waitFor(() =>
      expect(screen.getByText(/2026-08-05/)).toBeInTheDocument(),
    );
  });

  it("confirms before cancelling and calls the API", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "behavioral",
        interview: INTERVIEW_FIXTURE,
      }),
    });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.getByText("Cancel this interview meeting?"),
    ).toBeInTheDocument();
    expect(api.cancelInterview).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel meeting" }));
    await waitFor(() =>
      expect(api.cancelInterview).toHaveBeenCalledWith("101"),
    );
  });

  it("surfaces the backend message when the calendar event is gone", async () => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        assigneeId: ASSIGNEE_ID,
        stage: "behavioral",
        interview: INTERVIEW_FIXTURE,
      }),
    });
    api.updateInterview.mockRejectedValue(
      new Error(
        "This meeting no longer exists on the calendar. Cancel it here and schedule a new one.",
      ),
    );
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "This meeting no longer exists on the calendar. Cancel it here and schedule a new one.",
      ),
    );
  });

  /** Render the Timeline tab with one activity row and return the user. */
  const renderTimelineWith = async (row) => {
    const user = userEvent.setup();
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, stage: "behavioral" }),
    });
    api.getApplicationActivity.mockResolvedValue({ data: [row] });
    renderPage();
    await waitLoaded();
    await user.click(screen.getByRole("tab", { name: "Timeline" }));
    return user;
  };

  it("describes interview_scheduled with the resolved zone, time and interviewer", async () => {
    await renderTimelineWith({
      id: 1,
      eventType: "recruiting.interview_scheduled",
      details: {
        stage: "behavioral",
        round: 1,
        assigneeId: 10,
        assigneeName: "Bob Lee",
        startAt: "2026-08-05T21:00:00Z",
        endAt: "2026-08-05T21:45:00Z",
        timezone: "America/Los_Angeles",
        googleEventId: "evt-1",
      },
      actorName: "Jane Smith",
      createdAt: "2026-07-20T00:00:00Z",
    });

    // 21:00Z is 14:00 in America/Los_Angeles; IANA name verbatim, no PDT/PST.
    expect(
      screen.getByText(
        /Scheduled the Behavioral interview meeting for 2026-08-05 14:00 America\/Los_Angeles with Bob Lee, by Jane Smith/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/PDT|PST/)).toBeNull();
  });

  it("describes interview_cancelled with what was cancelled and when", async () => {
    await renderTimelineWith({
      id: 3,
      eventType: "recruiting.interview_cancelled",
      details: {
        stage: "behavioral",
        round: 1,
        assigneeId: 10,
        assigneeName: "Bob Lee",
        startAt: "2026-08-05T21:00:00Z",
        endAt: "2026-08-05T21:45:00Z",
        timezone: "America/Los_Angeles",
        googleEventId: "evt-1",
      },
      actorName: "Jane Smith",
      createdAt: "2026-07-22T00:00:00Z",
    });

    expect(
      screen.getByText(
        /Cancelled the Behavioral interview meeting that was set for 2026-08-05 14:00 America\/Los_Angeles, by Jane Smith/,
      ),
    ).toBeInTheDocument();
  });

  it("describes interview_updated as a reschedule when only the time moved", async () => {
    await renderTimelineWith({
      id: 2,
      eventType: "recruiting.interview_updated",
      details: {
        stage: "behavioral",
        round: 1,
        assigneeId: 10,
        assigneeName: "Bob Lee",
        startAt: "2026-08-06T22:00:00Z",
        endAt: "2026-08-06T22:45:00Z",
        timezone: "America/Los_Angeles",
        googleEventId: "evt-1",
        fromStartAt: "2026-08-05T21:00:00Z",
        fromEndAt: "2026-08-05T21:45:00Z",
        fromAssigneeId: 10,
      },
      actorName: "Jane Smith",
      createdAt: "2026-07-21T00:00:00Z",
    });

    expect(
      screen.getByText(
        /Rescheduled the Behavioral interview meeting from 2026-08-05 14:00 America\/Los_Angeles to 2026-08-06 15:00 America\/Los_Angeles, by Jane Smith/,
      ),
    ).toBeInTheDocument();
  });

  it("describes interview_updated as a reassignment when only the interviewer swapped", async () => {
    await renderTimelineWith({
      id: 2,
      eventType: "recruiting.interview_updated",
      details: {
        stage: "behavioral",
        round: 1,
        assigneeId: 11,
        assigneeName: "Ivan Interviewer",
        startAt: "2026-08-05T21:00:00Z",
        endAt: "2026-08-05T21:45:00Z",
        timezone: "America/Los_Angeles",
        googleEventId: "evt-1",
        fromStartAt: "2026-08-05T21:00:00Z",
        fromEndAt: "2026-08-05T21:45:00Z",
        fromAssigneeId: 10,
        fromAssigneeName: "Bob Lee",
      },
      actorName: "Jane Smith",
      createdAt: "2026-07-21T00:00:00Z",
    });

    expect(
      screen.getByText(
        /Reassigned the Behavioral interview meeting from Bob Lee to Ivan Interviewer, by Jane Smith/,
      ),
    ).toBeInTheDocument();
  });

  it("describes interview_updated as both when the time and the interviewer both changed", async () => {
    await renderTimelineWith({
      id: 2,
      eventType: "recruiting.interview_updated",
      details: {
        stage: "behavioral",
        round: 1,
        assigneeId: 11,
        assigneeName: "Ivan Interviewer",
        startAt: "2026-08-06T22:00:00Z",
        endAt: "2026-08-06T22:45:00Z",
        timezone: "America/Los_Angeles",
        googleEventId: "evt-1",
        fromStartAt: "2026-08-05T21:00:00Z",
        fromEndAt: "2026-08-05T21:45:00Z",
        fromAssigneeId: 10,
        fromAssigneeName: "Bob Lee",
      },
      actorName: "Jane Smith",
      createdAt: "2026-07-21T00:00:00Z",
    });

    expect(
      screen.getByText(
        /Rescheduled the Behavioral interview meeting from 2026-08-05 14:00 America\/Los_Angeles to 2026-08-06 15:00 America\/Los_Angeles, and reassigned it from Bob Lee to Ivan Interviewer, by Jane Smith/,
      ),
    ).toBeInTheDocument();
  });
});

describe("ApplicationDetailPage — ghost meeting cleanup", () => {
  // Dated far from any real "now" in both directions, so these never become
  // time bombs the way a fixture a week out would.
  const upcomingInterview = (stage = "behavioral") => ({
    ...INTERVIEW_FIXTURE,
    stage,
    startAt: "2099-08-05T21:00:00Z",
    endAt: "2099-08-05T21:45:00Z",
  });
  // makeDetail pins viewerTimezone to America/Los_Angeles, so 21:00Z reads as
  // 14:00 -- the copy below is in the READER's zone, not the booker's.
  const startedInterview = (stage = "behavioral") => ({
    ...INTERVIEW_FIXTURE,
    stage,
    startAt: "2000-08-05T21:00:00Z",
    endAt: "2000-08-05T21:45:00Z",
  });
  const CANCEL_BOX =
    /Cancel the Behavioral interview meeting scheduled for 2099-08-05 14:00 America\/Los_Angeles/;

  beforeEach(() => {
    authState.userId = OWNER_ID;
    // The ghost-meeting prompt is what's under test, not the soft
    // no-evaluation reminder that would otherwise intercept the advance.
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("behavioral", 1)],
    });
    api.changeApplicationStage.mockResolvedValue({ data: {} });
    api.setApplicationRound.mockResolvedValue({ data: {} });
  });

  const onBehavioral = (interview, currentRound = 1) =>
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({
        isOwner: true,
        stage: "behavioral",
        currentRound,
        interview,
      }),
    });

  /** The base JOB fixture with behavioral opened up to several rounds. */
  const jobWithBehavioralRounds = (rounds) => ({
    ...JOB,
    pipelineConfig: {
      ...JOB.pipelineConfig,
      stages: JOB.pipelineConfig.stages.map((s) =>
        s.stage === "behavioral" ? { ...s, rounds } : s,
      ),
    },
  });

  it("asks before stranding an upcoming meeting, ticked by default", async () => {
    const user = userEvent.setup();
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));

    expect(screen.getByRole("checkbox", { name: CANCEL_BOX })).toBeChecked();
    expect(api.changeApplicationStage).not.toHaveBeenCalled();
  });

  it("cancels the meeting together with the stage advance", async () => {
    const user = userEvent.setup();
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "tech",
        assigneeId: undefined,
        cancelInterview: true,
      }),
    );
  });

  it("keeps the meeting when the box is unticked", async () => {
    const user = userEvent.setup();
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));
    await user.click(screen.getByRole("checkbox", { name: CANCEL_BOX }));
    await user.click(screen.getByRole("button", { name: "Confirm advance" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "tech",
        assigneeId: undefined,
        cancelInterview: false,
      }),
    );
  });

  it("never offers to cancel a meeting that has already started", async () => {
    // A finished interview is history, not a ghost -- cancelling it would mail
    // every attendee a cancellation for a meeting that already happened.
    const user = userEvent.setup();
    onBehavioral(startedInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "tech",
        assigneeId: undefined,
      }),
    );
  });

  it("advances straight through when no meeting is booked", async () => {
    const user = userEvent.setup();
    onBehavioral(null);
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "tech",
        assigneeId: undefined,
      }),
    );
  });

  it("offers the same box on reject", async () => {
    const user = userEvent.setup();
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.click(
      screen.getByRole("combobox", { name: /rejection reason/i }),
    );
    await user.click(await screen.findByText("Insufficient experience"));
    expect(screen.getByRole("checkbox", { name: CANCEL_BOX })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Confirm reject" }));

    await waitFor(() =>
      expect(api.changeApplicationStage).toHaveBeenCalledWith("101", {
        toStage: "rejected",
        reason: "Insufficient experience",
        note: undefined,
        cancelInterview: true,
      }),
    );
  });

  it("offers the same box on a round advance", async () => {
    const user = userEvent.setup();
    api.getJob.mockResolvedValue({ data: jobWithBehavioralRounds(3) });
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    expect(screen.getByRole("checkbox", { name: CANCEL_BOX })).toBeChecked();
    await user.click(
      screen.getByRole("button", { name: "Confirm advance session" }),
    );

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith(
        "101",
        2,
        undefined,
        true,
      ),
    );
  });

  it("leaves a started meeting alone on a round advance too", async () => {
    const user = userEvent.setup();
    api.getJob.mockResolvedValue({ data: jobWithBehavioralRounds(3) });
    onBehavioral(startedInterview());
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Session 2" }),
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Confirm advance session" }),
    );

    await waitFor(() =>
      expect(api.setApplicationRound).toHaveBeenCalledWith(
        "101",
        2,
        undefined,
        undefined,
      ),
    );
  });

  it("shows the assignee picker and the cancel box together when the target needs one", async () => {
    // Board review picks its evaluator at advance time, so that dialog must
    // carry both controls rather than one replacing the other. It is the one
    // remaining INTERVIEW_STAGES member whose assignee is still picked there,
    // and it has to be added to the pipeline to become tech's advance target.
    const user = userEvent.setup();
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
        stage: "tech",
        currentRound: 1,
        interview: upcomingInterview("tech"),
      }),
    });
    api.getEvaluationsForApplication.mockResolvedValue({
      data: [confirmedEval("tech", 1)],
    });
    renderPage();
    await waitLoaded();

    await user.click(
      screen.getByRole("button", { name: "Advance to Board review" }),
    );

    expect(screen.getByRole("radio", { name: /decide later/i })).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: /Cancel the Tech interview meeting scheduled for 2099-08-05 14:00 America\/Los_Angeles/,
      }),
    ).toBeChecked();
  });

  it("re-ticks the box for the next decision after one is dismissed", async () => {
    // The box is a per-decision choice, not a sticky preference: unticking it
    // and backing out must not silently carry that over.
    const user = userEvent.setup();
    onBehavioral(upcomingInterview());
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));
    await user.click(screen.getByRole("checkbox", { name: CANCEL_BOX }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Advance to Tech" }));

    expect(screen.getByRole("checkbox", { name: CANCEL_BOX })).toBeChecked();
  });
});

describe("ApplicationDetailPage — blacklist cancels the upcoming interviews", () => {
  const UPCOMING = [
    {
      applicationId: 101,
      jobTitle: "Mentor",
      stage: "behavioral",
      round: 1,
      startAt: "2099-08-05T21:00:00Z",
    },
    {
      applicationId: 202,
      jobTitle: "Backend Engineer",
      stage: "tech",
      round: 2,
      startAt: "2099-08-06T22:00:00Z",
    },
  ];

  beforeEach(() => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true, assigneeId: ASSIGNEE_ID }),
    });
    api.blacklistUser.mockResolvedValue({ data: {} });
  });

  it("lists every interview the block is about to cancel", async () => {
    const user = userEvent.setup();
    api.listBlacklistUpcomingInterviews.mockResolvedValue({ data: UPCOMING });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Blacklist" }));

    expect(
      await screen.findByText(
        /Mentor — Behavioral session 1 — 2099-08-05 14:00 America\/Los_Angeles/,
      ),
    ).toBeInTheDocument();
    expect(
      // Rendered in the READER's zone (pinned to Los Angeles by makeDetail),
      // not in whatever zone each meeting was booked in: 22:00Z is 15:00 there.
      screen.getByText(
        /Backend Engineer — Tech session 2 — 2099-08-06 15:00 America\/Los_Angeles/,
      ),
    ).toBeInTheDocument();
    // Scoped to the candidate, not the application being viewed: a block is
    // org-wide, so it sweeps their other postings too.
    expect(api.listBlacklistUpcomingInterviews).toHaveBeenCalledWith(5);
  });

  it("says nothing about interviews when the candidate has none booked", async () => {
    const user = userEvent.setup();
    api.listBlacklistUpcomingInterviews.mockResolvedValue({ data: [] });
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Blacklist" }));

    expect(
      screen.getByRole("button", { name: "Confirm blacklist" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/scheduled interview/i)).not.toBeInTheDocument();
  });

  it("still lets the block through when the preview cannot be loaded", async () => {
    // The backend cancels the meetings either way -- a failed pre-flight read
    // must not stand between a recruiter and an org-level sanction.
    const user = userEvent.setup();
    api.listBlacklistUpcomingInterviews.mockRejectedValue(new Error("boom"));
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Blacklist" }));
    expect(
      await screen.findByText(/Couldn't check for scheduled interviews/i),
    ).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("Reason (required)"),
      "spamming",
    );
    await user.click(screen.getByRole("button", { name: "Confirm blacklist" }));

    await waitFor(() =>
      expect(api.blacklistUser).toHaveBeenCalledWith({
        userId: 5,
        applicationId: "101",
        reason: "spamming",
      }),
    );
  });

  it("only reads the preview once the dialog is opened", async () => {
    // Every owner loads this page; nobody should pay for a blacklist-only
    // query unless they actually reach for the button.
    api.listBlacklistUpcomingInterviews.mockResolvedValue({ data: [] });
    renderPage();
    await waitLoaded();

    expect(api.listBlacklistUpcomingInterviews).not.toHaveBeenCalled();
  });
});

describe("ApplicationDetailPage — getting back to where you came from", () => {
  it("offers an owner a link back to their board, pointed at this job and applicant", async () => {
    authState.userId = OWNER_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: true }),
    });
    renderPage(101);
    await waitLoaded();

    // JOB.id is 1 and the fixture's application id is 101.
    expect(
      screen.getByRole("link", { name: "Applications Board" }),
    ).toHaveAttribute("href", "/recruiting/board?jobId=1&focus=101");
  });

  it("offers an evaluator a link back to My Interview Evaluations instead", async () => {
    authState.userId = ASSIGNEE_ID;
    api.getApplicationDetail.mockResolvedValue({
      data: makeDetail({ isOwner: false, assigneeId: ASSIGNEE_ID }),
    });
    renderEvaluatorPage(101);
    await waitLoaded();

    expect(
      screen.getByRole("link", { name: "My Interview Evaluations" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Applications Board" }),
    ).not.toBeInTheDocument();
  });
});
